"""Deterministic claim-key canonicalization for structured agent outputs."""

from __future__ import annotations

from copy import deepcopy
from decimal import Decimal, InvalidOperation
from typing import Any

from pydantic import Field

from project_recovery_council.contracts import ContractModel
from project_recovery_council.experiment_contracts import AgentRole, MetricResult, EvaluationMetricId


CLAIM_NORMALIZATION_VERSION = "project-recovery-council.qwen.claim-normalization.v1"


class AppliedClaimAlias(ContractModel):
    raw_key: str = Field(min_length=1)
    canonical_key: str = Field(min_length=1)
    raw_value: Any


class ClaimAliasConflict(ContractModel):
    canonical_key: str = Field(min_length=1)
    raw_keys: list[str] = Field(min_length=2)
    raw_values: dict[str, Any] = Field(default_factory=dict)
    message: str = Field(min_length=1)


class ClaimNormalizationResult(ContractModel):
    invocation_id: str = Field(min_length=1)
    role: str = Field(min_length=1)
    raw_claims: dict[str, Any] = Field(default_factory=dict)
    normalized_claims: dict[str, Any] = Field(default_factory=dict)
    applied_aliases: list[AppliedClaimAlias] = Field(default_factory=list)
    unknown_claim_keys: list[str] = Field(default_factory=list)
    conflicts: list[ClaimAliasConflict] = Field(default_factory=list)
    valid: bool


SCHEDULE_CANONICAL_CLAIM_KEYS = [
    "milestone_id",
    "delivery_baseline_date",
    "delivery_forecast_date",
    "delivery_movement_days",
    "installation_total_float_days",
    "installation_total_float_consumed_days",
    "installation_total_float_remaining_days",
    "milestone_baseline_date",
    "milestone_forecast_date_without_intervention",
    "forecast_milestone_slip_days",
    "successor_testing_activity_id",
    "successor_dependency_effect",
    "successor_testing_constraint",
]


ROLE_CANONICAL_CLAIM_KEYS: dict[str, list[str]] = {
    AgentRole.SCHEDULE_EXPERT.value: SCHEDULE_CANONICAL_CLAIM_KEYS,
    AgentRole.COMMERCIAL_EXPERT.value: [
        "projected_milestone_slip_days",
        "delay_exposure_usd_per_day",
        "unmitigated_exposure_usd",
        "mitigation_cost_usd",
        "gross_avoided_exposure_usd",
    ],
    AgentRole.EVIDENCE_AUDITOR.value: [
        "claim_support",
        "contradiction",
        "unsupported_claim",
        "citation_validation",
    ],
    AgentRole.RISK_EXPERT.value: [
        "risk",
        "human_escalation_required",
        "contradiction_risk",
        "schedule_risk",
    ],
    AgentRole.RECOVERY_PLANNER.value: [
        "preferred_option_id",
        "human_confirmation_required",
        "recommendation",
        "approval_required",
    ],
    AgentRole.DIRECTOR.value: [
        "selected_experts",
        "routing_rationale",
    ],
    AgentRole.ARBITER.value: [
        "resolved_disagreements",
        "unresolved_disagreements",
        "preserved_provenance",
    ],
    AgentRole.GENERALIST.value: ["*"],
}


ROLE_CLAIM_ALIASES: dict[str, dict[str, str]] = {
    AgentRole.SCHEDULE_EXPERT.value: {
        "baseline_delivery_date": "delivery_baseline_date",
        "forecast_delivery_date": "delivery_forecast_date",
        "delivery_shift_days": "delivery_movement_days",
        "float_consumption_days": "installation_total_float_consumed_days",
        "remaining_float_days": "installation_total_float_remaining_days",
        "remaining_float_after_delivery_shift_days": "installation_total_float_remaining_days",
        "projected_milestone_slip_days": "forecast_milestone_slip_days",
        "contractual_milestone_baseline_date": "milestone_baseline_date",
        "contractual_milestone_forecast_without_intervention": (
            "milestone_forecast_date_without_intervention"
        ),
        "successor_dependency_effects": "successor_dependency_effect",
    }
}


def normalize_claim_keys(
    *,
    invocation_id: str,
    role: str,
    response_payload: dict[str, Any] | None,
) -> ClaimNormalizationResult:
    raw_claims = _extract_claims(response_payload)
    canonical_keys = ROLE_CANONICAL_CLAIM_KEYS.get(role, [])
    aliases = ROLE_CLAIM_ALIASES.get(role, {})
    wildcard = "*" in canonical_keys

    applied_aliases: list[AppliedClaimAlias] = []
    unknown_claim_keys: list[str] = []
    grouped: dict[str, list[tuple[str, Any]]] = {}

    for raw_key, raw_value in raw_claims.items():
        canonical_key = aliases.get(raw_key, raw_key)
        if raw_key in aliases:
            applied_aliases.append(
                AppliedClaimAlias(raw_key=raw_key, canonical_key=canonical_key, raw_value=raw_value)
            )
        elif not wildcard and canonical_key not in canonical_keys:
            unknown_claim_keys.append(raw_key)
        grouped.setdefault(canonical_key, []).append((raw_key, raw_value))

    normalized_claims: dict[str, Any] = {}
    conflicts: list[ClaimAliasConflict] = []
    for canonical_key, entries in grouped.items():
        if len(entries) == 1:
            normalized_claims[canonical_key] = entries[0][1]
            continue
        values = [value for _, value in entries]
        if all(_equivalent_values(values[0], value) for value in values[1:]):
            normalized_claims[canonical_key] = _preferred_value(canonical_key, entries)
            continue
        raw_keys = [key for key, _ in entries]
        conflicts.append(
            ClaimAliasConflict(
                canonical_key=canonical_key,
                raw_keys=raw_keys,
                raw_values={key: value for key, value in entries},
                message=(
                    f"conflicting values for canonical claim key {canonical_key}: "
                    f"{', '.join(raw_keys)}"
                ),
            )
        )

    return ClaimNormalizationResult(
        invocation_id=invocation_id,
        role=role,
        raw_claims=raw_claims,
        normalized_claims=normalized_claims,
        applied_aliases=applied_aliases,
        unknown_claim_keys=unknown_claim_keys,
        conflicts=conflicts,
        valid=not conflicts,
    )


def normalize_response_payload(
    response_payload: dict[str, Any] | None,
    normalization: ClaimNormalizationResult,
) -> dict[str, Any] | None:
    if response_payload is None:
        return None
    normalized = deepcopy(response_payload)
    normalized["claims"] = deepcopy(normalization.normalized_claims)
    return normalized


def claim_normalization_metrics(results: list[ClaimNormalizationResult]) -> dict[str, float]:
    if not results:
        return {
            "claim_normalization_success_rate": 1.0,
            "alias_application_count": 0.0,
            "unknown_claim_key_count": 0.0,
            "claim_alias_conflict_count": 0.0,
        }
    return {
        "claim_normalization_success_rate": sum(1 for result in results if result.valid) / len(results),
        "alias_application_count": float(sum(len(result.applied_aliases) for result in results)),
        "unknown_claim_key_count": float(sum(len(result.unknown_claim_keys) for result in results)),
        "claim_alias_conflict_count": float(sum(len(result.conflicts) for result in results)),
    }


def claim_normalization_metric_results(results: list[ClaimNormalizationResult]) -> list[MetricResult]:
    metrics = claim_normalization_metrics(results)
    return [
        MetricResult(
            metric_id=EvaluationMetricId.CLAIM_NORMALIZATION_SUCCESS_RATE,
            score=metrics["claim_normalization_success_rate"],
            passed=metrics["claim_normalization_success_rate"] == 1.0,
        ),
        MetricResult(
            metric_id=EvaluationMetricId.ALIAS_APPLICATION_COUNT,
            score=metrics["alias_application_count"],
        ),
        MetricResult(
            metric_id=EvaluationMetricId.UNKNOWN_CLAIM_KEY_COUNT,
            score=metrics["unknown_claim_key_count"],
            passed=metrics["unknown_claim_key_count"] == 0.0,
        ),
        MetricResult(
            metric_id=EvaluationMetricId.CLAIM_ALIAS_CONFLICT_COUNT,
            score=metrics["claim_alias_conflict_count"],
            passed=metrics["claim_alias_conflict_count"] == 0.0,
        ),
    ]


def _extract_claims(response_payload: dict[str, Any] | None) -> dict[str, Any]:
    if not response_payload:
        return {}
    claims = response_payload.get("claims", {})
    if not isinstance(claims, dict):
        return {}
    return deepcopy(claims)


def _preferred_value(canonical_key: str, entries: list[tuple[str, Any]]) -> Any:
    for raw_key, value in entries:
        if raw_key == canonical_key:
            return value
    return entries[0][1]


def _equivalent_values(left: Any, right: Any) -> bool:
    if left == right:
        return True
    left_number = _number_or_none(left)
    right_number = _number_or_none(right)
    return left_number is not None and right_number is not None and left_number == right_number


def _number_or_none(value: Any) -> Decimal | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float | str):
        try:
            return Decimal(str(value))
        except InvalidOperation:
            return None
    return None
