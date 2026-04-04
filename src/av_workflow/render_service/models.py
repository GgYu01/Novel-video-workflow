from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from av_workflow.contracts.enums import MotionTier, RenderBackend


class RenderRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    render_job_id: str
    job_id: str
    shot_id: str
    backend: RenderBackend
    motion_tier: MotionTier
    prompt_bundle: dict[str, str]
    source_asset_refs: list[str] = Field(default_factory=list)
    requested_duration_sec: float = Field(gt=0.0)


class RenderResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    render_job_id: str
    shot_id: str
    status: str
    clip_ref: str | None = None
    clip_path: str | None = None
    frame_refs: list[str] = Field(default_factory=list)
    frame_paths: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    error_code: str | None = None
