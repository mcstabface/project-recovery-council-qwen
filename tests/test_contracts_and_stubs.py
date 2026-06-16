from pathlib import Path

import pytest
from pydantic import ValidationError

from project_recovery_council import (
    Contradiction,
    EvidenceReference,
    ExpertFinding,
    ExpertRequest,
    ExpertStatus,
    FinalRecommendation,
    load_equipment_delay_case,
)
from project_recovery_council.stubs import DeterministicDirector
from project_recovery_council.validation import build_recovery_recommendation


FIXTURE_PATH = Path(__file__).parents[1] / "sample-data" / "equipment-delay-case"


def test_expert_request_rejects_attempt_beyond_max_attempts() -> None:
    with pytest.raises(ValidationError):
        ExpertRequest(
            request_id="REQ-BAD",
            case_id="PRC-EQ-DELAY-001",
            expert_role="ScheduleExpert",
            stage="expert_analysis",
            question="Will this validate?",
            attempt=3,
            max_attempts=2,
        )


def test_expert_failure_and_retry_are_representable() -> None:
    finding = ExpertFinding(
        finding_id="FIND-FAIL-001",
        request_id="REQ-SCHEDULE-001",
        expert_role="ScheduleExpert",
        status=ExpertStatus.FAILED,
        failure_reason="deterministic test failure",
        retry_count=1,
    )

    assert finding.status == ExpertStatus.FAILED
    assert finding.retry_count == 1
    assert finding.failure_reason == "deterministic test failure"


def test_failed_expert_finding_requires_failure_reason() -> None:
    with pytest.raises(ValidationError):
        ExpertFinding(
            finding_id="FIND-FAIL-002",
            request_id="REQ-SCHEDULE-001",
            expert_role="ScheduleExpert",
            status=ExpertStatus.FAILED,
        )


def test_incomplete_and_abstained_findings_require_concise_reason() -> None:
    incomplete = ExpertFinding(
        finding_id="FIND-INCOMPLETE-001",
        request_id="REQ-EVIDENCE-001",
        expert_role="EvidenceAuditor",
        status=ExpertStatus.INCOMPLETE,
        incomplete_reason="Awaiting human confirmation of physical arrival.",
    )

    assert incomplete.incomplete_reason.startswith("Awaiting human")

    with pytest.raises(ValidationError):
        ExpertFinding(
            finding_id="FIND-ABSTAIN-001",
            request_id="REQ-RISK-001",
            expert_role="RiskExpert",
            status=ExpertStatus.ABSTAINED,
        )


def test_unresolved_contradiction_requires_human_confirmation() -> None:
    ref_a = EvidenceReference(record_id="A", source_file="a.json", locator="/a")
    ref_b = EvidenceReference(record_id="B", source_file="b.json", locator="/b")

    with pytest.raises(ValidationError):
        Contradiction(
            contradiction_id="CONTRA-BAD",
            issue="equipment_onsite_status",
            status="unresolved",
            conflicting_evidence=[ref_a, ref_b],
            summary="Conflict should require human confirmation.",
            requires_human_confirmation=False,
        )


def test_final_recommendation_contract_validation() -> None:
    bundle = load_equipment_delay_case(FIXTURE_PATH)
    recommendation = build_recovery_recommendation(bundle)

    assert recommendation.preferred_option_id == "REC-ACCEL-LOGISTICS"
    assert recommendation.status == "blocked_pending_human_confirmation"
    assert recommendation.human_decision_required is True
    assert recommendation.gross_avoided_exposure_usd == 147000
    assert recommendation.human_decision_request.blocking is True


def test_final_recommendation_cannot_be_authorized_while_human_gate_is_open() -> None:
    bundle = load_equipment_delay_case(FIXTURE_PATH)
    recommendation = build_recovery_recommendation(bundle)
    payload = recommendation.model_dump()
    payload["status"] = "authorized"

    with pytest.raises(ValidationError):
        FinalRecommendation(**payload)


def test_deterministic_director_returns_completed_stub_findings() -> None:
    bundle = load_equipment_delay_case(FIXTURE_PATH)
    findings = DeterministicDirector().evaluate_case(bundle)

    assert [finding.status for finding in findings] == [
        ExpertStatus.COMPLETED,
        ExpertStatus.COMPLETED,
        ExpertStatus.COMPLETED,
    ]
    assert all(finding.evidence for finding in findings)

