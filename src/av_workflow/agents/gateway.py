from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from av_workflow.agents.permissions import (
    ALLOWED_PROPOSAL_TYPES,
    MAX_CONSECUTIVE_LOW_QUALITY_PROPOSALS,
    MIN_PROPOSAL_QUALITY_SCORE,
    SUPPORTED_AGENT_NAMES,
    contains_forbidden_mutation,
)


class AgentProposal(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    proposal_id: str
    agent_name: str
    proposal_type: str
    target_ref: str
    summary: str
    payload: dict[str, Any] = Field(default_factory=dict)
    quality_score: float = Field(ge=0.0, le=1.0)


class ProposalVerdict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    accepted: bool
    reason_code: str
    detail: str
    proposal_id: str


class AgentGateway:
    def __init__(self) -> None:
        self._low_quality_streaks: dict[str, int] = {}
        self._circuit_open_agents: set[str] = set()

    def submit_proposal(self, proposal: AgentProposal) -> ProposalVerdict:
        if proposal.agent_name in self._circuit_open_agents:
            return ProposalVerdict(
                accepted=False,
                reason_code="circuit_open",
                detail="Agent proposal circuit is open due to repeated low-quality proposals.",
                proposal_id=proposal.proposal_id,
            )

        if proposal.agent_name not in SUPPORTED_AGENT_NAMES:
            return ProposalVerdict(
                accepted=False,
                reason_code="unsupported_agent",
                detail="Agent is not allowed to submit workflow proposals.",
                proposal_id=proposal.proposal_id,
            )

        if proposal.proposal_type not in ALLOWED_PROPOSAL_TYPES:
            return ProposalVerdict(
                accepted=False,
                reason_code="unsupported_proposal_type",
                detail="Proposal type is not permitted by the gateway policy.",
                proposal_id=proposal.proposal_id,
            )

        if contains_forbidden_mutation(proposal.payload):
            return ProposalVerdict(
                accepted=False,
                reason_code="forbidden_state_mutation",
                detail="Agent proposals may not directly mutate workflow truth or delivery state.",
                proposal_id=proposal.proposal_id,
            )

        if proposal.quality_score < MIN_PROPOSAL_QUALITY_SCORE:
            streak = self._low_quality_streaks.get(proposal.agent_name, 0) + 1
            self._low_quality_streaks[proposal.agent_name] = streak
            if streak >= MAX_CONSECUTIVE_LOW_QUALITY_PROPOSALS:
                self._circuit_open_agents.add(proposal.agent_name)
            return ProposalVerdict(
                accepted=False,
                reason_code="low_quality_proposal",
                detail="Proposal quality score is below the acceptance threshold.",
                proposal_id=proposal.proposal_id,
            )

        self._low_quality_streaks[proposal.agent_name] = 0
        return ProposalVerdict(
            accepted=True,
            reason_code="accepted",
            detail="Proposal accepted for downstream schema and policy processing.",
            proposal_id=proposal.proposal_id,
        )
