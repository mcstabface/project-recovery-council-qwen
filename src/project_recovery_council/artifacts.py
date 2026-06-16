"""Public run artifact contracts and validators."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from pydantic import Field, TypeAdapter, ValidationError

from project_recovery_council.contracts import (
    AuditEvent,
    Contradiction,
    ContractModel,
    ExpertFinding,
    FinalRecommendation,
    HumanDecision,
    HumanDecisionRequest,
    RecoveryOption,
)
from project_recovery_council.fixtures import load_equipment_delay_case
from project_recovery_council.serialization import read_json, sha256_file
from project_recovery_council.state import PersistedWorkflowState, WorkflowStage
from project_recovery_council.validation import validate_evidence_references


ARTIFACT_CONTRACT_VERSION = "project-recovery-council.run-artifacts.v1"


class ArtifactEntry(ContractModel):
    """Manifest entry for one generated run artifact."""

    name: str = Field(min_length=1)
    relative_path: str = Field(min_length=1)
    media_type: str = "application/json"
    schema_id: str = Field(min_length=1)
    sha256: str = Field(min_length=64, max_length=64)
    generated_at: str = Field(min_length=1)
    required: bool = True


class RunArtifactManifest(ContractModel):
    """Formal manifest for inspectable workflow run artifacts."""

    artifact_contract_version: str = ARTIFACT_CONTRACT_VERSION
    run_id: str = Field(min_length=1)
    case_id: str = Field(min_length=1)
    workflow_status: WorkflowStage
    generated_at: str = Field(min_length=1)
    artifacts: list[ArtifactEntry] = Field(min_length=1)


class RunSummary(ContractModel):
    """Small summary of a workflow run."""

    schema_version: str = "project-recovery-council.run-summary.v1"
    run_id: str
    case_id: str
    state: WorkflowStage
    inject_commercial_failure: bool
    selected_experts: list[Any]
    expert_request_count: int = Field(ge=0)
    expert_finding_count: int = Field(ge=0)
    contradiction_count: int = Field(ge=0)
    human_decision_count: int = Field(ge=0)
    audit_event_count: int = Field(ge=0)
    run_path: str


class ReplayInput(ContractModel):
    """Replay input recorded with each run."""

    schema_version: str = "project-recovery-council.replay-input.v1"
    run_id: str
    case_path: str
    inject_commercial_failure: bool
    auto_human_decision: bool = False
    decisions: list[dict[str, Any]] = Field(default_factory=list)


class ReplayAcceptanceProfile(ContractModel):
    """Machine-readable replay equivalence rules."""

    schema_version: str = "project-recovery-council.replay-acceptance.v1"
    compared_fields: list[str]
    ignored_fields: list[str]
    order_sensitive_fields: list[str]
    compatibility_notes: list[str] = Field(default_factory=list)


class ArtifactInspectionResult(ContractModel):
    """Result of validating a run artifact directory."""

    run_path: str
    passed: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


LIST_ADAPTERS: dict[str, TypeAdapter[Any]] = {
    "project-recovery-council.audit-events.v1": TypeAdapter(list[AuditEvent]),
    "project-recovery-council.expert-findings.v1": TypeAdapter(list[ExpertFinding]),
    "project-recovery-council.contradictions.v1": TypeAdapter(list[Contradiction]),
    "project-recovery-council.human-decisions.v1": TypeAdapter(list[HumanDecision]),
    "project-recovery-council.human-decision-requests.v1": TypeAdapter(list[HumanDecisionRequest]),
    "project-recovery-council.recovery-options.v1": TypeAdapter(list[RecoveryOption]),
}

MODEL_ADAPTERS: dict[str, type[ContractModel]] = {
    "project-recovery-council.persisted-workflow-state.v1": PersistedWorkflowState,
    "project-recovery-council.run-summary.v1": RunSummary,
    "project-recovery-council.replay-input.v1": ReplayInput,
    "project-recovery-council.run-artifact-manifest.v1": RunArtifactManifest,
    "project-recovery-council.final-recommendation.v1": FinalRecommendation,
    "project-recovery-council.draft-recommendation.v1": FinalRecommendation,
}


def validate_run_artifacts(run_path: Path | str) -> ArtifactInspectionResult:
    root = Path(run_path)
    errors: list[str] = []
    warnings: list[str] = []
    manifest_path = root / "artifact-manifest.json"
    if not manifest_path.exists():
        return ArtifactInspectionResult(run_path=root.as_posix(), passed=False, errors=["missing artifact-manifest.json"])

    try:
        manifest = RunArtifactManifest.model_validate(read_json(manifest_path))
    except (json.JSONDecodeError, ValidationError, ValueError) as exc:
        return ArtifactInspectionResult(
            run_path=root.as_posix(),
            passed=False,
            errors=[f"invalid artifact-manifest.json: {exc}"],
        )

    state: PersistedWorkflowState | None = None
    loaded_payloads: dict[str, Any] = {}
    for entry in manifest.artifacts:
        path = root / entry.relative_path
        if entry.required and not path.exists():
            errors.append(f"missing required artifact: {entry.relative_path}")
            continue
        if not path.exists():
            continue
        if sha256_file(path) != entry.sha256:
            errors.append(f"checksum mismatch: {entry.relative_path}")
        try:
            payload = read_json(path)
        except json.JSONDecodeError as exc:
            errors.append(f"invalid JSON in {entry.relative_path}: {exc}")
            continue
        loaded_payloads[entry.relative_path] = payload
        try:
            _validate_payload(entry.schema_id, payload)
        except (ValidationError, ValueError) as exc:
            errors.append(f"schema validation failed for {entry.relative_path}: {exc}")
            continue
        if entry.schema_id == "project-recovery-council.persisted-workflow-state.v1":
            state = PersistedWorkflowState.model_validate(payload)

    if state is None:
        errors.append("missing persisted workflow state")
    else:
        errors.extend(_validate_state_consistency(root, state, loaded_payloads))

    return ArtifactInspectionResult(run_path=root.as_posix(), passed=not errors, errors=errors, warnings=warnings)


def _validate_payload(schema_id: str, payload: Any) -> None:
    if schema_id in LIST_ADAPTERS:
        LIST_ADAPTERS[schema_id].validate_python(payload)
        return
    model = MODEL_ADAPTERS.get(schema_id)
    if model is not None:
        model.model_validate(payload)
        return
    if schema_id == "project-recovery-council.nullable-final-recommendation.v1":
        if payload is not None:
            FinalRecommendation.model_validate(payload)
        return
    raise ValueError(f"unknown schema id: {schema_id}")


def _validate_state_consistency(
    root: Path,
    state: PersistedWorkflowState,
    loaded_payloads: dict[str, Any],
) -> list[str]:
    errors: list[str] = []
    if state.audit_sequence_position != len(state.audit_events):
        errors.append("audit_sequence_position does not match audit event count")
    sequences = [event.sequence for event in state.audit_events]
    if sequences != list(range(1, len(sequences) + 1)):
        errors.append("audit events are not ordered and gap-free")

    bundle = load_equipment_delay_case(state.case_path)
    evidence_refs = []
    for finding in state.expert_findings:
        evidence_refs.extend(finding.evidence)
        if finding.confidence:
            evidence_refs.extend(finding.confidence.evidence)
    for contradiction in state.contradictions:
        evidence_refs.extend(contradiction.conflicting_evidence)
    for request in state.pending_human_requests:
        evidence_refs.extend(request.evidence)
    for decision in state.received_human_decisions:
        evidence_refs.extend(decision.evidence)
    if state.draft_recommendation:
        evidence_refs.extend(state.draft_recommendation.evidence)
    if state.final_recommendation:
        evidence_refs.extend(state.final_recommendation.evidence)
    errors.extend(validate_evidence_references(bundle, evidence_refs))

    pending_count = len(state.pending_human_requests)
    if state.current_workflow_stage == WorkflowStage.AWAITING_HUMAN_DECISION and pending_count == 0:
        errors.append("awaiting_human_decision state has no pending human request")
    if state.current_workflow_stage != WorkflowStage.AWAITING_HUMAN_DECISION and pending_count > 0:
        errors.append("pending human requests exist outside awaiting_human_decision")
    if state.current_workflow_stage == WorkflowStage.AWAITING_FINAL_APPROVAL and state.approval_state != "pending":
        errors.append("awaiting_final_approval state must have pending approval_state")

    if state.current_workflow_stage == WorkflowStage.COMPLETED:
        approval_events = [event for event in state.audit_events if event.event_type == "final_approval_recorded"]
        if not state.final_recommendation:
            errors.append("completed run is missing final recommendation")
        if state.approval_state != "approved":
            errors.append("completed run does not have approved approval_state")
        if not approval_events:
            errors.append("completed run is missing final approval event")
    else:
        summary = loaded_payloads.get("run-summary.json")
        if summary and summary.get("state") == "completed":
            errors.append("incomplete run summary falsely claims completion")

    return errors
