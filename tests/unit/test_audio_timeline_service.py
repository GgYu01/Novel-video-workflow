from __future__ import annotations

from av_workflow.contracts.models import ShotPlan, SourceDocument, StorySpec, VoiceCast
from av_workflow.services.audio_timeline import DeterministicAudioTimelineService


def build_story_spec() -> StorySpec:
    return StorySpec(
        story_id="story-001",
        chapter_specs=[
            {"chapter_id": "ch-1", "title": "Chapter 1", "summary": "Jose speaks with Antonio."}
        ],
        character_registry=[
            {"character_id": "character-jose", "canonical_name": "Jose Alemany", "role": "primary"},
            {"character_id": "character-antonio", "canonical_name": "Antonio Asensio", "role": "supporting"},
        ],
        location_registry=[
            {"scene_id": "scene-1", "location_name": "Saint Moix Stadium", "time_of_day": "day"}
        ],
        timeline_summary="One chapter",
        tone_profile="grounded",
        visual_style_profile="cinematic realism",
        spec_validation_result="validated",
        approved_for_planning=True,
    )


def build_shot_plan() -> ShotPlan:
    return ShotPlan(
        shot_id="shot-001",
        chapter_id="ch-1",
        scene_id="scene-1",
        duration_target=4.5,
        shot_type="medium",
        camera_instruction="wide crowd coverage",
        subject_instruction="celebrating players throw the coach into the air",
        environment_instruction="packed Saint Moix Stadium",
        narration_text="The celebration exploded across the stadium.",
        dialogue_lines=["Jose: Now the real work begins.", "Antonio: Then let's get to it."],
        subtitle_source="auto",
        render_requirements={"aspect_ratio": "16:9"},
        review_targets={"must_match": ["coach", "stadium"]},
        fallback_strategy={"retry_scope": "shot"},
    )


def test_audio_timeline_service_assigns_voice_cast_and_segments_dialogue() -> None:
    service = DeterministicAudioTimelineService()
    source = SourceDocument(
        source_document_id="source-001",
        job_id="job-001",
        source_ref="asset://source.txt",
        title="Mallorca",
        language="zh-CN",
        normalized_text="Chapter 1: Arrival",
        chapter_documents=[
            {"chapter_id": "ch-1", "title": "Chapter 1: Arrival", "content": "Jose speaks with Antonio."}
        ],
    )
    story_spec = build_story_spec()
    shot_plan = build_shot_plan()

    voice_cast = service.build_voice_cast(source_document=source, story_spec=story_spec)
    timeline = service.build_timeline(
        shot_plan=shot_plan,
        voice_cast=voice_cast,
    )

    assert isinstance(voice_cast, VoiceCast)
    assert voice_cast.narrator_voice_id.startswith("narrator.")
    assert voice_cast.character_voice_map["character-jose"].startswith("role.")
    assert timeline.total_duration_ms > 0
    assert len(timeline.segments) == 3
    assert timeline.segments[1]["speaker"] == "character-jose"


def test_audio_timeline_service_skips_empty_narration_segments() -> None:
    service = DeterministicAudioTimelineService()
    source = SourceDocument(
        source_document_id="source-001",
        job_id="job-001",
        source_ref="asset://source.txt",
        title="Mallorca",
        language="zh-CN",
        normalized_text="Chapter 1: Arrival",
        chapter_documents=[
            {"chapter_id": "ch-1", "title": "Chapter 1: Arrival", "content": "Jose speaks with Antonio."}
        ],
    )
    story_spec = build_story_spec()
    shot_plan = build_shot_plan().model_copy(update={"narration_text": ""})

    voice_cast = service.build_voice_cast(source_document=source, story_spec=story_spec)
    timeline = service.build_timeline(
        shot_plan=shot_plan,
        voice_cast=voice_cast,
    )

    assert len(timeline.segments) == 2
    assert timeline.segments[0]["speaker"] == "character-jose"
