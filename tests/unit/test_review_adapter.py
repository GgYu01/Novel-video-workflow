from __future__ import annotations

from av_workflow.contracts.enums import ReviewMode, ReviewResult
from av_workflow.adapters.review import normalize_semantic_review


def test_normalize_semantic_review_maps_valid_provider_payload() -> None:
    review = normalize_semantic_review(
        provider_name="antigravity-image",
        provider_version="preview",
        target_type="shot",
        target_ref="shot-001",
        input_assets=["asset://frame-1.png"],
        response_payload={
            "result": "pass",
            "score": 0.93,
            "reason_codes": ["character_match"],
            "reason_text": "Character and environment are consistent.",
            "recommended_action": "continue",
            "fix_hint": None,
            "latency_ms": 812,
        },
        raw_response_ref="raw://review-001.json",
    )

    assert review.review_mode is ReviewMode.SEMANTIC_IMAGE
    assert review.result is ReviewResult.PASS
    assert review.score == 0.93
    assert review.recommended_action == "continue"
    assert review.reason_codes == ["character_match"]


def test_normalize_semantic_review_falls_back_for_malformed_payload() -> None:
    review = normalize_semantic_review(
        provider_name="antigravity-image",
        provider_version="preview",
        target_type="shot",
        target_ref="shot-001",
        input_assets=["asset://frame-1.png"],
        response_payload={
            "score": "not-a-number",
        },
        raw_response_ref="raw://review-002.json",
    )

    assert review.result is ReviewResult.FAIL
    assert review.reason_codes == ["provider_response_invalid"]
    assert review.recommended_action == "manual_hold"
    assert review.raw_response_ref == "raw://review-002.json"
