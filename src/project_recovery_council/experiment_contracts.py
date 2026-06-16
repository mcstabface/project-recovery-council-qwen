"""Competition-specific contracts for Qwen Agent Society experiments."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import Field, model_validator

from project_recovery_council.contracts import ContractModel
from project_recovery_council.model_client import ModelRequest, ModelResult


RECOVERY_ANALYSIS_RESPONSE_SCHEMA = "project-recovery-council.qwen.recovery-analysis-response.v1"
DIRECTOR_ROUTING_RESPONSE_SCHEMA = "project-recovery-council.qwen.director-routing-response.v1"
SPECIALIST_FINDING_RESPONSE_SCHEMA = "project-recovery-council.qwen.specialist-finding-response.v1"
ARBITER_RESPONSE_SCHEMA = "project-recovery-council.qwen.arbiter-response.v1"
LIVE_SMOKE_RESPONSE_SCHEMA = "project-recovery-council.qwen.live-smoke-response.v1"


class ExperimentVariant(StrEnum):
    DETERMINISTIC_ORACLE = "deterministic_oracle"
    SINGLE_GENERALIST = "single_generalist"
    FIXED_EXPERT_CHAIN = "fixed_expert_chain"
    DYNAMIC_EXPERT_COUNCIL = "dynamic_expert_council"


class AgentRole(StrEnum):
    GENERALIST = "GeneralistAgent"
    DIRECTOR = "DirectorAgent"
    SCHEDULE_EXPERT = "ScheduleExpert"
    COMMERCIAL_EXPERT = "CommercialExpert"
    EVIDENCE_AUDITOR = "EvidenceAuditor"
    RISK_EXPERT = "RiskExpert"
    RECOVERY_PLANNER = "RecoveryPlanner"
    ARBITER = "ArbiterAgent"
    DETERMINISTIC_ORACLE = "DeterministicOracle"


class ResponseStatus(StrEnum):
    COMPLETED = "completed"
    ABSTAINED = "abstained"
    FAILED = "failed"


class ClaimStatus(StrEnum):
    ABSENT = "absent"
    CORRECT = "correct"
    INCORRECT = "incorrect"
    UNSUPPORTED = "unsupported"
    AMBIGUOUS = "ambiguous"


class EvaluationMetricId(StrEnum):
    REQUIRED_FACT_ACCURACY = "required_fact_accuracy"
    MONETARY_CALCULATION_ACCURACY = "monetary_calculation_accuracy"
    SCHEDULE_IMPACT_ACCURACY = "schedule_impact_accuracy"
    EVIDENCE_CITATION_PRECISION = "evidence_citation_precision"
    EVIDENCE_CITATION_RECALL = "evidence_citation_recall"
    CONTRADICTION_DETECTION = "contradiction_detection"
    UNSUPPORTED_CLAIM_COUNT = "unsupported_claim_count"
    CORRECT_HUMAN_ESCALATION = "correct_human_escalation"
    PREFERRED_RECOVERY_OPTION = "preferred_recovery_option"
    SCHEMA_VALID_RESPONSE_RATE = "schema_valid_response_rate"
    AGENT_INVOCATION_COUNT = "agent_invocation_count"
    INPUT_TOKENS = "input_tokens"
    OUTPUT_TOKENS = "output_tokens"
    TOTAL_TOKENS = "total_tokens"
    LATENCY = "latency"
    RETRY_COUNT = "retry_count"
    ESTIMATED_PROVIDER_COST = "estimated_provider_cost"
    SCOPE_COMPLIANCE_RATE = "scope_compliance_rate"
    PROHIBITED_CLAIM_COUNT = "prohibited_claim_count"
    PROHIBITED_WARNING_COUNT = "prohibited_warning_count"
    PROHIBITED_CITATION_COUNT = "prohibited_citation_count"
    EVIDENCE_OVEREXPOSURE_COUNT = "evidence_overexposure_count"
    DELIVERY_MOVEMENT_CORRECTNESS = "delivery_movement_correctness"
    FLOAT_CONSUMED_CORRECTNESS = "float_consumed_correctness"
    REMAINING_FLOAT_CORRECTNESS = "remaining_float_correctness"
    MILESTONE_SLIP_CORRECTNESS = "milestone_slip_correctness"
    MILESTONE_DATE_ARITHMETIC_CORRECTNESS = "milestone_date_arithmetic_correctness"
    SCHEDULE_SEMANTIC_COMPLIANCE_RATE = "schedule_semantic_compliance_rate"


class Disagreement(ContractModel):
    disagreement_id: str = Field(min_length=1)
    issue: str = Field(min_length=1)
    positions: list[str] = Field(min_length=2)
    evidence_record_ids: list[str] = Field(default_factory=list)
    requires_arbitration: bool = True


class RecoveryAnalysisResponse(ContractModel):
    """Structured final analysis shape used for offline evaluation."""

    schema_version: str = RECOVERY_ANALYSIS_RESPONSE_SCHEMA
    agent_role: str = Field(min_length=1)
    status: ResponseStatus
    projected_slip_days: int | None = None
    unmitigated_exposure_usd: int | None = None
    mitigation_cost_usd: int | None = None
    gross_avoided_exposure_usd: int | None = None
    onsite_status_contradiction_detected: bool | None = None
    asserted_equipment_onsite: bool | None = None
    human_confirmation_required: bool | None = None
    preferred_option_id: str | None = None
    preferred_option_subject_to_approval: bool | None = None
    citations: dict[str, list[str]] = Field(default_factory=dict)
    unsupported_claims: list[str] = Field(default_factory=list)
    ambiguous_claims: list[str] = Field(default_factory=list)
    abstention_reason: str | None = None
    arbitration_required: bool = False
    unresolved_disagreements: list[Disagreement] = Field(default_factory=list)
    concise_rationale: str | None = None

    @model_validator(mode="after")
    def require_abstention_reason(self) -> "RecoveryAnalysisResponse":
        if self.status == ResponseStatus.ABSTAINED and not self.abstention_reason:
            raise ValueError("abstained responses require abstention_reason")
        if self.status == ResponseStatus.COMPLETED and not self.concise_rationale:
            raise ValueError("completed responses require concise_rationale")
        return self


class DirectorRoutingResponse(ContractModel):
    schema_version: str = DIRECTOR_ROUTING_RESPONSE_SCHEMA
    agent_role: Literal["DirectorAgent"] = "DirectorAgent"
    status: ResponseStatus
    selected_experts: list[str] = Field(default_factory=list)
    routing_rationale: str = Field(min_length=1)
    skipped_experts: dict[str, str] = Field(default_factory=dict)
    citations: dict[str, list[str]] = Field(default_factory=dict)


class SpecialistFindingResponse(ContractModel):
    schema_version: str = SPECIALIST_FINDING_RESPONSE_SCHEMA
    agent_role: str = Field(min_length=1)
    status: ResponseStatus
    claims: dict[str, Any] = Field(default_factory=dict)
    citations: dict[str, list[str]] = Field(default_factory=dict)
    unsupported_claims: list[str] = Field(default_factory=list)
    abstention_reason: str | None = None
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def require_abstention_reason(self) -> "SpecialistFindingResponse":
        if self.status == ResponseStatus.ABSTAINED and not self.abstention_reason:
            raise ValueError("abstained specialist findings require abstention_reason")
        return self


class ArbiterResponse(ContractModel):
    schema_version: str = ARBITER_RESPONSE_SCHEMA
    agent_role: Literal["ArbiterAgent"] = "ArbiterAgent"
    status: ResponseStatus
    resolved_disagreements: list[Disagreement] = Field(default_factory=list)
    unresolved_disagreements: list[Disagreement] = Field(default_factory=list)
    preserved_provenance_record_ids: list[str] = Field(default_factory=list)
    concise_rationale: str = Field(min_length=1)


class LiveSmokeResponse(ContractModel):
    schema_version: str = LIVE_SMOKE_RESPONSE_SCHEMA
    status: Literal["ok"]
    model_identifier: str = Field(min_length=1)
    short_message: str = Field(min_length=1, max_length=200)


class ExperimentStep(ContractModel):
    sequence: int = Field(ge=0)
    step_id: str = Field(min_length=1)
    agent_role: str = Field(min_length=1)
    prompt_id: str = Field(min_length=1)
    expected_response_schema: str = Field(min_length=1)
    model_identifier: str = Field(min_length=1)
    description: str = Field(min_length=1)
    depends_on: list[str] = Field(default_factory=list)
    dynamic: bool = False
    required: bool = True


class ExecutionPlan(ContractModel):
    plan_id: str = Field(min_length=1)
    variant: ExperimentVariant
    ai_competitor: bool
    description: str = Field(min_length=1)
    steps: list[ExperimentStep] = Field(default_factory=list)

    @model_validator(mode="after")
    def require_steps_for_ai_competitors(self) -> "ExecutionPlan":
        if self.ai_competitor and not self.steps:
            raise ValueError("AI competitor plans require at least one step")
        return self


class AgentInvocation(ContractModel):
    invocation_id: str = Field(min_length=1)
    variant: ExperimentVariant
    invocation_purpose: str | None = None
    agent_role: str = Field(min_length=1)
    prompt_id: str = Field(min_length=1)
    request: ModelRequest
    result: ModelResult
    started_at: datetime | None = None
    completed_at: datetime | None = None


class ExperimentRun(ContractModel):
    schema_version: str = "project-recovery-council.qwen.experiment-run.v1"
    experiment_id: str = Field(min_length=1)
    case_id: str = Field(min_length=1)
    variant: ExperimentVariant
    execution_plan: ExecutionPlan
    invocations: list[AgentInvocation] = Field(default_factory=list)
    simulated: bool = True
    status: Literal["planned", "completed", "failed"] = "planned"


class EvaluationCase(ContractModel):
    case_id: str = Field(min_length=1)
    expected_results: dict[str, Any]
    evidence_record_ids: list[str]


class EvaluationMetric(ContractModel):
    metric_id: EvaluationMetricId
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    higher_is_better: bool = True


class MetricResult(ContractModel):
    metric_id: EvaluationMetricId
    score: float | None = None
    passed: bool | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class ClaimAssessment(ContractModel):
    claim_id: str = Field(min_length=1)
    expected_value: Any = None
    observed_value: Any = None
    status: ClaimStatus
    required_record_ids: list[str] = Field(default_factory=list)
    provided_record_ids: list[str] = Field(default_factory=list)
    notes: str | None = None


class CitationAssessment(ContractModel):
    claim_id: str = Field(min_length=1)
    required_record_ids: list[str] = Field(default_factory=list)
    provided_record_ids: list[str] = Field(default_factory=list)
    valid_record_ids: list[str] = Field(default_factory=list)
    invalid_record_ids: list[str] = Field(default_factory=list)
    precision: float
    recall: float


class ContradictionAssessment(ContractModel):
    issue: str = Field(min_length=1)
    required: bool
    detected: bool
    status: ClaimStatus
    evidence_record_ids: list[str] = Field(default_factory=list)
    human_confirmation_required: bool


class EfficiencyMetrics(ContractModel):
    agent_invocation_count: int = Field(ge=0)
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)
    latency_seconds: float | None = Field(default=None, ge=0.0)
    retry_count: int = Field(default=0, ge=0)
    estimated_provider_cost_usd: float | None = Field(default=None, ge=0.0)
    simulated_measurements: bool = False


class EvaluationReport(ContractModel):
    schema_version: str = "project-recovery-council.qwen.evaluation-report.v1"
    fixture_id: str = Field(min_length=1)
    variant: ExperimentVariant
    ai_competitor: bool
    evaluation_case: EvaluationCase
    schema_valid: bool
    malformed_response: bool
    claim_assessments: list[ClaimAssessment]
    citation_assessments: list[CitationAssessment]
    contradiction_assessment: ContradictionAssessment
    metric_results: list[MetricResult]
    efficiency_metrics: EfficiencyMetrics
    abstentions: list[str] = Field(default_factory=list)
    disagreements: list[Disagreement] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class ComparisonMetricRow(ContractModel):
    variant: ExperimentVariant
    fixture_id: str
    metric_scores: dict[str, float | None]
    schema_valid: bool
    unsupported_claim_count: int
    simulated: bool = True


class ExperimentComparison(ContractModel):
    schema_version: str = "project-recovery-council.qwen.experiment-comparison.v1"
    comparison_id: str = Field(min_length=1)
    case_id: str = Field(min_length=1)
    oracle_variant: ExperimentVariant = ExperimentVariant.DETERMINISTIC_ORACLE
    ai_competitor_variants: list[ExperimentVariant]
    rows: list[ComparisonMetricRow]
    limitations: list[str] = Field(default_factory=list)


class ExperimentConfig(ContractModel):
    schema_version: str = "project-recovery-council.qwen.experiment-config.v1"
    experiment_id: str = Field(min_length=1)
    case_id: str = Field(min_length=1)
    fixture_id: str = Field(min_length=1)
    variant: ExperimentVariant
    invocation_purpose: str | None = None
    execution_plan: ExecutionPlan
    live_provider_enabled: bool = False
    simulated_outputs: bool = True


SCHEMA_REGISTRY = {
    RECOVERY_ANALYSIS_RESPONSE_SCHEMA: RecoveryAnalysisResponse,
    DIRECTOR_ROUTING_RESPONSE_SCHEMA: DirectorRoutingResponse,
    SPECIALIST_FINDING_RESPONSE_SCHEMA: SpecialistFindingResponse,
    ARBITER_RESPONSE_SCHEMA: ArbiterResponse,
    LIVE_SMOKE_RESPONSE_SCHEMA: LiveSmokeResponse,
}
