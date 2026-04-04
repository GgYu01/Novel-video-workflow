from __future__ import annotations

from pathlib import Path
import textwrap

from fastapi.testclient import TestClient

from av_workflow.api.app import create_app
from av_workflow.runtime.bootstrap import build_job_execution_service_factory


class RecordingFfmpegExecutor:
    def run(self, args: list[str], *, cwd: Path | None = None, output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"fake-video")


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
                "Chapter 1: Arrival at Saint Moix Stadium\n"
                "Jose Alemany watched Antonio Asensio celebrate at Saint Moix Stadium.\n"
                "Jose Alemany promised Mateo Alemany he would rebuild Mallorca."
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
