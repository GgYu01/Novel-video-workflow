from __future__ import annotations

from av_workflow.contracts.enums import ShotType
from av_workflow.contracts.models import Job, ShotPlan
from av_workflow.services.compose import assemble_output_package, build_asset_manifest


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


def build_shot_plan() -> ShotPlan:
    return ShotPlan(
        shot_id="shot-001",
        chapter_id="ch-1",
        scene_id="scene-1",
        duration_target=4.0,
        shot_type=ShotType.MEDIUM,
        camera_instruction="steady eye-level framing",
        subject_instruction="traveler steps off the train",
        environment_instruction="foggy station platform",
        narration_text="Dawn rolled across the tracks.",
        dialogue_lines=[],
        subtitle_source="narration",
        render_requirements={"aspect_ratio": "16:9"},
        review_targets={"must_match": ["traveler", "station"]},
        fallback_strategy={"retry_scope": "shot"},
    )


def test_build_asset_manifest_collects_traceable_media_outputs() -> None:
    job = build_job()
    shot_plan = build_shot_plan()

    manifest = build_asset_manifest(
        job=job,
        shot_plans=[shot_plan],
        rendered_shots={
            "shot-001": {
                "clip_ref": "asset://shots/shot-001.mp4",
                "frame_refs": ["asset://frames/shot-001-001.png"],
                "render_metadata": {"content_source": "image_model", "placeholder_mode": None},
            }
        },
        subtitle_refs=["asset://subtitles/final.srt"],
        audio_refs=["asset://audio/narration.wav"],
        audio_mix_ref="asset://audio/final-mix.wav",
        preview_refs=["asset://preview/final.png"],
        cover_refs=["asset://cover/final.png"],
        final_video_ref="asset://video/final.mp4",
    )

    assert manifest.job_id == job.job_id
    assert manifest.shot_assets[0]["shot_id"] == shot_plan.shot_id
    assert manifest.shot_assets[0]["render_metadata"] == {
        "content_source": "image_model",
        "placeholder_mode": None,
    }
    assert manifest.subtitle_refs == ["asset://subtitles/final.srt"]
    assert manifest.primary_audio_ref == "asset://audio/final-mix.wav"
    assert manifest.final_video_ref == "asset://video/final.mp4"


def test_assemble_output_package_uses_manifest_outputs() -> None:
    job = build_job()
    shot_plan = build_shot_plan()
    manifest = build_asset_manifest(
        job=job,
        shot_plans=[shot_plan],
        rendered_shots={
            "shot-001": {
                "clip_ref": "asset://shots/shot-001.mp4",
                "frame_refs": ["asset://frames/shot-001-001.png"],
                "render_metadata": {},
            }
        },
        subtitle_refs=["asset://subtitles/final.srt"],
        audio_refs=["asset://audio/narration.wav"],
        audio_mix_ref="asset://audio/final-mix.wav",
        preview_refs=["asset://preview/final.png"],
        cover_refs=["asset://cover/final.png"],
        final_video_ref="asset://video/final.mp4",
    )

    package = assemble_output_package(
        manifest=manifest,
        review_summary_ref="asset://reviews/technical.json",
    )

    assert package.job_id == job.job_id
    assert package.final_video_ref == manifest.final_video_ref
    assert package.production_manifest_ref == manifest.manifest_ref
    assert package.ready_for_delivery is False


def test_build_asset_manifest_uses_first_audio_ref_when_mix_not_provided() -> None:
    job = build_job()
    shot_plan = build_shot_plan()

    manifest = build_asset_manifest(
        job=job,
        shot_plans=[shot_plan],
        rendered_shots={
            "shot-001": {
                "clip_ref": "asset://shots/shot-001.mp4",
                "frame_refs": ["asset://frames/shot-001-001.png"],
                "render_metadata": {},
            }
        },
        subtitle_refs=["asset://subtitles/final.srt"],
        audio_refs=["asset://audio/narration.wav", "asset://audio/dialogue.wav"],
        preview_refs=["asset://preview/final.png"],
        cover_refs=["asset://cover/final.png"],
        final_video_ref="asset://video/final.mp4",
    )

    assert manifest.primary_audio_ref == "asset://audio/narration.wav"
