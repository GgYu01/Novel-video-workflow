from __future__ import annotations

from av_workflow.contracts.enums import ShotType
from av_workflow.contracts.models import Job, ShotPlan
from av_workflow.services.compose import build_asset_manifest, build_ffmpeg_compose_plan


def build_job() -> Job:
    return Job(
        job_id="job-001",
        input_mode="upload",
        source_ref="asset://source.txt",
        output_preset="preview_720p24",
        profile_id="internal-prod",
        language="zh-CN",
        review_level="strict",
    )


def build_shot_plan(shot_id: str) -> ShotPlan:
    return ShotPlan(
        shot_id=shot_id,
        chapter_id="ch-1",
        scene_id="scene-1",
        duration_target=4.0,
        shot_type=ShotType.MEDIUM,
        camera_instruction="steady eye-level framing",
        subject_instruction=f"subject for {shot_id}",
        environment_instruction="foggy station platform",
        narration_text="Dawn rolled across the tracks.",
        dialogue_lines=[],
        subtitle_source="narration",
        render_requirements={"aspect_ratio": "16:9"},
        review_targets={"must_match": ["traveler", "station"]},
        fallback_strategy={"retry_scope": "shot"},
    )


def test_build_ffmpeg_compose_plan_tracks_concat_and_preview_outputs() -> None:
    manifest = build_asset_manifest(
        job=build_job(),
        shot_plans=[build_shot_plan("shot-001"), build_shot_plan("shot-002")],
        rendered_shots={
            "shot-001": {
                "clip_ref": "asset://shots/shot-001.mp4",
                "frame_refs": ["asset://frames/shot-001-001.png"],
            },
            "shot-002": {
                "clip_ref": "asset://shots/shot-002.mp4",
                "frame_refs": ["asset://frames/shot-002-001.png"],
            },
        },
        subtitle_refs=["asset://subtitles/final.srt", "asset://subtitles/final.ass"],
        audio_refs=["asset://audio/narration.wav"],
        audio_mix_ref="asset://audio/final-mix.wav",
        preview_refs=["asset://preview/final.png"],
        cover_refs=["asset://cover/final.png"],
        final_video_ref="asset://video/final.mp4",
    )

    plan = build_ffmpeg_compose_plan(
        manifest=manifest,
        output_variant="preview_720p24",
        working_directory="/tmp/compose",
    )

    assert plan["concat_manifest_ref"] == "/tmp/compose/job-001-concat.txt"
    assert "asset://shots/shot-001.mp4" in plan["concat_manifest_text"]
    assert "asset://shots/shot-002.mp4" in plan["concat_manifest_text"]
    assert plan["primary_audio_ref"] == "asset://audio/final-mix.wav"
    assert plan["preview_variant_ref"] == "asset://compose/job-001-preview_720p24.mp4"
