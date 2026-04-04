from __future__ import annotations

import shutil
from pathlib import Path

from av_workflow.contracts.models import AssetManifest, Job, OutputPackage, ShotPlan
from av_workflow.runtime.ffmpeg import FfmpegExecutor
from av_workflow.runtime.workspace import RuntimeWorkspace


def build_asset_manifest(
    *,
    job: Job,
    shot_plans: list[ShotPlan],
    rendered_shots: dict[str, dict[str, object]],
    subtitle_refs: list[str],
    audio_refs: list[str],
    audio_mix_ref: str | None = None,
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
                "render_metadata": dict(rendered.get("render_metadata", {})),
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
        primary_audio_ref=audio_mix_ref or (audio_refs[0] if audio_refs else None),
        preview_refs=preview_refs,
        cover_refs=cover_refs,
        final_video_ref=final_video_ref,
        manifest_metadata={
            "shot_count": len(shot_assets),
            "duration_sec": total_duration,
            "subtitle_count": len(subtitle_refs),
            "audio_count": len(audio_refs),
            "primary_audio_ref": audio_mix_ref or (audio_refs[0] if audio_refs else None),
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


def build_ffmpeg_compose_plan(
    *,
    manifest: AssetManifest,
    output_variant: str,
    working_directory: str,
) -> dict[str, object]:
    concat_manifest_ref = f"{working_directory}/{manifest.job_id}-concat.txt"
    concat_manifest_text = "\n".join(
        f"file '{shot_asset['clip_ref']}'" for shot_asset in manifest.shot_assets
    )
    preview_variant_ref = f"asset://runtime/jobs/{manifest.job_id}/compose/{output_variant}.mp4"

    return {
        "concat_manifest_ref": concat_manifest_ref,
        "concat_manifest_text": concat_manifest_text,
        "subtitle_package_refs": list(manifest.subtitle_refs),
        "primary_audio_ref": manifest.primary_audio_ref,
        "preview_variant_ref": preview_variant_ref,
    }


def execute_ffmpeg_compose(
    *,
    manifest: AssetManifest,
    workspace: RuntimeWorkspace,
    ffmpeg_executor: FfmpegExecutor,
    shot_clip_paths: list[Path],
    primary_audio_path: Path | None = None,
    output_variant: str = "preview_720p24",
) -> dict[str, object]:
    if len(shot_clip_paths) != len(manifest.shot_assets):
        raise ValueError("Shot clip paths must match the manifest shot count")

    workspace.ensure_job_tree(manifest.job_id)
    concat_manifest_path = workspace.compose_dir(manifest.job_id) / f"{manifest.job_id}-concat.txt"
    concat_manifest_path.parent.mkdir(parents=True, exist_ok=True)
    concat_manifest_text = "\n".join(f"file '{path}'" for path in shot_clip_paths) + "\n"
    concat_manifest_path.write_text(concat_manifest_text, encoding="utf-8")

    final_video_path = workspace.output_dir(manifest.job_id) / "final.mp4"
    final_video_path.parent.mkdir(parents=True, exist_ok=True)

    ffmpeg_args = [
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(concat_manifest_path),
    ]
    if primary_audio_path is not None:
        ffmpeg_args.extend(
            [
                "-i",
                str(primary_audio_path),
                "-c:v",
                "libx264",
                "-c:a",
                "aac",
                "-shortest",
            ]
        )
    else:
        ffmpeg_args.extend(["-c:v", "libx264", "-pix_fmt", "yuv420p"])
    ffmpeg_args.append(str(final_video_path))

    ffmpeg_executor.run(ffmpeg_args, cwd=workspace.root_dir, output_path=final_video_path)

    preview_variant_path = workspace.compose_dir(manifest.job_id) / f"{output_variant}.mp4"
    if preview_variant_path != final_video_path:
        shutil.copyfile(final_video_path, preview_variant_path)

    return {
        "concat_manifest_path": concat_manifest_path,
        "concat_manifest_text": concat_manifest_text,
        "final_video_path": final_video_path,
        "final_video_ref": manifest.final_video_ref,
        "preview_variant_path": preview_variant_path,
        "preview_variant_ref": f"asset://runtime/jobs/{manifest.job_id}/compose/{output_variant}.mp4",
        "primary_audio_path": primary_audio_path,
    }
