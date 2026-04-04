from __future__ import annotations

import shutil
from pathlib import Path

from av_workflow.contracts.enums import JobStatus
from av_workflow.contracts.models import DialogueTimeline, Job, ReviewCase, ShotPlan, ShotRenderResult
from av_workflow.runtime.ffmpeg import FfmpegExecutor
from av_workflow.runtime.workspace import RuntimeWorkspace
from av_workflow.services.audio_mix import build_audio_mix_manifest, materialize_audio_mix
from av_workflow.services.audio_timeline import DeterministicAudioTimelineService
from av_workflow.services.compose import (
    assemble_output_package,
    build_asset_manifest,
    execute_ffmpeg_compose,
)
from av_workflow.services.ingest import normalize_source
from av_workflow.services.planning import DeterministicPlanningService
from av_workflow.services.render_jobs import DeterministicRenderJobService
from av_workflow.services.review.technical import evaluate_asset_manifest
from av_workflow.workflow.engine import WorkflowEngine
from av_workflow.workflow.stage_runner import DeterministicStageRunner, StageRunResult


class DeterministicLocalJobExecutionService:
    def __init__(
        self,
        *,
        runtime_root: str | Path,
        planning_service: DeterministicPlanningService,
        render_job_service: DeterministicRenderJobService,
        audio_timeline_service: DeterministicAudioTimelineService,
        ffmpeg_executor: FfmpegExecutor,
        workflow_engine: WorkflowEngine | None = None,
    ) -> None:
        self.workspace = RuntimeWorkspace(root_dir=runtime_root)
        self.planning_service = planning_service
        self.render_job_service = render_job_service
        self.audio_timeline_service = audio_timeline_service
        self.ffmpeg_executor = ffmpeg_executor
        self.stage_runner = DeterministicStageRunner(
            workflow_engine=workflow_engine,
            planning_service=planning_service,
            audio_timeline_service=audio_timeline_service,
            render_job_service=render_job_service,
        )

    def run(self, *, job: Job, raw_text: str) -> StageRunResult:
        self.workspace.reset_job_tree(job.job_id)

        source_document = normalize_source(job, raw_text)
        self._write_model(job.job_id, "source/source_document.json", source_document)
        self.workspace.write_text_artifact(job.job_id, "source/normalized_source.txt", source_document.normalized_text)

        normalized_job = self.stage_runner.normalize(job)
        story_spec = self.planning_service.build_story_spec(source_document)
        shot_plan_set = self.planning_service.generate_shot_plan_set(
            source_document=source_document,
            story_spec=story_spec,
            output_preset=job.output_preset,
        )
        self._write_model(job.job_id, "planning/story_spec.json", story_spec)
        self._write_model(job.job_id, "planning/shot_plan_set.json", shot_plan_set)

        planned_job = self.stage_runner.plan(normalized_job)
        voice_cast = self.audio_timeline_service.build_voice_cast(
            source_document=source_document,
            story_spec=story_spec,
        )
        self._write_model(job.job_id, "planning/voice_cast.json", voice_cast)

        render_requested_job = self.stage_runner.request_render(planned_job)
        target_video_duration_ms = sum(int(shot.duration_target * 1000) for shot in shot_plan_set.shots)
        render_results: dict[str, ShotRenderResult] = {}
        rendered_shots: dict[str, dict[str, object]] = {}
        subtitle_refs: list[str] = []
        subtitle_reports: dict[str, dict[str, object]] = {}
        ordered_audio_refs: list[str] = []
        ordered_audio_paths: list[Path] = []
        narration_refs: list[str] = []
        dialogue_refs: list[str] = []
        shot_clip_paths: list[Path] = []
        total_duration_ms = 0

        for shot_plan in shot_plan_set.shots:
            render_result, timeline, subtitle_ref, subtitle_report = self._materialize_shot(
                job_id=job.job_id,
                shot_plan=shot_plan,
                voice_cast=voice_cast,
            )
            render_results[shot_plan.shot_id] = render_result
            rendered_shots[shot_plan.shot_id] = {
                "clip_ref": render_result.clip_ref,
                "frame_refs": list(render_result.frame_refs),
                "render_metadata": dict(render_result.metadata),
            }
            if render_result.clip_path is not None:
                shot_clip_paths.append(Path(render_result.clip_path))
            else:
                shot_clip_paths.append(
                    self.workspace.shot_root(job.job_id, shot_plan.shot_id) / "render" / "clip.mp4"
                )
            subtitle_refs.append(subtitle_ref)
            subtitle_reports[subtitle_ref] = subtitle_report
            total_duration_ms += timeline.total_duration_ms

            for segment in timeline.segments:
                audio_ref = segment.get("audio_ref")
                audio_path = segment.get("audio_path")
                if not audio_ref or not audio_path:
                    continue
                ordered_audio_refs.append(str(audio_ref))
                ordered_audio_paths.append(Path(str(audio_path)))
                if segment.get("speaker") == "narration":
                    narration_refs.append(str(audio_ref))
                else:
                    dialogue_refs.append(str(audio_ref))

        mix_path = self.workspace.audio_dir(job.job_id) / "final-mix.wav"
        materialize_audio_mix(
            output_path=mix_path,
            source_audio_paths=ordered_audio_paths,
            target_duration_ms=max(target_video_duration_ms, 1000),
        )

        audio_mix_manifest = build_audio_mix_manifest(
            job=render_requested_job,
            narration_refs=narration_refs,
            dialogue_refs=dialogue_refs,
            duration_ms=max(target_video_duration_ms, total_duration_ms),
            bgm_ref=None,
            ambience_refs=[],
            mix_ref=self.workspace.asset_ref(job.job_id, "audio", "final-mix.wav"),
        )
        self._write_model(job.job_id, "audio/audio_mix_manifest.json", audio_mix_manifest)

        render_ready_job = self.stage_runner.mark_render_ready(render_requested_job)
        audio_ready_job = self.stage_runner.mark_audio_ready(render_ready_job)
        preview_ref, cover_ref = self._materialize_cover_assets(
            job_id=job.job_id,
            shot_plan_set=shot_plan_set.shots,
        )

        asset_manifest = build_asset_manifest(
            job=audio_ready_job,
            shot_plans=shot_plan_set.shots,
            rendered_shots=rendered_shots,
            subtitle_refs=subtitle_refs,
            audio_refs=ordered_audio_refs,
            audio_mix_ref=audio_mix_manifest.mix_ref,
            preview_refs=[preview_ref],
            cover_refs=[cover_ref],
            final_video_ref=self.workspace.asset_ref(job.job_id, "output", "final.mp4"),
        ).model_copy(
            update={
                "manifest_ref": self.workspace.asset_ref(job.job_id, "output", "asset_manifest.json"),
            }
        )

        compose_result = execute_ffmpeg_compose(
            manifest=asset_manifest,
            workspace=self.workspace,
            ffmpeg_executor=self.ffmpeg_executor,
            shot_clip_paths=shot_clip_paths,
            primary_audio_path=mix_path,
            output_variant=job.output_preset,
        )
        self._write_json(job.job_id, "compose/compose_result.json", compose_result)

        composed_job = self.stage_runner.mark_composed(audio_ready_job)
        review_case = self._build_review_case(
            job=composed_job,
            asset_manifest=asset_manifest,
            audio_mix_manifest_ref=audio_mix_manifest.mix_ref,
            total_duration_ms=max(target_video_duration_ms, total_duration_ms),
            subtitle_reports=subtitle_reports,
        )
        review_summary_ref = self.workspace.asset_ref(job.job_id, "output", "review_case.json")
        self._write_model(job.job_id, "output/asset_manifest.json", asset_manifest)
        self._write_model(job.job_id, "output/review_case.json", review_case)

        reviewed_job = self.stage_runner.apply_review_case(composed_job, review_case)
        if reviewed_job.status is JobStatus.QA_TECHNICAL_PASSED:
            reviewed_job = self.stage_runner.mark_semantic_review_passed(reviewed_job)
            reviewed_job = self.stage_runner.mark_output_ready(reviewed_job)
            completed_job = self.stage_runner.complete(reviewed_job)
        else:
            completed_job = reviewed_job

        output_package = assemble_output_package(
            manifest=asset_manifest,
            review_summary_ref=review_summary_ref,
        )
        self._write_model(job.job_id, "output/output_package.json", output_package)

        return StageRunResult(
            initial_job=job,
            final_job=completed_job,
            source_document=source_document,
            story_spec=story_spec,
            shot_plan_set=shot_plan_set,
            voice_cast=voice_cast,
            render_results=render_results,
            audio_mix_manifest=audio_mix_manifest,
            asset_manifest=asset_manifest,
            review_case=review_case,
            output_package=output_package,
        )

    def _materialize_shot(
        self,
        *,
        job_id: str,
        shot_plan: ShotPlan,
        voice_cast,
    ) -> tuple[ShotRenderResult, DialogueTimeline, str, dict[str, object]]:
        render_request = self.render_job_service.build_render_request(job_id=job_id, shot_plan=shot_plan)
        render_result = self.render_job_service.submit_render_request(render_request)
        self._write_model(job_id, f"shots/{shot_plan.shot_id}/render/render_request.json", render_request)
        self._write_model(job_id, f"shots/{shot_plan.shot_id}/render/render_result.json", render_result)

        timeline = self.audio_timeline_service.build_timeline(shot_plan=shot_plan, voice_cast=voice_cast)
        self._write_json(job_id, f"shots/{shot_plan.shot_id}/audio/dialogue_timeline.json", timeline.model_dump(mode="json"))

        self.workspace.write_text_artifact(
            job_id,
            f"subtitles/{shot_plan.shot_id}.srt",
            self._build_srt(timeline),
        )
        subtitle_ref = self.workspace.asset_ref(job_id, "subtitles", f"{shot_plan.shot_id}.srt")
        subtitle_report = {
            "cue_count": len(timeline.segments),
            "max_line_length": max((len(str(segment["text"])) for segment in timeline.segments), default=0),
        }
        return render_result, timeline, subtitle_ref, subtitle_report

    def _materialize_cover_assets(self, *, job_id: str, shot_plan_set: list[ShotPlan]) -> tuple[str, str]:
        first_shot_id = shot_plan_set[0].shot_id
        first_frame = self._resolve_cover_source_frame(job_id=job_id, first_shot_id=first_shot_id)
        preview_name = f"preview{first_frame.suffix or '.png'}"
        cover_name = f"cover{first_frame.suffix or '.png'}"
        preview_path = self.workspace.output_dir(job_id) / preview_name
        cover_path = self.workspace.output_dir(job_id) / cover_name
        shutil.copyfile(first_frame, preview_path)
        shutil.copyfile(first_frame, cover_path)
        return (
            self.workspace.asset_ref(job_id, "output", preview_name),
            self.workspace.asset_ref(job_id, "output", cover_name),
        )

    def _resolve_cover_source_frame(self, *, job_id: str, first_shot_id: str) -> Path:
        render_dir = self.workspace.shot_root(job_id, first_shot_id) / "render"
        candidate_paths = sorted(
            path
            for path in render_dir.iterdir()
            if path.is_file() and path.name.startswith("frame-")
        )
        if not candidate_paths:
            raise FileNotFoundError(f"cover_source_frame_missing: {render_dir}")
        return candidate_paths[0]

    def _build_review_case(
        self,
        *,
        job: Job,
        asset_manifest,
        audio_mix_manifest_ref: str,
        total_duration_ms: int,
        subtitle_reports: dict[str, dict[str, object]],
    ) -> ReviewCase:
        return evaluate_asset_manifest(
            job=job,
            manifest=asset_manifest,
            media_metadata={
                asset_manifest.final_video_ref: {
                    "duration_sec": max(total_duration_ms / 1000.0, 1.0),
                    "video_streams": [{"width": 1280, "height": 720}],
                    "audio_streams": [{"sample_rate": 24000}],
                },
                audio_mix_manifest_ref: {
                    "audio_streams": [{"sample_rate": 24000}],
                },
            },
            subtitle_reports=subtitle_reports,
        )

    def _build_srt(self, timeline: DialogueTimeline) -> str:
        lines: list[str] = []
        for index, segment in enumerate(timeline.segments, start=1):
            lines.extend(
                [
                    str(index),
                    f"{_format_srt_timestamp(int(segment['start_ms']))} --> {_format_srt_timestamp(int(segment['end_ms']))}",
                    str(segment["text"]),
                    "",
                ]
            )
        return "\n".join(lines).strip() + "\n"

    def _write_model(self, job_id: str, relative_path: str, model) -> None:
        self._write_json(job_id, relative_path, model.model_dump(mode="json"))

    def _write_json(self, job_id: str, relative_path: str, payload: object) -> None:
        self.workspace.write_json_artifact(job_id, relative_path, _json_ready(payload))

def _format_srt_timestamp(value_ms: int) -> str:
    hours, remainder = divmod(value_ms, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds, milliseconds = divmod(remainder, 1_000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"


def _json_ready(value: object) -> object:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    return value
