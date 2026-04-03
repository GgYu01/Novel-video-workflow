from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class StorageConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bucket: str


class ReviewConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    threshold: float = Field(ge=0.0, le=1.0)


class AdapterConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    review_provider: str


class RuntimeConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state_backend: str = "postgres"


class AppConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    storage: StorageConfig
    review: ReviewConfig
    adapters: AdapterConfig
    runtime: RuntimeConfig = Field(default_factory=RuntimeConfig)
