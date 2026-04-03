from __future__ import annotations

import re
from collections import Counter

from av_workflow.contracts.models import CharacterBible, SceneBible, SourceDocument

_TITLECASE_PHRASE_PATTERN = re.compile(r"\b[A-Z][a-z]+(?: [A-Z][a-z]+)+\b")
_LOCATION_MARKERS = {
    "stadium",
    "office",
    "harbor",
    "square",
    "station",
    "field",
    "room",
    "club",
}


class DeterministicStoryBibleService:
    def build_character_bibles(self, source_document: SourceDocument) -> list[CharacterBible]:
        counter: Counter[str] = Counter()

        for chapter in source_document.chapter_documents:
            for phrase in _extract_titlecase_phrases(chapter["content"]):
                if _looks_like_location(phrase):
                    continue
                counter[phrase] += 1

        ordered_names = sorted(counter.items(), key=lambda item: (-item[1], item[0]))
        return [
            CharacterBible(
                character_id=_slugify(name),
                canonical_name=name,
                role="supporting" if index else "primary",
                visual_identity=["grounded cinematic styling", "period-consistent wardrobe"],
                continuity_rules=["keep facial structure and age range stable"],
                voice_hints={
                    "gender_hint": "unknown",
                    "age_hint": "adult",
                    "tone_hint": "grounded_narrative",
                },
            )
            for index, (name, _) in enumerate(ordered_names)
        ]

    def build_scene_bibles(self, source_document: SourceDocument) -> list[SceneBible]:
        scenes: list[SceneBible] = []

        for chapter in source_document.chapter_documents:
            chapter_text = f"{chapter['title']}. {chapter['content']}"
            phrases = _extract_titlecase_phrases(chapter_text)
            location_name = next(
                (phrase for phrase in phrases if _looks_like_location(phrase)),
                _fallback_location_name(chapter["title"]),
            )
            scenes.append(
                SceneBible(
                    scene_id=f"scene-{chapter['chapter_id']}",
                    location_name=location_name,
                    time_of_day=_infer_time_of_day(chapter_text),
                    environment_description=chapter["title"],
                    continuity_requirements=["keep chapter lighting stable"],
                    prop_requirements=["preserve location-defining background elements"],
                )
            )

        return scenes


def _extract_titlecase_phrases(text: str) -> list[str]:
    return _TITLECASE_PHRASE_PATTERN.findall(text)


def _looks_like_location(phrase: str) -> bool:
    lowered = phrase.lower()
    return any(marker in lowered for marker in _LOCATION_MARKERS)


def _fallback_location_name(title: str) -> str:
    cleaned = title.split(":", 1)[-1].strip()
    return cleaned or "Unspecified Location"


def _infer_time_of_day(text: str) -> str:
    lowered = text.lower()
    if "midnight" in lowered or "night" in lowered:
        return "night"
    if "dawn" in lowered or "morning" in lowered:
        return "dawn"
    return "day"


def _slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
