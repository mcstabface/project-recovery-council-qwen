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
EVIDENCE_AUDITOR_RESPONSE_SCHEMA = "project-recovery-council.qwen.evidence-auditor-response.v1"
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


class AuditSupportStatus(StrEnum):
    SUPPORTED = "supported"
    CONTRADICTED = "contradicted"
    UNSUPPORTED = "unsupported"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


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
    COMMERCIAL_SEMANTIC_COMPLIANCE_RATE = "commercial_semantic_compliance_rate"
    DELAY_EXPOSURE_RATE_CORRECTNESS = "delay_exposure_rate_correctness"
    UNMITIGATED_EXPOSURE_CORRECTNESS = "unmitigated_exposure_correctness"
    MITIGATION_COST_CORRECTNESS = "mitigation_cost_correctness"
    AVOIDED_EXPOSURE_CORRECTNESS = "avoided_exposure_correctness"
    CLAIM_NORMALIZATION_SUCCESS_RATE = "claim_normalization_success_rate"
    ALIAS_APPLICATION_COUNT = "alias_application_count"
    UNKNOWN_CLAIM_KEY_COUNT = "unknown_claim_key_count"
    CLAIM_ALIAS_CONFLICT_COUNT = "claim_alias_conflict_count"
    SPECIALIST_FINDING_RETENTION_RATE = "specialist_finding_retention_rate"
    CITATION_PROPAGATION_RATE = "citation_propagation_rate"
    VALIDATED_CLAIM_UTILIZATION_RATE = "validated_claim_utilization_rate"
    RECOMMENDATION_CORRECTNESS = "recommendation_correctness"
    AUTHORIZATION_GATE_CORRECTNESS = "authorization_gate_correctness"
    RECOMMENDATION_WITH_PENDING_APPROVAL_CORRECTNESS = "recommendation_with_pending_approval_correctness"
    SYNTHESIS_OMISSION_COUNT = "synthesis_omission_count"


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


class EvidenceAuditClaimAssessment(ContractModel):
    support_status: AuditSupportStatus
    citations: list[str] = Field(default_factory=list)
    rationale: str | None = None
    observed_value: Any = None
    expected_value: Any = None
    validation_reference: str | None = None


class EvidenceAuditorResponse(ContractModel):
    schema_version: Literal["project-recovery-council.qwen.evidence-auditor-response.v1"] = (
        EVIDENCE_AUDITOR_RESPONSE_SCHEMA
    )
    agent_role: Literal["EvidenceAuditor"] = "EvidenceAuditor"
    status: ResponseStatus
    assessments_by_agent: dict[str, dict[str, EvidenceAuditClaimAssessment]] = Field(default_factory=dict)
    claims: dict[str, dict[str, Any]] = Field(default_factory=dict)
    citations: dict[str, dict[str, list[str]]] = Field(default_factory=dict)
    unsupported_claims: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    abstention_reason: str | None = None

    @model_validator(mode="before")
    @classmethod
    def build_assessments_from_nested_claims(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        if (
            data.get("agent_role") == AgentRole.EVIDENCE_AUDITOR.value
            and data.get("schema_version") == SPECIALIST_FINDING_RESPONSE_SCHEMA
        ):
            data = dict(data)
            data["schema_version"] = EVIDENCE_AUDITOR_RESPONSE_SCHEMA
        claims = data.get("claims")
        citations = data.get("citations")
        assessments = data.get("assessments_by_agent")
        if assessments is None and claims is None:
            return data
        if assessments is None:
            if not isinstance(claims, dict):
                raise ValueError("claims must be a nested object keyed by audited agent")
            if not isinstance(citations, dict):
                raise ValueError("citations must be a nested object keyed by audited agent")
            assessments = _build_audit_assessments(claims, citations)
            data = dict(data)
            data["assessments_by_agent"] = assessments
            return data
        if claims is not None or citations is not None:
            _validate_nested_audit_keys(claims or {}, citations or {}, assessments)
        return data

    @model_validator(mode="after")
    def validate_audit_contract(self) -> "EvidenceAuditorResponse":
        known_roles = {role.value for role in AgentRole if role != AgentRole.DETERMINISTIC_ORACLE}
        unknown = sorted(set(self.assessments_by_agent) - known_roles)
        if unknown:
            raise ValueError(f"unknown audited agent roles: {unknown}")
        claim_keys = {
            agent: set(claims)
            for agent, claims in self.claims.items()
        }
        citation_keys = {
            agent: set(citations)
            for agent, citations in self.citations.items()
        }
        if claim_keys and citation_keys and claim_keys != citation_keys:
            raise ValueError("nested claims and citations must contain the same audited agents and claim keys")
        if self.status == ResponseStatus.ABSTAINED and not self.abstention_reason:
            raise ValueError("abstained evidence-auditor responses require abstention_reason")
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
    EVIDENCE_AUDITOR_RESPONSE_SCHEMA: EvidenceAuditorResponse,
    ARBITER_RESPONSE_SCHEMA: ArbiterResponse,
    LIVE_SMOKE_RESPONSE_SCHEMA: LiveSmokeResponse,
}


def _build_audit_assessments(
    claims: dict[str, Any],
    citations: dict[str, Any],
) -> dict[str, dict[str, dict[str, Any]]]:
    _validate_nested_audit_keys(claims, citations, claims)
    assessments: dict[str, dict[str, dict[str, Any]]] = {}
    for agent, agent_claims in claims.items():
        if not isinstance(agent_claims, dict):
            raise ValueError(f"claims for {agent} must be an object")
        agent_citations = citations.get(agent)
        if not isinstance(agent_citations, dict):
            raise ValueError(f"citations for {agent} must be an object")
        assessments[agent] = {}
        for claim_key, claim_value in agent_claims.items():
            if claim_key not in agent_citations:
                raise ValueError(f"missing citation entry for {agent}.{claim_key}")
            citation_list = agent_citations[claim_key]
            if not isinstance(citation_list, list):
                raise ValueError(f"citations for {agent}.{claim_key} must be a list")
            if isinstance(claim_value, dict):
                assessment = dict(claim_value)
                if "support_status" not in assessment:
                    raise ValueError(f"missing support_status for {agent}.{claim_key}")
            else:
                assessment = {"support_status": claim_value}
            assessment["citations"] = [str(record_id) for record_id in citation_list]
            assessments[agent][claim_key] = assessment
    return assessments


def _validate_nested_audit_keys(claims: Any, citations: Any, assessments: Any) -> None:
    if not isinstance(claims, dict) or not isinstance(citations, dict):
        return
    claim_agents = set(claims)
    citation_agents = set(citations)
    if claim_agents != citation_agents:
        raise ValueError("nested claims and citations must have matching audited agents")
    for agent in sorted(claim_agents):
        agent_claims = claims.get(agent)
        agent_citations = citations.get(agent)
        if not isinstance(agent_claims, dict) or not isinstance(agent_citations, dict):
            raise ValueError(f"nested claims and citations for {agent} must be objects")
        if set(agent_claims) != set(agent_citations):
            raise ValueError(f"nested claims and citations must have matching claim keys for {agent}")
    if isinstance(assessments, dict):
        assessment_agents = set(assessments)
        if claim_agents and assessment_agents != claim_agents:
            raise ValueError("assessments_by_agent must match nested claim agents")
