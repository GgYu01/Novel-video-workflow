from __future__ import annotations

from pathlib import Path

from av_workflow.contracts.enums import ShotType
from av_workflow.contracts.models import Job, ShotPlan
from av_workflow.runtime.workspace import RuntimeWorkspace
from av_workflow.services.compose import build_asset_manifest, execute_ffmpeg_compose


class RecordingFfmpegExecutor:
    def __init__(self) -> None:
        self.calls: list[tuple[list[str], Path | None, Path]] = []

    def run(self, args: list[str], *, cwd: Path | None = None, output_path: Path) -> None:
        self.calls.append((args, cwd, output_path))
        output_path.write_bytes(b"fake-video")


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


def test_execute_ffmpeg_compose_materializes_concat_and_output_files(tmp_path: Path) -> None:
    workspace = RuntimeWorkspace(root_dir=tmp_path / "runtime")
    executor = RecordingFfmpegExecutor()
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
        subtitle_refs=["asset://subtitles/final.srt"],
        audio_refs=["asset://audio/narration.wav"],
        audio_mix_ref="asset://audio/final-mix.wav",
        preview_refs=["asset://preview/final.png"],
        cover_refs=["asset://cover/final.png"],
        final_video_ref="asset://video/final.mp4",
    )
    shot_clip_paths = [
        tmp_path / "runtime" / "inputs" / "shot-001.mp4",
        tmp_path / "runtime" / "inputs" / "shot-002.mp4",
    ]
    for path in shot_clip_paths:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"clip")
    primary_audio_path = tmp_path / "runtime" / "inputs" / "final-mix.wav"
    primary_audio_path.parent.mkdir(parents=True, exist_ok=True)
    primary_audio_path.write_bytes(b"audio")

    result = execute_ffmpeg_compose(
        manifest=manifest,
        workspace=workspace,
        ffmpeg_executor=executor,
        shot_clip_paths=shot_clip_paths,
        primary_audio_path=primary_audio_path,
    )

    concat_manifest_path = workspace.compose_dir("job-001") / "job-001-concat.txt"
    final_video_path = workspace.output_dir("job-001") / "final.mp4"
    preview_variant_path = workspace.compose_dir("job-001") / "preview_720p24.mp4"

    assert concat_manifest_path.read_text(encoding="utf-8") == (
        f"file '{shot_clip_paths[0]}'\nfile '{shot_clip_paths[1]}'\n"
    )
    assert final_video_path.read_bytes() == b"fake-video"
    assert preview_variant_path.read_bytes() == b"fake-video"
    assert executor.calls
    assert "-f" in executor.calls[0][0]
    assert "concat" in executor.calls[0][0]
    assert result["final_video_ref"] == "asset://video/final.mp4"
    assert result["preview_variant_ref"] == "asset://runtime/jobs/job-001/compose/preview_720p24.mp4"
    assert result["final_video_path"] == final_video_path
