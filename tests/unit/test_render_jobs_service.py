from __future__ import annotations

from av_workflow.contracts.enums import MotionTier, RenderBackend, RenderJobStatus
from av_workflow.contracts.models import ShotPlan
from av_workflow.services.render_jobs import DeterministicRenderJobService


class StubRenderAdapter:
    def __init__(self) -> None:
        self.submitted: list[str] = []

    def submit(self, render_request):
        self.submitted.append(render_request.render_job_id)
        return {
            "render_job_id": render_request.render_job_id,
            "shot_id": render_request.shot_id,
            "status": "completed",
            "clip_ref": f"asset://shots/{render_request.shot_id}.mp4",
            "frame_refs": [f"asset://shots/{render_request.shot_id}/frame-001.png"],
            "metadata": {"duration_sec": render_request.requested_duration_sec, "fps": 24},
        }


def build_shot_plan() -> ShotPlan:
    return ShotPlan(
        shot_id="shot-001",
        chapter_id="ch-1",
        scene_id="scene-1",
        duration_target=4.5,
        shot_type="medium",
        motion_tier=MotionTier.WAN_DYNAMIC,
        camera_instruction="dynamic crowd coverage",
        subject_instruction="celebrating players throw the coach into the air",
        environment_instruction="packed Saint Moix Stadium",
        narration_text="The celebration exploded across the stadium.",
        dialogue_lines=[],
        subtitle_source="narration",
        render_requirements={"aspect_ratio": "16:9"},
        review_targets={"must_match": ["coach", "stadium"]},
        fallback_strategy={"retry_scope": "shot"},
    )


def test_render_job_service_builds_requests_and_normalizes_results() -> None:
    adapter = StubRenderAdapter()
    service = DeterministicRenderJobService(render_adapter=adapter)
    shot_plan = build_shot_plan()

    request = service.build_render_request(job_id="job-001", shot_plan=shot_plan)
    result = service.submit_render_request(request)

    assert adapter.submitted == [request.render_job_id]
    assert request.backend is RenderBackend.WAN
    assert result.status is RenderJobStatus.SUCCEEDED
    assert result.clip_ref == "asset://shots/shot-001.mp4"
    assert result.frame_refs == ["asset://shots/shot-001/frame-001.png"]

