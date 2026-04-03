from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from av_workflow.contracts.enums import (
    JobStatus,
    MotionTier,
    PolicyAction,
    RenderBackend,
    RenderJobStatus,
    ReviewMode,
    ReviewResult,
    ShotType,
)


class SnapshotModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Job(SnapshotModel):
    job_id: str
    input_mode: str
    source_ref: str
    output_preset: str
    profile_id: str
    language: str
    review_level: str
    tts_profile: str | None = None
    user_overrides: dict[str, Any] = Field(default_factory=dict)
    normalized_source_version: int | None = None
    story_spec_version: int | None = None
    shot_plan_version: int | None = None
    output_package_version: int | None = None
    status: JobStatus = JobStatus.CREATED
    current_stage: str = "created"
    retry_count: int = 0
    policy_profile: str | None = None
    max_auto_retries: int = 2
    quarantine_reason: str | None = None


class SourceDocument(SnapshotModel):
    source_document_id: str
    job_id: str
    source_ref: str
    title: str
    language: str
    normalized_text: str
    chapter_documents: list[dict[str, Any]]
    source_metadata: dict[str, Any] = Field(default_factory=dict)
    version: int = 1


class StorySpec(SnapshotModel):
    story_id: str
    chapter_specs: list[dict[str, Any]]
    character_registry: list[dict[str, Any]]
    location_registry: list[dict[str, Any]]
    timeline_summary: str
    tone_profile: str
    visual_style_profile: str
    forbidden_elements: list[str] = Field(default_factory=list)
    required_elements: list[str] = Field(default_factory=list)
    consistency_rules: list[str] = Field(default_factory=list)
    spec_validation_result: str = "pending"
    approved_for_planning: bool = False
    version: int = 1


class CharacterBible(SnapshotModel):
    character_id: str
    canonical_name: str
    role: str
    visual_identity: list[str]
    wardrobe_rules: list[str] = Field(default_factory=list)
    continuity_rules: list[str] = Field(default_factory=list)
    voice_hints: dict[str, Any] = Field(default_factory=dict)
    version: int = 1


class SceneBible(SnapshotModel):
    scene_id: str
    location_name: str
    time_of_day: str
    environment_description: str
    continuity_requirements: list[str] = Field(default_factory=list)
    prop_requirements: list[str] = Field(default_factory=list)
    version: int = 1


class ShotPlan(SnapshotModel):
    shot_id: str
    chapter_id: str
    scene_id: str
    duration_target: float
    shot_type: ShotType
    motion_tier: MotionTier = MotionTier.LIMITED_MOTION
    camera_instruction: str
    subject_instruction: str
    environment_instruction: str
    narration_text: str
    dialogue_lines: list[str]
    subtitle_source: str
    render_requirements: dict[str, Any]
    review_targets: dict[str, Any]
    fallback_strategy: dict[str, Any]
    version: int = 1


class ShotPlanSet(SnapshotModel):
    shot_plan_set_id: str
    story_id: str
    chapter_id: str
    default_output_preset: str
    shots: list[ShotPlan]
    version: int = 1


class VoiceCast(SnapshotModel):
    voice_cast_id: str
    story_id: str
    narrator_voice_id: str
    character_voice_map: dict[str, str]
    voice_traits: dict[str, dict[str, Any]] = Field(default_factory=dict)
    version: int = 1


class DialogueTimeline(SnapshotModel):
    dialogue_timeline_id: str
    shot_id: str
    segments: list[dict[str, Any]]
    total_duration_ms: int
    version: int = 1


class AudioMixManifest(SnapshotModel):
    audio_mix_manifest_id: str
    job_id: str
    mix_ref: str
    narration_refs: list[str]
    dialogue_refs: list[str]
    bgm_ref: str | None = None
    ambience_refs: list[str] = Field(default_factory=list)
    duration_ms: int
    mix_strategy: dict[str, Any] = Field(default_factory=dict)
    version: int = 1


class ShotRenderJob(SnapshotModel):
    render_job_id: str
    job_id: str
    shot_id: str
    motion_tier: MotionTier
    backend: RenderBackend
    prompt_bundle: dict[str, Any]
    source_asset_refs: list[str] = Field(default_factory=list)
    requested_duration_sec: float
    version: int = 1


class ShotRenderResult(SnapshotModel):
    render_job_id: str
    shot_id: str
    status: RenderJobStatus
    clip_ref: str | None = None
    clip_path: str | None = None
    frame_refs: list[str] = Field(default_factory=list)
    frame_paths: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    error_code: str | None = None
    version: int = 1


class AssetManifest(SnapshotModel):
    asset_manifest_id: str
    job_id: str
    manifest_ref: str
    shot_assets: list[dict[str, Any]]
    subtitle_refs: list[str]
    audio_refs: list[str]
    primary_audio_ref: str | None = None
    preview_refs: list[str]
    cover_refs: list[str]
    final_video_ref: str
    manifest_metadata: dict[str, Any] = Field(default_factory=dict)
    version: int = 1


class ReviewCase(SnapshotModel):
    review_case_id: str
    target_type: str
    target_ref: str
    review_mode: ReviewMode
    input_assets: list[str]
    evaluation_prompt_ref: str
    result: ReviewResult
    score: float
    reason_codes: list[str]
    reason_text: str
    fix_hint: str | None = None
    recommended_action: str
    review_provider: str
    provider_version: str
    latency_ms: int
    raw_response_ref: str
    version: int = 1


class PolicyDecision(SnapshotModel):
    policy_decision_id: str
    job_id: str
    review_case_id: str
    action: PolicyAction
    scope: str | None = None
    target_ref: str
    target_status: JobStatus
    resume_at: JobStatus | None = None
    reason_codes: list[str]
    reason_text: str
    applied_threshold: float | None = None
    review_score: float | None = None
    review_result: ReviewResult
    version: int = 1


class OutputPackage(SnapshotModel):
    output_package_id: str
    job_id: str
    final_video_ref: str
    subtitle_refs: list[str]
    cover_refs: list[str]
    preview_refs: list[str]
    review_summary_ref: str
    production_manifest_ref: str
    ready_for_delivery: bool
    version: int
