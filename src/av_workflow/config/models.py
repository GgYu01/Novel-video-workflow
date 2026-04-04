from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StorageConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bucket: str


class SemanticReviewConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: Literal["fail_closed", "llama_cpp_cli"] = "fail_closed"
    provider: str = "semantic-review"
    launch_scope: Literal["per_job", "per_shot"] = "per_job"
    model_family: Literal["qwen2_vl", "qwen3_vl"] = "qwen3_vl"
    model_size: Literal["2b", "4b", "8b", "32b"] = "32b"
    model_quantization: str = "Q4_K_M"
    mmproj_quantization: str = "Q8_0"
    command_path: str | None = None
    model_path: str | None = None
    mmproj_path: str | None = None
    timeout_sec: float = Field(default=1800.0, gt=0.0)
    max_tokens: int = Field(default=256, ge=1)
    ctx_size: int = Field(default=4096, ge=1)
    max_input_frames: int = Field(default=4, ge=1)
    extra_args: list[str] = Field(default_factory=list)
    prompt_ref: str = "prompt://review/semantic-default"

    @model_validator(mode="after")
    def _validate_mode_contract(self) -> "SemanticReviewConfig":
        if self.mode != "llama_cpp_cli":
            return self

        missing_fields = [
            field_name
            for field_name, value in {
                "command_path": self.command_path,
                "model_path": self.model_path,
                "mmproj_path": self.mmproj_path,
            }.items()
            if not value
        ]
        if missing_fields:
            raise ValueError(
                "Semantic review CLI mode requires configured paths for: "
                f"{', '.join(missing_fields)}"
            )
        return self


class ReviewConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    threshold: float = Field(ge=0.0, le=1.0)
    escalation_threshold: float = Field(ge=0.0, le=1.0)
    require_semantic_pass_for_completion: bool = True
    semantic: SemanticReviewConfig = Field(default_factory=SemanticReviewConfig)


class AdapterConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    review_provider: str
    image_provider: str
    tts_provider: str
    wan_provider: str


class RenderEndpointConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    base_url: str
    submit_path: str
    timeout_sec: float = Field(gt=0.0)


class RenderConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: Literal["deterministic_local", "routed_api"]
    default_output_preset: str
    allow_wan_for_dynamic: bool
    image_endpoint: RenderEndpointConfig
    wan_endpoint: RenderEndpointConfig


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
