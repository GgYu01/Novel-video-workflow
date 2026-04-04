from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Mapping, Protocol, Sequence

from av_workflow.adapters.review import normalize_semantic_review
from av_workflow.config.models import SemanticReviewConfig
from av_workflow.contracts.enums import ReviewResult
from av_workflow.contracts.models import AssetManifest, Job, ReviewCase, ShotPlan, ShotPlanSet


class SemanticReviewService(Protocol):
    def evaluate(
        self,
        *,
        job: Job,
        manifest: AssetManifest,
        shot_plan_set: ShotPlanSet,
        frame_path_map: Mapping[str, Sequence[Path]] | None = None,
    ) -> ReviewCase:
        """Return a semantic review case for the composed output."""


@dataclass(frozen=True)
class _ShotReviewInput:
    shot_plan: ShotPlan
    frame_paths: tuple[Path, ...]


@dataclass(frozen=True)
class FailClosedSemanticReviewService:
    reason_code: str = "semantic_review_backend_disabled"
    reason_text: str = "Semantic review backend is disabled."
    fix_hint: str = "Enable a semantic image-review backend before auto-completion."
    provider_name: str = "semantic-review"
    provider_version: str = "v0"

    def evaluate(
        self,
        *,
        job: Job,
        manifest: AssetManifest,
        shot_plan_set: ShotPlanSet,
        frame_path_map: Mapping[str, Sequence[Path]] | None = None,
    ) -> ReviewCase:
        del shot_plan_set, frame_path_map
        return _build_failure_case(
            provider_name=self.provider_name,
            provider_version=self.provider_version,
            job=job,
            manifest=manifest,
            reason_code=self.reason_code,
            reason_text=self.reason_text,
            fix_hint=self.fix_hint,
        )


@dataclass(frozen=True)
class LlamaCppCliSemanticReviewService:
    command_path: str
    model_path: str
    mmproj_path: str
    timeout_sec: float
    max_tokens: int
    ctx_size: int
    max_input_frames: int
    launch_scope: Literal["per_job", "per_shot"] = "per_job"
    extra_args: Sequence[str] = ()
    prompt_ref: str = "prompt://review/semantic-default"
    provider_name: str = "llama-mtmd-cli"
    provider_version: str = "on-demand"

    def evaluate(
        self,
        *,
        job: Job,
        manifest: AssetManifest,
        shot_plan_set: ShotPlanSet,
        frame_path_map: Mapping[str, Sequence[Path]] | None = None,
    ) -> ReviewCase:
        review_inputs = self._collect_review_inputs(
            job=job,
            manifest=manifest,
            shot_plan_set=shot_plan_set,
            frame_path_map=frame_path_map or {},
        )
        if isinstance(review_inputs, ReviewCase):
            return review_inputs

        if not review_inputs:
            return _build_failure_case(
                provider_name=self.provider_name,
                provider_version=self.provider_version,
                job=job,
                manifest=manifest,
                reason_code="semantic_review_unavailable",
                reason_text="Semantic review backend received no readable frames.",
                fix_hint="Provide at least one readable frame before delivery.",
                evaluation_prompt_ref=self.prompt_ref,
            )

        if self.launch_scope == "per_shot":
            shot_cases = [
                self._evaluate_single_shot(
                    job=job,
                    manifest=manifest,
                    shot_plan=review_input.shot_plan,
                    frame_paths=review_input.frame_paths,
                )
                for review_input in review_inputs
            ]
            return _aggregate_cases(
                provider_name=self.provider_name,
                provider_version=self.provider_version,
                evaluation_prompt_ref=self.prompt_ref,
                job=job,
                manifest=manifest,
                shot_cases=shot_cases,
            )

        return self._evaluate_job_once(
            job=job,
            manifest=manifest,
            review_inputs=review_inputs,
        )

    def _collect_review_inputs(
        self,
        *,
        job: Job,
        manifest: AssetManifest,
        shot_plan_set: ShotPlanSet,
        frame_path_map: Mapping[str, Sequence[Path]],
    ) -> list[_ShotReviewInput] | ReviewCase:
        review_inputs: list[_ShotReviewInput] = []
        for shot_plan in shot_plan_set.shots:
            frame_paths = [Path(path) for path in frame_path_map.get(shot_plan.shot_id, []) if path]
            selected_frame_paths = tuple(_select_frame_paths(frame_paths, self.max_input_frames))
            if not selected_frame_paths:
                return _build_failure_case(
                    provider_name=self.provider_name,
                    provider_version=self.provider_version,
                    job=job,
                    manifest=manifest,
                    reason_code="semantic_review_unavailable",
                    reason_text=f"Semantic review frames were unavailable for shot {shot_plan.shot_id}.",
                    fix_hint="Provide at least one readable frame for each shot before delivery.",
                    evaluation_prompt_ref=self.prompt_ref,
                )
            review_inputs.append(
                _ShotReviewInput(
                    shot_plan=shot_plan,
                    frame_paths=selected_frame_paths,
                )
            )
        return review_inputs

    def _evaluate_job_once(
        self,
        *,
        job: Job,
        manifest: AssetManifest,
        review_inputs: Sequence[_ShotReviewInput],
    ) -> ReviewCase:
        frame_paths = [
            frame_path
            for review_input in review_inputs
            for frame_path in review_input.frame_paths
        ]
        command = self._build_command(
            frame_paths=frame_paths,
            prompt=_build_job_prompt(job=job, review_inputs=review_inputs),
        )
        try:
            completed = subprocess.run(
                command,
                check=True,
                capture_output=True,
                text=True,
                timeout=self.timeout_sec,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired, subprocess.CalledProcessError) as exc:
            return _build_failure_case(
                provider_name=self.provider_name,
                provider_version=self.provider_version,
                job=job,
                manifest=manifest,
                reason_code="semantic_review_backend_unavailable",
                reason_text="Semantic review CLI failed to execute for the job review batch.",
                fix_hint="Verify the review binary and model paths, then rerun the job.",
                extra_reason_text=str(exc),
                evaluation_prompt_ref=self.prompt_ref,
            )

        payload = _parse_json_payload(completed.stdout)
        return normalize_semantic_review(
            provider_name=self.provider_name,
            provider_version=self.provider_version,
            target_type="asset_manifest",
            target_ref=manifest.manifest_ref,
            input_assets=[str(frame_path) for frame_path in frame_paths],
            response_payload=payload,
            raw_response_ref=f"raw://semantic-review/{job.job_id}.json",
            evaluation_prompt_ref=self.prompt_ref,
        ).model_copy(update={"reason_codes": _normalize_reason_codes(payload.get("reason_codes", []))})

    def _evaluate_single_shot(
        self,
        *,
        job: Job,
        manifest: AssetManifest,
        shot_plan: ShotPlan,
        frame_paths: Sequence[Path],
    ) -> ReviewCase:
        command = self._build_command(
            frame_paths=frame_paths,
            prompt=_build_prompt(job=job, shot_plan=shot_plan, frame_count=len(frame_paths)),
        )

        try:
            completed = subprocess.run(
                command,
                check=True,
                capture_output=True,
                text=True,
                timeout=self.timeout_sec,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired, subprocess.CalledProcessError) as exc:
            return _build_failure_case(
                provider_name=self.provider_name,
                provider_version=self.provider_version,
                job=job,
                manifest=manifest,
                reason_code="semantic_review_backend_unavailable",
                reason_text=f"Semantic review CLI failed to execute for shot {shot_plan.shot_id}.",
                fix_hint="Verify the review binary and model paths, then rerun the job.",
                extra_reason_text=str(exc),
            )

        payload = _parse_json_payload(completed.stdout)
        return normalize_semantic_review(
            provider_name=self.provider_name,
            provider_version=self.provider_version,
            target_type="asset_manifest",
            target_ref=manifest.manifest_ref,
            input_assets=[str(frame_path) for frame_path in frame_paths],
            response_payload=payload,
            raw_response_ref=f"raw://semantic-review/{job.job_id}.json",
            evaluation_prompt_ref=self.prompt_ref,
        )

    def _build_command(self, *, frame_paths: Sequence[Path], prompt: str) -> list[str]:
        command = [
            self.command_path,
            "--model",
            self.model_path,
            "--mmproj",
            self.mmproj_path,
            "--ctx-size",
            str(self.ctx_size),
            "--n-predict",
            str(self.max_tokens),
        ]
        for frame_path in frame_paths:
            command.extend(["--image", str(frame_path)])
        command.extend(self.extra_args)
        command.extend(["-p", prompt])
        return command


def build_semantic_review_service(semantic_config: SemanticReviewConfig) -> SemanticReviewService:
    if semantic_config.mode == "fail_closed":
        return FailClosedSemanticReviewService(
            provider_name=semantic_config.provider,
            provider_version=semantic_config.model_family,
        )
    if semantic_config.mode == "llama_cpp_cli":
        return LlamaCppCliSemanticReviewService(
            command_path=_require_non_empty(semantic_config.command_path, "command_path"),
            model_path=_require_non_empty(semantic_config.model_path, "model_path"),
            mmproj_path=_require_non_empty(semantic_config.mmproj_path, "mmproj_path"),
            timeout_sec=semantic_config.timeout_sec,
            max_tokens=semantic_config.max_tokens,
            ctx_size=semantic_config.ctx_size,
            max_input_frames=semantic_config.max_input_frames,
            launch_scope=semantic_config.launch_scope,
            extra_args=tuple(semantic_config.extra_args),
            prompt_ref=semantic_config.prompt_ref,
            provider_name=semantic_config.provider,
            provider_version=(
                f"{semantic_config.model_family}-"
                f"{semantic_config.model_size}-"
                f"{semantic_config.model_quantization}-"
                f"{semantic_config.mmproj_quantization}"
            ),
        )
    raise ValueError(f"Unsupported semantic review mode: {semantic_config.mode}")


def _aggregate_cases(
    *,
    provider_name: str,
    provider_version: str,
    evaluation_prompt_ref: str,
    job: Job,
    manifest: AssetManifest,
    shot_cases: list[ReviewCase],
) -> ReviewCase:
    input_assets = [asset for case in shot_cases for asset in case.input_assets]
    reason_codes: list[str] = []
    reason_texts: list[str] = []
    score = 1.0
    result = ReviewResult.PASS
    recommended_action = "continue"
    fix_hint = None

    for case in shot_cases:
        reason_codes.extend(case.reason_codes)
        if case.reason_text:
            reason_texts.append(case.reason_text)
        score = min(score, case.score)
        if case.result is ReviewResult.WARN:
            result = ReviewResult.WARN
        elif case.result is ReviewResult.FAIL and result is ReviewResult.PASS:
            result = ReviewResult.FAIL

        if case.recommended_action in {"manual_hold", "quarantine"}:
            recommended_action = case.recommended_action
            fix_hint = fix_hint or case.fix_hint
        elif recommended_action == "continue" and case.recommended_action.startswith("retry_"):
            recommended_action = case.recommended_action
            fix_hint = fix_hint or case.fix_hint

    normalized_reason_codes = sorted(set(reason_codes) or {"semantic_alignment_ok"})
    normalized_reason_text = " ".join(reason_texts) if reason_texts else "Semantic review passed."
    return normalize_semantic_review(
        provider_name=provider_name,
        provider_version=provider_version,
        target_type="asset_manifest",
        target_ref=manifest.manifest_ref,
        input_assets=input_assets,
        response_payload={
            "result": result.value,
            "score": round(score, 4),
            "reason_codes": normalized_reason_codes,
            "reason_text": normalized_reason_text,
            "recommended_action": recommended_action,
            "fix_hint": fix_hint,
            "latency_ms": 0,
        },
        raw_response_ref=f"raw://semantic-review/{job.job_id}.json",
        evaluation_prompt_ref=evaluation_prompt_ref,
    )


def _build_failure_case(
    *,
    provider_name: str,
    provider_version: str,
    job: Job,
    manifest: AssetManifest,
    reason_code: str,
    reason_text: str,
    fix_hint: str,
    extra_reason_text: str | None = None,
    evaluation_prompt_ref: str = "prompt://review/semantic-default",
) -> ReviewCase:
    response_reason_text = reason_text if extra_reason_text is None else f"{reason_text} {extra_reason_text}".strip()
    return normalize_semantic_review(
        provider_name=provider_name,
        provider_version=provider_version,
        target_type="asset_manifest",
        target_ref=manifest.manifest_ref,
        input_assets=[*manifest.preview_refs, *manifest.cover_refs],
        response_payload={
            "result": ReviewResult.FAIL.value,
            "score": 0.0,
            "reason_codes": [reason_code],
            "reason_text": response_reason_text,
            "recommended_action": "manual_hold",
            "fix_hint": fix_hint,
            "latency_ms": 0,
        },
        raw_response_ref=f"raw://semantic-review/{job.job_id}.json",
        evaluation_prompt_ref=evaluation_prompt_ref,
    ).model_copy(update={"reason_codes": _normalize_reason_codes([reason_code])})


def _normalize_reason_codes(reason_codes: Sequence[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()

    for reason_code in reason_codes:
        if not reason_code or reason_code in seen:
            continue
        seen.add(reason_code)
        normalized.append(reason_code)

    return normalized


def _build_prompt(*, job: Job, shot_plan: ShotPlan, frame_count: int) -> str:
    review_targets = ", ".join(map(str, shot_plan.review_targets.get("must_match", [])))
    return (
        "You are a strict visual quality reviewer for an internal single-tenant novel-to-video pipeline. "
        "Inspect the sampled frames in chronological order for subject identity, scene continuity, motion coherence, "
        "and whether they match the shot plan. "
        "Return JSON only with keys result, score, reason_codes, reason_text, recommended_action, fix_hint, latency_ms.\n"
        f"Job: {job.job_id}\n"
        f"Shot: {shot_plan.shot_id}\n"
        f"Frame count: {frame_count}\n"
        f"Subject: {shot_plan.subject_instruction}\n"
        f"Environment: {shot_plan.environment_instruction}\n"
        f"Camera: {shot_plan.camera_instruction}\n"
        f"Must match: {review_targets}\n"
    )


def _build_job_prompt(*, job: Job, review_inputs: Sequence[_ShotReviewInput]) -> str:
    shot_lines: list[str] = []
    for review_input in review_inputs:
        shot_plan = review_input.shot_plan
        review_targets = ", ".join(map(str, shot_plan.review_targets.get("must_match", [])))
        shot_lines.extend(
            [
                f"Shot {shot_plan.shot_id}",
                f"Frames: {len(review_input.frame_paths)}",
                f"Subject: {shot_plan.subject_instruction}",
                f"Environment: {shot_plan.environment_instruction}",
                f"Camera: {shot_plan.camera_instruction}",
                f"Must match: {review_targets}",
            ]
        )
    shot_details = "\n".join(shot_lines)
    return (
        "You are a strict visual quality reviewer for an internal single-tenant novel-to-video pipeline. "
        "Inspect all supplied frames in chronological order. Frames are grouped by shot in the same order as the shot list below. "
        "Judge subject identity, scene continuity, composition quality, and whether the overall sampled frames match the planned shots. "
        "Return JSON only with keys result, score, reason_codes, reason_text, recommended_action, fix_hint, latency_ms.\n"
        f"Job: {job.job_id}\n"
        f"Shots: {len(review_inputs)}\n"
        f"{shot_details}\n"
    )


def _select_frame_paths(frame_paths: Sequence[Path], max_input_frames: int) -> list[Path]:
    selected = [frame_path for frame_path in frame_paths if str(frame_path)]
    if not selected:
        return []
    if max_input_frames <= 1 or len(selected) <= max_input_frames:
        return selected[:max_input_frames]

    selected_indices = [0]
    last_index = len(selected) - 1
    if max_input_frames > 2:
        for slot in range(1, max_input_frames - 1):
            position = round(slot * last_index / (max_input_frames - 1))
            if position not in selected_indices:
                selected_indices.append(position)
    if last_index not in selected_indices:
        selected_indices.append(last_index)

    if len(selected_indices) < max_input_frames:
        for index in range(len(selected)):
            if index in selected_indices:
                continue
            selected_indices.append(index)
            if len(selected_indices) == max_input_frames:
                break

    return [selected[index] for index in sorted(selected_indices[:max_input_frames])]


def _parse_json_payload(stdout: str) -> dict[str, object]:
    lines = [line.strip() for line in stdout.splitlines() if line.strip()]
    if not lines:
        raise ValueError("semantic_review_cli_empty_output")
    try:
        parsed = json.loads(lines[-1])
    except json.JSONDecodeError as exc:
        raise ValueError("semantic_review_cli_invalid_json") from exc
    if not isinstance(parsed, dict):
        raise ValueError("semantic_review_cli_invalid_json")
    return parsed


def _require_non_empty(value: str | None, field_name: str) -> str:
    if not value:
        raise ValueError(f"Semantic review CLI mode requires {field_name}.")
    return value
