from __future__ import annotations

from av_workflow.adapters.render import normalize_render_status, build_render_request
from av_workflow.contracts.enums import MotionTier, RenderBackend, RenderJobStatus
from av_workflow.contracts.models import ShotPlan


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


def test_build_render_request_normalizes_wan_dynamic_shots() -> None:
    shot_plan = build_shot_plan()

    request = build_render_request(
        job_id="job-001",
        shot_plan=shot_plan,
        backend=RenderBackend.WAN,
    )

    assert request.motion_tier is MotionTier.WAN_DYNAMIC
    assert request.backend is RenderBackend.WAN
    assert request.source_asset_refs == []
    assert request.requested_duration_sec == 4.5
    assert "video_prompt" in request.prompt_bundle


def test_normalize_render_status_maps_provider_states_to_internal_enum() -> None:
    assert normalize_render_status("queued") is RenderJobStatus.PENDING
    assert normalize_render_status("running") is RenderJobStatus.RUNNING
    assert normalize_render_status("completed") is RenderJobStatus.SUCCEEDED
    assert normalize_render_status("failed") is RenderJobStatus.FAILED

