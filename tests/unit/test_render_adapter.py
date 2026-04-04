from __future__ import annotations

from av_workflow.adapters.render import (
    ApiRenderBackendAdapter,
    RoutingRenderAdapter,
    build_render_request,
    normalize_render_result,
    normalize_render_status,
)
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


def test_normalize_render_result_tolerates_missing_metadata_blocks() -> None:
    result = normalize_render_result(
        {
            "render_job_id": "render-job-001",
            "shot_id": "shot-001",
            "status": "completed",
            "clip_ref": "asset://runtime/jobs/job-001/shots/shot-001/render/clip.mp4",
            "frame_refs": ["asset://runtime/jobs/job-001/shots/shot-001/render/frame-001.ppm"],
            "metadata": None,
        }
    )

    assert result.metadata == {}


class RecordingTransport:
    def __init__(self, response_payload: dict[str, object]) -> None:
        self.response_payload = response_payload
        self.calls: list[tuple[str, dict[str, object], float]] = []

    def post_json(self, url: str, payload: dict[str, object], *, timeout_sec: float) -> dict[str, object]:
        self.calls.append((url, payload, timeout_sec))
        return self.response_payload


class StubAdapter:
    def __init__(self, response_payload: dict[str, object]) -> None:
        self.response_payload = response_payload
        self.calls: list[str] = []

    def submit(self, render_request) -> dict[str, object]:
        self.calls.append(render_request.shot_id)
        return self.response_payload


def test_api_render_backend_adapter_posts_normalized_payload_to_provider() -> None:
    transport = RecordingTransport(
        {
            "render_job_id": "render-job-001",
            "shot_id": "shot-001",
            "status": "completed",
            "clip_ref": "asset://runtime/jobs/job-001/shots/shot-001/render/clip.mp4",
            "frame_refs": ["asset://runtime/jobs/job-001/shots/shot-001/render/frame-001.png"],
            "metadata": {"content_source": "image_model"},
        }
    )
    adapter = ApiRenderBackendAdapter(
        base_url="http://image-render.internal",
        submit_path="/v1/render/image",
        timeout_sec=18.0,
        transport=transport,
    )

    request = build_render_request(
        job_id="job-001",
        shot_plan=build_shot_plan(),
        backend=RenderBackend.IMAGE,
    )
    provider_payload = adapter.submit(request)

    assert provider_payload["status"] == "completed"
    assert transport.calls == [
        (
                "http://image-render.internal/v1/render/image",
                {
                    "render_job_id": "render-job-001-shot-001",
                    "job_id": "job-001",
                    "shot_id": "shot-001",
                    "backend": "image",
                "motion_tier": "wan_dynamic",
                "prompt_bundle": request.prompt_bundle,
                "source_asset_refs": [],
                "requested_duration_sec": 4.5,
            },
            18.0,
        )
    ]


def test_routing_render_adapter_dispatches_to_backend_specific_adapter() -> None:
    image_adapter = StubAdapter({"status": "completed", "shot_id": "shot-001", "render_job_id": "image"})
    wan_adapter = StubAdapter({"status": "completed", "shot_id": "shot-001", "render_job_id": "wan"})
    adapter = RoutingRenderAdapter(image_adapter=image_adapter, wan_adapter=wan_adapter)

    image_request = build_render_request(
        job_id="job-001",
        shot_plan=build_shot_plan(),
        backend=RenderBackend.IMAGE,
    )
    wan_request = build_render_request(
        job_id="job-001",
        shot_plan=build_shot_plan(),
        backend=RenderBackend.WAN,
    )

    image_result = adapter.submit(image_request)
    wan_result = adapter.submit(wan_request)

    assert image_result["render_job_id"] == "image"
    assert wan_result["render_job_id"] == "wan"
    assert image_adapter.calls == ["shot-001"]
    assert wan_adapter.calls == ["shot-001"]
