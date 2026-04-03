from __future__ import annotations

from av_workflow.contracts.enums import JobStatus
from av_workflow.workflow.states import LINEAR_FLOW_STATUSES

LEGAL_FORWARD_TRANSITIONS: dict[JobStatus, frozenset[JobStatus]] = {
    current: frozenset({LINEAR_FLOW_STATUSES[index + 1]})
    for index, current in enumerate(LINEAR_FLOW_STATUSES[:-1])
}
