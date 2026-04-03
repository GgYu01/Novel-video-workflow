from __future__ import annotations

from av_workflow.contracts.enums import JobStatus
from av_workflow.contracts.models import Job
from av_workflow.workflow.states import ACTIVE_FLOW_STATUSES, RETRY_RESUME_TARGETS
from av_workflow.workflow.transitions import LEGAL_FORWARD_TRANSITIONS


class IllegalTransitionError(ValueError):
    """Raised when a job is asked to move through an invalid state path."""


class WorkflowEngine:
    def advance(self, job: Job, next_status: JobStatus) -> Job:
        allowed = LEGAL_FORWARD_TRANSITIONS.get(job.status, frozenset())
        if next_status not in allowed:
            raise IllegalTransitionError(
                f"Illegal workflow transition: {job.status.value} -> {next_status.value}"
            )
        return self._copy_job(
            job,
            status=next_status,
            current_stage=next_status.value,
            quarantine_reason=None,
        )

    def schedule_retry(self, job: Job, *, resume_at: JobStatus) -> Job:
        if job.status not in ACTIVE_FLOW_STATUSES - {JobStatus.CREATED}:
            raise IllegalTransitionError(
                f"Cannot schedule retry from workflow state: {job.status.value}"
            )
        if job.retry_count >= job.max_auto_retries:
            raise IllegalTransitionError(
                f"Retry budget exhausted for job {job.job_id}: {job.retry_count}/{job.max_auto_retries}"
            )
        if resume_at not in RETRY_RESUME_TARGETS:
            raise IllegalTransitionError(f"Retry resume target is not allowed: {resume_at.value}")
        return self._copy_job(
            job,
            status=JobStatus.RETRY_SCHEDULED,
            current_stage=f"retry_scheduled:{resume_at.value}",
            retry_count=job.retry_count + 1,
            quarantine_reason=None,
        )

    def resume_retry(self, job: Job) -> Job:
        if job.status is not JobStatus.RETRY_SCHEDULED:
            raise IllegalTransitionError(
                f"Cannot resume retry from workflow state: {job.status.value}"
            )
        resume_at = self._extract_embedded_status(
            current_stage=job.current_stage,
            prefix="retry_scheduled",
        )
        if resume_at not in RETRY_RESUME_TARGETS:
            raise IllegalTransitionError(f"Retry resume target is not allowed: {resume_at.value}")
        return self._copy_job(
            job,
            status=resume_at,
            current_stage=resume_at.value,
            quarantine_reason=None,
        )

    def quarantine(self, job: Job, *, reason: str) -> Job:
        if not reason:
            raise IllegalTransitionError("Quarantine reason is required")
        if job.status not in ACTIVE_FLOW_STATUSES:
            raise IllegalTransitionError(
                f"Cannot quarantine workflow state: {job.status.value}"
            )
        return self._copy_job(
            job,
            status=JobStatus.QUARANTINED,
            current_stage=f"quarantined:{job.status.value}",
            quarantine_reason=reason,
        )

    def place_on_hold(self, job: Job) -> Job:
        if job.status not in ACTIVE_FLOW_STATUSES:
            raise IllegalTransitionError(
                f"Cannot place workflow state on hold: {job.status.value}"
            )
        return self._copy_job(
            job,
            status=JobStatus.MANUAL_HOLD,
            current_stage=f"manual_hold:{job.status.value}",
        )

    def resume_hold(self, job: Job) -> Job:
        if job.status is not JobStatus.MANUAL_HOLD:
            raise IllegalTransitionError(
                f"Cannot resume hold from workflow state: {job.status.value}"
            )
        resume_at = self._extract_embedded_status(
            current_stage=job.current_stage,
            prefix="manual_hold",
        )
        if resume_at not in ACTIVE_FLOW_STATUSES:
            raise IllegalTransitionError(
                f"Manual hold resume target is not allowed: {resume_at.value}"
            )
        return self._copy_job(
            job,
            status=resume_at,
            current_stage=resume_at.value,
        )

    def _copy_job(self, job: Job, **updates: object) -> Job:
        return job.model_copy(update=updates)

    def _extract_embedded_status(self, *, current_stage: str, prefix: str) -> JobStatus:
        expected_prefix = f"{prefix}:"
        if not current_stage.startswith(expected_prefix):
            raise IllegalTransitionError(
                f"Workflow stage does not contain a resumable state: {current_stage}"
            )
        _, encoded_status = current_stage.split(":", maxsplit=1)
        try:
            return JobStatus(encoded_status)
        except ValueError as exc:
            raise IllegalTransitionError(
                f"Unknown embedded workflow state: {encoded_status}"
            ) from exc
