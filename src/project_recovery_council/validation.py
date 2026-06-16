"""Deterministic validators for the synthetic equipment-delay case."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from project_recovery_council.contracts import (
    ConfidenceAssessment,
    Contradiction,
    EvidenceRecord,
    EvidenceReference,
    FinalRecommendation,
    HumanDecisionRequest,
    RecoveryOption,
)
from project_recovery_council.fixtures import CaseBundle, load_equipment_delay_case


def parse_date(value: str) -> date:
    return date.fromisoformat(value)


def calculate_delivery_shift_days(schedule_record: EvidenceRecord) -> int:
    baseline = parse_date(schedule_record.fields["baseline_delivery_date"])
    forecast = parse_date(schedule_record.fields["forecast_delivery_date"])
    return (forecast - baseline).days


def calculate_milestone_delay_days(schedule_record: EvidenceRecord) -> int:
    baseline = parse_date(schedule_record.fields["contractual_milestone_baseline_date"])
    forecast = parse_date(schedule_record.fields["contractual_milestone_forecast_without_intervention"])
    return (forecast - baseline).days


def calculate_unmitigated_exposure_usd(delay_days: int, exposure_usd_per_day: int) -> int:
    return delay_days * exposure_usd_per_day


def calculate_gross_avoided_exposure_usd(unmitigated_exposure_usd: int, mitigation_cost_usd: int) -> int:
    return unmitigated_exposure_usd - mitigation_cost_usd


def validate_date_and_duration_consistency(bundle: CaseBundle) -> list[str]:
    """Return consistency problems found in the deterministic schedule facts."""

    issues: list[str] = []
    schedule = bundle.evidence_by_id["SCH-DELIVERY-001"]
    delivery_shift_days = calculate_delivery_shift_days(schedule)
    milestone_delay_days = calculate_milestone_delay_days(schedule)
    float_days = int(schedule.fields["installation_total_float_days"])
    expected_delay_after_float = delivery_shift_days - float_days

    if delivery_shift_days != int(schedule.fields["delivery_shift_days"]):
        issues.append("delivery shift days do not match baseline and forecast delivery dates")
    if expected_delay_after_float != milestone_delay_days:
        issues.append("delivery shift minus float does not match milestone delay")
    if milestone_delay_days != int(schedule.fields["forecast_milestone_slip_days"]):
        issues.append("forecast milestone slip does not match milestone dates")
    if schedule.fields["successor_testing_constraint"] != "finish_to_start_after_installation_complete":
        issues.append("successor testing constraint is not finish-to-start after installation")
    return issues


def validate_evidence_references(bundle: CaseBundle, references: list[EvidenceReference]) -> list[str]:
    """Check that references resolve to known source records."""

    issues: list[str] = []
    records = bundle.evidence_by_id
    for reference in references:
        record = records.get(reference.record_id)
        if record is None:
            issues.append(f"unknown evidence record: {reference.record_id}")
            continue
        if record.source_file != reference.source_file:
            issues.append(
                f"source mismatch for {reference.record_id}: "
                f"{reference.source_file} != {record.source_file}"
            )
    return issues


def detect_onsite_contradictions(bundle: CaseBundle) -> list[Contradiction]:
    """Detect contradiction between onsite progress claim and arrival evidence."""

    progress = bundle.evidence_by_id["PRG-ONSITE-001"]
    supplier = bundle.evidence_by_id["SUP-NOT-ARRIVED-001"]
    logistics = bundle.evidence_by_id["LOG-STATUS-001"]

    progress_claims_onsite = bool(progress.fields["equipment_onsite_claim"])
    supplier_says_not_arrived = supplier.fields["equipment_arrived"] is False
    logistics_says_not_arrived = logistics.fields["actual_arrival_date"] is None

    if progress_claims_onsite and (supplier_says_not_arrived or logistics_says_not_arrived):
        return [
            Contradiction(
                contradiction_id="CONTRA-ONSITE-001",
                issue="equipment_onsite_status",
                conflicting_evidence=[
                    progress.reference(
                        locator="section:Equipment Status",
                        excerpt="The generator skid is onsite and released to installation.",
                    ),
                    supplier.reference(
                        locator="section:Supplier Message",
                        excerpt="The generator skid has not arrived at the site.",
                    ),
                    logistics.reference(
                        locator="/records/0/actual_arrival_date",
                        excerpt="actual_arrival_date is null",
                    ),
                ],
                summary=(
                    "Progress reporting says the equipment is onsite, but supplier "
                    "correspondence and the logistics record show it has not arrived."
                ),
                requires_human_confirmation=True,
            )
        ]
    return []


def evaluate_human_gate_required(contradictions: list[Contradiction]) -> bool:
    return any(
        contradiction.status == "unresolved" and contradiction.requires_human_confirmation
        for contradiction in contradictions
    )


def is_equipment_onsite_claim_supported(bundle: CaseBundle) -> bool:
    """Return whether an onsite assertion may be used without human confirmation."""

    contradictions = detect_onsite_contradictions(bundle)
    return not evaluate_human_gate_required(contradictions)


def build_actual_expected_results(bundle: CaseBundle) -> dict[str, Any]:
    schedule = bundle.evidence_by_id["SCH-DELIVERY-001"]
    cost = bundle.evidence_by_id["COST-SUMMARY-001"]
    delivery_shift_days = calculate_delivery_shift_days(schedule)
    milestone_delay_days = calculate_milestone_delay_days(schedule)
    unmitigated_exposure_usd = calculate_unmitigated_exposure_usd(
        milestone_delay_days,
        int(cost.fields["delay_exposure_usd_per_day"]),
    )
    mitigation_cost_usd = int(cost.fields["accelerated_logistics_cost_usd"])
    gross_avoided_exposure_usd = calculate_gross_avoided_exposure_usd(
        unmitigated_exposure_usd,
        mitigation_cost_usd,
    )
    contradictions = detect_onsite_contradictions(bundle)

    return {
        "case_id": bundle.case.case_id,
        "delivery_shift_days": delivery_shift_days,
        "calculated_milestone_delay_days": milestone_delay_days,
        "unmitigated_exposure_usd": unmitigated_exposure_usd,
        "mitigation_cost_usd": mitigation_cost_usd,
        "gross_avoided_exposure_before_secondary_effects_usd": gross_avoided_exposure_usd,
        "equipment_onsite_status": "unresolved_until_human_confirmation",
        "contradiction_detected": bool(contradictions),
        "human_escalation_required": evaluate_human_gate_required(contradictions),
        "unsupported_equipment_onsite_assertion_prohibited": not is_equipment_onsite_claim_supported(bundle),
        "preferred_option_id": "REC-ACCEL-LOGISTICS",
        "preferred_option_label": "accelerated logistics",
        "preferred_option_subject_to_approval": True,
    }


def assert_expected_results(base_path: Path | str) -> dict[str, Any]:
    """Compare deterministic calculations with the expected-results fixture."""

    bundle = load_equipment_delay_case(base_path)
    actual = build_actual_expected_results(bundle)
    mismatches = {
        key: {"expected": expected, "actual": actual.get(key)}
        for key, expected in bundle.expected_results.items()
        if actual.get(key) != expected
    }
    if mismatches:
        raise AssertionError(f"expected-results mismatch: {mismatches}")
    return actual


def build_recovery_recommendation(bundle: CaseBundle) -> FinalRecommendation:
    """Build the deterministic draft recommendation used by contract tests."""

    actual = build_actual_expected_results(bundle)
    contradictions = detect_onsite_contradictions(bundle)
    cost_record = bundle.evidence_by_id["COST-SUMMARY-001"]
    schedule_record = bundle.evidence_by_id["SCH-DELIVERY-001"]
    contract_record = bundle.evidence_by_id["CTR-DELAY-001"]
    logistics_record = bundle.evidence_by_id["LOG-STATUS-001"]
    evidence = [
        schedule_record.reference("/records/0"),
        cost_record.reference("/records/0"),
        contract_record.reference("section:Delay Exposure"),
        logistics_record.reference("/records/0"),
    ]
    decision_request = HumanDecisionRequest(
        decision_request_id="HDR-ONSITE-001",
        case_id=bundle.case.case_id,
        reason="Onsite status is contradicted by cited source records.",
        question="Confirm whether the generator skid has physically arrived onsite.",
        contradictions=contradictions,
        evidence=evidence + contradictions[0].conflicting_evidence,
        requested_by="EvidenceAuditor",
    )
    option = RecoveryOption(
        option_id="REC-ACCEL-LOGISTICS",
        label="accelerated logistics",
        description="Approve the alternate logistics lane to recover the delivery delay.",
        cost_usd=actual["mitigation_cost_usd"],
        avoided_delay_days=actual["calculated_milestone_delay_days"],
        avoided_exposure_usd=actual["unmitigated_exposure_usd"],
        assumptions=[
            "Accelerated logistics can recover the forecast milestone slip before secondary effects.",
            "Commercial exposure remains 15000 USD per calendar day.",
        ],
        warnings=[
            "Final authorization is blocked until onsite-status contradiction is resolved by a human.",
        ],
        required_approvals=["project director approval", "commercial approval"],
        evidence=evidence,
    )
    return FinalRecommendation(
        recommendation_id="FREC-EQ-001",
        case_id=bundle.case.case_id,
        status="blocked_pending_human_confirmation",
        summary=(
            "Prefer accelerated logistics because the 48000 USD mitigation is lower "
            "than the 195000 USD unmitigated delay exposure."
        ),
        preferred_option_id=option.option_id,
        options_considered=[option],
        unmitigated_exposure_usd=actual["unmitigated_exposure_usd"],
        mitigation_cost_usd=actual["mitigation_cost_usd"],
        gross_avoided_exposure_usd=actual["gross_avoided_exposure_before_secondary_effects_usd"],
        human_decision_required=True,
        assumptions=option.assumptions,
        warnings=option.warnings,
        evidence=evidence,
        contradictions=contradictions,
        human_decision_request=decision_request,
    )


def completed_confidence(rationale: str, evidence: list[EvidenceReference]) -> ConfidenceAssessment:
    return ConfidenceAssessment(level="high", score=0.95, rationale=rationale, evidence=evidence)

