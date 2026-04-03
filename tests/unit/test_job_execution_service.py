from __future__ import annotations

import wave
from pathlib import Path

from av_workflow.adapters.render import DeterministicLocalRenderAdapter
from av_workflow.adapters.tts import DeterministicLocalTTSAdapter
from av_workflow.contracts.enums import JobStatus, ShotType
from av_workflow.contracts.models import Job, SourceDocument
from av_workflow.runtime.workspace import RuntimeWorkspace
from av_workflow.services.audio_timeline import DeterministicAudioTimelineService
from av_workflow.services.job_execution import DeterministicLocalJobExecutionService
from av_workflow.services.planning import DeterministicPlanningService
from av_workflow.services.render_jobs import DeterministicRenderJobService
from av_workflow.services.story_bible import DeterministicStoryBibleService


class RecordingFfmpegExecutor:
    def __init__(self) -> None:
        self.calls: list[tuple[list[str], Path | None, Path]] = []

    def run(self, args: list[str], *, cwd: Path | None = None, output_path: Path) -> None:
        self.calls.append((args, cwd, output_path))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"fake-video")


class StubShotPlanner:
    def build_shots(self, source_document: SourceDocument, story_id: str) -> list[dict[str, object]]:
        first_chapter = source_document.chapter_documents[0]
        return [
            {
                "shot_id": "shot-001",
                "chapter_id": first_chapter["chapter_id"],
                "scene_id": "scene-1",
                "duration_target": 4.0,
                "shot_type": ShotType.MEDIUM,
                "camera_instruction": "steady eye-level framing",
                "subject_instruction": "coach is thrown into the air by celebrating players",
                "environment_instruction": "packed Saint Moix Stadium",
                "narration_text": "The celebration exploded across the stadium.",
                "dialogue_lines": ["Jose: Now the real work begins."],
                "subtitle_source": "narration",
                "render_requirements": {"aspect_ratio": "16:9"},
                "review_targets": {"must_match": ["coach", "stadium"]},
                "fallback_strategy": {"retry_scope": "shot"},
            }
        ]


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


def test_local_job_execution_service_materializes_runtime_outputs(tmp_path: Path) -> None:
    runtime_root = tmp_path / "runtime"
    workspace = RuntimeWorkspace(root_dir=runtime_root)
    ffmpeg_executor = RecordingFfmpegExecutor()

    render_adapter = DeterministicLocalRenderAdapter(
        workspace=workspace,
        ffmpeg_executor=ffmpeg_executor,
    )
    render_service = DeterministicRenderJobService(render_adapter=render_adapter)
    planning_service = DeterministicPlanningService(
        shot_planner=StubShotPlanner(),
        story_bible_service=DeterministicStoryBibleService(),
    )
    audio_service = DeterministicAudioTimelineService(
        tts_adapter=DeterministicLocalTTSAdapter(workspace=workspace, job_id="job-001")
    )
    execution_service = DeterministicLocalJobExecutionService(
        runtime_root=runtime_root,
        planning_service=planning_service,
        render_job_service=render_service,
        audio_timeline_service=audio_service,
        ffmpeg_executor=ffmpeg_executor,
    )

    result = execution_service.run(
        job=build_job(),
        raw_text=(
            "Chapter 1: Arrival at Saint Moix Stadium\n"
            "Jose Alemany watched Antonio Asensio celebrate at Saint Moix Stadium."
        ),
    )

    assert result.final_job.status is JobStatus.COMPLETED
    assert (runtime_root / "jobs" / "job-001" / "shots" / "shot-001" / "render" / "clip.mp4").is_file()
    assert (runtime_root / "jobs" / "job-001" / "audio" / "tts-shot-001-narration.wav").is_file()
    assert (runtime_root / "jobs" / "job-001" / "audio" / "final-mix.wav").is_file()
    assert (runtime_root / "jobs" / "job-001" / "compose" / "job-001-concat.txt").is_file()
    assert (runtime_root / "jobs" / "job-001" / "output" / "final.mp4").is_file()
    assert (runtime_root / "jobs" / "job-001" / "output" / "output_package.json").is_file()
    assert result.audio_mix_manifest.mix_ref == "asset://runtime/jobs/job-001/audio/final-mix.wav"
    assert result.audio_mix_manifest.duration_ms == 4000
    assert result.asset_manifest.final_video_ref == "asset://runtime/jobs/job-001/output/final.mp4"
    assert result.output_package.final_video_ref == "asset://runtime/jobs/job-001/output/final.mp4"
    assert ffmpeg_executor.calls

    with wave.open(str(runtime_root / "jobs" / "job-001" / "audio" / "final-mix.wav"), "rb") as handle:
        assert handle.getframerate() == 24000
        assert handle.getnframes() == 96000
