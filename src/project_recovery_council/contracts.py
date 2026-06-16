"""Typed public contracts for Project Recovery Council.

The models store conclusions, citations, warnings, assumptions, decisions,
and audit events. They intentionally exclude unrestricted reasoning traces.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ContractModel(BaseModel):
    """Base model with strict fields for durable case contracts."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class CaseStatus(StrEnum):
    OPEN = "open"
    UNDER_REVIEW = "under_review"
    WAITING_FOR_HUMAN = "waiting_for_human"
    READY_FOR_RECOMMENDATION = "ready_for_recommendation"
    CLOSED = "closed"


class CaseStage(StrEnum):
    INTAKE = "intake"
    EVIDENCE_REVIEW = "evidence_review"
    EXPERT_ANALYSIS = "expert_analysis"
    HUMAN_CONFIRMATION = "human_confirmation"
    RECOVERY_PLANNING = "recovery_planning"
    FINAL_RECOMMENDATION = "final_recommendation"


class ExpertStatus(StrEnum):
    PENDING = "pending"
    COMPLETED = "completed"
    INCOMPLETE = "incomplete"
    ABSTAINED = "abstained"
    FAILED = "failed"


class EvidenceReference(ContractModel):
    """Source-level pointer used by findings, decisions, and recommendations."""

    record_id: str = Field(min_length=1)
    source_file: str = Field(min_length=1)
    locator: str = Field(min_length=1)
    excerpt: str | None = None


class EvidenceRecord(ContractModel):
    """Compact representation of one cited source record."""

    record_id: str = Field(min_length=1)
    source_file: str = Field(min_length=1)
    record_type: str = Field(min_length=1)
    title: str = Field(min_length=1)
    record_date: date | None = None
    summary: str = Field(min_length=1)
    fields: dict[str, Any] = Field(default_factory=dict)

    def reference(self, locator: str, excerpt: str | None = None) -> EvidenceReference:
        return EvidenceReference(
            record_id=self.record_id,
            source_file=self.source_file,
            locator=locator,
            excerpt=excerpt,
        )


class ConfidenceAssessment(ContractModel):
    """Explicit confidence summary for a conclusion."""

    level: Literal["low", "medium", "high"]
    score: float = Field(ge=0.0, le=1.0)
    rationale: str = Field(min_length=1)
    evidence: list[EvidenceReference] = Field(default_factory=list)


class Contradiction(ContractModel):
    """Contradictory evidence requiring resolution before final authorization."""

    contradiction_id: str = Field(min_length=1)
    issue: str = Field(min_length=1)
    status: Literal["unresolved", "resolved", "dismissed"] = "unresolved"
    conflicting_evidence: list[EvidenceReference] = Field(min_length=2)
    summary: str = Field(min_length=1)
    requires_human_confirmation: bool = True

    @model_validator(mode="after")
    def require_human_gate_for_unresolved(self) -> "Contradiction":
        if self.status == "unresolved" and not self.requires_human_confirmation:
            raise ValueError("unresolved contradictions must require human confirmation")
        return self


class ExpertRequest(ContractModel):
    """Narrow work packet sent from the Director to a specialist."""

    request_id: str = Field(min_length=1)
    case_id: str = Field(min_length=1)
    expert_role: str = Field(min_length=1)
    stage: CaseStage
    question: str = Field(min_length=1)
    evidence_scope: list[EvidenceReference] = Field(default_factory=list)
    attempt: int = Field(default=1, ge=1)
    max_attempts: int = Field(default=2, ge=1)

    @model_validator(mode="after")
    def attempt_cannot_exceed_max(self) -> "ExpertRequest":
        if self.attempt > self.max_attempts:
            raise ValueError("attempt cannot exceed max_attempts")
        return self


class ExpertFinding(ContractModel):
    """Specialist conclusion or explicit non-conclusion."""

    finding_id: str = Field(min_length=1)
    request_id: str = Field(min_length=1)
    expert_role: str = Field(min_length=1)
    status: ExpertStatus
    conclusion: str | None = None
    confidence: ConfidenceAssessment | None = None
    evidence: list[EvidenceReference] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    incomplete_reason: str | None = None
    failure_reason: str | None = None
    retry_count: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def require_status_specific_fields(self) -> "ExpertFinding":
        if self.status == ExpertStatus.COMPLETED:
            if not self.conclusion:
                raise ValueError("completed findings require a conclusion")
            if self.confidence is None:
                raise ValueError("completed findings require confidence")
        if self.status in {ExpertStatus.INCOMPLETE, ExpertStatus.ABSTAINED}:
            if not self.incomplete_reason:
                raise ValueError("incomplete or abstained findings require incomplete_reason")
        if self.status == ExpertStatus.FAILED and not self.failure_reason:
            raise ValueError("failed findings require failure_reason")
        return self


class HumanDecisionRequest(ContractModel):
    """Blocking request for human confirmation or approval."""

    decision_request_id: str = Field(min_length=1)
    case_id: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    question: str = Field(min_length=1)
    blocking: bool = True
    contradictions: list[Contradiction] = Field(default_factory=list)
    evidence: list[EvidenceReference] = Field(default_factory=list)
    requested_by: str = Field(min_length=1)
    status: Literal["pending", "answered", "cancelled"] = "pending"


class HumanDecision(ContractModel):
    """Human answer or approval recorded in the case history."""

    decision_id: str = Field(min_length=1)
    decision_request_id: str = Field(min_length=1)
    outcome: Literal["approved", "rejected", "confirmed", "unable_to_confirm"]
    rationale: str = Field(min_length=1)
    decided_by: str = Field(min_length=1)
    decided_at: datetime
    evidence: list[EvidenceReference] = Field(default_factory=list)


class RecoveryOption(ContractModel):
    """Candidate recovery action with cited economics."""

    option_id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    description: str = Field(min_length=1)
    cost_usd: int = Field(ge=0)
    avoided_delay_days: int = Field(ge=0)
    avoided_exposure_usd: int = Field(ge=0)
    assumptions: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    required_approvals: list[str] = Field(default_factory=list)
    evidence: list[EvidenceReference] = Field(default_factory=list)


class FinalRecommendation(ContractModel):
    """Draft or authorized recovery recommendation."""

    recommendation_id: str = Field(min_length=1)
    case_id: str = Field(min_length=1)
    status: Literal["draft", "blocked_pending_human_confirmation", "authorized", "rejected"]
    summary: str = Field(min_length=1)
    preferred_option_id: str = Field(min_length=1)
    options_considered: list[RecoveryOption] = Field(min_length=1)
    unmitigated_exposure_usd: int = Field(ge=0)
    mitigation_cost_usd: int = Field(ge=0)
    gross_avoided_exposure_usd: int
    human_decision_required: bool
    assumptions: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    evidence: list[EvidenceReference] = Field(default_factory=list)
    contradictions: list[Contradiction] = Field(default_factory=list)
    human_decision_request: HumanDecisionRequest | None = None

    @model_validator(mode="after")
    def validate_recommendation(self) -> "FinalRecommendation":
        option_ids = {option.option_id for option in self.options_considered}
        if self.preferred_option_id not in option_ids:
            raise ValueError("preferred option must be present in options_considered")
        expected_avoided = self.unmitigated_exposure_usd - self.mitigation_cost_usd
        if self.gross_avoided_exposure_usd != expected_avoided:
            raise ValueError("gross avoided exposure must equal unmitigated exposure minus mitigation cost")
        if self.human_decision_required and self.status == "authorized":
            raise ValueError("recommendation cannot be authorized while a human decision is required")
        if self.human_decision_required and self.human_decision_request is None:
            raise ValueError("human_decision_request is required when human_decision_required is true")
        return self


class AuditEvent(ContractModel):
    """Append-only event for preserving case and orchestration history."""

    event_id: str = Field(min_length=1)
    case_id: str = Field(min_length=1)
    occurred_at: datetime
    actor: str = Field(min_length=1)
    action: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    evidence: list[EvidenceReference] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class RecoveryCase(ContractModel):
    """Governed project-delivery exception case."""

    case_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    status: CaseStatus
    stage: CaseStage
    opened_on: date
    summary: str = Field(min_length=1)
    evidence_records: list[EvidenceRecord] = Field(default_factory=list)
    contradictions: list[Contradiction] = Field(default_factory=list)
    human_decision_requests: list[HumanDecisionRequest] = Field(default_factory=list)
    audit_history: list[AuditEvent] = Field(default_factory=list)

