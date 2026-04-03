from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from av_workflow.config.models import AppConfig


class ConfigLoader:
    _runtime_override_allowlist = {
        "review.threshold",
        "review.escalation_threshold",
        "adapters.review_provider",
        "render.default_output_preset",
        "audio.narrator_voice_id",
    }

    def __init__(self, config_root: str | Path) -> None:
        self.config_root = Path(config_root)

    def load(
        self,
        profile_name: str | None = None,
        module_names: list[str] | None = None,
        env_overrides: dict[str, Any] | None = None,
        runtime_overrides: dict[str, Any] | None = None,
    ) -> AppConfig:
        data: dict[str, Any] = {}

        self._merge_file(data, self.config_root / "defaults/system.yaml")

        if profile_name:
            self._merge_file(data, self.config_root / f"profiles/{profile_name}.yaml")

        for module_name in module_names or []:
            self._merge_file(data, self.config_root / f"modules/{module_name}.yaml")

        data = self._deep_merge(data, env_overrides or {})
        self._validate_runtime_overrides(runtime_overrides or {})
        data = self._deep_merge(data, runtime_overrides or {})

        try:
            return AppConfig.model_validate(data)
        except ValidationError as exc:
            raise ValueError(str(exc)) from exc

    def _merge_file(self, base: dict[str, Any], path: Path) -> None:
        if not path.exists():
            return
        with path.open("r", encoding="utf-8") as handle:
            loaded = yaml.safe_load(handle) or {}
        merged = self._deep_merge(base, loaded)
        base.clear()
        base.update(merged)

    def _validate_runtime_overrides(self, overrides: dict[str, Any]) -> None:
        for path in self._flatten_paths(overrides):
            if path not in self._runtime_override_allowlist:
                raise ValueError(f"Runtime override is not allowed for path: {path}")

    def _flatten_paths(self, payload: dict[str, Any], prefix: str = "") -> list[str]:
        paths: list[str] = []
        for key, value in payload.items():
            next_prefix = f"{prefix}.{key}" if prefix else key
            if isinstance(value, dict):
                paths.extend(self._flatten_paths(value, next_prefix))
            else:
                paths.append(next_prefix)
        return paths

    def _deep_merge(self, base: dict[str, Any], updates: dict[str, Any]) -> dict[str, Any]:
        merged = dict(base)
        for key, value in updates.items():
            current = merged.get(key)
            if isinstance(current, dict) and isinstance(value, dict):
                merged[key] = self._deep_merge(current, value)
            else:
                merged[key] = value
        return merged
