from __future__ import annotations

from av_workflow.contracts.models import AssetManifest, Job, OutputPackage, ShotPlan


def build_asset_manifest(
    *,
    job: Job,
    shot_plans: list[ShotPlan],
    rendered_shots: dict[str, dict[str, object]],
    subtitle_refs: list[str],
    audio_refs: list[str],
    preview_refs: list[str],
    cover_refs: list[str],
    final_video_ref: str,
) -> AssetManifest:
    shot_assets: list[dict[str, object]] = []
    total_duration = 0.0

    for shot_plan in shot_plans:
        rendered = rendered_shots.get(shot_plan.shot_id)
        if rendered is None:
            raise ValueError(f"Missing rendered output for shot: {shot_plan.shot_id}")
        shot_assets.append(
            {
                "shot_id": shot_plan.shot_id,
                "chapter_id": shot_plan.chapter_id,
                "scene_id": shot_plan.scene_id,
                "clip_ref": rendered["clip_ref"],
                "frame_refs": list(rendered.get("frame_refs", [])),
            }
        )
        total_duration += shot_plan.duration_target

    return AssetManifest(
        asset_manifest_id=f"manifest-{job.job_id}-v1",
        job_id=job.job_id,
        manifest_ref=f"asset://manifests/{job.job_id}.json",
        shot_assets=shot_assets,
        subtitle_refs=subtitle_refs,
        audio_refs=audio_refs,
        preview_refs=preview_refs,
        cover_refs=cover_refs,
        final_video_ref=final_video_ref,
        manifest_metadata={
            "shot_count": len(shot_assets),
            "duration_sec": total_duration,
            "subtitle_count": len(subtitle_refs),
            "audio_count": len(audio_refs),
            "preview_count": len(preview_refs),
            "cover_count": len(cover_refs),
        },
    )


def assemble_output_package(
    *,
    manifest: AssetManifest,
    review_summary_ref: str,
) -> OutputPackage:
    return OutputPackage(
        output_package_id=f"output-{manifest.job_id}-v1",
        job_id=manifest.job_id,
        final_video_ref=manifest.final_video_ref,
        subtitle_refs=manifest.subtitle_refs,
        cover_refs=manifest.cover_refs,
        preview_refs=manifest.preview_refs,
        review_summary_ref=review_summary_ref,
        production_manifest_ref=manifest.manifest_ref,
        ready_for_delivery=False,
        version=manifest.version,
    )
