from __future__ import annotations

from pathlib import Path

from av_workflow.adapters.render import DeterministicLocalRenderAdapter, build_render_request
from av_workflow.adapters.tts import DeterministicLocalTTSAdapter, build_tts_request
from av_workflow.contracts.enums import MotionTier, RenderBackend, ShotType
from av_workflow.contracts.models import ShotPlan
from av_workflow.runtime.workspace import RuntimeWorkspace


class RecordingFfmpegExecutor:
    def __init__(self) -> None:
        self.calls: list[tuple[list[str], Path | None, Path]] = []

    def run(self, args: list[str], *, cwd: Path | None = None, output_path: Path) -> None:
        self.calls.append((args, cwd, output_path))
        output_path.write_bytes(b"fake-mp4")


def build_shot_plan() -> ShotPlan:
    return ShotPlan(
        shot_id="shot-001",
        chapter_id="ch-1",
        scene_id="scene-1",
        duration_target=4.5,
        shot_type=ShotType.MEDIUM,
        motion_tier=MotionTier.WAN_DYNAMIC,
        camera_instruction="dynamic crowd coverage",
        subject_instruction="celebrating players throw the coach into the air",
        environment_instruction="packed Saint Moix Stadium",
        narration_text="The celebration exploded across the stadium.",
        dialogue_lines=["Jose: Now the real work begins."],
        subtitle_source="narration",
        render_requirements={"aspect_ratio": "16:9"},
        review_targets={"must_match": ["coach", "stadium"]},
        fallback_strategy={"retry_scope": "shot"},
    )


def test_local_render_adapter_writes_frame_and_clip_files() -> None:
    workspace = RuntimeWorkspace(root_dir=Path("/tmp/runtime-root"))
    executor = RecordingFfmpegExecutor()
    adapter = DeterministicLocalRenderAdapter(workspace=workspace, ffmpeg_executor=executor)
    request = build_render_request(
        job_id="job-001",
        shot_plan=build_shot_plan(),
        backend=RenderBackend.WAN,
    )

    result = adapter.submit(request)

    assert result["status"] == "completed"
    assert result["clip_ref"] == "asset://runtime/jobs/job-001/shots/shot-001/render/clip.mp4"
    assert result["frame_refs"] == ["asset://runtime/jobs/job-001/shots/shot-001/render/frame-001.ppm"]
    assert result["clip_path"] == "/tmp/runtime-root/jobs/job-001/shots/shot-001/render/clip.mp4"
    assert result["frame_paths"] == ["/tmp/runtime-root/jobs/job-001/shots/shot-001/render/frame-001.ppm"]
    assert executor.calls
    assert executor.calls[0][0][0] == "-y"
    assert "-loop" in executor.calls[0][0]
    assert executor.calls[0][2] == Path("/tmp/runtime-root/jobs/job-001/shots/shot-001/render/clip.mp4")
    assert Path("/tmp/runtime-root/jobs/job-001/shots/shot-001/render/frame-001.ppm").read_bytes().startswith(b"P6")
    assert Path("/tmp/runtime-root/jobs/job-001/shots/shot-001/render/clip.mp4").read_bytes() == b"fake-mp4"
    assert result["metadata"]["content_source"] == "deterministic_placeholder"
    assert result["metadata"]["placeholder_mode"] == "solid_color_loop"


def test_local_tts_adapter_writes_wav_file_and_keeps_duration_contract() -> None:
    workspace = RuntimeWorkspace(root_dir=Path("/tmp/runtime-root"))
    adapter = DeterministicLocalTTSAdapter(workspace=workspace, job_id="job-001")
    request = build_tts_request(
        request_id="tts-001",
        voice_id="role.zh_01",
        text="Now the real work begins.",
        speaker_role="character-jose",
        speech_rate=1.0,
    )

    result = adapter.submit(request)

    assert result["status"] == "completed"
    assert result["audio_ref"] == "asset://runtime/jobs/job-001/audio/tts-001.wav"
    assert result["audio_path"] == "/tmp/runtime-root/jobs/job-001/audio/tts-001.wav"
    assert result["duration_ms"] > 0
    assert Path("/tmp/runtime-root/jobs/job-001/audio/tts-001.wav").read_bytes().startswith(b"RIFF")
