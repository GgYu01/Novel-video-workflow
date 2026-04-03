from __future__ import annotations

import wave
from pathlib import Path

from av_workflow.contracts.models import Job
from av_workflow.services.audio_mix import build_audio_mix_manifest, materialize_audio_mix


def build_job() -> Job:
    return Job(
        job_id="job-001",
        input_mode="upload",
        source_ref="asset://source.txt",
        output_preset="short-story",
        profile_id="internal-prod",
        language="zh-CN",
        review_level="strict",
    )


def test_build_audio_mix_manifest_tracks_narration_dialogue_and_bgm() -> None:
    job = build_job()

    mix_manifest = build_audio_mix_manifest(
        job=job,
        narration_refs=["asset://audio/narration-seg-001.wav"],
        dialogue_refs=[
            "asset://audio/dialogue-jose-001.wav",
            "asset://audio/dialogue-antonio-001.wav",
        ],
        bgm_ref="asset://audio/bgm-main.wav",
        ambience_refs=["asset://audio/crowd-loop.wav"],
        duration_ms=4300,
    )

    assert mix_manifest.job_id == job.job_id
    assert mix_manifest.mix_ref == "asset://audio/job-001/final-mix.wav"
    assert mix_manifest.dialogue_refs[1] == "asset://audio/dialogue-antonio-001.wav"
    assert mix_manifest.duration_ms == 4300
    assert mix_manifest.mix_strategy["duck_bgm_under_dialogue"] is True


def test_build_audio_mix_manifest_disables_ducking_without_bgm() -> None:
    job = build_job()

    mix_manifest = build_audio_mix_manifest(
        job=job,
        narration_refs=["asset://audio/narration-seg-001.wav"],
        dialogue_refs=["asset://audio/dialogue-jose-001.wav"],
        bgm_ref=None,
        ambience_refs=[],
        duration_ms=1800,
    )

    assert mix_manifest.mix_strategy["duck_bgm_under_dialogue"] is False
    assert mix_manifest.bgm_ref is None


def test_materialize_audio_mix_concatenates_source_wavs(tmp_path: Path) -> None:
    first = tmp_path / "tts-001.wav"
    second = tmp_path / "tts-002.wav"
    output = tmp_path / "final-mix.wav"

    _write_test_wav(first, frame_count=240)
    _write_test_wav(second, frame_count=360)

    result_path = materialize_audio_mix(output_path=output, source_audio_paths=[first, second])

    assert result_path == output
    with wave.open(str(output), "rb") as handle:
        assert handle.getframerate() == 24000
        assert handle.getnchannels() == 1
        assert handle.getnframes() == 600


def test_materialize_audio_mix_pads_silence_to_target_duration(tmp_path: Path) -> None:
    source = tmp_path / "tts-001.wav"
    output = tmp_path / "final-mix.wav"

    _write_test_wav(source, frame_count=240)

    materialize_audio_mix(
        output_path=output,
        source_audio_paths=[source],
        target_duration_ms=50,
    )

    with wave.open(str(output), "rb") as handle:
        assert handle.getframerate() == 24000
        assert handle.getnframes() == 1200


def _write_test_wav(path: Path, *, frame_count: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(24000)
        handle.writeframes(b"\x00\x00" * frame_count)
