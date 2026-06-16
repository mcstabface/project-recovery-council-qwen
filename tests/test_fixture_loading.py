from pathlib import Path

from project_recovery_council import (
    CaseStage,
    CaseStatus,
    RecoveryCase,
    load_equipment_delay_case,
)


FIXTURE_PATH = Path(__file__).parents[1] / "sample-data" / "equipment-delay-case"


def test_fixture_loading_constructs_recovery_case() -> None:
    bundle = load_equipment_delay_case(FIXTURE_PATH)

    assert isinstance(bundle.case, RecoveryCase)
    assert bundle.case.case_id == "PRC-EQ-DELAY-001"
    assert bundle.case.status == CaseStatus.WAITING_FOR_HUMAN
    assert bundle.case.stage == CaseStage.HUMAN_CONFIRMATION
    assert bundle.case.audit_history[0].action == "case_loaded"


def test_fixture_loading_collects_stable_source_record_ids() -> None:
    bundle = load_equipment_delay_case(FIXTURE_PATH)
    record_ids = set(bundle.evidence_by_id)

    assert {
        "CASE-INTAKE-001",
        "SCH-DELIVERY-001",
        "PRG-ONSITE-001",
        "SUP-NOT-ARRIVED-001",
        "LOG-STATUS-001",
        "COST-SUMMARY-001",
        "CTR-DELAY-001",
        "RISK-001",
    }.issubset(record_ids)


def test_expected_results_fixture_is_machine_readable() -> None:
    bundle = load_equipment_delay_case(FIXTURE_PATH)

    assert bundle.expected_results["calculated_milestone_delay_days"] == 13
    assert bundle.expected_results["unmitigated_exposure_usd"] == 195000
    assert bundle.expected_results["preferred_option_id"] == "REC-ACCEL-LOGISTICS"

