from __future__ import annotations

from av_workflow.adapters.render import RenderAdapter, build_render_request, normalize_render_result
from av_workflow.contracts.enums import MotionTier, RenderBackend
from av_workflow.contracts.models import ShotPlan, ShotRenderJob, ShotRenderResult


class DeterministicRenderJobService:
    def __init__(self, *, render_adapter: RenderAdapter) -> None:
        self.render_adapter = render_adapter

    def build_render_request(self, *, job_id: str, shot_plan: ShotPlan) -> ShotRenderJob:
        backend = RenderBackend.WAN if shot_plan.motion_tier is MotionTier.WAN_DYNAMIC else RenderBackend.IMAGE
        return build_render_request(job_id=job_id, shot_plan=shot_plan, backend=backend)

    def submit_render_request(self, render_request: ShotRenderJob) -> ShotRenderResult:
        provider_payload = self.render_adapter.submit(render_request)
        return normalize_render_result(provider_payload)
