from __future__ import annotations

from av_workflow.adapters.tts import build_tts_request, normalize_tts_result


def test_build_tts_request_preserves_voice_id_and_text() -> None:
    request = build_tts_request(
        request_id="tts-001",
        voice_id="role.zh_male_02",
        text="The stadium exploded in celebration.",
        speaker_role="character-jose",
        speech_rate=0.95,
    )

    assert request.request_id == "tts-001"
    assert request.voice_id == "role.zh_male_02"
    assert request.text == "The stadium exploded in celebration."
    assert request.speech_rate == 0.95


def test_normalize_tts_result_uses_synthesis_duration_as_timeline_source() -> None:
    result = normalize_tts_result(
        {
            "request_id": "tts-001",
            "status": "completed",
            "audio_ref": "asset://audio/tts-001.wav",
            "duration_ms": 1870,
            "speaker_role": "character-jose",
        }
    )

    assert result.audio_ref == "asset://audio/tts-001.wav"
    assert result.duration_ms == 1870
    assert result.status == "completed"

