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
          default_output_preset: preview_720p24
          allow_wan_for_dynamic: true
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
          default_output_preset: master_1080p24
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
    assert config.render.default_output_preset == "preview_720p24"
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
          default_output_preset: preview_720p24
          allow_wan_for_dynamic: true
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
          default_output_preset: preview_720p24
          allow_wan_for_dynamic: true
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
