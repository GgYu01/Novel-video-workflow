from __future__ import annotations

from av_workflow.contracts.enums import JobStatus, MotionTier, RenderBackend, ShotType
from av_workflow.contracts.models import Job, ShotPlan
from av_workflow.services.audio_timeline import DeterministicAudioTimelineService
from av_workflow.services.planning import DeterministicPlanningService
from av_workflow.services.render_jobs import DeterministicRenderJobService
from av_workflow.services.story_bible import DeterministicStoryBibleService
from av_workflow.services.ingest import normalize_source
from av_workflow.workflow.engine import WorkflowEngine
from av_workflow.workflow.stage_runner import DeterministicStageRunner


class StubRenderAdapter:
    def submit(self, render_request):
        return {
            "render_job_id": render_request.render_job_id,
            "shot_id": render_request.shot_id,
            "status": "completed",
            "clip_ref": f"asset://shots/{render_request.shot_id}.mp4",
            "frame_refs": [f"asset://shots/{render_request.shot_id}/frame-001.png"],
            "metadata": {"duration_sec": render_request.requested_duration_sec, "fps": 24},
        }


class PlaceholderRenderAdapter:
    def submit(self, render_request):
        return {
            "render_job_id": render_request.render_job_id,
            "shot_id": render_request.shot_id,
            "status": "completed",
            "clip_ref": f"asset://shots/{render_request.shot_id}.mp4",
            "frame_refs": [f"asset://shots/{render_request.shot_id}/frame-001.png"],
            "metadata": {
                "duration_sec": render_request.requested_duration_sec,
                "fps": 24,
                "content_source": "deterministic_placeholder",
                "placeholder_mode": "solid_color_loop",
            },
        }


class StubShotPlanner:
    def build_shots(self, source_document, story_id):
        return [
            {
                "shot_id": "shot-001",
                "chapter_id": source_document.chapter_documents[0]["chapter_id"],
                "scene_id": "scene-1",
                "duration_target": 4.5,
                "shot_type": ShotType.MEDIUM,
                "motion_tier": MotionTier.WAN_DYNAMIC,
                "camera_instruction": "dynamic crowd coverage",
                "subject_instruction": "celebrating players throw the coach into the air",
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


def test_stage_runner_executes_happy_path_end_to_end() -> None:
    job = build_job()
    raw_text = """
    Chapter 1: Arrival at Saint Moix Stadium
    Jose Alemany watched Antonio Asensio celebrate at Saint Moix Stadium.
    Jose Alemany promised Mateo Alemany he would rebuild Mallorca.
    """

    planning_service = DeterministicPlanningService(
        shot_planner=StubShotPlanner(),
        story_bible_service=DeterministicStoryBibleService(),
    )
    render_service = DeterministicRenderJobService(render_adapter=StubRenderAdapter())
    runner = DeterministicStageRunner(
        workflow_engine=WorkflowEngine(),
        planning_service=planning_service,
        audio_timeline_service=DeterministicAudioTimelineService(),
        render_job_service=render_service,
    )

    result = runner.run(job=job, raw_text=raw_text)

    assert result.final_job.status is JobStatus.COMPLETED
    assert result.output_package.ready_for_delivery is False
    assert result.asset_manifest.primary_audio_ref == result.audio_mix_manifest.mix_ref
    assert result.asset_manifest.final_video_ref == "asset://video/job-001/final.mp4"
    assert result.review_case.recommended_action == "continue"
    assert result.render_results["shot-001"].status.value == "succeeded"


def test_stage_runner_stops_on_placeholder_render_review_failure() -> None:
    job = build_job()
    raw_text = """
    Chapter 1: Arrival at Saint Moix Stadium
    Jose Alemany watched Antonio Asensio celebrate at Saint Moix Stadium.
    """

    planning_service = DeterministicPlanningService(
        shot_planner=StubShotPlanner(),
        story_bible_service=DeterministicStoryBibleService(),
    )
    render_service = DeterministicRenderJobService(render_adapter=PlaceholderRenderAdapter())
    runner = DeterministicStageRunner(
        workflow_engine=WorkflowEngine(),
        planning_service=planning_service,
        audio_timeline_service=DeterministicAudioTimelineService(),
        render_job_service=render_service,
    )

    result = runner.run(job=job, raw_text=raw_text)

    assert result.final_job.status is JobStatus.MANUAL_HOLD
    assert result.review_case.result.value == "fail"
    assert "placeholder_render_output" in result.review_case.reason_codes
