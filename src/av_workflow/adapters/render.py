from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Protocol
from urllib.request import Request, urlopen

from av_workflow.contracts.enums import MotionTier, RenderBackend, RenderJobStatus
from av_workflow.contracts.models import ShotPlan, ShotRenderJob, ShotRenderResult
from av_workflow.runtime.ffmpeg import FfmpegExecutor
from av_workflow.runtime.workspace import RuntimeWorkspace


class RenderAdapter(Protocol):
    def submit(self, render_request: ShotRenderJob) -> dict[str, Any]:
        """Submit a render request and return provider-normalized status data."""


class JsonTransport(Protocol):
    def post_json(self, url: str, payload: dict[str, object], *, timeout_sec: float) -> dict[str, object]:
        """Send a JSON request and return a decoded JSON payload."""


class UrllibJsonTransport:
    def post_json(self, url: str, payload: dict[str, object], *, timeout_sec: float) -> dict[str, object]:
        request = Request(
            url=url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request, timeout=timeout_sec) as response:
            body = response.read().decode("utf-8")
        decoded = json.loads(body)
        return decoded if isinstance(decoded, dict) else {"status": "failed", "raw_response": decoded}


class ApiRenderBackendAdapter:
    def __init__(
        self,
        *,
        base_url: str,
        submit_path: str,
        timeout_sec: float,
        transport: JsonTransport | None = None,
    ) -> None:
        self.base_url = base_url
        self.submit_path = submit_path
        self.timeout_sec = timeout_sec
        self.transport = transport or UrllibJsonTransport()

    def submit(self, render_request: ShotRenderJob) -> dict[str, object]:
        payload = {
            "render_job_id": render_request.render_job_id,
            "job_id": render_request.job_id,
            "shot_id": render_request.shot_id,
            "backend": render_request.backend.value,
            "motion_tier": render_request.motion_tier.value,
            "prompt_bundle": render_request.prompt_bundle,
            "source_asset_refs": list(render_request.source_asset_refs),
            "requested_duration_sec": render_request.requested_duration_sec,
        }
        return self.transport.post_json(
            self._build_submit_url(),
            payload,
            timeout_sec=self.timeout_sec,
        )

    def _build_submit_url(self) -> str:
        return f"{self.base_url.rstrip('/')}/{self.submit_path.lstrip('/')}"


class RoutingRenderAdapter:
    def __init__(self, *, image_adapter: RenderAdapter, wan_adapter: RenderAdapter) -> None:
        self.image_adapter = image_adapter
        self.wan_adapter = wan_adapter

    def submit(self, render_request: ShotRenderJob) -> dict[str, Any]:
        if render_request.backend is RenderBackend.WAN:
            return self.wan_adapter.submit(render_request)
        return self.image_adapter.submit(render_request)


class DeterministicLocalRenderAdapter:
    def __init__(
        self,
        *,
        workspace: RuntimeWorkspace,
        ffmpeg_executor: FfmpegExecutor,
        output_size: tuple[int, int] = (1280, 720),
        fps: int = 24,
    ) -> None:
        self.workspace = workspace
        self.ffmpeg_executor = ffmpeg_executor
        self.output_size = output_size
        self.fps = fps

    def submit(self, render_request: ShotRenderJob) -> dict[str, Any]:
        job_root = self.workspace.ensure_job_tree(render_request.job_id)
        render_dir = self.workspace.shot_root(render_request.job_id, render_request.shot_id) / "render"
        render_dir.mkdir(parents=True, exist_ok=True)

        frame_path = render_dir / "frame-001.ppm"
        clip_path = render_dir / "clip.mp4"
        self._write_frame(frame_path, render_request)
        self.ffmpeg_executor.run(
            [
                "-y",
                "-loop",
                "1",
                "-framerate",
                str(self.fps),
                "-i",
                str(frame_path),
                "-t",
                f"{render_request.requested_duration_sec:.3f}",
                "-pix_fmt",
                "yuv420p",
                str(clip_path),
            ],
            cwd=job_root,
            output_path=clip_path,
        )

        return {
            "render_job_id": render_request.render_job_id,
            "shot_id": render_request.shot_id,
            "status": "completed",
            "clip_ref": self.workspace.asset_ref(
                render_request.job_id,
                "shots",
                render_request.shot_id,
                "render",
                "clip.mp4",
            ),
            "frame_refs": [
                self.workspace.asset_ref(
                    render_request.job_id,
                    "shots",
                    render_request.shot_id,
                    "render",
                    "frame-001.ppm",
                )
            ],
            "clip_path": str(clip_path.resolve()),
            "frame_paths": [str(frame_path.resolve())],
            "metadata": {
                "duration_sec": render_request.requested_duration_sec,
                "fps": self.fps,
                "output_size": self.output_size,
                "backend": render_request.backend.value,
                "content_source": "deterministic_placeholder",
                "placeholder_mode": "solid_color_loop",
                "dominant_rgb": list(self._derive_color(render_request)),
                "frame_count": 1,
            },
        }

    def _write_frame(self, frame_path: Path, render_request: ShotRenderJob) -> None:
        width, height = self.output_size
        rgb = self._derive_color(render_request)
        header = f"P6\n{width} {height}\n255\n".encode("ascii")
        frame_path.write_bytes(header + bytes(rgb) * width * height)

    def _derive_color(self, render_request: ShotRenderJob) -> tuple[int, int, int]:
        digest = hashlib.sha256(
            f"{render_request.job_id}:{render_request.shot_id}:{render_request.backend.value}".encode(
                "utf-8"
            )
        ).digest()
        return digest[0], digest[1], digest[2]


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
    metadata = payload.get("metadata") or {}
    return ShotRenderResult(
        render_job_id=str(payload["render_job_id"]),
        shot_id=str(payload["shot_id"]),
        status=normalize_render_status(str(payload.get("status", "failed"))),
        clip_ref=payload.get("clip_ref"),
        clip_path=payload.get("clip_path"),
        frame_refs=list(payload.get("frame_refs", [])),
        frame_paths=list(payload.get("frame_paths", [])),
        metadata=dict(metadata),
        error_code=payload.get("error_code"),
    )
