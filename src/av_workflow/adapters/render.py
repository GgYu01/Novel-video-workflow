from __future__ import annotations

from typing import Any, Protocol

from av_workflow.contracts.enums import MotionTier, RenderBackend, RenderJobStatus
from av_workflow.contracts.models import ShotPlan, ShotRenderJob, ShotRenderResult


class RenderAdapter(Protocol):
    def submit(self, render_request: ShotRenderJob) -> dict[str, Any]:
        """Submit a render request and return provider-normalized status data."""


def build_render_request(
    *,
    job_id: str,
    shot_plan: ShotPlan,
    backend: RenderBackend,
) -> ShotRenderJob:
    prompt_bundle = {
        "image_prompt": f"{shot_plan.subject_instruction}. {shot_plan.environment_instruction}",
        "video_prompt": f"{shot_plan.camera_instruction}. {shot_plan.narration_text}",
    }
    return ShotRenderJob(
        render_job_id=f"render-{job_id}-{shot_plan.shot_id}",
        job_id=job_id,
        shot_id=shot_plan.shot_id,
        motion_tier=shot_plan.motion_tier,
        backend=backend,
        prompt_bundle=prompt_bundle,
        source_asset_refs=[],
        requested_duration_sec=shot_plan.duration_target,
    )


def normalize_render_status(provider_status: str) -> RenderJobStatus:
    normalized = provider_status.strip().lower()
    if normalized in {"queued", "pending", "waiting"}:
        return RenderJobStatus.PENDING
    if normalized in {"running", "processing"}:
        return RenderJobStatus.RUNNING
    if normalized in {"completed", "succeeded", "success", "done"}:
        return RenderJobStatus.SUCCEEDED
    return RenderJobStatus.FAILED


def normalize_render_result(payload: dict[str, Any]) -> ShotRenderResult:
    return ShotRenderResult(
        render_job_id=str(payload["render_job_id"]),
        shot_id=str(payload["shot_id"]),
        status=normalize_render_status(str(payload.get("status", "failed"))),
        clip_ref=payload.get("clip_ref"),
        frame_refs=list(payload.get("frame_refs", [])),
        metadata=dict(payload.get("metadata", {})),
        error_code=payload.get("error_code"),
    )

