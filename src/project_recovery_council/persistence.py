"""Persisted workflow state conversion helpers."""

from __future__ import annotations

from pathlib import Path

from project_recovery_council.audit import AuditRecorder, DeterministicClock
from project_recovery_council.fixtures import load_equipment_delay_case
from project_recovery_council.serialization import read_json, write_json
from project_recovery_council.state import (
    ExpertAttemptRecord,
    PersistedWorkflowState,
    WorkflowConfig,
    WorkflowContext,
    WorkflowStage,
)


WORKFLOW_STATE_FILE = "workflow-state.json"


def context_to_persisted_state(context: WorkflowContext) -> PersistedWorkflowState:
    completed_stages = [
        WorkflowStage(event.metadata["to"])
        for event in context.audit_events
        if event.event_type == "workflow_stage_changed" and "to" in event.metadata
    ]
    pending_requests = [
        request for request in context.human_decision_requests if request.status == "pending"
    ]
    answered_requests = [
        request for request in context.human_decision_requests if request.status != "pending"
    ]
    recovery_options = []
    if context.draft_recommendation:
        recovery_options.extend(context.draft_recommendation.options_considered)
    elif context.final_recommendation:
        recovery_options.extend(context.final_recommendation.options_considered)
    return PersistedWorkflowState(
        run_id=context.config.run_id,
        case_id=context.bundle.case.case_id,
        case_path=context.config.case_path.as_posix(),
        artifacts_root=context.config.artifacts_root.as_posix(),
        current_workflow_stage=context.state,
        completed_stages=completed_stages,
        selected_experts=context.selections,
        expert_requests=context.expert_requests,
        expert_attempts=_expert_attempts(context),
        expert_findings=context.expert_findings,
        contradictions=context.contradictions,
        pending_human_requests=pending_requests,
        answered_human_requests=answered_requests,
        received_human_decisions=context.human_decisions,
        recovery_options=recovery_options,
        draft_recommendation=context.draft_recommendation,
        final_recommendation=context.final_recommendation,
        approval_state=_approval_state(context),
        audit_sequence_position=len(context.audit_events),
        audit_events=context.audit_events,
        inject_commercial_failure=context.config.inject_commercial_failure,
    )


def context_from_persisted_state(state: PersistedWorkflowState) -> WorkflowContext:
    bundle = load_equipment_delay_case(state.case_path)
    config = WorkflowConfig(
        case_path=Path(state.case_path),
        artifacts_root=Path(state.artifacts_root),
        run_id=state.run_id,
        inject_commercial_failure=state.inject_commercial_failure,
        auto_human_decision=False,
        auto_final_approval=False,
        replace_existing=False,
    )
    audit = AuditRecorder(
        state.case_id,
        DeterministicClock(),
        existing_events=state.audit_events,
    )
    return WorkflowContext(
        config=config,
        bundle=bundle,
        audit=audit,
        state=state.current_workflow_stage,
        selections=list(state.selected_experts),
        expert_requests=list(state.expert_requests),
        expert_findings=list(state.expert_findings),
        contradictions=list(state.contradictions),
        human_decision_requests=list(state.pending_human_requests + state.answered_human_requests),
        human_decisions=list(state.received_human_decisions),
        draft_recommendation=state.draft_recommendation,
        final_recommendation=state.final_recommendation,
    )


def load_persisted_state(run_path: Path | str) -> PersistedWorkflowState:
    path = Path(run_path) / WORKFLOW_STATE_FILE
    payload = read_json(path)
    state = PersistedWorkflowState.model_validate(payload)
    if state.schema_version != "project-recovery-council.persisted-workflow-state.v1":
        raise ValueError(f"incompatible workflow state schema version: {state.schema_version}")
    return state


def save_persisted_state(run_path: Path | str, context: WorkflowContext) -> PersistedWorkflowState:
    state = context_to_persisted_state(context)
    write_json(Path(run_path) / WORKFLOW_STATE_FILE, state)
    return state


def _expert_attempts(context: WorkflowContext) -> list[ExpertAttemptRecord]:
    attempts: list[ExpertAttemptRecord] = []
    findings_by_request = {finding.request_id: finding for finding in context.expert_findings}
    for request in context.expert_requests:
        finding = findings_by_request.get(request.request_id)
        attempts.append(
            ExpertAttemptRecord(
                expert_role=request.expert_role,
                request_id=request.request_id,
                attempt=request.attempt,
                status=finding.status.value if finding else "completed",
                finding_id=finding.finding_id if finding else None,
                failure_reason=finding.failure_reason if finding else None,
                correlation_id=f"corr-{request.request_id.lower()}",
            )
        )
    return attempts


def _approval_state(context: WorkflowContext) -> str:
    if context.final_recommendation:
        return context.final_recommendation.approval_status
    if context.draft_recommendation:
        return context.draft_recommendation.approval_status
    return "not_requested"
