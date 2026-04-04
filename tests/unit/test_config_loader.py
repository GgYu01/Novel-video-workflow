from __future__ import annotations

from pathlib import Path
import textwrap

import pytest

from av_workflow.config.loader import ConfigLoader


def write_yaml(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    normalized = textwrap.dedent(content).strip() + "\n"
    path.write_text(normalized, encoding="utf-8")


def test_config_loader_merges_layers_with_expected_precedence(tmp_path: Path) -> None:
    write_yaml(
        tmp_path / "defaults/system.yaml",
        """
        storage:
          bucket: raw-assets
        review:
          threshold: 0.75
          escalation_threshold: 0.6
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
            base_url: http://image-default.internal
            submit_path: /v1/render/image
            timeout_sec: 20.0
          wan_endpoint:
            base_url: http://wan-default.internal
            submit_path: /v1/render/video
            timeout_sec: 90.0
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
        """,
    )
    write_yaml(
        tmp_path / "profiles/prod.yaml",
        """
        review:
          threshold: 0.82
        audio:
          narrator_voice_id: narrator.zh_pro
        """,
    )
    write_yaml(
        tmp_path / "modules/review.yaml",
        """
        review:
          threshold: 0.88
          escalation_threshold: 0.72
        adapters:
          review_provider: internal-vision
        """,
    )
    write_yaml(
        tmp_path / "modules/render.yaml",
        """
        render:
          mode: routed_api
          default_output_preset: master_1080p24
          image_endpoint:
            base_url: http://image-render.internal
        agents:
          max_parallel_proposals: 4
        """,
    )
    write_yaml(
        tmp_path / "modules/audio.yaml",
        """
        audio:
          subtitle_source_mode: tts_segments
        adapters:
          tts_provider: kokoro-local
        """,
    )

    loader = ConfigLoader(config_root=tmp_path)
    config = loader.load(
        profile_name="prod",
        module_names=["review", "render", "audio"],
        env_overrides={
            "review": {"threshold": 0.9},
            "audio": {"default_speech_rate": 0.95},
        },
        runtime_overrides={
            "adapters": {"review_provider": "runtime-review"},
            "render": {"default_output_preset": "preview_720p24"},
            "audio": {"narrator_voice_id": "narrator.zh_runtime"},
        },
    )

    assert config.storage.bucket == "raw-assets"
    assert config.review.threshold == 0.9
    assert config.review.escalation_threshold == 0.72
    assert config.adapters.review_provider == "runtime-review"
    assert config.adapters.tts_provider == "kokoro-local"
    assert config.render.mode == "routed_api"
    assert config.render.default_output_preset == "preview_720p24"
    assert config.render.image_endpoint.base_url == "http://image-render.internal"
    assert config.render.image_endpoint.submit_path == "/v1/render/image"
    assert config.render.image_endpoint.timeout_sec == 20.0
    assert config.render.wan_endpoint.base_url == "http://wan-default.internal"
    assert config.render.wan_endpoint.submit_path == "/v1/render/video"
    assert config.render.wan_endpoint.timeout_sec == 90.0
    assert config.audio.narrator_voice_id == "narrator.zh_runtime"
    assert config.audio.subtitle_source_mode == "tts_segments"
    assert config.audio.default_speech_rate == 0.95
    assert config.agents.max_parallel_proposals == 4


def test_config_loader_rejects_forbidden_runtime_override(tmp_path: Path) -> None:
    write_yaml(
        tmp_path / "defaults/system.yaml",
        """
        runtime:
          state_backend: postgres
        review:
          threshold: 0.75
          escalation_threshold: 0.6
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
            base_url: http://image-default.internal
            submit_path: /v1/render/image
            timeout_sec: 20.0
          wan_endpoint:
            base_url: http://wan-default.internal
            submit_path: /v1/render/video
            timeout_sec: 90.0
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
        storage:
          bucket: raw-assets
        """,
    )

    loader = ConfigLoader(config_root=tmp_path)

    with pytest.raises(ValueError, match="agents.allowed_agents"):
        loader.load(
            runtime_overrides={"agents": {"allowed_agents": ["openclaw"]}},
        )


def test_config_loader_applies_profile_after_module_defaults(tmp_path: Path) -> None:
    write_yaml(
        tmp_path / "defaults/system.yaml",
        """
        storage:
          bucket: raw-assets
        review:
          threshold: 0.75
          escalation_threshold: 0.6
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
            base_url: http://image-default.internal
            submit_path: /v1/render/image
            timeout_sec: 20.0
          wan_endpoint:
            base_url: http://wan-default.internal
            submit_path: /v1/render/video
            timeout_sec: 90.0
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
        """,
    )
    write_yaml(
        tmp_path / "profiles/routed_api_local.yaml",
        """
        render:
          mode: routed_api
        """,
    )
    write_yaml(
        tmp_path / "modules/render.yaml",
        """
        render:
          mode: deterministic_local
          image_endpoint:
            base_url: http://image-render.internal
        """,
    )

    loader = ConfigLoader(config_root=tmp_path)
    config = loader.load(profile_name="routed_api_local", module_names=["render"])

    assert config.render.mode == "routed_api"
    assert config.render.image_endpoint.base_url == "http://image-render.internal"


def test_repo_routed_render_defaults_allow_cpu_backend_latency() -> None:
    config_root = Path(__file__).resolve().parents[2] / "config"
    loader = ConfigLoader(config_root=config_root)

    config = loader.load(
        profile_name="routed_api_local",
        module_names=["render", "audio", "review"],
    )

    assert config.render.mode == "routed_api"
    assert config.render.image_endpoint.timeout_sec == 300.0
    assert config.render.wan_endpoint.timeout_sec == 1800.0


def test_config_loader_rejects_invalid_module_schema(tmp_path: Path) -> None:
    write_yaml(
        tmp_path / "defaults/system.yaml",
        """
        review:
          threshold: 0.75
          escalation_threshold: 0.6
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
            base_url: http://image-default.internal
            submit_path: /v1/render/image
            timeout_sec: 20.0
          wan_endpoint:
            base_url: http://wan-default.internal
            submit_path: /v1/render/video
            timeout_sec: 90.0
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
        storage:
          bucket: raw-assets
        """,
    )
    write_yaml(
        tmp_path / "modules/review.yaml",
        """
        render:
          default_output_preset: preview_720p24
          allow_wan_for_dynamic: nope
        """,
    )

    loader = ConfigLoader(config_root=tmp_path)

    with pytest.raises(ValueError, match="allow_wan_for_dynamic"):
        loader.load(module_names=["review"])
