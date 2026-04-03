from __future__ import annotations

from av_workflow.contracts.enums import JobStatus, PolicyAction, ReviewMode, ReviewResult
from av_workflow.contracts.models import Job, PolicyDecision, ReviewCase

_RETRY_ACTIONS: dict[str, tuple[str, JobStatus]] = {
    "retry_shot": ("shot", JobStatus.PLANNED),
    "retry_neighborhood": ("shot_neighborhood", JobStatus.PLANNED),
    "retry_scene": ("scene", JobStatus.PLANNED),
    "retry_chapter": ("chapter", JobStatus.PLANNED),
    "retry_compose": ("compose", JobStatus.RENDER_READY),
}


class PolicyEngine:
    def __init__(self, *, semantic_threshold: float) -> None:
        self.semantic_threshold = semantic_threshold

    def evaluate_review(self, job: Job, review: ReviewCase) -> PolicyDecision:
        if self._should_manual_hold(review):
            return self._build_decision(
                job=job,
                review=review,
                action=PolicyAction.MANUAL_HOLD,
                target_status=JobStatus.MANUAL_HOLD,
            )

        if self._should_quarantine(review):
            return self._build_decision(
                job=job,
                review=review,
                action=PolicyAction.QUARANTINE,
                target_status=JobStatus.QUARANTINED,
            )

        if review.result is ReviewResult.PASS and review.score >= self.semantic_threshold:
            return self._build_decision(
                job=job,
                review=review,
                action=PolicyAction.CONTINUE,
                target_status=self._resolve_continue_status(review.review_mode),
            )

        retry_mapping = _RETRY_ACTIONS.get(review.recommended_action)
        if retry_mapping is not None and job.retry_count < job.max_auto_retries:
            scope, resume_at = retry_mapping
            return self._build_decision(
                job=job,
                review=review,
                action=PolicyAction.RETRY,
                scope=scope,
                target_status=JobStatus.RETRY_SCHEDULED,
                resume_at=resume_at,
            )

        return self._build_decision(
            job=job,
            review=review,
            action=PolicyAction.MANUAL_HOLD,
            target_status=JobStatus.MANUAL_HOLD,
        )

    def _resolve_continue_status(self, review_mode: ReviewMode) -> JobStatus:
        if review_mode is ReviewMode.TECHNICAL:
            return JobStatus.QA_TECHNICAL_PASSED
        return JobStatus.QA_SEMANTIC_PASSED

    def _should_manual_hold(self, review: ReviewCase) -> bool:
        return (
            "provider_response_invalid" in review.reason_codes
            or review.result is ReviewResult.WARN
            or review.recommended_action == "manual_hold"
        )

    def _should_quarantine(self, review: ReviewCase) -> bool:
        return review.recommended_action == "quarantine" or any(
            reason_code.startswith("policy_") for reason_code in review.reason_codes
        )

    def _build_decision(
        self,
        *,
        job: Job,
        review: ReviewCase,
        action: PolicyAction,
        target_status: JobStatus,
        scope: str | None = None,
        resume_at: JobStatus | None = None,
    ) -> PolicyDecision:
        return PolicyDecision(
            policy_decision_id=f"policy-{job.job_id}-{review.review_case_id}",
            job_id=job.job_id,
            review_case_id=review.review_case_id,
            action=action,
            scope=scope,
            target_ref=review.target_ref,
            target_status=target_status,
            resume_at=resume_at,
            reason_codes=review.reason_codes,
            reason_text=review.reason_text,
            applied_threshold=self.semantic_threshold,
            review_score=review.score,
            review_result=review.result,
        )
