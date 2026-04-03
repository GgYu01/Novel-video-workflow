from __future__ import annotations

import math
import wave
from pathlib import Path
from typing import Any, Protocol

from av_workflow.runtime.workspace import RuntimeWorkspace


class TTSAdapter(Protocol):
    def submit(self, request: "TTSRequest") -> dict[str, Any]:
        """Submit a text-to-speech request and return provider-normalized data."""


class DeterministicLocalTTSAdapter:
    def __init__(
        self,
        *,
        workspace: RuntimeWorkspace,
        job_id: str,
        sample_rate: int = 24000,
    ) -> None:
        self.workspace = workspace
        self.job_id = job_id
        self.sample_rate = sample_rate

    def submit(self, request: "TTSRequest") -> dict[str, Any]:
        audio_dir = self.workspace.audio_dir(self.job_id)
        audio_dir.mkdir(parents=True, exist_ok=True)
        audio_path = audio_dir / f"{request.request_id}.wav"
        duration_ms = max(600, int(len(request.text) * 55 / max(request.speech_rate, 0.5)))
        frame_count = max(1, int(self.sample_rate * duration_ms / 1000))
        with wave.open(str(audio_path), "wb") as handle:
            handle.setnchannels(1)
            handle.setsampwidth(2)
            handle.setframerate(self.sample_rate)
            samples = bytearray()
            for index in range(frame_count):
                amplitude = int(1800 * math.sin(2 * math.pi * 220 * (index / self.sample_rate)))
                samples.extend(amplitude.to_bytes(2, byteorder="little", signed=True))
            handle.writeframes(bytes(samples))
        return {
            "request_id": request.request_id,
            "status": "completed",
            "audio_ref": self.workspace.asset_ref(self.job_id, "audio", f"{request.request_id}.wav"),
            "audio_path": str(audio_path.resolve()),
            "duration_ms": duration_ms,
            "speaker_role": request.speaker_role,
        }


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
        audio_path: str | None,
        duration_ms: int,
        speaker_role: str,
    ) -> None:
        self.request_id = request_id
        self.status = status
        self.audio_ref = audio_ref
        self.audio_path = audio_path
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
        audio_path=payload.get("audio_path"),
        duration_ms=int(payload.get("duration_ms", 0)),
        speaker_role=str(payload.get("speaker_role", "narrator")),
    )
