import os
import subprocess
import sys
from pathlib import Path

import pytest

from project_recovery_council.adapters import DeterministicExpertAdapter, ExternalExpertAdapter
from project_recovery_council.artifacts import validate_run_artifacts
from project_recovery_council.fixtures import load_equipment_delay_case
from project_recovery_council.persistence import load_persisted_state
from project_recovery_council.runner import (
    approve_workflow,
    inspect_run,
    resume_workflow,
    run_equipment_delay_case,
    start_equipment_delay_case,
    submit_decision,
    workflow_status,
)
from project_recovery_council.schemas import SCHEMA_EXPORTS, export_schemas
from project_recovery_council.serialization import read_json
from project_recovery_council.state import WorkflowStage
from project_recovery_council.workflow import default_workflow_config


ROOT = Path(__file__).parents[1]
FIXTURE_PATH = ROOT / "sample-data" / "equipment-delay-case"


def cli_env() -> dict[str, str]:
    env = os.environ.copy()
    src_path = str(ROOT / "src")
    current = env.get("PYTHONPATH")
    env["PYTHONPATH"] = src_path if not current else os.pathsep.join([src_path, current])
    return env


def test_schema_export_and_catalog_completeness(tmp_path: Path) -> None:
    catalog = export_schemas(tmp_path)
    catalog_payload = read_json(tmp_path / "schema-catalog.json")

    assert len(catalog) == len(SCHEMA_EXPORTS)
    assert {item["schema_id"] for item in catalog_payload["schemas"]} >= {
        "project-recovery-council.recovery-case.v1",
        "project-recovery-council.persisted-workflow-state.v1",
        "project-recovery-council.run-summary.v1",
        "project-recovery-council.replay-input.v1",
    }
    for item in catalog_payload["schemas"]:
        assert (tmp_path / Path(item["file_path"]).name).is_file()
        assert item["compatibility_notes"]


def test_deterministic_adapter_success_and_failure_representation() -> None:
    bundle = load_equipment_delay_case(FIXTURE_PATH)
    request = default_workflow_config(case_path=FIXTURE_PATH, artifacts_root=Path("unused"))
    from project_recovery_council.contracts import CaseStage, ExpertRequest

    expert_request = ExpertRequest(
        request_id="REQ-COMMERCIAL-001",
        case_id=bundle.case.case_id,
        expert_role="CommercialExpert",
        stage=CaseStage.EXPERT_ANALYSIS,
        question="Compare mitigation cost with exposure.",
        attempt=1,
    )
    ok = DeterministicExpertAdapter().execute(
        "CommercialExpert",
        expert_request,
        bundle,
        attempt=1,
        correlation_id="corr-test",
    )
    failed = DeterministicExpertAdapter(inject_commercial_failure=True).execute(
        "CommercialExpert",
        expert_request,
        bundle,
        attempt=1,
        correlation_id="corr-fail",
    )
    external = ExternalExpertAdapter().execute(
        "CommercialExpert",
        expert_request,
        bundle,
        attempt=1,
        correlation_id="corr-external",
    )

    assert ok.status == "completed"
    assert ok.finding.status == "completed"
    assert failed.status == "failed"
    assert "Injected deterministic" in failed.failure_reason
    assert external.status == "failed"
    assert "disabled" in external.failure_reason


def test_persistent_pause_resume_lifecycle(tmp_path: Path) -> None:
    started = start_equipment_delay_case(
        case_path=FIXTURE_PATH,
        artifacts_root=tmp_path,
        run_id="persistent",
    )
    run_path = started.run_path

    assert started.context.state == WorkflowStage.AWAITING_HUMAN_DECISION
    assert workflow_status(run_path)["pending_requests"][0]["decision_request_id"] == "HDR-ONSITE-001"

    # Simulates a new process by loading from disk through runner functions.
    submit_decision(
        run_path,
        request_id="HDR-ONSITE-001",
        decision="equipment_not_onsite",
        actor="demo-reviewer",
    )
    decided_state = load_persisted_state(run_path)
    assert decided_state.received_human_decisions[0].decided_by == "demo-reviewer"
    assert decided_state.current_workflow_stage == WorkflowStage.AWAITING_HUMAN_DECISION

    resumed = resume_workflow(run_path)
    assert resumed.context.state == WorkflowStage.AWAITING_FINAL_APPROVAL
    assert resumed.context.draft_recommendation.approval_status == "pending"

    approved = approve_workflow(run_path, actor="demo-approver")
    assert approved.context.state == WorkflowStage.COMPLETED
    assert approved.context.final_recommendation.approval_status == "approved"


def test_premature_approval_and_duplicate_decision_are_rejected(tmp_path: Path) -> None:
    started = start_equipment_delay_case(
        case_path=FIXTURE_PATH,
        artifacts_root=tmp_path,
        run_id="rejects",
    )
    run_path = started.run_path

    with pytest.raises(Exception):
        approve_workflow(run_path, actor="too-soon")

    submit_decision(
        run_path,
        request_id="HDR-ONSITE-001",
        decision="equipment_not_onsite",
        actor="reviewer-one",
    )
    with pytest.raises(Exception):
        submit_decision(
            run_path,
            request_id="HDR-ONSITE-001",
            decision="equipment_not_onsite",
            actor="reviewer-two",
        )


def test_artifact_manifest_validation_and_tamper_detection(tmp_path: Path) -> None:
    result = run_equipment_delay_case(
        case_path=FIXTURE_PATH,
        artifacts_root=tmp_path,
        run_id="artifact-contract",
    )
    run_path = result.run_path
    manifest = read_json(run_path / "artifact-manifest.json")

    assert {entry["relative_path"] for entry in manifest["artifacts"]} >= {
        "workflow-state.json",
        "run-summary.json",
        "audit-events.json",
        "final-recommendation.json",
        "replay-input.json",
    }
    assert inspect_run(run_path).passed is True

    summary_path = run_path / "run-summary.json"
    summary_payload = read_json(summary_path)
    summary_payload["state"] = "completed"
    summary_path.write_text("{}\n", encoding="utf-8")

    tampered = validate_run_artifacts(run_path)
    assert tampered.passed is False
    assert any("checksum mismatch" in error for error in tampered.errors)


def test_incomplete_and_completed_run_validation(tmp_path: Path) -> None:
    incomplete = start_equipment_delay_case(
        case_path=FIXTURE_PATH,
        artifacts_root=tmp_path,
        run_id="incomplete",
    )
    complete = run_equipment_delay_case(
        case_path=FIXTURE_PATH,
        artifacts_root=tmp_path,
        run_id="complete",
    )

    assert validate_run_artifacts(incomplete.run_path).passed is True
    assert validate_run_artifacts(complete.run_path).passed is True


def test_replay_acceptance_profile_and_equivalence(tmp_path: Path) -> None:
    original = run_equipment_delay_case(
        case_path=FIXTURE_PATH,
        artifacts_root=tmp_path,
        run_id="replay-original",
    )
    from project_recovery_council.runner import replay_run

    replayed = replay_run(original.run_path, artifacts_root=tmp_path, run_id="replay-copy")

    profile = read_json(ROOT / "docs" / "REPLAY_ACCEPTANCE_PROFILE.json")
    assert replayed.replay_comparison["equivalent"] is True
    assert "selected_experts" in profile["compared_fields"]
    assert "audit_events" in profile["order_sensitive_fields"]


def test_cli_persistent_lifecycle_success_and_failure_codes(tmp_path: Path) -> None:
    run_path = tmp_path / "cli-persist"
    start = subprocess.run(
        [
            sys.executable,
            "-m",
            "project_recovery_council",
            "start",
            "--case-path",
            str(FIXTURE_PATH),
            "--artifacts-root",
            str(tmp_path),
            "--run-id",
            "cli-persist",
        ],
        cwd=ROOT,
        env=cli_env(),
        text=True,
        capture_output=True,
        check=False,
    )
    assert start.returncode == 0
    assert "awaiting_human_decision" in start.stdout

    status = subprocess.run(
        [sys.executable, "-m", "project_recovery_council", "status", str(run_path)],
        cwd=ROOT,
        env=cli_env(),
        text=True,
        capture_output=True,
        check=False,
    )
    assert status.returncode == 0
    assert "HDR-ONSITE-001" in status.stdout

    premature = subprocess.run(
        [sys.executable, "-m", "project_recovery_council", "approve", str(run_path), "--actor", "too-soon"],
        cwd=ROOT,
        env=cli_env(),
        text=True,
        capture_output=True,
        check=False,
    )
    assert premature.returncode == 1

