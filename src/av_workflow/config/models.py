from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class StorageConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bucket: str


class ReviewConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    threshold: float = Field(ge=0.0, le=1.0)
    escalation_threshold: float = Field(ge=0.0, le=1.0)


class AdapterConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    review_provider: str
    image_provider: str
    tts_provider: str
    wan_provider: str


class RenderConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    default_output_preset: str
    allow_wan_for_dynamic: bool


class AudioConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    narrator_voice_id: str
    subtitle_source_mode: str
    default_speech_rate: float = Field(gt=0.0)


class AgentsConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enable_control_plane: bool
    allowed_agents: list[str]
    max_parallel_proposals: int = Field(ge=1)


class RuntimeConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state_backend: str = "postgres"


class AppConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    storage: StorageConfig
    review: ReviewConfig
    adapters: AdapterConfig
    render: RenderConfig
    audio: AudioConfig
    agents: AgentsConfig
    runtime: RuntimeConfig = Field(default_factory=RuntimeConfig)
