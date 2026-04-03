from __future__ import annotations

import pytest

from av_workflow.contracts.enums import JobStatus
from av_workflow.contracts.models import Job
from av_workflow.workflow.engine import IllegalTransitionError, WorkflowEngine


def build_job(
    *,
    status: JobStatus = JobStatus.CREATED,
    current_stage: str | None = None,
    retry_count: int = 0,
) -> Job:
    return Job(
        job_id="job-001",
        input_mode="upload",
        source_ref="asset://source.txt",
        output_preset="short-story",
        profile_id="internal-prod",
        language="zh-CN",
        review_level="strict",
        status=status,
        current_stage=current_stage or status.value,
        retry_count=retry_count,
    )


def test_workflow_engine_advances_job_through_happy_path() -> None:
    engine = WorkflowEngine()
    job = build_job()

    path = [
        JobStatus.NORMALIZED,
        JobStatus.PLANNED,
        JobStatus.RENDER_REQUESTED,
        JobStatus.RENDER_READY,
        JobStatus.AUDIO_READY,
        JobStatus.COMPOSED,
        JobStatus.QA_TECHNICAL_PASSED,
        JobStatus.QA_SEMANTIC_PASSED,
        JobStatus.OUTPUT_READY,
        JobStatus.COMPLETED,
    ]

    for next_status in path:
        job = engine.advance(job, next_status)

    assert job.status is JobStatus.COMPLETED
    assert job.current_stage == JobStatus.COMPLETED.value


def test_workflow_engine_rejects_illegal_forward_transition() -> None:
    engine = WorkflowEngine()
    job = build_job()

    with pytest.raises(IllegalTransitionError, match="created -> planned"):
        engine.advance(job, JobStatus.PLANNED)


def test_workflow_engine_schedules_retry_and_resumes_target_stage() -> None:
    engine = WorkflowEngine()
    job = build_job(status=JobStatus.COMPOSED, current_stage=JobStatus.COMPOSED.value)

    scheduled = engine.schedule_retry(job, resume_at=JobStatus.PLANNED)

    assert scheduled.status is JobStatus.RETRY_SCHEDULED
    assert scheduled.retry_count == 1
    assert scheduled.current_stage == "retry_scheduled:planned"

    resumed = engine.resume_retry(scheduled)

    assert resumed.status is JobStatus.PLANNED
    assert resumed.current_stage == JobStatus.PLANNED.value


def test_workflow_engine_rejects_retry_scheduling_from_created_state() -> None:
    engine = WorkflowEngine()
    job = build_job()

    with pytest.raises(IllegalTransitionError, match="created"):
        engine.schedule_retry(job, resume_at=JobStatus.PLANNED)


def test_workflow_engine_rejects_manual_hold_from_retry_scheduled_state() -> None:
    engine = WorkflowEngine()
    job = build_job(
        status=JobStatus.RETRY_SCHEDULED,
        current_stage="retry_scheduled:planned",
        retry_count=1,
    )

    with pytest.raises(IllegalTransitionError, match="retry_scheduled"):
        engine.place_on_hold(job)


def test_workflow_engine_quarantines_job_and_blocks_automatic_progress() -> None:
    engine = WorkflowEngine()
    job = build_job(
        status=JobStatus.QA_TECHNICAL_PASSED,
        current_stage=JobStatus.QA_TECHNICAL_PASSED.value,
    )

    quarantined = engine.quarantine(job, reason="semantic-mismatch")

    assert quarantined.status is JobStatus.QUARANTINED
    assert quarantined.quarantine_reason == "semantic-mismatch"

    with pytest.raises(IllegalTransitionError, match="quarantined"):
        engine.advance(quarantined, JobStatus.QA_SEMANTIC_PASSED)


def test_workflow_engine_rejects_quarantine_from_manual_hold_state() -> None:
    engine = WorkflowEngine()
    job = build_job(
        status=JobStatus.MANUAL_HOLD,
        current_stage="manual_hold:render_ready",
    )

    with pytest.raises(IllegalTransitionError, match="manual_hold"):
        engine.quarantine(job, reason="operator-escalation")


def test_workflow_engine_places_job_on_manual_hold_and_can_resume() -> None:
    engine = WorkflowEngine()
    job = build_job(
        status=JobStatus.RENDER_READY,
        current_stage=JobStatus.RENDER_READY.value,
    )

    held = engine.place_on_hold(job)

    assert held.status is JobStatus.MANUAL_HOLD
    assert held.current_stage == "manual_hold:render_ready"

    resumed = engine.resume_hold(held)

    assert resumed.status is JobStatus.RENDER_READY
    assert resumed.current_stage == JobStatus.RENDER_READY.value


def test_workflow_engine_rejects_resume_hold_to_non_active_state() -> None:
    engine = WorkflowEngine()
    job = build_job(
        status=JobStatus.MANUAL_HOLD,
        current_stage="manual_hold:completed",
    )

    with pytest.raises(IllegalTransitionError, match="completed"):
        engine.resume_hold(job)
