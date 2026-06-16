"""Platform-neutral expert execution adapter boundary."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Literal

from pydantic import Field

from project_recovery_council.contracts import (
    ContractModel,
    Contradiction,
    ExpertFinding,
    ExpertRequest,
    ExpertStatus,
    FinalRecommendation,
)
from project_recovery_council.fixtures import CaseBundle
from project_recovery_council.stubs import (
    DeterministicCommercialExpert,
    DeterministicEvidenceAuditor,
    DeterministicRecoveryPlanner,
    DeterministicRiskExpert,
    DeterministicScheduleExpert,
)


class ExpertExecutionMetadata(ContractModel):
    """Metadata suitable for external orchestration without vendor-specific fields."""

    correlation_id: str = Field(min_length=1)
    expert_name: str = Field(min_length=1)
    attempt: int = Field(ge=1)
    adapter_name: str = Field(min_length=1)
    timeout_seconds: int | None = Field(default=None, ge=1)
    external_task_id: str | None = None
    additional: dict[str, Any] = Field(default_factory=dict)


class ExpertExecutionResult(ContractModel):
    """Structured adapter result for one expert attempt."""

    expert_name: str
    request_id: str
    attempt: int = Field(ge=1)
    status: Literal["completed", "failed", "timed_out"]
    finding: ExpertFinding | None = None
    contradictions: list[Contradiction] = Field(default_factory=list)
    recommendation: FinalRecommendation | None = None
    failure_reason: str | None = None
    timeout_seconds: int | None = None
    metadata: ExpertExecutionMetadata


class ExpertAdapter(ABC):
    """Boundary between orchestration and concrete expert execution."""

    @abstractmethod
    def execute(
        self,
        expert_name: str,
        request: ExpertRequest,
        bundle: CaseBundle,
        *,
        attempt: int,
        correlation_id: str,
    ) -> ExpertExecutionResult:
        raise NotImplementedError


class DeterministicExpertAdapter(ExpertAdapter):
    """Adapter that wraps deterministic local stubs."""

    def __init__(self, *, inject_commercial_failure: bool = False) -> None:
        self.schedule_expert = DeterministicScheduleExpert()
        self.commercial_expert = DeterministicCommercialExpert(
            fail_first_attempt=inject_commercial_failure
        )
        self.risk_expert = DeterministicRiskExpert()
        self.evidence_auditor = DeterministicEvidenceAuditor()
        self.recovery_planner = DeterministicRecoveryPlanner()

    def execute(
        self,
        expert_name: str,
        request: ExpertRequest,
        bundle: CaseBundle,
        *,
        attempt: int,
        correlation_id: str,
    ) -> ExpertExecutionResult:
        metadata = ExpertExecutionMetadata(
            correlation_id=correlation_id,
            expert_name=expert_name,
            attempt=attempt,
            adapter_name="DeterministicExpertAdapter",
        )
        try:
            if expert_name == "EvidenceAuditor":
                return ExpertExecutionResult(
                    expert_name=expert_name,
                    request_id=request.request_id,
                    attempt=attempt,
                    status="completed",
                    contradictions=self.evidence_auditor.audit(bundle.case, bundle),
                    metadata=metadata,
                )
            if expert_name == "RecoveryPlanner":
                return ExpertExecutionResult(
                    expert_name=expert_name,
                    request_id=request.request_id,
                    attempt=attempt,
                    status="completed",
                    recommendation=self.recovery_planner.plan(bundle.case, bundle),
                    metadata=metadata,
                )
            finding = self._evaluate_finding_expert(expert_name, request, bundle)
        except Exception as exc:
            return ExpertExecutionResult(
                expert_name=expert_name,
                request_id=request.request_id,
                attempt=attempt,
                status="failed",
                failure_reason=str(exc),
                metadata=metadata,
            )
        if finding.status == ExpertStatus.FAILED:
            return ExpertExecutionResult(
                expert_name=expert_name,
                request_id=request.request_id,
                attempt=attempt,
                status="failed",
                finding=finding,
                failure_reason=finding.failure_reason,
                metadata=metadata,
            )
        return ExpertExecutionResult(
            expert_name=expert_name,
            request_id=request.request_id,
            attempt=attempt,
            status="completed",
            finding=finding,
            metadata=metadata,
        )

    def _evaluate_finding_expert(
        self,
        expert_name: str,
        request: ExpertRequest,
        bundle: CaseBundle,
    ) -> ExpertFinding:
        if expert_name == "ScheduleExpert":
            return self.schedule_expert.evaluate(request, bundle)
        if expert_name == "CommercialExpert":
            return self.commercial_expert.evaluate(request, bundle)
        if expert_name == "RiskExpert":
            return self.risk_expert.evaluate(request, bundle)
        raise ValueError(f"unsupported deterministic expert: {expert_name}")


class ExternalExpertAdapter(ExpertAdapter):
    """Disabled placeholder for future external orchestration integration."""

    def execute(
        self,
        expert_name: str,
        request: ExpertRequest,
        bundle: CaseBundle,
        *,
        attempt: int,
        correlation_id: str,
    ) -> ExpertExecutionResult:
        metadata = ExpertExecutionMetadata(
            correlation_id=correlation_id,
            expert_name=expert_name,
            attempt=attempt,
            adapter_name="ExternalExpertAdapter",
        )
        return ExpertExecutionResult(
            expert_name=expert_name,
            request_id=request.request_id,
            attempt=attempt,
            status="failed",
            failure_reason="External expert adapter is intentionally disabled in the local reference implementation.",
            metadata=metadata,
        )
