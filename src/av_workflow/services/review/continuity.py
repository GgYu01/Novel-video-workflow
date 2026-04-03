from __future__ import annotations

from av_workflow.adapters.review import normalize_continuity_review
from av_workflow.contracts.enums import MotionTier, ReviewResult
from av_workflow.contracts.models import ReviewCase


class ContinuityReviewService:
    def evaluate_shot_continuity(
        self,
        *,
        target_ref: str,
        input_assets: list[str],
        score: float,
        drift_codes: list[str],
        motion_tier: MotionTier,
        uncertain: bool = False,
    ) -> ReviewCase:
        payload = _build_payload(
            score=score,
            drift_codes=drift_codes,
            motion_tier=motion_tier,
            uncertain=uncertain,
        )
        return normalize_continuity_review(
            provider_name="continuity-review",
            provider_version="deterministic-v1",
            target_ref=target_ref,
            input_assets=input_assets,
            response_payload=payload,
            raw_response_ref=f"raw://continuity-{target_ref}.json",
        )


def _build_payload(
    *,
    score: float,
    drift_codes: list[str],
    motion_tier: MotionTier,
    uncertain: bool,
) -> dict[str, object]:
    if uncertain:
        return {
            "result": ReviewResult.WARN,
            "score": score,
            "reason_codes": drift_codes,
            "reason_text": "Continuity reviewer could not resolve the drift with enough confidence.",
            "fix_hint": "Escalate the case for manual inspection.",
            "recommended_action": "manual_hold",
            "latency_ms": 0,
        }

    if score < 0.75:
        fix_hint = "Retry the shot neighborhood."
        if motion_tier is MotionTier.WAN_DYNAMIC:
            fix_hint += " Consider downgrading to limited_motion."
        return {
            "result": ReviewResult.FAIL,
            "score": score,
            "reason_codes": drift_codes,
            "reason_text": "Adjacent shots drift beyond the continuity threshold.",
            "fix_hint": fix_hint,
            "recommended_action": "retry_neighborhood",
            "latency_ms": 0,
        }

    return {
        "result": ReviewResult.PASS,
        "score": score,
        "reason_codes": drift_codes or ["continuity_ok"],
        "reason_text": "Adjacent shots remain visually consistent.",
        "fix_hint": None,
        "recommended_action": "continue",
        "latency_ms": 0,
    }
