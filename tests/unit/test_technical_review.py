from __future__ import annotations

from av_workflow.contracts.enums import ReviewMode, ReviewResult, ShotType
from av_workflow.contracts.models import AssetManifest, Job, ShotPlan
from av_workflow.services.compose import build_asset_manifest
from av_workflow.services.review.technical import evaluate_asset_manifest


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


def build_manifest() -> AssetManifest:
    job = build_job()
    shot_plan = ShotPlan(
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
    return build_asset_manifest(
        job=job,
        shot_plans=[shot_plan],
        rendered_shots={
            "shot-001": {
                "clip_ref": "asset://shots/shot-001.mp4",
                "frame_refs": ["asset://frames/shot-001-001.png"],
            }
        },
        subtitle_refs=["asset://subtitles/final.srt"],
        audio_refs=["asset://audio/narration.wav"],
        preview_refs=["asset://preview/final.png"],
        cover_refs=["asset://cover/final.png"],
        final_video_ref="asset://video/final.mp4",
    )


def test_evaluate_asset_manifest_passes_for_complete_media_metadata() -> None:
    job = build_job()
    manifest = build_manifest()

    review = evaluate_asset_manifest(
        job=job,
        manifest=manifest,
        media_metadata={
            "asset://video/final.mp4": {
                "duration_sec": 4.0,
                "video_streams": [{"width": 1920, "height": 1080}],
                "audio_streams": [{"sample_rate": 48000}],
            }
        },
        subtitle_reports={
            "asset://subtitles/final.srt": {
                "cue_count": 3,
                "max_line_length": 24,
            }
        },
    )

    assert review.review_mode is ReviewMode.TECHNICAL
    assert review.result is ReviewResult.PASS
    assert review.recommended_action == "continue"


def test_evaluate_asset_manifest_fails_when_video_stream_is_missing() -> None:
    job = build_job()
    manifest = build_manifest()

    review = evaluate_asset_manifest(
        job=job,
        manifest=manifest,
        media_metadata={
            "asset://video/final.mp4": {
                "duration_sec": 4.0,
                "video_streams": [],
                "audio_streams": [{"sample_rate": 48000}],
            }
        },
        subtitle_reports={
            "asset://subtitles/final.srt": {
                "cue_count": 3,
                "max_line_length": 24,
            }
        },
    )

    assert review.result is ReviewResult.FAIL
    assert "missing_video_stream" in review.reason_codes
    assert review.recommended_action == "retry_compose"


def test_evaluate_asset_manifest_fails_when_subtitle_line_is_too_long() -> None:
    job = build_job()
    manifest = build_manifest()

    review = evaluate_asset_manifest(
        job=job,
        manifest=manifest,
        media_metadata={
            "asset://video/final.mp4": {
                "duration_sec": 4.0,
                "video_streams": [{"width": 1920, "height": 1080}],
                "audio_streams": [{"sample_rate": 48000}],
            }
        },
        subtitle_reports={
            "asset://subtitles/final.srt": {
                "cue_count": 3,
                "max_line_length": 60,
            }
        },
    )

    assert review.result is ReviewResult.FAIL
    assert "subtitle_line_too_long" in review.reason_codes
