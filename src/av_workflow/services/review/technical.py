from __future__ import annotations

from typing import Any

from av_workflow.contracts.enums import ReviewMode, ReviewResult
from av_workflow.contracts.models import AssetManifest, Job, ReviewCase

_MAX_SUBTITLE_LINE_LENGTH = 42


def evaluate_asset_manifest(
    *,
    job: Job,
    manifest: AssetManifest,
    media_metadata: dict[str, dict[str, Any]],
    subtitle_reports: dict[str, dict[str, Any]],
) -> ReviewCase:
    reason_codes: list[str] = []

    final_video_metadata = media_metadata.get(manifest.final_video_ref)
    if final_video_metadata is None:
        reason_codes.append("missing_media_metadata")
    else:
        duration_sec = float(final_video_metadata.get("duration_sec", 0.0))
        if duration_sec <= 0:
            reason_codes.append("invalid_duration")
        video_streams = list(final_video_metadata.get("video_streams", []))
        if not video_streams:
            reason_codes.append("missing_video_stream")
        if manifest.audio_refs and not list(final_video_metadata.get("audio_streams", [])):
            reason_codes.append("missing_audio_stream")

    if not manifest.subtitle_refs:
        reason_codes.append("missing_subtitles")

    for subtitle_ref in manifest.subtitle_refs:
        subtitle_report = subtitle_reports.get(subtitle_ref)
        if subtitle_report is None:
            reason_codes.append("missing_subtitle_report")
            continue
        cue_count = int(subtitle_report.get("cue_count", 0))
        max_line_length = int(subtitle_report.get("max_line_length", 0))
        if cue_count <= 0:
            reason_codes.append("empty_subtitles")
        if max_line_length > _MAX_SUBTITLE_LINE_LENGTH:
            reason_codes.append("subtitle_line_too_long")

    is_pass = not reason_codes
    result = ReviewResult.PASS if is_pass else ReviewResult.FAIL
    recommended_action = "continue" if is_pass else "retry_compose"
    reason_text = (
        "Technical quality checks passed."
        if is_pass
        else f"Technical quality checks failed: {', '.join(sorted(set(reason_codes)))}."
    )

    return ReviewCase(
        review_case_id=f"review-{job.job_id}-technical-v1",
        target_type="asset_manifest",
        target_ref=manifest.manifest_ref,
        review_mode=ReviewMode.TECHNICAL,
        input_assets=[manifest.final_video_ref, *manifest.subtitle_refs],
        evaluation_prompt_ref="system://technical-review/v1",
        result=result,
        score=1.0 if is_pass else 0.0,
        reason_codes=sorted(set(reason_codes)),
        reason_text=reason_text,
        fix_hint=None if is_pass else "Rebuild composition outputs and rerun technical QA.",
        recommended_action=recommended_action,
        review_provider="local-technical-qa",
        provider_version="v1",
        latency_ms=0,
        raw_response_ref=f"raw://technical/{job.job_id}.json",
    )
