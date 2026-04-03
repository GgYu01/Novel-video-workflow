from __future__ import annotations

from av_workflow.contracts.enums import JobStatus, PolicyAction, ReviewMode, ReviewResult
from av_workflow.contracts.models import Job, ReviewCase
from av_workflow.policy.engine import PolicyEngine


def build_job(*, retry_count: int = 0, max_auto_retries: int = 2) -> Job:
    return Job(
        job_id="job-001",
        input_mode="upload",
        source_ref="asset://source.txt",
        output_preset="short-story",
        profile_id="internal-prod",
        language="zh-CN",
        review_level="strict",
        retry_count=retry_count,
        max_auto_retries=max_auto_retries,
    )


def build_review(
    *,
    result: ReviewResult,
    score: float,
    reason_codes: list[str],
    reason_text: str,
    recommended_action: str,
) -> ReviewCase:
    return ReviewCase(
        review_case_id="review-001",
        target_type="shot",
        target_ref="shot-001",
        review_mode=ReviewMode.SEMANTIC_IMAGE,
        input_assets=["asset://frame-1.png"],
        evaluation_prompt_ref="prompt://review/default",
        result=result,
        score=score,
        reason_codes=reason_codes,
        reason_text=reason_text,
        fix_hint=None,
        recommended_action=recommended_action,
        review_provider="antigravity-image",
        provider_version="preview",
        latency_ms=812,
        raw_response_ref="raw://review-001.json",
    )


def test_policy_engine_continues_when_review_passes_threshold() -> None:
    engine = PolicyEngine(semantic_threshold=0.9)
    job = build_job()
    review = build_review(
        result=ReviewResult.PASS,
        score=0.93,
        reason_codes=["character_match"],
        reason_text="Character and environment are consistent.",
        recommended_action="continue",
    )

    decision = engine.evaluate_review(job, review)

    assert decision.action is PolicyAction.CONTINUE
    assert decision.target_status is JobStatus.QA_SEMANTIC_PASSED
    assert decision.resume_at is None


def test_policy_engine_schedules_scoped_retry_for_low_score_failure() -> None:
    engine = PolicyEngine(semantic_threshold=0.9)
    job = build_job(retry_count=0, max_auto_retries=2)
    review = build_review(
        result=ReviewResult.FAIL,
        score=0.41,
        reason_codes=["semantic_mismatch"],
        reason_text="Subject appearance no longer matches the shot plan.",
        recommended_action="retry_shot",
    )

    decision = engine.evaluate_review(job, review)

    assert decision.action is PolicyAction.RETRY
    assert decision.scope == "shot"
    assert decision.target_status is JobStatus.RETRY_SCHEDULED
    assert decision.resume_at is JobStatus.PLANNED
    assert decision.applied_threshold == 0.9


def test_policy_engine_quarantines_policy_sensitive_review_failures() -> None:
    engine = PolicyEngine(semantic_threshold=0.9)
    job = build_job()
    review = build_review(
        result=ReviewResult.FAIL,
        score=0.2,
        reason_codes=["policy_sensitive_content"],
        reason_text="Sensitive content detected in generated imagery.",
        recommended_action="quarantine",
    )

    decision = engine.evaluate_review(job, review)

    assert decision.action is PolicyAction.QUARANTINE
    assert decision.target_status is JobStatus.QUARANTINED
    assert decision.resume_at is None


def test_policy_engine_places_invalid_provider_reviews_on_manual_hold() -> None:
    engine = PolicyEngine(semantic_threshold=0.9)
    job = build_job()
    review = build_review(
        result=ReviewResult.FAIL,
        score=0.0,
        reason_codes=["provider_response_invalid"],
        reason_text="Provider payload could not be normalized.",
        recommended_action="manual_hold",
    )

    decision = engine.evaluate_review(job, review)

    assert decision.action is PolicyAction.MANUAL_HOLD
    assert decision.target_status is JobStatus.MANUAL_HOLD
    assert decision.resume_at is None
