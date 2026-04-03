from __future__ import annotations

from pydantic import ValidationError

from av_workflow.contracts.enums import JobStatus, PolicyAction, ReviewMode, ReviewResult, ShotType
from av_workflow.contracts.models import (
    AssetManifest,
    Job,
    OutputPackage,
    PolicyDecision,
    ReviewCase,
    ShotPlan,
    SourceDocument,
    StorySpec,
)


def test_job_requires_profile_id_and_defaults_created_status() -> None:
    job = Job(
        job_id="job-001",
        input_mode="upload",
        source_ref="asset://source.txt",
        output_preset="short-story",
        profile_id="internal-prod",
        language="zh-CN",
        review_level="strict",
    )

    assert job.status is JobStatus.CREATED
    assert job.current_stage == "created"
    assert job.retry_count == 0


def test_job_rejects_missing_profile_id() -> None:
    try:
        Job(
            job_id="job-002",
            input_mode="upload",
            source_ref="asset://source.txt",
            output_preset="short-story",
            language="zh-CN",
            review_level="strict",
        )
    except ValidationError as exc:
        assert "profile_id" in str(exc)
    else:
        raise AssertionError("Expected ValidationError for missing profile_id")


def test_story_spec_defaults_to_pending_planning_approval() -> None:
    story = StorySpec(
        story_id="story-001",
        chapter_specs=[{"chapter_id": "ch-1", "title": "Arrival"}],
        character_registry=[{"character_id": "hero", "name": "Hero"}],
        location_registry=[{"location_id": "city", "name": "City"}],
        timeline_summary="A hero arrives in a new city.",
        tone_profile="grounded",
        visual_style_profile="cinematic realism",
    )

    assert story.approved_for_planning is False
    assert story.spec_validation_result == "pending"


def test_source_document_tracks_normalized_text_and_chapters() -> None:
    source = SourceDocument(
        source_document_id="source-001",
        job_id="job-001",
        source_ref="asset://source.txt",
        title="Arrival",
        language="zh-CN",
        normalized_text="Chapter 1: Arrival\nThe train arrived at dawn.",
        chapter_documents=[
            {
                "chapter_id": "ch-1",
                "title": "Chapter 1: Arrival",
                "content": "The train arrived at dawn.",
            }
        ],
    )

    assert source.version == 1
    assert source.chapter_documents[0]["chapter_id"] == "ch-1"


def test_shot_plan_requires_supported_shot_type() -> None:
    shot = ShotPlan(
        shot_id="shot-001",
        chapter_id="ch-1",
        scene_id="scene-1",
        duration_target=4.0,
        shot_type=ShotType.MEDIUM,
        camera_instruction="steady eye-level framing",
        subject_instruction="hero steps into the station",
        environment_instruction="foggy industrial train station",
        narration_text="The city greeted him with iron and smoke.",
        dialogue_lines=[],
        subtitle_source="narration",
        render_requirements={"aspect_ratio": "16:9"},
        review_targets={"must_match": ["hero", "station"]},
        fallback_strategy={"retry_scope": "shot"},
    )

    assert shot.shot_type is ShotType.MEDIUM
    assert shot.duration_target == 4.0


def test_asset_manifest_tracks_traceable_asset_references() -> None:
    manifest = AssetManifest(
        asset_manifest_id="manifest-001",
        job_id="job-001",
        manifest_ref="asset://manifests/job-001.json",
        shot_assets=[
            {
                "shot_id": "shot-001",
                "clip_ref": "asset://shots/shot-001.mp4",
                "frame_refs": ["asset://frames/shot-001-001.png"],
            }
        ],
        subtitle_refs=["asset://subtitles/final.srt"],
        audio_refs=["asset://audio/narration.wav"],
        preview_refs=["asset://preview/final.png"],
        cover_refs=["asset://cover/final.png"],
        final_video_ref="asset://video/final.mp4",
        manifest_metadata={"duration_sec": 4.0},
    )

    assert manifest.version == 1
    assert manifest.shot_assets[0]["shot_id"] == "shot-001"
    assert manifest.manifest_ref == "asset://manifests/job-001.json"
    assert manifest.final_video_ref == "asset://video/final.mp4"


def test_review_case_requires_structured_result_fields() -> None:
    review = ReviewCase(
        review_case_id="review-001",
        target_type="shot",
        target_ref="shot-001",
        review_mode=ReviewMode.SEMANTIC_IMAGE,
        input_assets=["asset://frame-1.png"],
        evaluation_prompt_ref="prompt://review/default",
        result=ReviewResult.PASS,
        score=0.92,
        reason_codes=["character_match"],
        reason_text="Character appearance matches the shot plan.",
        fix_hint=None,
        recommended_action="continue",
        review_provider="antigravity-image",
        provider_version="preview",
        latency_ms=820,
        raw_response_ref="raw://review-001.json",
    )

    assert review.result is ReviewResult.PASS
    assert review.score == 0.92


def test_policy_decision_tracks_retry_scope_and_resume_target() -> None:
    decision = PolicyDecision(
        policy_decision_id="decision-001",
        job_id="job-001",
        review_case_id="review-001",
        action=PolicyAction.RETRY,
        scope="shot",
        target_ref="shot-001",
        target_status=JobStatus.RETRY_SCHEDULED,
        resume_at=JobStatus.PLANNED,
        reason_codes=["semantic_mismatch"],
        reason_text="Semantic review failed and should retry the affected shot.",
        applied_threshold=0.9,
        review_score=0.41,
        review_result=ReviewResult.FAIL,
    )

    assert decision.action is PolicyAction.RETRY
    assert decision.scope == "shot"
    assert decision.target_status is JobStatus.RETRY_SCHEDULED
    assert decision.resume_at is JobStatus.PLANNED


def test_output_package_requires_final_video_reference() -> None:
    package = OutputPackage(
        output_package_id="output-001",
        job_id="job-001",
        final_video_ref="asset://final.mp4",
        subtitle_refs=["asset://subtitle.srt"],
        cover_refs=["asset://cover.png"],
        preview_refs=["asset://preview.png"],
        review_summary_ref="asset://review-summary.json",
        production_manifest_ref="asset://manifest.json",
        ready_for_delivery=False,
        version=1,
    )

    assert package.version == 1
    assert package.ready_for_delivery is False
