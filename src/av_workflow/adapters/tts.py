from __future__ import annotations

from typing import Any, Protocol


class TTSAdapter(Protocol):
    def submit(self, request: "TTSRequest") -> dict[str, Any]:
        """Submit a text-to-speech request and return provider-normalized data."""


class TTSRequest:
    def __init__(
        self,
        *,
        request_id: str,
        voice_id: str,
        text: str,
        speaker_role: str,
        speech_rate: float,
    ) -> None:
        self.request_id = request_id
        self.voice_id = voice_id
        self.text = text
        self.speaker_role = speaker_role
        self.speech_rate = speech_rate


class TTSResult:
    def __init__(
        self,
        *,
        request_id: str,
        status: str,
        audio_ref: str | None,
        duration_ms: int,
        speaker_role: str,
    ) -> None:
        self.request_id = request_id
        self.status = status
        self.audio_ref = audio_ref
        self.duration_ms = duration_ms
        self.speaker_role = speaker_role


def build_tts_request(
    *,
    request_id: str,
    voice_id: str,
    text: str,
    speaker_role: str,
    speech_rate: float,
) -> TTSRequest:
    return TTSRequest(
        request_id=request_id,
        voice_id=voice_id,
        text=text,
        speaker_role=speaker_role,
        speech_rate=speech_rate,
    )


def normalize_tts_result(payload: dict[str, Any]) -> TTSResult:
    return TTSResult(
        request_id=str(payload["request_id"]),
        status=str(payload.get("status", "failed")).lower(),
        audio_ref=payload.get("audio_ref"),
        duration_ms=int(payload.get("duration_ms", 0)),
        speaker_role=str(payload.get("speaker_role", "narrator")),
    )

