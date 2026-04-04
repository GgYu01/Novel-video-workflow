from __future__ import annotations

from pathlib import Path
import textwrap

from av_workflow.adapters.render import (
    ApiRenderBackendAdapter,
    DeterministicLocalRenderAdapter,
    RoutingRenderAdapter,
)
from av_workflow.runtime.bootstrap import build_job_execution_service_factory


class FakeFfmpegExecutor:
    def run(self, args: list[str], *, cwd: Path | None = None, output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"fake-video")


def write_yaml(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content).strip() + "\n", encoding="utf-8")


def write_base_config(config_root: Path, *, render_mode: str) -> None:
    write_yaml(
        config_root / "defaults/system.yaml",
        f"""
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
          mode: {render_mode}
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


def test_build_job_execution_service_factory_uses_deterministic_local_render_mode(
    tmp_path: Path,
) -> None:
    config_root = tmp_path / "config"
    write_base_config(config_root, render_mode="deterministic_local")

    factory = build_job_execution_service_factory(
        config_root=config_root,
        runtime_root=tmp_path / "runtime",
        ffmpeg_executor=FakeFfmpegExecutor(),
    )

    service = factory.create(job_id="job-001")

    assert isinstance(service.render_job_service.render_adapter, DeterministicLocalRenderAdapter)


def test_build_job_execution_service_factory_uses_routed_api_render_mode(tmp_path: Path) -> None:
    config_root = tmp_path / "config"
    write_base_config(config_root, render_mode="routed_api")

    factory = build_job_execution_service_factory(
        config_root=config_root,
        runtime_root=tmp_path / "runtime",
        ffmpeg_executor=FakeFfmpegExecutor(),
    )

    service = factory.create(job_id="job-001")
    adapter = service.render_job_service.render_adapter

    assert isinstance(adapter, RoutingRenderAdapter)
    assert isinstance(adapter.image_adapter, ApiRenderBackendAdapter)
    assert isinstance(adapter.wan_adapter, ApiRenderBackendAdapter)
    assert adapter.image_adapter.base_url == "http://image-render.internal:8091"
    assert adapter.wan_adapter.base_url == "http://wan-render.internal:8092"
