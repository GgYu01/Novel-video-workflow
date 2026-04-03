from __future__ import annotations

from av_workflow.agents.gateway import AgentGateway, AgentProposal


def build_proposal(
    *,
    agent_name: str = "codex",
    quality_score: float = 0.9,
    payload: dict[str, object] | None = None,
) -> AgentProposal:
    return AgentProposal(
        proposal_id="proposal-001",
        agent_name=agent_name,
        proposal_type="repair_hint",
        target_ref="shot-001",
        summary="Suggest a tighter framing prompt.",
        payload=payload or {"prompt_revision": "Use a medium shot with stable framing."},
        quality_score=quality_score,
    )


def test_agent_gateway_accepts_supported_proposal() -> None:
    gateway = AgentGateway()

    verdict = gateway.submit_proposal(build_proposal())

    assert verdict.accepted is True
    assert verdict.reason_code == "accepted"


def test_agent_gateway_rejects_direct_state_mutation_proposal() -> None:
    gateway = AgentGateway()

    verdict = gateway.submit_proposal(
        build_proposal(payload={"status": "completed"})
    )

    assert verdict.accepted is False
    assert verdict.reason_code == "forbidden_state_mutation"


def test_agent_gateway_rejects_nested_list_state_mutation_proposal() -> None:
    gateway = AgentGateway()

    verdict = gateway.submit_proposal(
        build_proposal(
            payload={
                "operations": [
                    {"kind": "annotate"},
                    {"status": "completed"},
                ]
            }
        )
    )

    assert verdict.accepted is False
    assert verdict.reason_code == "forbidden_state_mutation"


def test_agent_gateway_opens_circuit_after_repeated_low_quality_proposals() -> None:
    gateway = AgentGateway()

    first = gateway.submit_proposal(build_proposal(agent_name="openclaw", quality_score=0.2))
    second = gateway.submit_proposal(
        AgentProposal(
            proposal_id="proposal-002",
            agent_name="openclaw",
            proposal_type="repair_hint",
            target_ref="shot-001",
            summary="Second low-quality suggestion.",
            payload={"prompt_revision": "Try again."},
            quality_score=0.25,
        )
    )
    third = gateway.submit_proposal(
        AgentProposal(
            proposal_id="proposal-003",
            agent_name="openclaw",
            proposal_type="repair_hint",
            target_ref="shot-001",
            summary="Now send a good suggestion.",
            payload={"prompt_revision": "Use a wider establishing frame."},
            quality_score=0.92,
        )
    )

    assert first.reason_code == "low_quality_proposal"
    assert second.reason_code == "low_quality_proposal"
    assert third.accepted is False
    assert third.reason_code == "circuit_open"
