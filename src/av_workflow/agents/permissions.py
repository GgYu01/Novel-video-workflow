from __future__ import annotations

from typing import Any

SUPPORTED_AGENT_NAMES: frozenset[str] = frozenset(
    {
        "openclaw",
        "codex",
        "claude_code",
    }
)

ALLOWED_PROPOSAL_TYPES: frozenset[str] = frozenset(
    {
        "repair_hint",
        "plan",
        "prompt_revision",
        "review_summary",
    }
)

FORBIDDEN_MUTATION_KEYS: frozenset[str] = frozenset(
    {
        "status",
        "current_stage",
        "ready_for_delivery",
        "delete_asset",
        "policy_bypass",
    }
)

MIN_PROPOSAL_QUALITY_SCORE = 0.6
MAX_CONSECUTIVE_LOW_QUALITY_PROPOSALS = 2


def contains_forbidden_mutation(payload: dict[str, Any]) -> bool:
    return _contains_forbidden_value(payload)


def _contains_forbidden_value(value: Any) -> bool:
    if isinstance(value, dict):
        for key, nested_value in value.items():
            if key in FORBIDDEN_MUTATION_KEYS:
                return True
            if _contains_forbidden_value(nested_value):
                return True
        return False

    if isinstance(value, list):
        return any(_contains_forbidden_value(item) for item in value)

    return False
