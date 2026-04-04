from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, status

from av_workflow.render_service.backends import (
    RenderServiceBackend,
    build_image_backend_from_env,
    build_wan_backend_from_env,
)
from av_workflow.render_service.models import RenderRequest, RenderResponse
from av_workflow.runtime.ffmpeg import FfmpegExecutor, SubprocessFfmpegExecutor


def create_app(
    *,
    image_backend: RenderServiceBackend | None = None,
    wan_backend: RenderServiceBackend | None = None,
) -> FastAPI:
    app = FastAPI(title="av-render-service", version="0.1.0")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/v1/render/image", response_model=RenderResponse)
    def render_image(request: RenderRequest) -> RenderResponse:
        if image_backend is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="image_backend_not_configured",
            )
        if request.backend.value != "image":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="backend_mismatch")
        return image_backend.render(request)

    @app.post("/v1/render/video", response_model=RenderResponse)
    def render_video(request: RenderRequest) -> RenderResponse:
        if wan_backend is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="wan_backend_not_configured",
            )
        if request.backend.value != "wan":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="backend_mismatch")
        return wan_backend.render(request)

    return app


def create_app_from_env(
    *,
    ffmpeg_executor: FfmpegExecutor | None = None,
) -> FastAPI:
    runtime_root = Path(os.environ.get("AV_WORKFLOW_RUNTIME_ROOT", "/app/runtime"))
    role = os.environ.get("AV_WORKFLOW_RENDERER_ROLE", "image").strip().lower()
    executor = ffmpeg_executor or SubprocessFfmpegExecutor()
    image_backend = None
    wan_backend = None
    if role == "image":
        image_backend = build_image_backend_from_env(
            runtime_root=runtime_root,
            ffmpeg_executor=executor,
        )
    elif role == "wan":
        wan_backend = build_wan_backend_from_env(
            runtime_root=runtime_root,
            ffmpeg_executor=executor,
        )
    else:
        raise ValueError(f"Unsupported renderer role: {role}")
    return create_app(image_backend=image_backend, wan_backend=wan_backend)


app = create_app_from_env()
