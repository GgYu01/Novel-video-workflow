from __future__ import annotations

from av_workflow.contracts.enums import ShotType
from av_workflow.contracts.models import SourceDocument
from av_workflow.services.planning import DeterministicPlanningService


class StubShotPlanner:
    def __init__(self) -> None:
        self.calls: list[tuple[SourceDocument, str]] = []

    def build_shots(self, source_document: SourceDocument, story_id: str) -> list[dict[str, object]]:
        self.calls.append((source_document, story_id))
        first_chapter = source_document.chapter_documents[0]
        return [
            {
                "shot_id": "shot-001",
                "chapter_id": first_chapter["chapter_id"],
                "scene_id": "scene-001",
                "duration_target": 4.0,
                "shot_type": ShotType.MEDIUM,
                "camera_instruction": "steady eye-level framing",
                "subject_instruction": "traveler steps off the train",
                "environment_instruction": "foggy station platform",
                "narration_text": "Dawn rolled across the tracks.",
                "dialogue_lines": [],
                "subtitle_source": "narration",
                "render_requirements": {"aspect_ratio": "16:9"},
                "review_targets": {"must_match": ["traveler", "station"]},
                "fallback_strategy": {"retry_scope": "shot"},
            }
        ]


def build_source_document() -> SourceDocument:
    return SourceDocument(
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


def test_planning_service_builds_story_spec_from_source_document() -> None:
    service = DeterministicPlanningService(shot_planner=StubShotPlanner())
    source = build_source_document()

    story_spec = service.build_story_spec(source)

    assert story_spec.story_id == source.source_document_id
    assert story_spec.approved_for_planning is True
    assert story_spec.spec_validation_result == "validated"
    assert story_spec.chapter_specs[0]["chapter_id"] == "ch-1"


def test_planning_service_generates_shot_plans_via_injected_planner() -> None:
    planner = StubShotPlanner()
    service = DeterministicPlanningService(shot_planner=planner)
    source = build_source_document()
    story_spec = service.build_story_spec(source)

    shot_plans = service.generate_shot_plans(source, story_spec)

    assert len(shot_plans) == 1
    assert shot_plans[0].shot_type is ShotType.MEDIUM
    assert planner.calls == [(source, story_spec.story_id)]
