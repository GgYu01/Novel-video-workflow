from __future__ import annotations

from enum import Enum


class StrEnum(str, Enum):
    """Small helper to keep contract enums JSON-friendly."""


class JobStatus(StrEnum):
    CREATED = "created"
    NORMALIZED = "normalized"
    PLANNED = "planned"
    RENDER_REQUESTED = "render_requested"
    RENDER_READY = "render_ready"
    AUDIO_READY = "audio_ready"
    COMPOSED = "composed"
    QA_TECHNICAL_PASSED = "qa_technical_passed"
    QA_SEMANTIC_PASSED = "qa_semantic_passed"
    OUTPUT_READY = "output_ready"
    COMPLETED = "completed"
    RETRY_SCHEDULED = "retry_scheduled"
    QUARANTINED = "quarantined"
    MANUAL_HOLD = "manual_hold"
    FAILED_TERMINAL = "failed_terminal"


class ShotType(StrEnum):
    CLOSE_UP = "close_up"
    MEDIUM = "medium"
    WIDE = "wide"
    OVER_SHOULDER = "over_shoulder"
    INSERT = "insert"


class MotionTier(StrEnum):
    STATIC = "static"
    LIMITED_MOTION = "limited_motion"
    WAN_DYNAMIC = "wan_dynamic"


class RenderBackend(StrEnum):
    IMAGE = "image"
    WAN = "wan"


class RenderJobStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class ReviewMode(StrEnum):
    TECHNICAL = "technical"
    SEMANTIC_IMAGE = "semantic_image"
    CONTINUITY = "continuity"
    POLICY = "policy"


class ReviewResult(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    WARN = "warn"


class PolicyAction(StrEnum):
    CONTINUE = "continue"
    RETRY = "retry"
    QUARANTINE = "quarantine"
    MANUAL_HOLD = "manual_hold"
