from __future__ import annotations

from typing import Protocol

from av_workflow.contracts.enums import MotionTier
from av_workflow.contracts.models import ShotPlan, ShotPlanSet, SourceDocument, StorySpec
from av_workflow.services.story_bible import DeterministicStoryBibleService


class ShotPlanner(Protocol):
    def build_shots(
        self,
        source_document: SourceDocument,
        story_id: str,
    ) -> list[dict[str, object]]:
        """Return validated shot payloads for the current source document."""


class DeterministicPlanningService:
    def __init__(
        self,
        *,
        shot_planner: ShotPlanner,
        story_bible_service: DeterministicStoryBibleService | None = None,
    ) -> None:
        self.shot_planner = shot_planner
        self.story_bible_service = story_bible_service or DeterministicStoryBibleService()

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
        character_bibles = self.story_bible_service.build_character_bibles(source_document)
        scene_bibles = self.story_bible_service.build_scene_bibles(source_document)

        return StorySpec(
            story_id=source_document.source_document_id,
            chapter_specs=chapter_specs,
            character_registry=[
                {
                    "character_id": character.character_id,
                    "canonical_name": character.canonical_name,
                    "role": character.role,
                }
                for character in character_bibles
            ],
            location_registry=[
                {
                    "scene_id": scene.scene_id,
                    "location_name": scene.location_name,
                    "time_of_day": scene.time_of_day,
                }
                for scene in scene_bibles
            ],
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
        validated_shots: list[ShotPlan] = []

        for raw_shot in raw_shots:
            normalized_shot = dict(raw_shot)
            normalized_shot.setdefault("motion_tier", _infer_motion_tier(normalized_shot))
            validated_shots.append(ShotPlan.model_validate(normalized_shot))

        return validated_shots

    def generate_shot_plan_set(
        self,
        *,
        source_document: SourceDocument,
        story_spec: StorySpec,
        output_preset: str,
    ) -> ShotPlanSet:
        shot_plans = self.generate_shot_plans(source_document, story_spec)
        chapter_id = shot_plans[0].chapter_id if shot_plans else source_document.chapter_documents[0]["chapter_id"]

        return ShotPlanSet(
            shot_plan_set_id=f"shot-plan-{chapter_id}-v1",
            story_id=story_spec.story_id,
            chapter_id=chapter_id,
            default_output_preset=output_preset,
            shots=shot_plans,
        )


def _summarize_chapter(content: str) -> str:
    stripped = content.strip()
    if not stripped:
        return "No chapter summary available."
    first_line = stripped.splitlines()[0]
    return first_line[:160]


def _infer_motion_tier(raw_shot: dict[str, object]) -> MotionTier:
    searchable_parts = [
        str(raw_shot.get("subject_instruction", "")),
        str(raw_shot.get("narration_text", "")),
        str(raw_shot.get("environment_instruction", "")),
    ]
    searchable_text = " ".join(searchable_parts).lower()
    dynamic_keywords = (
        "throws",
        "thrown",
        "celebration",
        "crowd",
        "fight",
        "chase",
        "running",
        "surge",
        "explosion",
    )
    if any(keyword in searchable_text for keyword in dynamic_keywords):
        return MotionTier.WAN_DYNAMIC
    return MotionTier.LIMITED_MOTION
