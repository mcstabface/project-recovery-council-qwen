"""Role evidence-access and semantic scope validation policies."""

from __future__ import annotations

import re
from enum import StrEnum
from typing import Any

from pydantic import Field

from project_recovery_council.claim_normalization import normalize_claim_keys, normalize_response_payload
from project_recovery_council.contracts import ContractModel, EvidenceRecord
from project_recovery_council.experiment_contracts import AgentRole, SpecialistFindingResponse
from project_recovery_council.fixtures import CaseBundle


class InvocationPurpose(StrEnum):
    LIVE_SMOKE = "live_smoke"
    STANDALONE_LIVE_AGENT = "standalone_live_agent"
    SINGLE_GENERALIST = "single_generalist"
    FIXED_EXPERT_CHAIN = "fixed_expert_chain"
    DYNAMIC_EXPERT_COUNCIL = "dynamic_expert_council"


class RoleScopePolicy(ContractModel):
    role: str = Field(min_length=1)
    allowed_record_types: list[str] = Field(default_factory=list)
    allowed_record_ids: list[str] = Field(default_factory=list)
    prohibited_record_types: list[str] = Field(default_factory=list)
    allowed_claim_keys: list[str] = Field(default_factory=list)
    prohibited_claim_categories: list[str] = Field(default_factory=list)
    allowed_warning_categories: list[str] = Field(default_factory=list)
    prohibited_warning_categories: list[str] = Field(default_factory=list)
    required_citation_record_types: list[str] = Field(default_factory=list)
    prohibited_citation_record_types: list[str] = Field(default_factory=list)


class RoleValidationResult(ContractModel):
    role: str = Field(min_length=1)
    invocation_id: str = Field(min_length=1)
    valid: bool
    allowed_claims: list[str] = Field(default_factory=list)
    prohibited_claims: list[str] = Field(default_factory=list)
    allowed_warnings: list[str] = Field(default_factory=list)
    prohibited_warnings: list[str] = Field(default_factory=list)
    citation_policy_violations: list[str] = Field(default_factory=list)
    evidence_scope_violations: list[str] = Field(default_factory=list)
    concise_findings: list[str] = Field(default_factory=list)


SCHEDULE_ALLOWED_CLAIMS = [
    "milestone_id",
    "delivery_baseline_date",
    "delivery_forecast_date",
    "delivery_movement_days",
    "installation_total_float_consumed_days",
    "installation_total_float_remaining_days",
    "float_consumption_status",
    "delivery_movement_direction",
    "milestone_baseline_date",
    "milestone_forecast_date_without_intervention",
    "installation_total_float_days",
    "forecast_milestone_slip_days",
    "successor_testing_activity_id",
    "successor_dependency_effect",
    "successor_testing_constraint",
    "equipment_id",
]


ROLE_SCOPE_POLICIES: dict[str, RoleScopePolicy] = {
    AgentRole.SCHEDULE_EXPERT.value: RoleScopePolicy(
        role=AgentRole.SCHEDULE_EXPERT.value,
        allowed_record_types=["case_intake", "schedule_record"],
        prohibited_record_types=[
            "cost_summary",
            "contract_excerpt",
            "supplier_correspondence",
            "logistics_status",
            "progress_report",
            "risk_register",
        ],
        allowed_claim_keys=SCHEDULE_ALLOWED_CLAIMS,
        prohibited_claim_categories=[
            "onsite_status",
            "supplier_arrival",
            "logistics_arrival",
            "commercial_exposure",
            "mitigation_cost",
            "preferred_recovery_option",
            "final_authorization",
            "human_decision",
        ],
        allowed_warning_categories=["schedule_data_dependency"],
        prohibited_warning_categories=[
            "onsite_status",
            "supplier_arrival",
            "logistics_arrival",
            "commercial_exposure",
            "recovery_option",
            "authorization",
            "human_decision",
        ],
        required_citation_record_types=["schedule_record"],
        prohibited_citation_record_types=[
            "cost_summary",
            "contract_excerpt",
            "supplier_correspondence",
            "logistics_status",
            "progress_report",
            "risk_register",
        ],
    ),
    AgentRole.COMMERCIAL_EXPERT.value: RoleScopePolicy(
        role=AgentRole.COMMERCIAL_EXPERT.value,
        allowed_record_types=["case_intake", "schedule_record", "cost_summary", "contract_excerpt"],
        prohibited_record_types=["supplier_correspondence", "logistics_status", "progress_report", "risk_register"],
        allowed_claim_keys=[
            "projected_milestone_slip_days",
            "forecast_milestone_slip_days",
            "delay_exposure_usd_per_day",
            "unmitigated_exposure_usd",
            "mitigation_cost_usd",
            "gross_avoided_exposure_usd",
        ],
        prohibited_claim_categories=["onsite_status", "supplier_arrival", "logistics_arrival", "human_decision"],
        allowed_warning_categories=["commercial_data_dependency"],
        prohibited_warning_categories=["onsite_status", "supplier_arrival", "logistics_arrival"],
        required_citation_record_types=["cost_summary", "contract_excerpt"],
        prohibited_citation_record_types=["supplier_correspondence", "logistics_status", "progress_report"],
    ),
    AgentRole.EVIDENCE_AUDITOR.value: RoleScopePolicy(
        role=AgentRole.EVIDENCE_AUDITOR.value,
        allowed_record_types=[
            "case_intake",
            "schedule_record",
            "progress_report",
            "supplier_correspondence",
            "logistics_status",
            "cost_summary",
            "contract_excerpt",
            "risk_register",
        ],
        allowed_claim_keys=[
            "claim_support",
            "contradiction",
            "unsupported_claim",
            "citation_validation",
            "C-ONSITE-ASSERTION",
            "C-MILESTONE-SLIP-13D",
            "C-DELAY-EXPOSURE-15K-USD-PER-DAY",
            "C-UNMITIGATED-EXPOSURE-195K-USD",
            "C-ACCEL-COST-48K-USD",
        ],
        allowed_warning_categories=["evidence_conflict", "unsupported_claim"],
    ),
    AgentRole.RISK_EXPERT.value: RoleScopePolicy(
        role=AgentRole.RISK_EXPERT.value,
        allowed_record_types=["case_intake", "schedule_record", "progress_report", "supplier_correspondence", "logistics_status", "risk_register"],
        prohibited_record_types=["cost_summary", "contract_excerpt"],
        allowed_claim_keys=[
            "risk",
            "human_escalation_required",
            "contradiction_risk",
            "schedule_risk",
            "onsite_status_conflict",
            "recovery_approval_risk",
            "milestone_slip_impact",
            "conflicting_onsite_status_requires_human_confirmation",
            "recovery_option_approval_blocked",
            "escalation_required_for_milestone_integrity",
        ],
        prohibited_claim_categories=["commercial_exposure", "mitigation_cost", "preferred_recovery_option"],
        allowed_warning_categories=["risk", "evidence_conflict", "human_escalation"],
        prohibited_warning_categories=["commercial_exposure", "mitigation_cost"],
        prohibited_citation_record_types=["cost_summary", "contract_excerpt"],
    ),
    AgentRole.RECOVERY_PLANNER.value: RoleScopePolicy(
        role=AgentRole.RECOVERY_PLANNER.value,
        allowed_record_types=["case_intake", "schedule_record", "cost_summary", "contract_excerpt", "progress_report", "supplier_correspondence", "logistics_status", "risk_register"],
        allowed_claim_keys=["preferred_option_id", "human_confirmation_required", "recommendation", "approval_required"],
        allowed_warning_categories=["approval", "human_gate", "evidence_conflict", "recovery_option"],
    ),
    AgentRole.DIRECTOR.value: RoleScopePolicy(
        role=AgentRole.DIRECTOR.value,
        allowed_record_types=["case_intake", "schedule_record", "progress_report", "supplier_correspondence", "logistics_status", "cost_summary", "contract_excerpt", "risk_register"],
        allowed_claim_keys=["selected_experts", "routing_rationale"],
        allowed_warning_categories=["routing_gap"],
    ),
    AgentRole.ARBITER.value: RoleScopePolicy(
        role=AgentRole.ARBITER.value,
        allowed_record_types=["case_intake", "progress_report", "supplier_correspondence", "logistics_status", "schedule_record", "cost_summary", "contract_excerpt", "risk_register"],
        allowed_claim_keys=["resolved_disagreements", "unresolved_disagreements", "preserved_provenance"],
        allowed_warning_categories=["unresolved_disagreement", "evidence_conflict"],
    ),
    AgentRole.GENERALIST.value: RoleScopePolicy(
        role=AgentRole.GENERALIST.value,
        allowed_record_types=["case_intake", "schedule_record", "progress_report", "supplier_correspondence", "logistics_status", "cost_summary", "contract_excerpt", "risk_register"],
        allowed_claim_keys=["*"],
        allowed_warning_categories=["*"],
    ),
}


CATEGORY_PATTERNS: dict[str, list[str]] = {
    "onsite_status": [r"\bonsite\b", r"on[- ]?site", r"equipment.*arrived", r"physically arrived"],
    "supplier_arrival": [r"\bsupplier\b", r"carrier", r"not arrived"],
    "logistics_arrival": [r"\blogistics\b", r"arrival status", r"actual arrival"],
    "commercial_exposure": [r"exposure", r"liquidated", r"\busd\b", r"\$"],
    "mitigation_cost": [r"mitigation cost", r"accelerated logistics cost", r"cost"],
    "preferred_recovery_option": [r"preferred option", r"recommend", r"accelerated logistics"],
    "final_authorization": [r"authori[sz]ation", r"approve", r"approval"],
    "human_decision": [r"human decision", r"human confirmation", r"confirmed by human"],
    "recovery_option": [r"recovery option", r"accelerated logistics"],
}


def get_role_scope_policy(role: str) -> RoleScopePolicy:
    try:
        return ROLE_SCOPE_POLICIES[role]
    except KeyError as exc:
        raise ValueError(f"unknown role scope policy: {role}") from exc


def select_evidence_for_role(bundle: CaseBundle, role: str) -> list[EvidenceRecord]:
    policy = get_role_scope_policy(role)
    if role == AgentRole.GENERALIST.value:
        return list(bundle.case.evidence_records)
    selected = []
    for record in bundle.case.evidence_records:
        if record.record_id in policy.allowed_record_ids or record.record_type in policy.allowed_record_types:
            selected.append(record)
    return selected


def selected_evidence_record_ids(bundle: CaseBundle, role: str) -> list[str]:
    return [record.record_id for record in select_evidence_for_role(bundle, role)]


def validate_role_scope(
    *,
    role: str,
    invocation_id: str,
    response_payload: dict[str, Any] | None,
    selected_record_ids: list[str],
    bundle: CaseBundle,
) -> RoleValidationResult:
    policy = get_role_scope_policy(role)
    records_by_id = bundle.evidence_by_id
    evidence_scope_violations = _evidence_scope_violations(policy, selected_record_ids, records_by_id)
    allowed_claims: list[str] = []
    prohibited_claims: list[str] = []
    allowed_warnings: list[str] = []
    prohibited_warnings: list[str] = []
    citation_violations: list[str] = []

    if response_payload:
        claims = response_payload.get("claims", {})
        if isinstance(claims, dict):
            for key, value in claims.items():
                text = f"{key} {value}"
                categories = _matched_categories(text, policy.prohibited_claim_categories)
                if _claim_key_allowed(policy, key) and not categories:
                    allowed_claims.append(key)
                else:
                    prohibited_claims.append(f"{key}: {', '.join(categories) if categories else 'claim key outside role policy'}")

        warnings = response_payload.get("warnings", [])
        if isinstance(warnings, list):
            for warning in warnings:
                text = str(warning)
                categories = _matched_categories(text, policy.prohibited_warning_categories)
                if categories:
                    prohibited_warnings.append(f"{text}: {', '.join(categories)}")
                else:
                    allowed_warnings.append(text)

        citations = response_payload.get("citations", {})
        if isinstance(citations, dict):
            for claim_key, record_ids in citations.items():
                if not isinstance(record_ids, list):
                    continue
                for record_id in record_ids:
                    record = records_by_id.get(str(record_id))
                    if record is None:
                        citation_violations.append(f"{claim_key}: unknown record {record_id}")
                        continue
                    if record.record_id not in selected_record_ids:
                        citation_violations.append(f"{claim_key}: cited unselected record {record.record_id}")
                    if record.record_type in policy.prohibited_citation_record_types:
                        citation_violations.append(
                            f"{claim_key}: prohibited citation {record.record_id} ({record.record_type})"
                        )

    concise_findings = []
    if prohibited_claims:
        concise_findings.append(f"prohibited claims: {len(prohibited_claims)}")
    if prohibited_warnings:
        concise_findings.append(f"prohibited warnings: {len(prohibited_warnings)}")
    if citation_violations:
        concise_findings.append(f"citation policy violations: {len(citation_violations)}")
    if evidence_scope_violations:
        concise_findings.append(f"evidence scope violations: {len(evidence_scope_violations)}")
    valid = not (prohibited_claims or prohibited_warnings or citation_violations or evidence_scope_violations)
    if valid:
        concise_findings.append("role scope compliant")
    return RoleValidationResult(
        role=role,
        invocation_id=invocation_id,
        valid=valid,
        allowed_claims=allowed_claims,
        prohibited_claims=prohibited_claims,
        allowed_warnings=allowed_warnings,
        prohibited_warnings=prohibited_warnings,
        citation_policy_violations=citation_violations,
        evidence_scope_violations=evidence_scope_violations,
        concise_findings=concise_findings,
    )


def validate_specialist_response(
    *,
    role: str,
    invocation_id: str,
    response: SpecialistFindingResponse,
    selected_record_ids: list[str],
    bundle: CaseBundle,
) -> RoleValidationResult:
    payload = response.model_dump(mode="json")
    normalization = normalize_claim_keys(
        invocation_id=invocation_id,
        role=role,
        response_payload=payload,
    )
    return validate_role_scope(
        role=role,
        invocation_id=invocation_id,
        response_payload=normalize_response_payload(payload, normalization),
        selected_record_ids=selected_record_ids,
        bundle=bundle,
    )


def role_compliance_metrics(results: list[RoleValidationResult]) -> dict[str, float]:
    total = len(results)
    if total == 0:
        return {
            "scope_compliance_rate": 1.0,
            "prohibited_claim_count": 0.0,
            "prohibited_warning_count": 0.0,
            "prohibited_citation_count": 0.0,
            "evidence_overexposure_count": 0.0,
        }
    return {
        "scope_compliance_rate": sum(1 for result in results if result.valid) / total,
        "prohibited_claim_count": float(sum(len(result.prohibited_claims) for result in results)),
        "prohibited_warning_count": float(sum(len(result.prohibited_warnings) for result in results)),
        "prohibited_citation_count": float(sum(len(result.citation_policy_violations) for result in results)),
        "evidence_overexposure_count": float(sum(len(result.evidence_scope_violations) for result in results)),
    }


def _evidence_scope_violations(
    policy: RoleScopePolicy,
    selected_record_ids: list[str],
    records_by_id: dict[str, EvidenceRecord],
) -> list[str]:
    violations = []
    for record_id in selected_record_ids:
        record = records_by_id.get(record_id)
        if record is None:
            violations.append(f"unknown selected record {record_id}")
            continue
        if record.record_type in policy.prohibited_record_types:
            violations.append(f"prohibited selected record {record.record_id} ({record.record_type})")
    return violations


def _claim_key_allowed(policy: RoleScopePolicy, key: str) -> bool:
    return "*" in policy.allowed_claim_keys or key in policy.allowed_claim_keys


def _matched_categories(text: str, categories: list[str]) -> list[str]:
    lowered = text.lower()
    matched = []
    for category in categories:
        patterns = CATEGORY_PATTERNS.get(category, [re.escape(category.replace("_", " "))])
        if any(re.search(pattern, lowered) for pattern in patterns):
            matched.append(category)
    return matched
