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
        adapters:
          review_provider: antigravity
        """,
    )
    write_yaml(
        tmp_path / "profiles/prod.yaml",
        """
        review:
          threshold: 0.82
        """,
    )
    write_yaml(
        tmp_path / "modules/review.yaml",
        """
        review:
          threshold: 0.88
        adapters:
          review_provider: internal-vision
        """,
    )

    loader = ConfigLoader(config_root=tmp_path)
    config = loader.load(
        profile_name="prod",
        module_names=["review"],
        env_overrides={"review": {"threshold": 0.9}},
        runtime_overrides={"adapters": {"review_provider": "runtime-review"}},
    )

    assert config.storage.bucket == "raw-assets"
    assert config.review.threshold == 0.9
    assert config.adapters.review_provider == "runtime-review"


def test_config_loader_rejects_forbidden_runtime_override(tmp_path: Path) -> None:
    write_yaml(
        tmp_path / "defaults/system.yaml",
        """
        runtime:
          state_backend: postgres
        review:
          threshold: 0.75
        adapters:
          review_provider: antigravity
        storage:
          bucket: raw-assets
        """,
    )

    loader = ConfigLoader(config_root=tmp_path)

    with pytest.raises(ValueError, match="runtime.state_backend"):
        loader.load(
            runtime_overrides={"runtime": {"state_backend": "sqlite"}},
        )


def test_config_loader_rejects_invalid_module_schema(tmp_path: Path) -> None:
    write_yaml(
        tmp_path / "defaults/system.yaml",
        """
        review:
          threshold: 0.75
        adapters:
          review_provider: antigravity
        storage:
          bucket: raw-assets
        """,
    )
    write_yaml(
        tmp_path / "modules/review.yaml",
        """
        review:
          threshold: 1.5
        """,
    )

    loader = ConfigLoader(config_root=tmp_path)

    with pytest.raises(ValueError, match="threshold"):
        loader.load(module_names=["review"])
