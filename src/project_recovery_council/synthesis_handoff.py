"""Validated specialist finding handoff for live synthesis steps."""

from __future__ import annotations

from copy import deepcopy
from decimal import Decimal, InvalidOperation
from typing import Any, Literal

from pydantic import Field

from project_recovery_council.claim_normalization import ClaimNormalizationResult, ROLE_CLAIM_ALIASES
from project_recovery_council.contracts import ContractModel
from project_recovery_council.experiment_contracts import AgentInvocation, AgentRole, EvaluationMetricId, MetricResult
from project_recovery_council.fixtures import CaseBundle
from project_recovery_council.model_client import FinishStatus, ModelResult
from project_recovery_council.role_scope import RoleValidationResult


SemanticValidationStatus = Literal["passed", "failed", "not_applicable", "unavailable"]


class ValidatedFinding(ContractModel):
    case_id: str = Field(min_length=1)
    source_agent: str = Field(min_length=1)
    invocation_id: str = Field(min_length=1)
    claim_id: str = Field(min_length=1)
    canonical_claim_key: str = Field(min_length=1)
    value: Any = None
    citations: list[str] = Field(default_factory=list)
    schema_valid: bool
    normalization_valid: bool
    role_scope_valid: bool
    semantic_validation_status: SemanticValidationStatus
    assumptions: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    contradiction_status: str | None = None
    eligible_for_synthesis: bool
    exclusion_reason: str | None = None


class RecommendationAuthorizationState(ContractModel):
    recommendation_available: bool
    recommended_option_id: str | None = None
    recommendation_confidence: Literal["none", "low", "medium", "high"] = "none"
    authorization_status: Literal["not_applicable", "ready_for_authorization", "blocked_pending_human_confirmation"]
    blocking_human_request: str | None = None
    unresolved_contradictions: list[str] = Field(default_factory=list)
    approval_required: bool


class SynthesisInput(ContractModel):
    case_id: str = Field(min_length=1)
    invocation_purpose: str = Field(min_length=1)
    target_agent: str = Field(min_length=1)
    validated_findings: list[ValidatedFinding] = Field(default_factory=list)
    excluded_findings_summary: list[dict[str, Any]] = Field(default_factory=list)
    recommendation_authorization_state: RecommendationAuthorizationState
    contradiction_status: str | None = None
    unresolved_human_gates: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    citation_requirements: dict[str, list[str]] = Field(default_factory=dict)
    recommendation_authorization_semantics: list[str] = Field(default_factory=list)


class SynthesisHandoff(ContractModel):
    validated_findings: list[ValidatedFinding] = Field(default_factory=list)
    excluded_findings: list[ValidatedFinding] = Field(default_factory=list)
    synthesis_input: SynthesisInput
    recommendation_authorization_state: RecommendationAuthorizationState


FINAL_FIELD_SOURCE_KEYS: dict[str, set[str]] = {
    "projected_slip_days": {"forecast_milestone_slip_days", "projected_milestone_slip_days"},
    "unmitigated_exposure_usd": {"unmitigated_exposure_usd"},
    "mitigation_cost_usd": {"mitigation_cost_usd"},
    "gross_avoided_exposure_usd": {"gross_avoided_exposure_usd", "avoided_exposure_usd"},
    "human_confirmation_required": {"human_escalation_required", "recovery_approval_risk", "onsite_status_conflict"},
    "onsite_status_contradiction_detected": {"onsite_status_conflict", "C-ONSITE-ASSERTION", "contradiction"},
    "preferred_option_id": {"unmitigated_exposure_usd", "mitigation_cost_usd", "gross_avoided_exposure_usd"},
    "preferred_option_subject_to_approval": {
        "recovery_approval_risk",
        "onsite_status_conflict",
        "C-ONSITE-ASSERTION",
    },
}


FINAL_CITATION_REQUIREMENTS = {
    "projected_slip_days": ["SCH-DELIVERY-001"],
    "unmitigated_exposure_usd": ["SCH-DELIVERY-001", "COST-SUMMARY-001", "CTR-DELAY-001"],
    "mitigation_cost_usd": ["COST-SUMMARY-001"],
    "gross_avoided_exposure_usd": ["COST-SUMMARY-001", "CTR-DELAY-001"],
    "onsite_status_contradiction_detected": ["PRG-ONSITE-001", "SUP-NOT-ARRIVED-001", "LOG-STATUS-001"],
    "human_confirmation_required": ["PRG-ONSITE-001", "SUP-NOT-ARRIVED-001", "LOG-STATUS-001"],
    "preferred_option_id": ["COST-SUMMARY-001", "SCH-DELIVERY-001", "LOG-STATUS-001"],
    "preferred_option_subject_to_approval": [
        "COST-SUMMARY-001",
        "PRG-ONSITE-001",
        "SUP-NOT-ARRIVED-001",
        "LOG-STATUS-001",
    ],
}


def build_synthesis_handoff(
    *,
    bundle: CaseBundle,
    invocation_purpose: str,
    target_agent: str,
    invocations: list[AgentInvocation],
    normalized_responses: list[dict[str, Any]],
    normalization_results: list[ClaimNormalizationResult],
    role_results: list[RoleValidationResult],
    domain_results: list[Any],
) -> SynthesisHandoff:
    normalized_by_id = {
        item.get("invocation_id"): item.get("normalized_response")
        for item in normalized_responses
        if isinstance(item, dict)
    }
    normalization_by_id = {result.invocation_id: result for result in normalization_results}
    role_by_id = {result.invocation_id: result for result in role_results}
    domain_by_id = {getattr(result, "invocation_id", None): result for result in domain_results}

    findings: list[ValidatedFinding] = []
    for invocation in invocations:
        if invocation.agent_role not in {
            AgentRole.SCHEDULE_EXPERT.value,
            AgentRole.COMMERCIAL_EXPERT.value,
            AgentRole.EVIDENCE_AUDITOR.value,
            AgentRole.RISK_EXPERT.value,
        }:
            continue
        invocation_id = invocation.invocation_id
        normalized_payload = normalized_by_id.get(invocation_id)
        if not isinstance(normalized_payload, dict):
            normalized_payload = invocation.result.parsed_response if isinstance(invocation.result.parsed_response, dict) else {}
        claims = normalized_payload.get("claims", {})
        if not isinstance(claims, dict):
            claims = {}
        normalization = normalization_by_id.get(invocation_id)
        role_result = role_by_id.get(invocation_id)
        domain_result = domain_by_id.get(invocation_id)
        schema_valid = _schema_valid(invocation.result)
        normalization_valid = normalization.valid if normalization else False
        role_scope_valid = role_result.valid if role_result else False
        assumptions = _string_list(normalized_payload.get("assumptions", []))
        warnings = _string_list(normalized_payload.get("warnings", []))
        citations_by_key = _canonical_citations(
            role=invocation.agent_role,
            raw_payload=invocation.result.parsed_response,
            normalized_payload=normalized_payload,
            normalization=normalization,
        )
        for canonical_key, value in claims.items():
            semantic_status = _semantic_status_for_claim(domain_result, canonical_key)
            reasons = _exclusion_reasons(
                schema_valid=schema_valid,
                normalization_valid=normalization_valid,
                role_scope_valid=role_scope_valid,
                semantic_status=semantic_status,
            )
            findings.append(
                ValidatedFinding(
                    case_id=bundle.case.case_id,
                    source_agent=invocation.agent_role,
                    invocation_id=invocation_id,
                    claim_id=canonical_key,
                    canonical_claim_key=canonical_key,
                    value=value,
                    citations=citations_by_key.get(canonical_key, []),
                    schema_valid=schema_valid,
                    normalization_valid=normalization_valid,
                    role_scope_valid=role_scope_valid,
                    semantic_validation_status=semantic_status,
                    assumptions=assumptions,
                    warnings=warnings,
                    contradiction_status=_contradiction_status(canonical_key, value),
                    eligible_for_synthesis=not reasons,
                    exclusion_reason="; ".join(reasons) if reasons else None,
                )
            )

    eligible = [finding for finding in findings if finding.eligible_for_synthesis]
    excluded = [finding for finding in findings if not finding.eligible_for_synthesis]
    state = build_recommendation_authorization_state(bundle=bundle, validated_findings=eligible)
    synthesis_input = SynthesisInput(
        case_id=bundle.case.case_id,
        invocation_purpose=invocation_purpose,
        target_agent=target_agent,
        validated_findings=eligible,
        excluded_findings_summary=[
            {
                "invocation_id": finding.invocation_id,
                "source_agent": finding.source_agent,
                "canonical_claim_key": finding.canonical_claim_key,
                "exclusion_reason": finding.exclusion_reason,
            }
            for finding in excluded
        ],
        recommendation_authorization_state=state,
        contradiction_status="unresolved" if state.unresolved_contradictions else None,
        unresolved_human_gates=[state.blocking_human_request] if state.blocking_human_request else [],
        warnings=sorted({warning for finding in eligible for warning in finding.warnings}),
        citation_requirements=FINAL_CITATION_REQUIREMENTS,
        recommendation_authorization_semantics=[
            "A recovery option may be recommended when validated evidence shows it is economically or operationally preferred.",
            "Authorization may remain blocked by an unresolved human gate.",
            "Human confirmation required does not require RecoveryPlanner abstention.",
            "Abstain only when validated evidence is insufficient to form a recommendation.",
        ],
    )
    return SynthesisHandoff(
        validated_findings=eligible,
        excluded_findings=excluded,
        synthesis_input=synthesis_input,
        recommendation_authorization_state=state,
    )


def build_recommendation_authorization_state(
    *,
    bundle: CaseBundle,
    validated_findings: list[ValidatedFinding],
    resolved_human_decision_request_ids: set[str] | None = None,
) -> RecommendationAuthorizationState:
    keys = {finding.canonical_claim_key for finding in validated_findings}
    has_schedule = "forecast_milestone_slip_days" in keys or "projected_milestone_slip_days" in keys
    has_commercial = (
        {"unmitigated_exposure_usd", "mitigation_cost_usd"}.issubset(keys)
        and ("gross_avoided_exposure_usd" in keys or "avoided_exposure_usd" in keys)
    )
    contradiction = _onsite_contradiction_unresolved(validated_findings)
    human_gate = _human_gate_required(validated_findings) or contradiction
    request_id = "HDR-ONSITE-001" if human_gate and contradiction else None
    resolved_request_ids = resolved_human_decision_request_ids or set()
    blocked_by_human_gate = request_id is not None and request_id not in resolved_request_ids
    recommendation_available = has_schedule and has_commercial
    recommended_option_id = _preferred_recovery_option_id(bundle) if recommendation_available else None
    return RecommendationAuthorizationState(
        recommendation_available=recommendation_available,
        recommended_option_id=recommended_option_id,
        recommendation_confidence=(
            "high" if recommendation_available and blocked_by_human_gate else ("medium" if recommendation_available else "none")
        ),
        authorization_status=(
            "blocked_pending_human_confirmation" if blocked_by_human_gate else "ready_for_authorization"
        ),
        blocking_human_request=request_id if blocked_by_human_gate else None,
        unresolved_contradictions=["equipment_onsite_status"] if blocked_by_human_gate else [],
        approval_required=True,
    )


def merge_final_response_citations(
    *,
    response_payload: dict[str, Any] | None,
    validated_findings: list[ValidatedFinding],
    citation_requirements: dict[str, list[str]] | None = None,
) -> dict[str, Any] | None:
    """Return an accepted final response with validated claim citations merged in.

    The provider payload is not mutated. Only configured final-field citation
    requirements whose record IDs are present in validated findings are added.
    """

    if response_payload is None:
        return None
    merged = deepcopy(response_payload)
    citations = merged.get("citations", {})
    if not isinstance(citations, dict):
        citations = {}
    else:
        citations = deepcopy(citations)
    available_record_ids = {
        record_id
        for finding in validated_findings
        for record_id in finding.citations
    }
    for field, required_record_ids in (citation_requirements or FINAL_CITATION_REQUIREMENTS).items():
        if merged.get(field) is None:
            continue
        selected = [record_id for record_id in required_record_ids if record_id in available_record_ids]
        if not selected:
            continue
        existing = _string_list(citations.get(field, []))
        citations[field] = sorted(dict.fromkeys(existing + selected))
    merged["citations"] = citations
    return merged


def find_substantive_disagreements(findings: list[ValidatedFinding]) -> list[dict[str, Any]]:
    eligible = [finding for finding in findings if finding.eligible_for_synthesis]
    by_domain: dict[str, list[ValidatedFinding]] = {}
    for finding in eligible:
        by_domain.setdefault(_claim_domain(finding.canonical_claim_key), []).append(finding)
    disagreements: list[dict[str, Any]] = []
    for domain, domain_findings in by_domain.items():
        if len(domain_findings) < 2:
            continue
        values = [_comparison_value(finding.value) for finding in domain_findings]
        if domain == "equipment_onsite_status" and _onsite_values_are_human_gate_only(values):
            continue
        values = [value for value in values if value is not None]
        if len(values) < 2:
            continue
        if all(_equivalent_values(values[0], value) for value in values[1:]):
            continue
        disagreements.append(
            {
                "disagreement_id": f"DISAG-{domain.upper()}",
                "issue_domain": domain,
                "conflicting_findings": [
                    {
                        "invocation_id": finding.invocation_id,
                        "source_agent": finding.source_agent,
                        "canonical_claim_key": finding.canonical_claim_key,
                        "value": finding.value,
                        "citations": finding.citations,
                    }
                    for finding in domain_findings
                ],
            }
        )
    return disagreements


def synthesis_metrics(
    *,
    bundle: CaseBundle,
    validated_findings: list[ValidatedFinding],
    excluded_findings: list[ValidatedFinding],
    recommendation_state: RecommendationAuthorizationState,
    final_result: ModelResult | None,
) -> dict[str, float | None]:
    all_findings = validated_findings + excluded_findings
    retention_rate = len(validated_findings) / len(all_findings) if all_findings else None
    citation_rate = (
        sum(1 for finding in validated_findings if finding.citations) / len(validated_findings)
        if validated_findings
        else None
    )
    response = final_result.parsed_response if final_result and isinstance(final_result.parsed_response, dict) else {}
    source_fields = _source_supported_final_fields(validated_findings, recommendation_state)
    utilized = [field for field in source_fields if response.get(field) is not None]
    utilization_rate = len(utilized) / len(source_fields) if source_fields else None
    omission_count = float(len(set(source_fields) - set(utilized)))
    preferred_option_id = bundle.expected_results["preferred_option_id"]
    recommendation_correct = 1.0 if response.get("preferred_option_id") == preferred_option_id else 0.0
    authorization_correct = (
        1.0
        if bool(response.get("human_confirmation_required")) is True
        and bool(response.get("preferred_option_subject_to_approval")) is True
        and recommendation_state.authorization_status == "blocked_pending_human_confirmation"
        else 0.0
    )
    pending_approval_correct = (
        1.0
        if response.get("status") == "completed"
        and response.get("preferred_option_id") == preferred_option_id
        and bool(response.get("human_confirmation_required")) is True
        and bool(response.get("preferred_option_subject_to_approval")) is True
        else 0.0
    )
    return {
        "specialist_finding_retention_rate": retention_rate,
        "citation_propagation_rate": citation_rate,
        "validated_claim_utilization_rate": utilization_rate,
        "recommendation_correctness": recommendation_correct,
        "authorization_gate_correctness": authorization_correct,
        "recommendation_with_pending_approval_correctness": pending_approval_correct,
        "synthesis_omission_count": omission_count,
    }


def synthesis_metric_results(metrics: dict[str, float | None]) -> list[MetricResult]:
    return [
        MetricResult(metric_id=EvaluationMetricId.SPECIALIST_FINDING_RETENTION_RATE, score=metrics["specialist_finding_retention_rate"]),
        MetricResult(metric_id=EvaluationMetricId.CITATION_PROPAGATION_RATE, score=metrics["citation_propagation_rate"]),
        MetricResult(metric_id=EvaluationMetricId.VALIDATED_CLAIM_UTILIZATION_RATE, score=metrics["validated_claim_utilization_rate"]),
        MetricResult(metric_id=EvaluationMetricId.RECOMMENDATION_CORRECTNESS, score=metrics["recommendation_correctness"], passed=metrics["recommendation_correctness"] == 1.0),
        MetricResult(metric_id=EvaluationMetricId.AUTHORIZATION_GATE_CORRECTNESS, score=metrics["authorization_gate_correctness"], passed=metrics["authorization_gate_correctness"] == 1.0),
        MetricResult(
            metric_id=EvaluationMetricId.RECOMMENDATION_WITH_PENDING_APPROVAL_CORRECTNESS,
            score=metrics["recommendation_with_pending_approval_correctness"],
            passed=metrics["recommendation_with_pending_approval_correctness"] == 1.0,
        ),
        MetricResult(metric_id=EvaluationMetricId.SYNTHESIS_OMISSION_COUNT, score=metrics["synthesis_omission_count"], passed=metrics["synthesis_omission_count"] == 0.0),
    ]


def _schema_valid(result: ModelResult) -> bool:
    return result.finish_status == FinishStatus.COMPLETED and result.parsed_response is not None and not result.validation_errors


def _semantic_status(result: Any) -> SemanticValidationStatus:
    if result is None:
        return "unavailable"
    if getattr(result, "implemented", False) is False:
        return "not_applicable"
    if getattr(result, "valid", None) is True:
        return "passed"
    if getattr(result, "valid", None) is False:
        return "failed"
    return "unavailable"


def _semantic_status_for_claim(result: Any, canonical_key: str) -> SemanticValidationStatus:
    if result is None:
        return "unavailable"
    invalid_claim_keys = set(getattr(result, "invalid_claim_keys", []) or [])
    valid_claim_keys = set(getattr(result, "valid_claim_keys", []) or [])
    if canonical_key in invalid_claim_keys:
        return "failed"
    if canonical_key in valid_claim_keys:
        return "passed"
    return _semantic_status(result)


def _exclusion_reasons(
    *,
    schema_valid: bool,
    normalization_valid: bool,
    role_scope_valid: bool,
    semantic_status: SemanticValidationStatus,
) -> list[str]:
    reasons = []
    if not schema_valid:
        reasons.append("schema invalid")
    if not normalization_valid:
        reasons.append("claim normalization invalid")
    if not role_scope_valid:
        reasons.append("role scope invalid")
    if semantic_status == "failed":
        reasons.append("semantic validation failed")
    return reasons


def _canonical_citations(
    *,
    role: str,
    raw_payload: dict[str, Any] | None,
    normalized_payload: dict[str, Any],
    normalization: ClaimNormalizationResult | None,
) -> dict[str, list[str]]:
    citations = normalized_payload.get("citations", {})
    if not isinstance(citations, dict) and isinstance(raw_payload, dict):
        citations = raw_payload.get("citations", {})
    if not isinstance(citations, dict):
        citations = {}
    raw_claims = normalization.raw_claims if normalization else {}
    alias_map = ROLE_CLAIM_ALIASES.get(role, {})
    raw_to_canonical = {key: alias_map.get(key, key) for key in raw_claims}
    normalized_claims = normalized_payload.get("claims", {})
    if isinstance(normalized_claims, dict):
        claim_keys = normalized_claims.keys()
    else:
        claim_keys = []
    for key in claim_keys:
        raw_to_canonical.setdefault(key, key)
    result: dict[str, list[str]] = {}
    for citation_key, record_ids in citations.items():
        canonical_key = raw_to_canonical.get(str(citation_key), str(citation_key))
        result.setdefault(canonical_key, [])
        result[canonical_key].extend(_string_list(record_ids))
    claims = normalized_payload.get("claims", {})
    if isinstance(claims, dict):
        for canonical_key, value in claims.items():
            embedded = _embedded_citations(value)
            if embedded:
                result.setdefault(canonical_key, [])
                result[canonical_key].extend(embedded)
    return {key: sorted(dict.fromkeys(values)) for key, values in result.items()}


def _embedded_citations(value: Any) -> list[str]:
    if not isinstance(value, dict):
        return []
    for key in ["citations", "evidence_record_ids", "source_record_ids", "record_ids"]:
        if key in value:
            return _string_list(value[key])
    return []


def _contradiction_status(key: str, value: Any) -> str | None:
    text = f"{key} {value}".lower()
    if "contradiction" in text or "conflict" in text or "onsite" in text:
        if "unresolved" in text or "not resolved" in text or "requires" in text:
            return "unresolved"
        return "identified"
    return None


def _human_gate_required(findings: list[ValidatedFinding]) -> bool:
    for finding in findings:
        text = f"{finding.canonical_claim_key} {finding.value}".lower()
        if finding.canonical_claim_key in {
            "human_escalation_required",
            "recovery_approval_risk",
            "conflicting_onsite_status_requires_human_confirmation",
            "recovery_option_approval_blocked",
            "escalation_required_for_milestone_integrity",
        }:
            return True
        if "human confirmation" in text and (
            "required" in text or "before authorization" in text or "requires" in text
        ):
            return True
        if "approval" in text and ("blocked" in text or "pending" in text):
            return True
    return False


def _onsite_contradiction_unresolved(findings: list[ValidatedFinding]) -> bool:
    for finding in findings:
        text = f"{finding.canonical_claim_key} {finding.value}".lower()
        if finding.canonical_claim_key in {
            "onsite_status_conflict",
            "conflicting_onsite_status_requires_human_confirmation",
            "C-ONSITE-ASSERTION",
            "contradiction",
        }:
            return True
        if "onsite" in text and ("conflict" in text or "contradiction" in text):
            return True
    return False


def _source_supported_final_fields(
    findings: list[ValidatedFinding],
    recommendation_state: RecommendationAuthorizationState,
) -> list[str]:
    keys = {finding.canonical_claim_key for finding in findings}
    fields = []
    for field, source_keys in FINAL_FIELD_SOURCE_KEYS.items():
        if keys.intersection(source_keys):
            fields.append(field)
    if recommendation_state.recommendation_available:
        fields.append("preferred_option_id")
        fields.append("preferred_option_subject_to_approval")
    return sorted(set(fields))


def _claim_domain(key: str) -> str:
    if key in {
        "forecast_milestone_slip_days",
        "projected_milestone_slip_days",
        "forecast_milestone_slip_days_support",
        "C-MILESTONE-SLIP-13D",
    }:
        return "milestone_slip"
    if key in {"delivery_movement_days", "delivery_shift_days", "delivery_shift_days_support"}:
        return "delivery_movement"
    if key in {
        "onsite_status_conflict",
        "conflicting_onsite_status_requires_human_confirmation",
        "equipment_onsite_claim_conflict",
        "C-ONSITE-ASSERTION",
        "contradiction",
    }:
        return "equipment_onsite_status"
    if key in {
        "delay_exposure_usd_per_day",
        "delay_exposure_usd_per_day_support",
        "C-DELAY-EXPOSURE-15K-USD-PER-DAY",
    }:
        return "delay_exposure_rate"
    if key in {"unmitigated_exposure_usd", "C-UNMITIGATED-EXPOSURE-195K-USD"}:
        return "unmitigated_exposure"
    if key in {"mitigation_cost_usd", "C-ACCEL-COST-48K-USD"}:
        return "mitigation_cost"
    if key in {"gross_avoided_exposure_usd", "avoided_exposure_usd"}:
        return "avoided_exposure"
    return key


def _comparison_value(value: Any) -> Any:
    if isinstance(value, dict):
        for key in ["value", "days", "amount_usd", "assessment", "status", "supported"]:
            if key in value:
                if key in {"assessment", "status", "supported"} and str(value[key]).lower() in {
                    "supported",
                    "verified",
                    "true",
                    "yes",
                }:
                    return None
                return value[key]
    return value


def _onsite_values_are_human_gate_only(values: list[Any]) -> bool:
    if not values:
        return False
    text = " ".join(str(value).lower() for value in values)
    if not any(term in text for term in ["conflict", "contradiction", "unresolved", "human", "confirmation", "blocked"]):
        return False
    return not any(term in text for term in ["resolved onsite", "confirmed onsite", "no conflict", "cleared"])


def _equivalent_values(left: Any, right: Any) -> bool:
    if left == right:
        return True
    try:
        return Decimal(str(left)) == Decimal(str(right))
    except (InvalidOperation, ValueError):
        return False


def _preferred_recovery_option_id(bundle: CaseBundle) -> str | None:
    record = bundle.evidence_by_id.get("COST-SUMMARY-001")
    if record is None:
        return None
    value = record.fields.get("accelerated_logistics_option_id")
    return str(value) if value is not None else None


def _string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, (tuple, set)):
        return [str(item) for item in value]
    if value is None:
        return []
    return [str(value)]
