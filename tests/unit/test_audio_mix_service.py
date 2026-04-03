from __future__ import annotations

from av_workflow.contracts.models import Job
from av_workflow.services.audio_mix import build_audio_mix_manifest


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
