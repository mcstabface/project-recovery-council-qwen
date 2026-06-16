"""Workflow state contracts for deterministic local execution."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Literal

from pydantic import Field

from project_recovery_council.audit import AuditRecorder
from project_recovery_council.contracts import (
    AuditEvent,
    Contradiction,
    ContractModel,
    ExpertFinding,
    ExpertRequest,
    FinalRecommendation,
    HumanDecision,
    HumanDecisionRequest,
    RecoveryOption,
)
from project_recovery_council.fixtures import CaseBundle


class WorkflowStage(StrEnum):
    INITIALIZED = "initialized"
    VALIDATING = "validating"
    TRIAGING = "triaging"
    EXPERT_ANALYSIS = "expert_analysis"
    CONTRADICTION_REVIEW = "contradiction_review"
    AWAITING_HUMAN_DECISION = "awaiting_human_decision"
    RECOVERY_PLANNING = "recovery_planning"
    AWAITING_FINAL_APPROVAL = "awaiting_final_approval"
    COMPLETED = "completed"
    FAILED = "failed"


class WorkflowTransitionError(ValueError):
    """Raised when a workflow state transition is not allowed."""


VALID_TRANSITIONS: dict[WorkflowStage, set[WorkflowStage]] = {
    WorkflowStage.INITIALIZED: {WorkflowStage.VALIDATING, WorkflowStage.FAILED},
    WorkflowStage.VALIDATING: {WorkflowStage.TRIAGING, WorkflowStage.FAILED},
    WorkflowStage.TRIAGING: {WorkflowStage.EXPERT_ANALYSIS, WorkflowStage.FAILED},
    WorkflowStage.EXPERT_ANALYSIS: {WorkflowStage.CONTRADICTION_REVIEW, WorkflowStage.FAILED},
    WorkflowStage.CONTRADICTION_REVIEW: {
        WorkflowStage.AWAITING_HUMAN_DECISION,
        WorkflowStage.RECOVERY_PLANNING,
        WorkflowStage.FAILED,
    },
    WorkflowStage.AWAITING_HUMAN_DECISION: {WorkflowStage.RECOVERY_PLANNING, WorkflowStage.FAILED},
    WorkflowStage.RECOVERY_PLANNING: {WorkflowStage.AWAITING_FINAL_APPROVAL, WorkflowStage.FAILED},
    WorkflowStage.AWAITING_FINAL_APPROVAL: {WorkflowStage.COMPLETED, WorkflowStage.FAILED},
    WorkflowStage.COMPLETED: set(),
    WorkflowStage.FAILED: set(),
}


def validate_transition(current: WorkflowStage, target: WorkflowStage) -> None:
    if target not in VALID_TRANSITIONS[current]:
        raise WorkflowTransitionError(f"invalid workflow transition: {current.value} -> {target.value}")


class ExpertSelection(ContractModel):
    """Director-selected expert with concise routing rationale."""

    expert_role: Literal[
        "ScheduleExpert",
        "CommercialExpert",
        "EvidenceAuditor",
        "RiskExpert",
        "RecoveryPlanner",
    ]
    phase: Literal["expert_analysis", "contradiction_review", "recovery_planning"]
    rationale: str
    required: bool = True


class ExpertAttemptRecord(ContractModel):
    """Persisted record of one expert execution attempt."""

    expert_role: str
    request_id: str
    attempt: int
    status: str
    finding_id: str | None = None
    failure_reason: str | None = None
    correlation_id: str | None = None


class WorkflowFailureInfo(ContractModel):
    """Persisted failure information for a failed workflow."""

    stage: WorkflowStage
    error_type: str
    message: str


class PersistedWorkflowState(ContractModel):
    """Versioned persisted state sufficient to resume a workflow in a new process."""

    schema_version: str = "project-recovery-council.persisted-workflow-state.v1"
    run_id: str
    case_id: str
    case_path: str
    artifacts_root: str
    current_workflow_stage: WorkflowStage
    completed_stages: list[WorkflowStage] = Field(default_factory=list)
    selected_experts: list[ExpertSelection] = Field(default_factory=list)
    expert_requests: list[ExpertRequest] = Field(default_factory=list)
    expert_attempts: list[ExpertAttemptRecord] = Field(default_factory=list)
    expert_findings: list[ExpertFinding] = Field(default_factory=list)
    contradictions: list[Contradiction] = Field(default_factory=list)
    pending_human_requests: list[HumanDecisionRequest] = Field(default_factory=list)
    answered_human_requests: list[HumanDecisionRequest] = Field(default_factory=list)
    received_human_decisions: list[HumanDecision] = Field(default_factory=list)
    recovery_options: list[RecoveryOption] = Field(default_factory=list)
    draft_recommendation: FinalRecommendation | None = None
    final_recommendation: FinalRecommendation | None = None
    approval_state: Literal["not_requested", "pending", "approved", "rejected"] = "not_requested"
    audit_sequence_position: int = 0
    audit_events: list[AuditEvent] = Field(default_factory=list)
    inject_commercial_failure: bool = False
    failure_information: WorkflowFailureInfo | None = None


@dataclass(frozen=True)
class WorkflowConfig:
    """Configurable inputs for one local workflow execution."""

    case_path: Path
    artifacts_root: Path
    run_id: str
    inject_commercial_failure: bool = False
    auto_human_decision: bool = False
    auto_final_approval: bool = False
    replace_existing: bool = False


@dataclass
class WorkflowContext:
    """Mutable execution state for a single workflow run."""

    config: WorkflowConfig
    bundle: CaseBundle
    audit: AuditRecorder
    state: WorkflowStage = WorkflowStage.INITIALIZED
    selections: list[ExpertSelection] = field(default_factory=list)
    expert_requests: list[ExpertRequest] = field(default_factory=list)
    expert_findings: list[ExpertFinding] = field(default_factory=list)
    contradictions: list[Contradiction] = field(default_factory=list)
    human_decision_requests: list[HumanDecisionRequest] = field(default_factory=list)
    human_decisions: list[HumanDecision] = field(default_factory=list)
    draft_recommendation: FinalRecommendation | None = None
    final_recommendation: FinalRecommendation | None = None
    validation_issues: list[str] = field(default_factory=list)

    @property
    def audit_events(self) -> list[AuditEvent]:
        return self.audit.events
