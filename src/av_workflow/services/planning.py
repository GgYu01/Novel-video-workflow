from __future__ import annotations

from typing import Protocol

from av_workflow.contracts.models import ShotPlan, SourceDocument, StorySpec


class ShotPlanner(Protocol):
    def build_shots(
        self,
        source_document: SourceDocument,
        story_id: str,
    ) -> list[dict[str, object]]:
        """Return validated shot payloads for the current source document."""


class DeterministicPlanningService:
    def __init__(self, *, shot_planner: ShotPlanner) -> None:
        self.shot_planner = shot_planner

    def build_story_spec(self, source_document: SourceDocument) -> StorySpec:
        chapter_specs = [
            {
                "chapter_id": chapter["chapter_id"],
                "title": chapter["title"],
                "summary": _summarize_chapter(chapter["content"]),
            }
            for chapter in source_document.chapter_documents
        ]
        chapter_total = len(chapter_specs)

        return StorySpec(
            story_id=source_document.source_document_id,
            chapter_specs=chapter_specs,
            character_registry=[],
            location_registry=[],
            timeline_summary=f"{chapter_total} chapter(s) extracted from normalized source.",
            tone_profile="grounded",
            visual_style_profile="cinematic realism",
            consistency_rules=[
                "Keep primary subjects visually consistent across adjacent shots."
            ],
            spec_validation_result="validated",
            approved_for_planning=True,
        )

    def generate_shot_plans(
        self,
        source_document: SourceDocument,
        story_spec: StorySpec,
    ) -> list[ShotPlan]:
        raw_shots = self.shot_planner.build_shots(source_document, story_spec.story_id)
        return [ShotPlan.model_validate(raw_shot) for raw_shot in raw_shots]


def _summarize_chapter(content: str) -> str:
    stripped = content.strip()
    if not stripped:
        return "No chapter summary available."
    first_line = stripped.splitlines()[0]
    return first_line[:160]
