from pathlib import Path

import pytest

from project_recovery_council.contracts import ExpertStatus
from project_recovery_council.director import RuleBasedDirector
from project_recovery_council.runner import replay_run, run_equipment_delay_case
from project_recovery_council.serialization import read_json
from project_recovery_council.state import (
    WorkflowStage,
    WorkflowTransitionError,
    validate_transition,
)
from project_recovery_council.workflow import LocalWorkflowRunner, default_workflow_config


FIXTURE_PATH = Path(__file__).parents[1] / "sample-data" / "equipment-delay-case"


def test_valid_workflow_transitions() -> None:
    validate_transition(WorkflowStage.INITIALIZED, WorkflowStage.VALIDATING)
    validate_transition(WorkflowStage.AWAITING_HUMAN_DECISION, WorkflowStage.RECOVERY_PLANNING)
    validate_transition(WorkflowStage.AWAITING_FINAL_APPROVAL, WorkflowStage.COMPLETED)


def test_invalid_workflow_transition_is_rejected() -> None:
    with pytest.raises(WorkflowTransitionError, match="initialized -> completed"):
        validate_transition(WorkflowStage.INITIALIZED, WorkflowStage.COMPLETED)


def test_director_dynamic_expert_selection() -> None:
    config = default_workflow_config(case_path=FIXTURE_PATH, artifacts_root=Path("unused"))
    runner = LocalWorkflowRunner(config)
    context = runner._initialize_context()

    selections = RuleBasedDirector().select_experts(context.bundle)

    assert [selection.expert_role for selection in selections] == [
        "ScheduleExpert",
        "CommercialExpert",
        "EvidenceAuditor",
        "RiskExpert",
        "RecoveryPlanner",
    ]
    assert all(selection.rationale for selection in selections)


def test_human_gate_pause_prohibits_premature_final_authorization(tmp_path: Path) -> None:
    config = default_workflow_config(
        case_path=FIXTURE_PATH,
        artifacts_root=tmp_path,
        run_id="pause-test",
        auto_human_decision=False,
    )
    runner = LocalWorkflowRunner(config)

    context = runner.run_until_human_gate()

    assert context.state == WorkflowStage.AWAITING_HUMAN_DECISION
    assert context.human_decision_requests[0].status == "pending"
    assert context.final_recommendation is None
    assert context.draft_recommendation is None


def test_simulated_human_decision_resume_completes_workflow(tmp_path: Path) -> None:
    config = default_workflow_config(
        case_path=FIXTURE_PATH,
        artifacts_root=tmp_path,
        run_id="resume-test",
        auto_human_decision=False,
    )
    runner = LocalWorkflowRunner(config)
    runner.run_until_human_gate()

    context = runner.resume_with_human_decision()

    assert context.state == WorkflowStage.COMPLETED
    assert context.human_decisions[0].rationale.endswith("not onsite.")
    assert context.human_decision_requests[0].status == "answered"
    assert context.final_recommendation.status == "authorized"
    assert context.final_recommendation.human_decision_required is False


def test_ordered_audit_sequencing(tmp_path: Path) -> None:
    result = run_equipment_delay_case(
        case_path=FIXTURE_PATH,
        artifacts_root=tmp_path,
        run_id="audit-test",
    )
    sequences = [event.sequence for event in result.context.audit_events]

    assert sequences == list(range(1, len(sequences) + 1))
    assert result.context.audit_events[0].event_type == "case_created"
    assert result.context.audit_events[-1].event_type == "case_completed"


def test_commercial_failure_retry_preserves_both_attempts(tmp_path: Path) -> None:
    result = run_equipment_delay_case(
        case_path=FIXTURE_PATH,
        artifacts_root=tmp_path,
        run_id="failure-test",
        inject_commercial_failure=True,
    )

    commercial_findings = [
        finding for finding in result.context.expert_findings if finding.expert_role == "CommercialExpert"
    ]
    event_types = [event.event_type for event in result.context.audit_events]

    assert [finding.status for finding in commercial_findings] == [
        ExpertStatus.FAILED,
        ExpertStatus.COMPLETED,
    ]
    assert commercial_findings[1].retry_count == 1
    assert "expert_execution_failed" in event_types
    assert "retry_authorized" in event_types


def test_successful_final_recommendation_content(tmp_path: Path) -> None:
    result = run_equipment_delay_case(
        case_path=FIXTURE_PATH,
        artifacts_root=tmp_path,
        run_id="recommendation-test",
    )
    recommendation = result.context.final_recommendation

    assert recommendation.status == "authorized"
    assert recommendation.approval_status == "approved"
    assert recommendation.unmitigated_exposure_usd == 195000
    assert recommendation.mitigation_cost_usd == 48000
    assert recommendation.gross_avoided_exposure_usd == 147000
    assert "not onsite" in recommendation.summary
    assert recommendation.confidence.level == "high"
    assert {ref.record_id for ref in recommendation.evidence} >= {
        "SCH-DELIVERY-001",
        "COST-SUMMARY-001",
        "CTR-DELAY-001",
        "LOG-STATUS-001",
    }


def test_artifact_creation(tmp_path: Path) -> None:
    result = run_equipment_delay_case(
        case_path=FIXTURE_PATH,
        artifacts_root=tmp_path,
        run_id="artifact-test",
    )
    run_path = result.run_path

    assert run_path is not None
    for name in [
        "run-summary.json",
        "audit-events.json",
        "expert-findings.json",
        "contradictions.json",
        "human-decisions.json",
        "final-recommendation.json",
        "replay-input.json",
    ]:
        assert (run_path / name).is_file()
    assert read_json(run_path / "run-summary.json")["state"] == "completed"


def test_replay_equivalence(tmp_path: Path) -> None:
    original = run_equipment_delay_case(
        case_path=FIXTURE_PATH,
        artifacts_root=tmp_path,
        run_id="original-run",
    )

    replayed = replay_run(
        original.run_path,
        artifacts_root=tmp_path,
        run_id="different-replay-run",
    )

    assert replayed.run_path != original.run_path
    assert replayed.replay_comparison["equivalent"] is True
    assert read_json(replayed.run_path / "replay-comparison.json")["equivalent"] is True

