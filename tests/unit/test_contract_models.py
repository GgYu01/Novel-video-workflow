from __future__ import annotations

from pydantic import ValidationError

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
from av_workflow.contracts.models import (
    AssetManifest,
    CharacterBible,
    AudioMixManifest,
    DialogueTimeline,
    Job,
    OutputPackage,
    PolicyDecision,
    ReviewCase,
    SceneBible,
    ShotPlan,
    ShotPlanSet,
    ShotRenderJob,
    ShotRenderResult,
    SourceDocument,
    StorySpec,
    VoiceCast,
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


def test_audio_mix_manifest_tracks_primary_mix_and_component_refs() -> None:
    mix = AudioMixManifest(
        audio_mix_manifest_id="mix-001",
        job_id="job-001",
        mix_ref="asset://audio/mix.wav",
        narration_refs=["asset://audio/narrator.wav"],
        dialogue_refs=["asset://audio/dialogue-1.wav", "asset://audio/dialogue-2.wav"],
        bgm_ref="asset://audio/bgm.wav",
        ambience_refs=["asset://audio/ambience.wav"],
        duration_ms=4200,
        mix_strategy={"ducking_enabled": True, "loudness_target_lufs": -16},
    )

    assert mix.mix_ref == "asset://audio/mix.wav"
    assert mix.duration_ms == 4200
    assert mix.mix_strategy["ducking_enabled"] is True


def test_character_bible_tracks_visual_identity_and_voice_hints() -> None:
    character = CharacterBible(
        character_id="character-jose",
        canonical_name="Jose Alemany",
        role="protagonist",
        visual_identity=[
            "young man",
            "short dark hair",
            "late 20th century football setting",
        ],
        wardrobe_rules=["avoid modern sportswear logos", "use grounded 1999 styling"],
        continuity_rules=["keep face shape and age range stable across adjacent shots"],
        voice_hints={
            "gender_hint": "male",
            "age_hint": "young_adult",
            "tone_hint": "calm_confident",
        },
    )

    assert character.version == 1
    assert character.voice_hints["tone_hint"] == "calm_confident"
    assert "young man" in character.visual_identity


def test_scene_bible_requires_environment_and_continuity_rules() -> None:
    scene = SceneBible(
        scene_id="scene-stadium-celebration",
        location_name="Saint Moix Stadium",
        time_of_day="day",
        environment_description="football stadium filled with celebrating home supporters",
        continuity_requirements=[
            "maintain crowd density across celebration shots",
            "preserve Mallorca team color presence",
        ],
        prop_requirements=["stadium stands", "pitch sideline", "match-day atmosphere"],
    )

    assert scene.location_name == "Saint Moix Stadium"
    assert len(scene.continuity_requirements) == 2


def test_shot_plan_set_groups_shots_under_story_and_chapter_scope() -> None:
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
    shot_plan_set = ShotPlanSet(
        shot_plan_set_id="shot-plan-ch1-v1",
        story_id="story-001",
        chapter_id="ch-1",
        default_output_preset="preview_720p24",
        shots=[shot],
    )

    assert shot_plan_set.version == 1
    assert shot_plan_set.shots[0].shot_id == "shot-001"
    assert shot_plan_set.default_output_preset == "preview_720p24"


def test_voice_cast_requires_stable_narrator_and_character_voice_ids() -> None:
    voice_cast = VoiceCast(
        voice_cast_id="voice-cast-001",
        story_id="story-001",
        narrator_voice_id="narrator.zh_female_01",
        character_voice_map={
            "character-jose": "role.zh_male_02",
            "character-antonio": "role.zh_male_05",
        },
        voice_traits={
            "character-jose": {"speech_rate": 1.0, "pitch_bias": -1},
            "character-antonio": {"speech_rate": 0.92, "pitch_bias": -3},
        },
    )

    assert voice_cast.narrator_voice_id == "narrator.zh_female_01"
    assert voice_cast.character_voice_map["character-jose"] == "role.zh_male_02"


def test_dialogue_timeline_tracks_timed_segments_per_shot() -> None:
    timeline = DialogueTimeline(
        dialogue_timeline_id="timeline-shot-001",
        shot_id="shot-001",
        segments=[
            {
                "segment_id": "seg-001",
                "speaker": "narrator",
                "text": "The stadium exploded in celebration.",
                "start_ms": 0,
                "end_ms": 1800,
                "audio_ref": "asset://audio/seg-001.wav",
            },
            {
                "segment_id": "seg-002",
                "speaker": "character-jose",
                "text": "Now the real work begins.",
                "start_ms": 1800,
                "end_ms": 3200,
                "audio_ref": "asset://audio/seg-002.wav",
            },
        ],
        total_duration_ms=3200,
    )

    assert timeline.total_duration_ms == 3200
    assert timeline.segments[1]["speaker"] == "character-jose"


def test_shot_render_job_tracks_motion_tier_backend_and_prompt_bundle() -> None:
    render_job = ShotRenderJob(
        render_job_id="render-job-001",
        job_id="job-001",
        shot_id="shot-001",
        motion_tier=MotionTier.WAN_DYNAMIC,
        backend=RenderBackend.WAN,
        prompt_bundle={
            "image_prompt": "football coach lifted into the air by celebrating players",
            "video_prompt": "dynamic crowd celebration with upward throwing motion",
        },
        source_asset_refs=["asset://planning/scene-stadium.json"],
        requested_duration_sec=4.5,
    )

    assert render_job.motion_tier is MotionTier.WAN_DYNAMIC
    assert render_job.backend is RenderBackend.WAN
    assert render_job.requested_duration_sec == 4.5


def test_shot_render_result_requires_normalized_status_and_artifact_refs() -> None:
    result = ShotRenderResult(
        render_job_id="render-job-001",
        shot_id="shot-001",
        status=RenderJobStatus.SUCCEEDED,
        clip_ref="asset://shots/shot-001.mp4",
        frame_refs=[
            "asset://shots/shot-001/frame-001.png",
            "asset://shots/shot-001/frame-002.png",
        ],
        metadata={"duration_sec": 4.48, "fps": 24},
    )

    assert result.status is RenderJobStatus.SUCCEEDED
    assert result.clip_ref == "asset://shots/shot-001.mp4"
    assert result.metadata["fps"] == 24
