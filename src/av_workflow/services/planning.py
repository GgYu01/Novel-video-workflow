from __future__ import annotations

import re
from typing import Protocol

from av_workflow.contracts.enums import MotionTier, ShotType
from av_workflow.contracts.models import ShotPlan, ShotPlanSet, SourceDocument, StorySpec
from av_workflow.services.story_bible import DeterministicStoryBibleService


class ShotPlanner(Protocol):
    def build_shots(
        self,
        source_document: SourceDocument,
        story_id: str,
    ) -> list[dict[str, object]]:
        """Return validated shot payloads for the current source document."""


class HeuristicChapterShotPlanner:
    def __init__(self, *, max_shots_per_chapter: int = 3) -> None:
        self.max_shots_per_chapter = max_shots_per_chapter

    def build_shots(self, source_document: SourceDocument, story_id: str) -> list[dict[str, object]]:
        shots: list[dict[str, object]] = []
        global_index = 1

        for chapter in source_document.chapter_documents:
            segments = _segment_chapter_text(chapter["content"])[: self.max_shots_per_chapter]
            if not segments:
                segments = [chapter["title"]]

            for chapter_index, segment in enumerate(segments, start=1):
                shot_id = f"shot-{global_index:03d}"
                global_index += 1
                shots.append(
                    {
                        "shot_id": shot_id,
                        "chapter_id": chapter["chapter_id"],
                        "scene_id": f"scene-{chapter['chapter_id']}",
                        "duration_target": _estimate_duration(segment),
                        "shot_type": ShotType.WIDE if chapter_index == 1 else ShotType.MEDIUM,
                        "camera_instruction": _camera_instruction(chapter_index),
                        "subject_instruction": _subject_instruction(segment),
                        "environment_instruction": _environment_instruction(chapter["title"]),
                        "narration_text": segment,
                        "dialogue_lines": _extract_dialogue_lines(segment),
                        "subtitle_source": "narration",
                        "render_requirements": {"aspect_ratio": "16:9", "style": "cinematic_realism"},
                        "review_targets": {"must_match": _keyword_targets(segment)},
                        "fallback_strategy": {"retry_scope": "shot"},
                    }
                )

        return shots


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
        "欢呼",
        "庆祝",
        "狂欢",
        "人群",
        "追逐",
        "追赶",
        "冲刺",
        "奔跑",
        "狂奔",
        "打斗",
        "爆炸",
        "挥舞",
        "扑向",
    )
    if any(keyword in searchable_text for keyword in dynamic_keywords):
        return MotionTier.WAN_DYNAMIC
    return MotionTier.LIMITED_MOTION


def _segment_chapter_text(content: str) -> list[str]:
    collapsed = " ".join(part.strip() for part in content.splitlines() if part.strip())
    if not collapsed:
        return []
    sentences = [
        sentence.strip()
        for sentence in re.findall(r".+?(?:[。！？!?\.](?=\s|$)|[。！？!?\.])|.+$", collapsed)
        if sentence.strip()
    ]
    return sentences or [collapsed]


def _estimate_duration(segment: str) -> float:
    return max(3.0, min(6.0, round(len(segment) / 28.0, 1)))


def _camera_instruction(index: int) -> str:
    if index == 1:
        return "establish the location with stable cinematic coverage"
    return "hold a steady medium framing on the primary action"


def _subject_instruction(segment: str) -> str:
    return segment[:180]


def _environment_instruction(chapter_title: str) -> str:
    cleaned = chapter_title.split(":", 1)[-1].strip()
    return cleaned or "story location inferred from chapter context"


def _extract_dialogue_lines(segment: str) -> list[str]:
    if ":" not in segment:
        return []
    speaker, text = segment.split(":", 1)
    if not speaker.strip() or not text.strip():
        return []
    return [f"{speaker.strip()}: {text.strip()}"]


def _keyword_targets(segment: str) -> list[str]:
    tokens = re.findall(r"[A-Za-z][A-Za-z'-]+", segment)
    unique_tokens: list[str] = []
    for token in tokens:
        lowered = token.lower()
        if lowered not in unique_tokens:
            unique_tokens.append(lowered)
        if len(unique_tokens) == 4:
            break
    return unique_tokens
