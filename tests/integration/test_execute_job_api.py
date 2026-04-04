from __future__ import annotations

from pathlib import Path
import textwrap

from fastapi.testclient import TestClient

from av_workflow.api.app import create_app
from av_workflow.adapters.tts import DeterministicLocalTTSAdapter
from av_workflow.contracts.enums import ReviewMode, ReviewResult
from av_workflow.contracts.models import AssetManifest, Job, ReviewCase, ShotPlanSet
from av_workflow.runtime.bootstrap import build_job_execution_service_factory
from av_workflow.runtime.workspace import RuntimeWorkspace
from av_workflow.services.audio_timeline import DeterministicAudioTimelineService
from av_workflow.services.job_execution import DeterministicLocalJobExecutionService
from av_workflow.services.planning import DeterministicPlanningService, HeuristicChapterShotPlanner
from av_workflow.services.render_jobs import DeterministicRenderJobService
from av_workflow.services.story_bible import DeterministicStoryBibleService
from av_workflow.workflow.stage_runner import SemanticReviewService


class RecordingFfmpegExecutor:
    def run(self, args: list[str], *, cwd: Path | None = None, output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"fake-video")


class RealFrameRenderAdapter:
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
        del shot_plan_set
        input_assets = [
            str(frame_path)
            for frame_paths in (frame_path_map or {}).values()
            for frame_path in frame_paths
        ]
        if not input_assets:
            input_assets = [*manifest.preview_refs, *manifest.cover_refs]
        return ReviewCase(
            review_case_id=f"review-{job.job_id}-semantic-pass",
            target_type="asset_manifest",
            target_ref=manifest.manifest_ref,
            review_mode=ReviewMode.SEMANTIC_IMAGE,
            input_assets=input_assets,
            evaluation_prompt_ref="prompt://review/semantic-default",
            result=ReviewResult.PASS,
            score=0.96,
            reason_codes=["semantic_alignment_ok"],
            reason_text="Semantic review passed.",
            fix_hint=None,
            recommended_action="continue",
            review_provider="semantic-stub",
            provider_version="test",
            latency_ms=13,
            raw_response_ref=f"raw://semantic-review/{job.job_id}.json",
        )


class PassingExecutionServiceFactory:
    def __init__(self, *, runtime_root: Path) -> None:
        self.runtime_root = runtime_root
        self.ffmpeg_executor = RecordingFfmpegExecutor()

    def create(self, *, job_id: str) -> DeterministicLocalJobExecutionService:
        workspace = RuntimeWorkspace(root_dir=self.runtime_root)
        render_service = DeterministicRenderJobService(render_adapter=RealFrameRenderAdapter(workspace))
        planning_service = DeterministicPlanningService(
            shot_planner=HeuristicChapterShotPlanner(),
            story_bible_service=DeterministicStoryBibleService(),
        )
        audio_service = DeterministicAudioTimelineService(
            tts_adapter=DeterministicLocalTTSAdapter(workspace=workspace, job_id=job_id)
        )
        return DeterministicLocalJobExecutionService(
            runtime_root=self.runtime_root,
            planning_service=planning_service,
            render_job_service=render_service,
            audio_timeline_service=audio_service,
            ffmpeg_executor=self.ffmpeg_executor,
            semantic_review_service=PassingSemanticReviewService(),
        )


def write_yaml(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content).strip() + "\n", encoding="utf-8")


def write_base_config(config_root: Path) -> None:
    write_yaml(
        config_root / "defaults/system.yaml",
        """
        storage:
          bucket: raw-assets
        review:
          threshold: 0.8
          escalation_threshold: 0.7
        adapters:
          review_provider: antigravity
          image_provider: local-image
          tts_provider: local-tts
          wan_provider: local-wan
        render:
          mode: deterministic_local
          default_output_preset: preview_720p24
          allow_wan_for_dynamic: true
          image_endpoint:
            base_url: http://image-render.internal:8091
            submit_path: /v1/render/image
            timeout_sec: 20.0
          wan_endpoint:
            base_url: http://wan-render.internal:8092
            submit_path: /v1/render/video
            timeout_sec: 120.0
        audio:
          narrator_voice_id: narrator.zh_default
          subtitle_source_mode: tts_durations
          default_speech_rate: 1.0
        agents:
          enable_control_plane: true
          allowed_agents:
            - codex
            - claude_code
          max_parallel_proposals: 2
        runtime:
          state_backend: postgres
        """,
    )


def test_execute_job_endpoint_runs_workflow_and_records_artifacts(tmp_path: Path) -> None:
    config_root = tmp_path / "config"
    runtime_root = tmp_path / "runtime"
    write_base_config(config_root)
    factory = build_job_execution_service_factory(
        config_root=config_root,
        runtime_root=runtime_root,
        ffmpeg_executor=RecordingFfmpegExecutor(),
    )
    client = TestClient(create_app(execution_service_factory=factory))

    created = client.post(
        "/v1/jobs",
        json={
            "input_mode": "upload",
            "source_ref": "asset://source.txt",
            "output_preset": "preview_720p24",
            "profile_id": "internal-prod",
            "language": "zh-CN",
            "review_level": "strict",
        },
    )
    job_id = created.json()["job_id"]

    executed = client.post(
        f"/v1/jobs/{job_id}/execute",
        json={
            "raw_text": (
                "Chapter 1: Match Day\n"
                "Jose saw Saint Moix.\n"
                "Mateo would rebuild."
            )
        },
    )

    assert executed.status_code == 200
    assert executed.json()["job_id"] == job_id
    assert executed.json()["status"] == "manual_hold"
    assert executed.json()["review_result"] == "fail"
    assert "placeholder_render_output" in executed.json()["reason_codes"]
    assert executed.json()["final_video_ref"] == f"asset://runtime/jobs/{job_id}/output/final.mp4"

    stage = client.get(f"/v1/jobs/{job_id}/stage")
    assert stage.status_code == 200
    assert stage.json()["status"] == "manual_hold"

    artifacts = client.get(f"/v1/jobs/{job_id}/artifacts")
    assert artifacts.status_code == 200
    assert artifacts.json()["final_video_ref"] == f"asset://runtime/jobs/{job_id}/output/final.mp4"
    assert artifacts.json()["primary_audio_ref"] == f"asset://runtime/jobs/{job_id}/audio/final-mix.wav"
    assert artifacts.json()["shot_assets"]

    assert (runtime_root / "jobs" / job_id / "output" / "final.mp4").is_file()


def test_execute_job_endpoint_returns_semantic_review_result_when_final_gate_passes(
    tmp_path: Path,
) -> None:
    runtime_root = tmp_path / "runtime"
    client = TestClient(create_app(execution_service_factory=PassingExecutionServiceFactory(runtime_root=runtime_root)))

    created = client.post(
        "/v1/jobs",
        json={
            "input_mode": "upload",
            "source_ref": "asset://source.txt",
            "output_preset": "preview_720p24",
            "profile_id": "internal-prod",
            "language": "zh-CN",
            "review_level": "strict",
        },
    )
    job_id = created.json()["job_id"]

    executed = client.post(
        f"/v1/jobs/{job_id}/execute",
        json={
            "raw_text": (
                "Chapter 1: Match Day\n"
                "Jose saw Saint Moix.\n"
                "Mateo would rebuild."
            )
        },
    )

    assert executed.status_code == 200
    assert executed.json()["job_id"] == job_id
    assert executed.json()["status"] == "completed"
    assert executed.json()["review_result"] == "pass"
    assert executed.json()["reason_codes"] == ["semantic_alignment_ok"]
    assert executed.json()["final_video_ref"] == f"asset://runtime/jobs/{job_id}/output/final.mp4"

    stage = client.get(f"/v1/jobs/{job_id}/stage")
    assert stage.status_code == 200
    assert stage.json()["status"] == "completed"

    artifacts = client.get(f"/v1/jobs/{job_id}/artifacts")
    assert artifacts.status_code == 200
    assert artifacts.json()["final_video_ref"] == f"asset://runtime/jobs/{job_id}/output/final.mp4"
    assert artifacts.json()["primary_audio_ref"] == f"asset://runtime/jobs/{job_id}/audio/final-mix.wav"
    assert artifacts.json()["shot_assets"]
