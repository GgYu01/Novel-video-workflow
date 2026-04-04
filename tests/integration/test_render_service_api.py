from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from av_workflow.render_service.app import create_app
from av_workflow.render_service.backends import PlaceholderImageBackend, PlaceholderWanBackend
from av_workflow.runtime.workspace import RuntimeWorkspace


class RecordingFfmpegExecutor:
    def run(self, args: list[str], *, cwd: Path | None = None, output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"fake-video")


def build_render_request(*, backend: str) -> dict[str, object]:
    return {
        "render_job_id": "render-job-001",
        "job_id": "job-001",
        "shot_id": "shot-001",
        "backend": backend,
        "motion_tier": "wan_dynamic" if backend == "wan" else "static",
        "prompt_bundle": {
            "image_prompt": "A football club chairman in a stadium box",
            "video_prompt": "Slow camera move across the celebrating crowd",
        },
        "source_asset_refs": [],
        "requested_duration_sec": 3.5,
    }


def test_image_render_service_returns_normalized_placeholder_payload(tmp_path: Path) -> None:
    app = create_app(
        image_backend=PlaceholderImageBackend(
            workspace=RuntimeWorkspace(root_dir=tmp_path / "runtime"),
            ffmpeg_executor=RecordingFfmpegExecutor(),
        )
    )
    client = TestClient(app)

    response = client.post("/v1/render/image", json=build_render_request(backend="image"))

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "completed"
    assert payload["clip_ref"] == "asset://runtime/jobs/job-001/shots/shot-001/render/clip.mp4"
    assert payload["metadata"]["content_source"] == "deterministic_placeholder"
    assert payload["metadata"]["placeholder_mode"] == "pattern_frame_loop"
    assert (tmp_path / "runtime" / "jobs" / "job-001" / "shots" / "shot-001" / "render" / "clip.mp4").is_file()


def test_wan_render_service_returns_motion_placeholder_payload(tmp_path: Path) -> None:
    app = create_app(
        wan_backend=PlaceholderWanBackend(
            workspace=RuntimeWorkspace(root_dir=tmp_path / "runtime"),
            ffmpeg_executor=RecordingFfmpegExecutor(),
        )
    )
    client = TestClient(app)

    response = client.post("/v1/render/video", json=build_render_request(backend="wan"))

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "completed"
    assert payload["clip_ref"] == "asset://runtime/jobs/job-001/shots/shot-001/render/clip.mp4"
    assert payload["metadata"]["content_source"] == "deterministic_placeholder"
    assert payload["metadata"]["placeholder_mode"] == "motion_placeholder_sequence"
    assert len(payload["frame_refs"]) == 3


def test_render_service_returns_503_when_backend_is_not_configured() -> None:
    client = TestClient(create_app())

    response = client.post("/v1/render/image", json=build_render_request(backend="image"))

    assert response.status_code == 503
    assert response.json()["detail"] == "image_backend_not_configured"
