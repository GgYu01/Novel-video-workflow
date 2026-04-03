from __future__ import annotations

from av_workflow.contracts.models import AudioMixManifest, Job


def build_audio_mix_manifest(
    *,
    job: Job,
    narration_refs: list[str],
    dialogue_refs: list[str],
    duration_ms: int,
    bgm_ref: str | None = None,
    ambience_refs: list[str] | None = None,
) -> AudioMixManifest:
    return AudioMixManifest(
        audio_mix_manifest_id=f"audio-mix-{job.job_id}-v1",
        job_id=job.job_id,
        mix_ref=f"asset://audio/{job.job_id}/final-mix.wav",
        narration_refs=narration_refs,
        dialogue_refs=dialogue_refs,
        bgm_ref=bgm_ref,
        ambience_refs=list(ambience_refs or []),
        duration_ms=duration_ms,
        mix_strategy={
            "duck_bgm_under_dialogue": True,
            "normalize_dialogue_loudness": True,
            "normalize_final_mix": True,
        },
    )
