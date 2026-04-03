from __future__ import annotations

import re

from av_workflow.adapters.tts import TTSAdapter, TTSRequest, build_tts_request, normalize_tts_result
from av_workflow.contracts.models import DialogueTimeline, ShotPlan, SourceDocument, StorySpec, VoiceCast


class DeterministicAudioTimelineService:
    def __init__(self, *, tts_adapter: TTSAdapter | None = None) -> None:
        self.tts_adapter = tts_adapter

    def build_voice_cast(
        self,
        *,
        source_document: SourceDocument,
        story_spec: StorySpec,
    ) -> VoiceCast:
        narrator_voice_id = "narrator.zh_default"
        character_voice_map: dict[str, str] = {}
        voice_traits: dict[str, dict[str, object]] = {}

        for index, character in enumerate(story_spec.character_registry, start=1):
            character_id = str(character["character_id"])
            character_voice_map[character_id] = f"role.zh_{index:02d}"
            voice_traits[character_id] = {
                "speech_rate": 1.0,
                "pitch_bias": -index,
            }

        return VoiceCast(
            voice_cast_id=f"voice-cast-{source_document.source_document_id}",
            story_id=story_spec.story_id,
            narrator_voice_id=narrator_voice_id,
            character_voice_map=character_voice_map,
            voice_traits=voice_traits,
        )

    def build_timeline(self, *, shot_plan: ShotPlan, voice_cast: VoiceCast) -> DialogueTimeline:
        segments: list[dict[str, object]] = []
        cursor_ms = 0

        if shot_plan.narration_text.strip():
            narration_request = build_tts_request(
                request_id=f"tts-{shot_plan.shot_id}-narration",
                voice_id=voice_cast.narrator_voice_id,
                text=shot_plan.narration_text,
                speaker_role="narrator",
                speech_rate=1.0,
            )
            narration_result = self._synthesize(narration_request, speaker_role="narrator")
            segments.append(
                self._build_segment("narration", shot_plan.narration_text, cursor_ms, narration_result)
            )
            cursor_ms += narration_result.duration_ms

        for index, line in enumerate(shot_plan.dialogue_lines, start=1):
            speaker_role, dialogue_text = _split_dialogue_line(line)
            voice_id = self._resolve_voice_id(voice_cast, speaker_role)
            request = build_tts_request(
                request_id=f"tts-{shot_plan.shot_id}-dialogue-{index:02d}",
                voice_id=voice_id,
                text=dialogue_text,
                speaker_role=speaker_role,
                speech_rate=self._resolve_speech_rate(voice_cast, speaker_role),
            )
            result = self._synthesize(request, speaker_role=speaker_role)
            segments.append(self._build_segment(speaker_role, dialogue_text, cursor_ms, result))
            cursor_ms += result.duration_ms

        return DialogueTimeline(
            dialogue_timeline_id=f"timeline-{shot_plan.shot_id}",
            shot_id=shot_plan.shot_id,
            segments=segments,
            total_duration_ms=cursor_ms,
        )

    def _synthesize(self, request: TTSRequest, *, speaker_role: str):
        if self.tts_adapter is not None:
            payload = self.tts_adapter.submit(request)
            payload.setdefault("speaker_role", speaker_role)
            return normalize_tts_result(payload)

        duration_ms = max(600, int(len(request.text) * 55 / max(request.speech_rate, 0.5)))
        payload = {
            "request_id": request.request_id,
            "status": "completed",
            "audio_ref": f"asset://audio/{request.request_id}.wav",
            "duration_ms": duration_ms,
            "speaker_role": speaker_role,
        }
        return normalize_tts_result(payload)

    def _build_segment(self, speaker: str, text: str, start_ms: int, result) -> dict[str, object]:
        segment: dict[str, object] = {
            "segment_id": result.request_id,
            "speaker": speaker,
            "text": text,
            "start_ms": start_ms,
            "end_ms": start_ms + result.duration_ms,
            "audio_ref": result.audio_ref,
        }
        if result.audio_path:
            segment["audio_path"] = result.audio_path
        return segment

    def _resolve_voice_id(self, voice_cast: VoiceCast, speaker_role: str) -> str:
        return voice_cast.character_voice_map.get(speaker_role, voice_cast.narrator_voice_id)

    def _resolve_speech_rate(self, voice_cast: VoiceCast, speaker_role: str) -> float:
        trait = voice_cast.voice_traits.get(speaker_role, {})
        value = trait.get("speech_rate", 1.0)
        return float(value)


def _split_dialogue_line(line: str) -> tuple[str, str]:
    if ":" not in line:
        return "unknown", line
    speaker, text = line.split(":", 1)
    return _slug_to_role(speaker.strip()), text.strip()


def _slug_to_role(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return f"character-{slug}" if slug else "character-unknown"
