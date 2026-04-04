from __future__ import annotations

import hashlib
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from av_workflow.contracts.enums import RenderBackend
from av_workflow.render_service.models import RenderRequest, RenderResponse
from av_workflow.runtime.ffmpeg import FfmpegExecutor
from av_workflow.runtime.workspace import RuntimeWorkspace


class RenderServiceBackend(Protocol):
    def render(self, request: RenderRequest) -> RenderResponse:
        """Materialize render artifacts and return a normalized response."""


@dataclass(frozen=True)
class SdCppImageBackendConfig:
    binary_path: str
    diffusion_model_path: str
    vae_path: str
    llm_path: str
    width: int = 1024
    height: int = 576
    steps: int = 4
    cfg_scale: float = 1.0
    sampling_method: str = "euler"
    extra_args: tuple[str, ...] = field(default_factory=tuple)


def build_sd_cpp_image_command(
    *,
    prompt: str,
    output_path: Path,
    config: SdCppImageBackendConfig,
) -> list[str]:
    return [
        config.binary_path,
        "--diffusion-model",
        config.diffusion_model_path,
        "--vae",
        config.vae_path,
        "--llm",
        config.llm_path,
        "-o",
        str(output_path),
        "-W",
        str(config.width),
        "-H",
        str(config.height),
        "--steps",
        str(config.steps),
        "--cfg-scale",
        str(config.cfg_scale),
        "--sampling-method",
        config.sampling_method,
        "-p",
        prompt,
        *config.extra_args,
    ]


class PlaceholderImageBackend:
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

    def render(self, request: RenderRequest) -> RenderResponse:
        render_dir = self.workspace.shot_root(request.job_id, request.shot_id) / "render"
        render_dir.mkdir(parents=True, exist_ok=True)
        frame_path = render_dir / "frame-001.ppm"
        clip_path = render_dir / "clip.mp4"
        self._write_pattern_frame(frame_path, request=request, frame_index=0)
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
                f"{request.requested_duration_sec:.3f}",
                "-pix_fmt",
                "yuv420p",
                str(clip_path),
            ],
            cwd=self.workspace.ensure_job_tree(request.job_id),
            output_path=clip_path,
        )
        return self._build_response(
            request=request,
            clip_path=clip_path,
            frame_paths=[frame_path],
            placeholder_mode="pattern_frame_loop",
        )

    def _build_response(
        self,
        *,
        request: RenderRequest,
        clip_path: Path,
        frame_paths: list[Path],
        placeholder_mode: str,
    ) -> RenderResponse:
        return RenderResponse(
            render_job_id=request.render_job_id,
            shot_id=request.shot_id,
            status="completed",
            clip_ref=self.workspace.asset_ref(
                request.job_id,
                "shots",
                request.shot_id,
                "render",
                "clip.mp4",
            ),
            clip_path=str(clip_path.resolve()),
            frame_refs=[
                self.workspace.asset_ref(
                    request.job_id,
                    "shots",
                    request.shot_id,
                    "render",
                    frame_path.name,
                )
                for frame_path in frame_paths
            ],
            frame_paths=[str(frame_path.resolve()) for frame_path in frame_paths],
            metadata={
                "duration_sec": request.requested_duration_sec,
                "fps": self.fps,
                "output_size": list(self.output_size),
                "backend": request.backend.value,
                "content_source": "deterministic_placeholder",
                "placeholder_mode": placeholder_mode,
                "frame_count": len(frame_paths),
            },
        )

    def _write_pattern_frame(
        self,
        frame_path: Path,
        *,
        request: RenderRequest,
        frame_index: int,
    ) -> None:
        width, height = self.output_size
        digest = hashlib.sha256(
            (
                f"{request.job_id}:{request.shot_id}:{request.backend.value}:"
                f"{request.prompt_bundle.get('image_prompt', '')}:{frame_index}"
            ).encode("utf-8")
        ).digest()
        header = f"P6\n{width} {height}\n255\n".encode("ascii")
        pixels = bytearray()
        for y in range(height):
            for x in range(width):
                red = (digest[0] + x * 3 + y + frame_index * 11) % 256
                green = (digest[1] + x + y * 2 + frame_index * 17) % 256
                blue = (digest[2] + x * 2 + y * 3 + frame_index * 23) % 256
                pixels.extend((red, green, blue))
        frame_path.write_bytes(header + bytes(pixels))


class PlaceholderWanBackend(PlaceholderImageBackend):
    def render(self, request: RenderRequest) -> RenderResponse:
        render_dir = self.workspace.shot_root(request.job_id, request.shot_id) / "render"
        render_dir.mkdir(parents=True, exist_ok=True)
        frame_paths = [render_dir / f"frame-{index:03d}.ppm" for index in range(1, 4)]
        clip_path = render_dir / "clip.mp4"
        for index, frame_path in enumerate(frame_paths):
            self._write_pattern_frame(frame_path, request=request, frame_index=index)

        frame_rate = len(frame_paths) / request.requested_duration_sec
        self.ffmpeg_executor.run(
            [
                "-y",
                "-framerate",
                f"{frame_rate:.6f}",
                "-i",
                str(render_dir / "frame-%03d.ppm"),
                "-t",
                f"{request.requested_duration_sec:.3f}",
                "-pix_fmt",
                "yuv420p",
                str(clip_path),
            ],
            cwd=self.workspace.ensure_job_tree(request.job_id),
            output_path=clip_path,
        )
        return self._build_response(
            request=request,
            clip_path=clip_path,
            frame_paths=frame_paths,
            placeholder_mode="motion_placeholder_sequence",
        )


class StableDiffusionCppImageBackend(PlaceholderImageBackend):
    def __init__(
        self,
        *,
        workspace: RuntimeWorkspace,
        ffmpeg_executor: FfmpegExecutor,
        config: SdCppImageBackendConfig,
        fps: int = 24,
    ) -> None:
        super().__init__(
            workspace=workspace,
            ffmpeg_executor=ffmpeg_executor,
            output_size=(config.width, config.height),
            fps=fps,
        )
        self.config = config

    def render(self, request: RenderRequest) -> RenderResponse:
        render_dir = self.workspace.shot_root(request.job_id, request.shot_id) / "render"
        render_dir.mkdir(parents=True, exist_ok=True)
        frame_path = render_dir / "frame-001.png"
        clip_path = render_dir / "clip.mp4"
        subprocess.run(
            build_sd_cpp_image_command(
                prompt=request.prompt_bundle.get("image_prompt", ""),
                output_path=frame_path,
                config=self.config,
            ),
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if not frame_path.exists():
            raise RuntimeError(f"sd_cpp_output_missing: {frame_path}")
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
                f"{request.requested_duration_sec:.3f}",
                "-pix_fmt",
                "yuv420p",
                str(clip_path),
            ],
            cwd=self.workspace.ensure_job_tree(request.job_id),
            output_path=clip_path,
        )
        response = self._build_response(
            request=request,
            clip_path=clip_path,
            frame_paths=[frame_path],
            placeholder_mode="",
        )
        response.metadata.update(
            {
                "content_source": "image_model",
                "placeholder_mode": None,
                "model_family": "Z-Image-Turbo-GGUF",
                "diffusion_model_path": self.config.diffusion_model_path,
                "vae_path": self.config.vae_path,
                "llm_path": self.config.llm_path,
            }
        )
        return response


def build_image_backend_from_env(
    *,
    runtime_root: str | Path,
    ffmpeg_executor: FfmpegExecutor,
) -> RenderServiceBackend:
    workspace = RuntimeWorkspace(root_dir=runtime_root)
    backend_kind = os.environ.get("AV_WORKFLOW_IMAGE_BACKEND_KIND", "placeholder").strip().lower()
    width = int(os.environ.get("AV_WORKFLOW_IMAGE_OUTPUT_WIDTH", "1280"))
    height = int(os.environ.get("AV_WORKFLOW_IMAGE_OUTPUT_HEIGHT", "720"))
    fps = int(os.environ.get("AV_WORKFLOW_IMAGE_OUTPUT_FPS", "24"))
    if backend_kind == "placeholder":
        return PlaceholderImageBackend(
            workspace=workspace,
            ffmpeg_executor=ffmpeg_executor,
            output_size=(width, height),
            fps=fps,
        )
    if backend_kind == "sd_cpp":
        binary_path = _require_env("AV_WORKFLOW_SD_CPP_BIN")
        diffusion_model_path = _require_env("AV_WORKFLOW_Z_IMAGE_DIFFUSION_MODEL_PATH")
        vae_path = _require_env("AV_WORKFLOW_Z_IMAGE_VAE_PATH")
        llm_path = _require_env("AV_WORKFLOW_Z_IMAGE_LLM_PATH")
        extra_args = tuple(
            item for item in os.environ.get("AV_WORKFLOW_Z_IMAGE_EXTRA_ARGS", "").split() if item.strip()
        )
        return StableDiffusionCppImageBackend(
            workspace=workspace,
            ffmpeg_executor=ffmpeg_executor,
            fps=fps,
            config=SdCppImageBackendConfig(
                binary_path=binary_path,
                diffusion_model_path=diffusion_model_path,
                vae_path=vae_path,
                llm_path=llm_path,
                width=width,
                height=height,
                steps=int(os.environ.get("AV_WORKFLOW_Z_IMAGE_STEPS", "4")),
                cfg_scale=float(os.environ.get("AV_WORKFLOW_Z_IMAGE_CFG_SCALE", "1.0")),
                sampling_method=os.environ.get("AV_WORKFLOW_Z_IMAGE_SAMPLING_METHOD", "euler"),
                extra_args=extra_args,
            ),
        )
    raise ValueError(f"Unsupported image backend kind: {backend_kind}")


def build_wan_backend_from_env(
    *,
    runtime_root: str | Path,
    ffmpeg_executor: FfmpegExecutor,
) -> RenderServiceBackend:
    workspace = RuntimeWorkspace(root_dir=runtime_root)
    backend_kind = os.environ.get("AV_WORKFLOW_WAN_BACKEND_KIND", "placeholder").strip().lower()
    width = int(os.environ.get("AV_WORKFLOW_WAN_OUTPUT_WIDTH", "1280"))
    height = int(os.environ.get("AV_WORKFLOW_WAN_OUTPUT_HEIGHT", "720"))
    fps = int(os.environ.get("AV_WORKFLOW_WAN_OUTPUT_FPS", "24"))
    if backend_kind == "placeholder":
        return PlaceholderWanBackend(
            workspace=workspace,
            ffmpeg_executor=ffmpeg_executor,
            output_size=(width, height),
            fps=fps,
        )
    raise ValueError(f"Unsupported wan backend kind: {backend_kind}")


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if value is None or not value.strip():
        raise ValueError(f"Missing required environment variable: {name}")
    return value.strip()
