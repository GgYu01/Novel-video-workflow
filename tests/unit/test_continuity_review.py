from __future__ import annotations

from av_workflow.contracts.enums import MotionTier, ReviewMode, ReviewResult
from av_workflow.services.review.continuity import ContinuityReviewService


def test_continuity_review_service_builds_retryable_review_for_shot_drift() -> None:
    service = ContinuityReviewService()

    review = service.evaluate_shot_continuity(
        target_ref="shot-002",
        input_assets=["asset://shots/shot-001/frame-001.png", "asset://shots/shot-002/frame-001.png"],
        score=0.41,
        drift_codes=["character_drift", "scene_drift"],
        motion_tier=MotionTier.WAN_DYNAMIC,
    )

    assert review.review_mode is ReviewMode.CONTINUITY
    assert review.result is ReviewResult.FAIL
    assert review.recommended_action == "retry_neighborhood"
    assert "limited_motion" in (review.fix_hint or "")


def test_continuity_review_service_marks_uncertain_cases_for_manual_hold() -> None:
    service = ContinuityReviewService()

    review = service.evaluate_shot_continuity(
        target_ref="shot-003",
        input_assets=["asset://shots/shot-002/frame-001.png", "asset://shots/shot-003/frame-001.png"],
        score=0.68,
        drift_codes=["uncertain_face_match"],
        motion_tier=MotionTier.LIMITED_MOTION,
        uncertain=True,
    )

    assert review.result is ReviewResult.WARN
    assert review.recommended_action == "manual_hold"
    assert review.reason_codes == ["uncertain_face_match"]
