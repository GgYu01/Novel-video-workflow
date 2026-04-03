from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from av_workflow.contracts.enums import ReviewMode, ReviewResult
from av_workflow.contracts.models import ReviewCase


class _ProviderSemanticReviewPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    result: ReviewResult
    score: float = Field(ge=0.0, le=1.0)
    reason_codes: list[str]
    reason_text: str
    recommended_action: str
    fix_hint: str | None = None
    latency_ms: int = 0


def normalize_semantic_review(
    *,
    provider_name: str,
    provider_version: str,
    target_type: str,
    target_ref: str,
    input_assets: list[str],
    response_payload: dict[str, Any],
    raw_response_ref: str,
    evaluation_prompt_ref: str = "prompt://review/semantic-default",
) -> ReviewCase:
    try:
        payload = _ProviderSemanticReviewPayload.model_validate(response_payload)
    except ValidationError:
        return ReviewCase(
            review_case_id=_build_review_case_id(target_ref),
            target_type=target_type,
            target_ref=target_ref,
            review_mode=ReviewMode.SEMANTIC_IMAGE,
            input_assets=input_assets,
            evaluation_prompt_ref=evaluation_prompt_ref,
            result=ReviewResult.FAIL,
            score=0.0,
            reason_codes=["provider_response_invalid"],
            reason_text="Provider payload could not be normalized into a review result.",
            fix_hint="Inspect provider output and rerun semantic review.",
            recommended_action="manual_hold",
            review_provider=provider_name,
            provider_version=provider_version,
            latency_ms=_extract_latency(response_payload),
            raw_response_ref=raw_response_ref,
        )

    return ReviewCase(
        review_case_id=_build_review_case_id(target_ref),
        target_type=target_type,
        target_ref=target_ref,
        review_mode=ReviewMode.SEMANTIC_IMAGE,
        input_assets=input_assets,
        evaluation_prompt_ref=evaluation_prompt_ref,
        result=payload.result,
        score=payload.score,
        reason_codes=payload.reason_codes,
        reason_text=payload.reason_text,
        fix_hint=payload.fix_hint,
        recommended_action=payload.recommended_action,
        review_provider=provider_name,
        provider_version=provider_version,
        latency_ms=payload.latency_ms,
        raw_response_ref=raw_response_ref,
    )


def _build_review_case_id(target_ref: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", target_ref).strip("-").lower()
    return f"review-semantic-{slug or 'target'}"


def _extract_latency(response_payload: dict[str, Any]) -> int:
    latency = response_payload.get("latency_ms")
    return latency if isinstance(latency, int) and latency >= 0 else 0
