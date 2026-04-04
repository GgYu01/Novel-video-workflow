from __future__ import annotations

import wave
from pathlib import Path

from av_workflow.adapters.render import DeterministicLocalRenderAdapter
from av_workflow.adapters.tts import DeterministicLocalTTSAdapter
from av_workflow.contracts.enums import JobStatus, ReviewMode, ReviewResult, ShotType
from av_workflow.contracts.models import AssetManifest, Job, ReviewCase, ShotPlanSet, SourceDocument
from av_workflow.runtime.workspace import RuntimeWorkspace
from av_workflow.services.audio_timeline import DeterministicAudioTimelineService
from av_workflow.services.job_execution import DeterministicLocalJobExecutionService
from av_workflow.services.planning import DeterministicPlanningService
from av_workflow.services.render_jobs import DeterministicRenderJobService
from av_workflow.services.story_bible import DeterministicStoryBibleService
from av_workflow.workflow.stage_runner import SemanticReviewService


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


class StaticShotPlanner:
    def build_shots(self, source_document: SourceDocument, story_id: str) -> list[dict[str, object]]:
        first_chapter = source_document.chapter_documents[0]
        return [
            {
                "shot_id": "shot-001",
                "chapter_id": first_chapter["chapter_id"],
                "scene_id": "scene-1",
                "duration_target": 3.0,
                "shot_type": ShotType.MEDIUM,
                "camera_instruction": "steady eye-level framing",
                "subject_instruction": "Jose Alemany studies the empty stadium box",
                "environment_instruction": "quiet Saint Moix Stadium box",
                "narration_text": "Jose studied the empty stadium box.",
                "dialogue_lines": [],
                "subtitle_source": "narration",
                "render_requirements": {"aspect_ratio": "16:9"},
                "review_targets": {"must_match": ["jose", "stadium"]},
                "fallback_strategy": {"retry_scope": "shot"},
            }
        ]


class PngRenderAdapter:
    def __init__(self, workspace: RuntimeWorkspace) -> None:
        self.workspace = workspace

    def submit(self, render_request) -> dict[str, object]:
        render_dir = self.workspace.shot_root(render_request.job_id, render_request.shot_id) / "render"
        render_dir.mkdir(parents=True, exist_ok=True)
        frame_path = render_dir / "frame-001.png"
        clip_path = render_dir / "clip.mp4"
        frame_path.write_bytes(b"fake-png")
        clip_path.write_bytes(b"fake-clip")
        return {
            "render_job_id": render_request.render_job_id,
            "shot_id": render_request.shot_id,
            "status": "completed",
            "clip_ref": self.workspace.asset_ref(
                render_request.job_id,
                "shots",
                render_request.shot_id,
                "render",
                "clip.mp4",
            ),
            "frame_refs": [
                self.workspace.asset_ref(
                    render_request.job_id,
                    "shots",
                    render_request.shot_id,
                    "render",
                    "frame-001.png",
                )
            ],
            "clip_path": str(clip_path),
            "frame_paths": [str(frame_path)],
            "metadata": {
                "duration_sec": render_request.requested_duration_sec,
                "fps": 24,
                "output_size": [640, 384],
                "backend": render_request.backend.value,
                "content_source": "image_model",
                "placeholder_mode": None,
                "frame_count": 1,
            },
        }


class PassingSemanticReviewService(SemanticReviewService):
    def evaluate(
        self,
        *,
        job: Job,
        manifest: AssetManifest,
        shot_plan_set: ShotPlanSet,
        frame_path_map=None,
    ) -> ReviewCase:
        return ReviewCase(
            review_case_id=f"review-{job.job_id}-semantic-pass",
            target_type="asset_manifest",
            target_ref=manifest.manifest_ref,
            review_mode=ReviewMode.SEMANTIC_IMAGE,
            input_assets=[*manifest.preview_refs, *manifest.cover_refs],
            evaluation_prompt_ref="prompt://review/semantic-default",
            result=ReviewResult.PASS,
            score=0.95,
            reason_codes=["semantic_alignment_ok"],
            reason_text="Semantic review passed.",
            fix_hint=None,
            recommended_action="continue",
            review_provider="semantic-stub",
            provider_version="test",
            latency_ms=9,
            raw_response_ref=f"raw://semantic-review/{job.job_id}.json",
        )


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

    assert result.final_job.status is JobStatus.MANUAL_HOLD
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
    assert result.review_case.result is ReviewResult.FAIL
    assert "placeholder_render_output" in result.review_case.reason_codes

    with wave.open(str(runtime_root / "jobs" / "job-001" / "audio" / "final-mix.wav"), "rb") as handle:
        assert handle.getframerate() == 24000
        assert handle.getnframes() == 96000


def test_local_job_execution_service_clears_stale_runtime_tree_before_run(tmp_path: Path) -> None:
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

    stale_subtitle = workspace.write_text_artifact("job-001", "subtitles/stale.srt", "stale")
    stale_render = workspace.write_text_artifact("job-001", "shots/shot-999/render/frame-001.ppm", "stale")
    assert stale_subtitle.is_file()
    assert stale_render.is_file()

    execution_service.run(
        job=build_job(),
        raw_text=(
            "Chapter 1: Arrival at Saint Moix Stadium\n"
            "Jose Alemany watched Antonio Asensio celebrate at Saint Moix Stadium."
        ),
    )

    assert not stale_subtitle.exists()
    assert not stale_render.exists()


def test_local_job_execution_service_uses_real_frame_suffix_for_preview_assets(tmp_path: Path) -> None:
    runtime_root = tmp_path / "runtime"
    workspace = RuntimeWorkspace(root_dir=runtime_root)
    ffmpeg_executor = RecordingFfmpegExecutor()

    render_service = DeterministicRenderJobService(render_adapter=PngRenderAdapter(workspace))
    planning_service = DeterministicPlanningService(
        shot_planner=StaticShotPlanner(),
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
            "Chapter 1: Quiet Box\n"
            "Jose studied the empty stadium box."
        ),
    )

    assert result.asset_manifest.preview_refs == ["asset://runtime/jobs/job-001/output/preview.png"]
    assert result.asset_manifest.cover_refs == ["asset://runtime/jobs/job-001/output/cover.png"]
    assert (runtime_root / "jobs" / "job-001" / "output" / "preview.png").is_file()
    assert (runtime_root / "jobs" / "job-001" / "output" / "cover.png").is_file()


def test_local_job_execution_service_fails_closed_when_real_render_has_no_semantic_review(
    tmp_path: Path,
) -> None:
    runtime_root = tmp_path / "runtime"
    workspace = RuntimeWorkspace(root_dir=runtime_root)
    ffmpeg_executor = RecordingFfmpegExecutor()

    render_service = DeterministicRenderJobService(render_adapter=PngRenderAdapter(workspace))
    planning_service = DeterministicPlanningService(
        shot_planner=StaticShotPlanner(),
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
            "Chapter 1: Quiet Box\n"
            "Jose studied the empty stadium box."
        ),
    )

    assert result.final_job.status is JobStatus.MANUAL_HOLD
    assert result.semantic_review_case is not None
    assert result.technical_review_case.review_mode is ReviewMode.TECHNICAL
    assert result.review_case.review_mode is ReviewMode.SEMANTIC_IMAGE
    assert "semantic_review_backend_disabled" in result.review_case.reason_codes


def test_local_job_execution_service_completes_real_render_after_semantic_review_pass(
    tmp_path: Path,
) -> None:
    runtime_root = tmp_path / "runtime"
    workspace = RuntimeWorkspace(root_dir=runtime_root)
    ffmpeg_executor = RecordingFfmpegExecutor()

    render_service = DeterministicRenderJobService(render_adapter=PngRenderAdapter(workspace))
    planning_service = DeterministicPlanningService(
        shot_planner=StaticShotPlanner(),
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
        semantic_review_service=PassingSemanticReviewService(),
    )

    result = execution_service.run(
        job=build_job(),
        raw_text=(
            "Chapter 1: Quiet Box\n"
            "Jose studied the empty stadium box."
        ),
    )

    assert result.final_job.status is JobStatus.COMPLETED
    assert result.semantic_review_case is not None
    assert result.technical_review_case.review_mode is ReviewMode.TECHNICAL
    assert result.semantic_review_case.review_mode is ReviewMode.SEMANTIC_IMAGE
    assert result.review_case.review_mode is ReviewMode.SEMANTIC_IMAGE
    assert result.review_case.result is ReviewResult.PASS
