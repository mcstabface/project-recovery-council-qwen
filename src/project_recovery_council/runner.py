"""Convenience entry points for local runs, validation, and replay."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from project_recovery_council.artifacts import ArtifactInspectionResult, validate_run_artifacts
from project_recovery_council.contracts import HumanDecision
from project_recovery_council.persistence import context_from_persisted_state, load_persisted_state
from project_recovery_council.serialization import (
    compare_run_artifacts,
    read_json,
    write_json,
)
from project_recovery_council.workflow import (
    DEFAULT_ARTIFACTS_ROOT,
    DEFAULT_CASE_PATH,
    LocalWorkflowRunner,
    WorkflowRunResult,
    default_workflow_config,
    validate_fixture_bundle,
)


def run_equipment_delay_case(
    *,
    case_path: Path | str = DEFAULT_CASE_PATH,
    artifacts_root: Path | str = DEFAULT_ARTIFACTS_ROOT,
    run_id: str = "equipment-delay-standard",
    inject_commercial_failure: bool = False,
    replace_existing: bool = False,
) -> WorkflowRunResult:
    config = default_workflow_config(
        case_path=case_path,
        artifacts_root=artifacts_root,
        run_id=run_id,
        inject_commercial_failure=inject_commercial_failure,
        auto_human_decision=True,
        auto_final_approval=True,
        replace_existing=replace_existing,
    )
    return LocalWorkflowRunner(config).run(write_artifacts=True)


def start_equipment_delay_case(
    *,
    case_path: Path | str = DEFAULT_CASE_PATH,
    artifacts_root: Path | str = DEFAULT_ARTIFACTS_ROOT,
    run_id: str = "equipment-delay-paused",
    inject_commercial_failure: bool = False,
    replace_existing: bool = False,
) -> WorkflowRunResult:
    config = default_workflow_config(
        case_path=case_path,
        artifacts_root=artifacts_root,
        run_id=run_id,
        inject_commercial_failure=inject_commercial_failure,
        auto_human_decision=False,
        auto_final_approval=False,
        replace_existing=replace_existing,
    )
    runner = LocalWorkflowRunner(config)
    context = runner.run_until_human_gate()
    run_path = runner.write_artifacts(context)
    return WorkflowRunResult(context=context, run_path=run_path)


def workflow_status(run_path: Path | str) -> dict[str, Any]:
    state = load_persisted_state(run_path)
    return {
        "run_id": state.run_id,
        "case_id": state.case_id,
        "stage": state.current_workflow_stage.value,
        "pending_requests": [
            {
                "decision_request_id": request.decision_request_id,
                "question": request.question,
                "reason": request.reason,
                "status": request.status,
            }
            for request in state.pending_human_requests
        ],
        "approval_state": state.approval_state,
        "final_recommendation": state.final_recommendation is not None,
    }


def submit_decision(
    run_path: Path | str,
    *,
    request_id: str,
    decision: str,
    actor: str,
) -> WorkflowRunResult:
    state = load_persisted_state(run_path)
    context = context_from_persisted_state(state)
    runner = LocalWorkflowRunner(context.config)
    runner.context = context
    request = next(
        (item for item in context.human_decision_requests if item.decision_request_id == request_id and item.status == "pending"),
        None,
    )
    if request is None:
        raise ValueError(f"no pending request found: {request_id}")
    if decision != "equipment_not_onsite":
        raise ValueError(f"unsupported demo decision: {decision}")
    human_decision = HumanDecision(
        decision_id="HD-ONSITE-001",
        decision_request_id=request.decision_request_id,
        outcome="confirmed",
        rationale="Human decision confirms the generator skid is not onsite.",
        decided_by=actor,
        decided_at=context.audit.model_timestamp(),
        evidence=request.evidence,
    )
    context = runner.record_human_decision(human_decision)
    written = runner.write_artifacts(context)
    return WorkflowRunResult(context=context, run_path=written)


def resume_workflow(run_path: Path | str) -> WorkflowRunResult:
    state = load_persisted_state(run_path)
    context = context_from_persisted_state(state)
    runner = LocalWorkflowRunner(context.config)
    runner.context = context
    context = runner.resume_after_recorded_human_decision()
    written = runner.write_artifacts(context)
    return WorkflowRunResult(context=context, run_path=written)


def approve_workflow(run_path: Path | str, *, actor: str) -> WorkflowRunResult:
    state = load_persisted_state(run_path)
    context = context_from_persisted_state(state)
    runner = LocalWorkflowRunner(context.config)
    runner.context = context
    context = runner.approve_final(actor=actor)
    written = runner.write_artifacts(context)
    return WorkflowRunResult(context=context, run_path=written)


def inspect_run(run_path: Path | str) -> ArtifactInspectionResult:
    return validate_run_artifacts(run_path)


def demo_equipment_delay_case(
    *,
    case_path: Path | str = DEFAULT_CASE_PATH,
    artifacts_root: Path | str = DEFAULT_ARTIFACTS_ROOT,
    run_id: str = "deterministic-demo",
    inject_commercial_failure: bool = False,
    replace_existing: bool = False,
) -> dict[str, Any]:
    started = start_equipment_delay_case(
        case_path=case_path,
        artifacts_root=artifacts_root,
        run_id=run_id,
        inject_commercial_failure=inject_commercial_failure,
        replace_existing=replace_existing,
    )
    run_path = started.run_path
    submit_decision(
        run_path,
        request_id="HDR-ONSITE-001",
        decision="equipment_not_onsite",
        actor="demo-reviewer",
    )
    resume_workflow(run_path)
    approved = approve_workflow(run_path, actor="demo-approver")
    inspection = inspect_run(run_path)
    if not inspection.passed:
        raise RuntimeError(f"demo artifact inspection failed: {inspection.errors}")
    recommendation = approved.context.final_recommendation
    if recommendation is None:
        raise RuntimeError("demo completed without final recommendation")
    return {
        "run_path": Path(run_path).as_posix(),
        "projected_delay_days": recommendation.options_considered[0].avoided_delay_days,
        "unmitigated_exposure_usd": recommendation.unmitigated_exposure_usd,
        "mitigation_cost_usd": recommendation.mitigation_cost_usd,
        "gross_avoided_exposure_usd": recommendation.gross_avoided_exposure_usd,
        "contradiction_status": recommendation.contradictions[0].status if recommendation.contradictions else "none",
        "human_decision_status": approved.context.human_decision_requests[0].status if approved.context.human_decision_requests else "none",
        "final_approval_status": recommendation.approval_status,
        "inspection_passed": inspection.passed,
        "commercial_failure_injected": inject_commercial_failure,
    }


def validate_case_fixture(case_path: Path | str = DEFAULT_CASE_PATH) -> list[str]:
    return validate_fixture_bundle(case_path)


def replay_run(
    path: Path | str,
    *,
    artifacts_root: Path | str | None = None,
    run_id: str | None = None,
    replace_existing: bool = False,
) -> WorkflowRunResult:
    replay_path = Path(path)
    replay_input_path = replay_path / "replay-input.json" if replay_path.is_dir() else replay_path
    replay_input: dict[str, Any] = read_json(replay_input_path)
    original_run_path = replay_input_path.parent
    replay_run_id = run_id or f"{replay_input['run_id']}-replay"
    output_root = Path(artifacts_root) if artifacts_root is not None else original_run_path.parent
    result = run_equipment_delay_case(
        case_path=Path(replay_input["case_path"]),
        artifacts_root=output_root,
        run_id=replay_run_id,
        inject_commercial_failure=bool(replay_input["inject_commercial_failure"]),
        replace_existing=replace_existing,
    )
    if result.run_path is None:
        return result
    comparison = compare_run_artifacts(original_run_path, result.run_path)
    write_json(result.run_path / "replay-comparison.json", comparison)
    return WorkflowRunResult(
        context=result.context,
        run_path=result.run_path,
        replay_comparison=comparison,
    )
