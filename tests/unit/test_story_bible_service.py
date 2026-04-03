from __future__ import annotations

from av_workflow.contracts.models import SourceDocument
from av_workflow.services.story_bible import DeterministicStoryBibleService


def build_source_document() -> SourceDocument:
    return SourceDocument(
        source_document_id="source-001",
        job_id="job-001",
        source_ref="asset://source.txt",
        title="Mallorca",
        language="en",
        normalized_text=(
            "Chapter 1: Arrival at Saint Moix Stadium\n"
            "Jose Alemany watched Antonio Asensio celebrate at Saint Moix Stadium.\n"
            "Jose Alemany promised Mateo Alemany he would rebuild Mallorca.\n"
            "Chapter 2: Midnight Office\n"
            "Antonio Asensio met Jose Alemany in the office overlooking Saint Moix Stadium."
        ),
        chapter_documents=[
            {
                "chapter_id": "ch-1",
                "title": "Chapter 1: Arrival at Saint Moix Stadium",
                "content": (
                    "Jose Alemany watched Antonio Asensio celebrate at Saint Moix Stadium. "
                    "Jose Alemany promised Mateo Alemany he would rebuild Mallorca."
                ),
            },
            {
                "chapter_id": "ch-2",
                "title": "Chapter 2: Midnight Office",
                "content": (
                    "Antonio Asensio met Jose Alemany in the office overlooking Saint Moix Stadium."
                ),
            },
        ],
    )


def test_story_bible_service_extracts_character_bibles_from_repeated_names() -> None:
    service = DeterministicStoryBibleService()
    source = build_source_document()

    characters = service.build_character_bibles(source)

    assert any(character.canonical_name == "Jose Alemany" for character in characters)
    assert any(character.canonical_name == "Antonio Asensio" for character in characters)
    jose = next(character for character in characters if character.canonical_name == "Jose Alemany")
    assert jose.voice_hints["tone_hint"] == "grounded_narrative"


def test_story_bible_service_builds_scene_bibles_from_location_clues() -> None:
    service = DeterministicStoryBibleService()
    source = build_source_document()

    scenes = service.build_scene_bibles(source)

    assert scenes[0].location_name == "Saint Moix Stadium"
    assert "keep chapter lighting stable" in scenes[0].continuity_requirements
    assert scenes[1].location_name == "Midnight Office"
