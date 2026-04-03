from __future__ import annotations

import wave
from pathlib import Path

from av_workflow.contracts.models import AudioMixManifest, Job


def build_audio_mix_manifest(
    *,
    job: Job,
    narration_refs: list[str],
    dialogue_refs: list[str],
    duration_ms: int,
    bgm_ref: str | None = None,
    ambience_refs: list[str] | None = None,
    mix_ref: str | None = None,
) -> AudioMixManifest:
    return AudioMixManifest(
        audio_mix_manifest_id=f"audio-mix-{job.job_id}-v1",
        job_id=job.job_id,
        mix_ref=mix_ref or f"asset://audio/{job.job_id}/final-mix.wav",
        narration_refs=narration_refs,
        dialogue_refs=dialogue_refs,
        bgm_ref=bgm_ref,
        ambience_refs=list(ambience_refs or []),
        duration_ms=duration_ms,
        mix_strategy={
            "duck_bgm_under_dialogue": bgm_ref is not None,
            "normalize_dialogue_loudness": True,
            "normalize_final_mix": True,
        },
    )


def materialize_audio_mix(
    *,
    output_path: Path,
    source_audio_paths: list[Path],
    target_duration_ms: int | None = None,
    sample_rate: int = 24000,
) -> Path:
    if not source_audio_paths and target_duration_ms is None:
        raise ValueError("At least one source audio path or a target duration is required.")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    params: tuple[int, int, int, str, str] | None = None
    total_frames = 0

    with wave.open(str(output_path), "wb") as sink:
        for audio_path in source_audio_paths:
            with wave.open(str(audio_path), "rb") as source:
                source_params = (
                    source.getnchannels(),
                    source.getsampwidth(),
                    source.getframerate(),
                    source.getcomptype(),
                    source.getcompname(),
                )
                if params is None:
                    params = source_params
                    sink.setnchannels(source_params[0])
                    sink.setsampwidth(source_params[1])
                    sink.setframerate(source_params[2])
                    sink.setcomptype(source_params[3], source_params[4])
                elif source_params != params:
                    raise ValueError("All source audio files must share identical wave parameters.")
                frame_count = source.getnframes()
                sink.writeframes(source.readframes(frame_count))
                total_frames += frame_count

        if params is None:
            params = (1, 2, sample_rate, "NONE", "not compressed")
            sink.setnchannels(params[0])
            sink.setsampwidth(params[1])
            sink.setframerate(params[2])
            sink.setcomptype(params[3], params[4])

        if target_duration_ms is not None:
            target_frames = max(1, int(params[2] * target_duration_ms / 1000))
            if total_frames < target_frames:
                silence_frame = b"\x00" * (params[0] * params[1])
                sink.writeframes(silence_frame * (target_frames - total_frames))

    return output_path
