from pathlib import Path

from project_recovery_council import (
    assert_expected_results,
    build_actual_expected_results,
    calculate_delivery_shift_days,
    calculate_gross_avoided_exposure_usd,
    calculate_milestone_delay_days,
    calculate_unmitigated_exposure_usd,
    detect_onsite_contradictions,
    evaluate_human_gate_required,
    is_equipment_onsite_claim_supported,
    load_equipment_delay_case,
    validate_date_and_duration_consistency,
    validate_evidence_references,
)
from project_recovery_council.validation import build_recovery_recommendation


FIXTURE_PATH = Path(__file__).parents[1] / "sample-data" / "equipment-delay-case"


def test_required_schedule_and_cost_calculations() -> None:
    bundle = load_equipment_delay_case(FIXTURE_PATH)
    schedule = bundle.evidence_by_id["SCH-DELIVERY-001"]
    cost = bundle.evidence_by_id["COST-SUMMARY-001"]

    delay_days = calculate_milestone_delay_days(schedule)
    exposure = calculate_unmitigated_exposure_usd(
        delay_days,
        int(cost.fields["delay_exposure_usd_per_day"]),
    )

    assert calculate_delivery_shift_days(schedule) == 21
    assert delay_days == 13
    assert exposure == 195000
    assert int(cost.fields["accelerated_logistics_cost_usd"]) == 48000
    assert calculate_gross_avoided_exposure_usd(exposure, 48000) == 147000


def test_date_and_duration_consistency() -> None:
    bundle = load_equipment_delay_case(FIXTURE_PATH)

    assert validate_date_and_duration_consistency(bundle) == []


def test_onsite_contradiction_detection_and_human_gate() -> None:
    bundle = load_equipment_delay_case(FIXTURE_PATH)
    contradictions = detect_onsite_contradictions(bundle)

    assert len(contradictions) == 1
    assert contradictions[0].issue == "equipment_onsite_status"
    assert contradictions[0].requires_human_confirmation is True
    assert evaluate_human_gate_required(contradictions) is True


def test_unsupported_onsite_claim_is_rejected_until_human_confirmation() -> None:
    bundle = load_equipment_delay_case(FIXTURE_PATH)

    assert is_equipment_onsite_claim_supported(bundle) is False
    assert build_actual_expected_results(bundle)["unsupported_equipment_onsite_assertion_prohibited"] is True


def test_evidence_reference_integrity_for_contradictions_and_recommendation() -> None:
    bundle = load_equipment_delay_case(FIXTURE_PATH)
    contradiction_refs = detect_onsite_contradictions(bundle)[0].conflicting_evidence
    recommendation = build_recovery_recommendation(bundle)

    assert validate_evidence_references(bundle, contradiction_refs) == []
    assert validate_evidence_references(bundle, recommendation.evidence) == []
    assert validate_evidence_references(bundle, recommendation.human_decision_request.evidence) == []


def test_expected_result_comparison() -> None:
    actual = assert_expected_results(FIXTURE_PATH)

    assert actual["calculated_milestone_delay_days"] == 13
    assert actual["human_escalation_required"] is True

