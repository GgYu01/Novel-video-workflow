from __future__ import annotations

from av_workflow.contracts.enums import JobStatus

LINEAR_FLOW_STATUSES: tuple[JobStatus, ...] = (
    JobStatus.CREATED,
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
)

ACTIVE_FLOW_STATUSES: frozenset[JobStatus] = frozenset(LINEAR_FLOW_STATUSES[:-1])
TERMINAL_FLOW_STATUSES: frozenset[JobStatus] = frozenset(
    {
        JobStatus.COMPLETED,
        JobStatus.QUARANTINED,
        JobStatus.FAILED_TERMINAL,
    }
)
CONTROL_FLOW_STATUSES: frozenset[JobStatus] = frozenset(
    {
        JobStatus.RETRY_SCHEDULED,
        JobStatus.MANUAL_HOLD,
    }
)
PAUSED_FLOW_STATUSES: frozenset[JobStatus] = frozenset(
    {
        JobStatus.RETRY_SCHEDULED,
        JobStatus.MANUAL_HOLD,
        JobStatus.QUARANTINED,
    }
)

RETRY_RESUME_TARGETS: frozenset[JobStatus] = frozenset(
    {
        JobStatus.NORMALIZED,
        JobStatus.PLANNED,
        JobStatus.RENDER_REQUESTED,
        JobStatus.RENDER_READY,
        JobStatus.AUDIO_READY,
        JobStatus.COMPOSED,
        JobStatus.QA_TECHNICAL_PASSED,
    }
)
