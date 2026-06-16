"""Deterministic offline evaluation for Qwen competition responses."""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from project_recovery_council.experiment_contracts import (
    EvaluationCase,
    EvaluationMetric,
    EvaluationMetricId,
    EvaluationReport,
    ExperimentVariant,
    ClaimAssessment,
    ClaimStatus,
    CitationAssessment,
    ContradictionAssessment,
    Disagreement,
    EfficiencyMetrics,
    MetricResult,
    RecoveryAnalysisResponse,
)
from project_recovery_council.fixtures import CaseBundle
from project_recovery_council.model_client import FinishStatus, ModelResult
from project_recovery_council.role_scope import RoleValidationResult, role_compliance_metrics
from project_recovery_council.schedule_semantics import (
    ScheduleSemanticValidationResult,
    schedule_semantic_metrics,
)


CLAIM_REQUIREMENTS: dict[str, tuple[str, list[str]]] = {
    "projected_slip_days": ("calculated_milestone_delay_days", ["SCH-DELIVERY-001"]),
    "unmitigated_exposure_usd": (
        "unmitigated_exposure_usd",
        ["SCH-DELIVERY-001", "COST-SUMMARY-001", "CTR-DELAY-001"],
    ),
    "mitigation_cost_usd": ("mitigation_cost_usd", ["COST-SUMMARY-001"]),
    "gross_avoided_exposure_usd": (
        "gross_avoided_exposure_before_secondary_effects_usd",
        ["COST-SUMMARY-001", "CTR-DELAY-001"],
    ),
    "onsite_status_contradiction_detected": (
        "contradiction_detected",
        ["PRG-ONSITE-001", "SUP-NOT-ARRIVED-001", "LOG-STATUS-001"],
    ),
    "human_confirmation_required": (
        "human_escalation_required",
        ["PRG-ONSITE-001", "SUP-NOT-ARRIVED-001", "LOG-STATUS-001"],
    ),
    "preferred_option_id": ("preferred_option_id", ["COST-SUMMARY-001", "SCH-DELIVERY-001"]),
    "preferred_option_subject_to_approval": (
        "preferred_option_subject_to_approval",
        ["COST-SUMMARY-001", "PRG-ONSITE-001", "SUP-NOT-ARRIVED-001", "LOG-STATUS-001"],
    ),
}


def evaluation_metric_catalog() -> list[EvaluationMetric]:
    return [
        EvaluationMetric(
            metric_id=EvaluationMetricId.REQUIRED_FACT_ACCURACY,
            name="Required fact accuracy",
            description="Share of required non-monetary facts that are correct.",
        ),
        EvaluationMetric(
            metric_id=EvaluationMetricId.MONETARY_CALCULATION_ACCURACY,
            name="Monetary calculation accuracy",
            description="Share of required monetary calculations that are correct.",
        ),
        EvaluationMetric(
            metric_id=EvaluationMetricId.SCHEDULE_IMPACT_ACCURACY,
            name="Schedule-impact accuracy",
            description="Whether projected schedule slip is correct.",
        ),
        EvaluationMetric(
            metric_id=EvaluationMetricId.EVIDENCE_CITATION_PRECISION,
            name="Evidence citation precision",
            description="Average citation precision against stable record IDs.",
        ),
        EvaluationMetric(
            metric_id=EvaluationMetricId.EVIDENCE_CITATION_RECALL,
            name="Evidence citation recall",
            description="Average citation recall against stable record IDs.",
        ),
        EvaluationMetric(
            metric_id=EvaluationMetricId.CONTRADICTION_DETECTION,
            name="Contradiction detection",
            description="Whether onsite-status contradiction is detected.",
        ),
        EvaluationMetric(
            metric_id=EvaluationMetricId.UNSUPPORTED_CLAIM_COUNT,
            name="Unsupported claim count",
            description="Count of unsupported structured claims.",
            higher_is_better=False,
        ),
        EvaluationMetric(
            metric_id=EvaluationMetricId.CORRECT_HUMAN_ESCALATION,
            name="Correct human escalation",
            description="Whether unresolved contradiction triggers human confirmation.",
        ),
        EvaluationMetric(
            metric_id=EvaluationMetricId.PREFERRED_RECOVERY_OPTION,
            name="Preferred recovery option",
            description="Whether accelerated logistics is preferred subject to approval.",
        ),
        EvaluationMetric(
            metric_id=EvaluationMetricId.SCHEMA_VALID_RESPONSE_RATE,
            name="Schema-valid response rate",
            description="One for a schema-valid response, otherwise zero.",
        ),
        EvaluationMetric(
            metric_id=EvaluationMetricId.AGENT_INVOCATION_COUNT,
            name="Agent invocation count",
            description="Number of model invocations recorded.",
            higher_is_better=False,
        ),
        EvaluationMetric(
            metric_id=EvaluationMetricId.INPUT_TOKENS,
            name="Input tokens",
            description="Input token count when provider reports it.",
            higher_is_better=False,
        ),
        EvaluationMetric(
            metric_id=EvaluationMetricId.OUTPUT_TOKENS,
            name="Output tokens",
            description="Output token count when provider reports it.",
            higher_is_better=False,
        ),
        EvaluationMetric(
            metric_id=EvaluationMetricId.TOTAL_TOKENS,
            name="Total tokens",
            description="Total token count when provider reports it.",
            higher_is_better=False,
        ),
        EvaluationMetric(
            metric_id=EvaluationMetricId.LATENCY,
            name="Latency",
            description="Latency in seconds when provider reports it.",
            higher_is_better=False,
        ),
        EvaluationMetric(
            metric_id=EvaluationMetricId.RETRY_COUNT,
            name="Retry count",
            description="Total retry count.",
            higher_is_better=False,
        ),
        EvaluationMetric(
            metric_id=EvaluationMetricId.ESTIMATED_PROVIDER_COST,
            name="Estimated provider cost",
            description="Estimated cost only when explicit provider pricing is supplied.",
            higher_is_better=False,
        ),
        EvaluationMetric(
            metric_id=EvaluationMetricId.SCOPE_COMPLIANCE_RATE,
            name="Scope compliance rate",
            description="Share of role validation results with no scope violations.",
        ),
        EvaluationMetric(
            metric_id=EvaluationMetricId.PROHIBITED_CLAIM_COUNT,
            name="Prohibited claim count",
            description="Count of role-prohibited claims.",
            higher_is_better=False,
        ),
        EvaluationMetric(
            metric_id=EvaluationMetricId.PROHIBITED_WARNING_COUNT,
            name="Prohibited warning count",
            description="Count of role-prohibited warnings.",
            higher_is_better=False,
        ),
        EvaluationMetric(
            metric_id=EvaluationMetricId.PROHIBITED_CITATION_COUNT,
            name="Prohibited citation count",
            description="Count of citations that violate role policy.",
            higher_is_better=False,
        ),
        EvaluationMetric(
            metric_id=EvaluationMetricId.EVIDENCE_OVEREXPOSURE_COUNT,
            name="Evidence overexposure count",
            description="Count of selected evidence records outside role policy.",
            higher_is_better=False,
        ),
        EvaluationMetric(
            metric_id=EvaluationMetricId.DELIVERY_MOVEMENT_CORRECTNESS,
            name="Delivery movement correctness",
            description="Whether delivery movement matches forecast minus baseline delivery dates.",
        ),
        EvaluationMetric(
            metric_id=EvaluationMetricId.FLOAT_CONSUMED_CORRECTNESS,
            name="Float consumed correctness",
            description="Whether consumed float equals min(delivery movement, available float).",
        ),
        EvaluationMetric(
            metric_id=EvaluationMetricId.REMAINING_FLOAT_CORRECTNESS,
            name="Remaining float correctness",
            description="Whether remaining float equals max(available float minus delivery movement, zero).",
        ),
        EvaluationMetric(
            metric_id=EvaluationMetricId.MILESTONE_SLIP_CORRECTNESS,
            name="Milestone slip correctness",
            description="Whether milestone slip equals max(delivery movement minus available float, zero).",
        ),
        EvaluationMetric(
            metric_id=EvaluationMetricId.MILESTONE_DATE_ARITHMETIC_CORRECTNESS,
            name="Milestone date arithmetic correctness",
            description="Whether milestone forecast date equals baseline date plus milestone slip.",
        ),
        EvaluationMetric(
            metric_id=EvaluationMetricId.SCHEDULE_SEMANTIC_COMPLIANCE_RATE,
            name="Schedule semantic compliance rate",
            description="Share of schedule semantic validations with no deterministic arithmetic violations.",
        ),
    ]


def build_evaluation_case(bundle: CaseBundle) -> EvaluationCase:
    return EvaluationCase(
        case_id=bundle.case.case_id,
        expected_results=bundle.expected_results,
        evidence_record_ids=sorted(bundle.evidence_by_id),
    )


def evaluate_model_result(
    result: ModelResult,
    *,
    variant: ExperimentVariant | str,
    bundle: CaseBundle,
    fixture_id: str,
    invocation_results: list[ModelResult] | None = None,
    pricing_usd_per_1k_input_tokens: float | None = None,
    pricing_usd_per_1k_output_tokens: float | None = None,
) -> EvaluationReport:
    selected_variant = ExperimentVariant(variant)
    response, schema_valid, malformed, validation_errors = _coerce_response(result)
    claim_assessments = _assess_claims(response, bundle) if response else _absent_claims(bundle)
    citation_assessments = _assess_citations(response, bundle) if response else _empty_citations(bundle)
    contradiction_assessment = _assess_contradiction(response, bundle)
    efficiency = aggregate_efficiency_metrics(
        invocation_results or [result],
        pricing_usd_per_1k_input_tokens=pricing_usd_per_1k_input_tokens,
        pricing_usd_per_1k_output_tokens=pricing_usd_per_1k_output_tokens,
    )
    metrics = _build_metric_results(
        claim_assessments,
        citation_assessments,
        contradiction_assessment,
        schema_valid=schema_valid,
        efficiency=efficiency,
    )
    limitations = [
        "Offline fixtures are simulated outputs for contract testing, not empirical Qwen results.",
        "Token, latency, and cost metrics remain null unless a provider reports them or explicit pricing is supplied.",
    ]
    if validation_errors:
        limitations.extend(validation_errors)
    return EvaluationReport(
        fixture_id=fixture_id,
        variant=selected_variant,
        ai_competitor=selected_variant != ExperimentVariant.DETERMINISTIC_ORACLE,
        evaluation_case=build_evaluation_case(bundle),
        schema_valid=schema_valid,
        malformed_response=malformed,
        claim_assessments=claim_assessments,
        citation_assessments=citation_assessments,
        contradiction_assessment=contradiction_assessment,
        metric_results=metrics,
        efficiency_metrics=efficiency,
        abstentions=[response.abstention_reason] if response and response.abstention_reason else [],
        disagreements=response.unresolved_disagreements if response else [],
        limitations=limitations,
    )


def aggregate_efficiency_metrics(
    results: list[ModelResult],
    *,
    pricing_usd_per_1k_input_tokens: float | None = None,
    pricing_usd_per_1k_output_tokens: float | None = None,
) -> EfficiencyMetrics:
    input_tokens = _sum_optional([result.input_token_count for result in results])
    output_tokens = _sum_optional([result.output_token_count for result in results])
    total_tokens = _sum_optional([result.total_token_count for result in results])
    latency = _sum_optional_float([result.latency_seconds for result in results])
    retry_count = sum(result.retry_count for result in results)
    cost = None
    if (
        input_tokens is not None
        and output_tokens is not None
        and pricing_usd_per_1k_input_tokens is not None
        and pricing_usd_per_1k_output_tokens is not None
    ):
        cost = (input_tokens / 1000.0 * pricing_usd_per_1k_input_tokens) + (
            output_tokens / 1000.0 * pricing_usd_per_1k_output_tokens
        )
    return EfficiencyMetrics(
        agent_invocation_count=len(results),
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        latency_seconds=latency,
        retry_count=retry_count,
        estimated_provider_cost_usd=cost,
        simulated_measurements=any(result.simulated for result in results),
    )


def _coerce_response(result: ModelResult) -> tuple[RecoveryAnalysisResponse | None, bool, bool, list[str]]:
    if result.finish_status != FinishStatus.COMPLETED or result.parsed_response is None:
        return None, False, True, result.validation_errors
    try:
        return RecoveryAnalysisResponse.model_validate(result.parsed_response), True, False, []
    except ValidationError as exc:
        return None, False, True, [str(error) for error in exc.errors()]


def _assess_claims(response: RecoveryAnalysisResponse, bundle: CaseBundle) -> list[ClaimAssessment]:
    expected = bundle.expected_results
    assessments: list[ClaimAssessment] = []
    for claim_id, (expected_key, required_records) in CLAIM_REQUIREMENTS.items():
        expected_value = expected[expected_key]
        observed = getattr(response, claim_id)
        status = _claim_status(claim_id, observed, expected_value, response)
        assessments.append(
            ClaimAssessment(
                claim_id=claim_id,
                expected_value=expected_value,
                observed_value=observed,
                status=status,
                required_record_ids=required_records,
                provided_record_ids=response.citations.get(claim_id, []),
            )
        )

    onsite_unsupported = response.asserted_equipment_onsite is True and expected[
        "unsupported_equipment_onsite_assertion_prohibited"
    ]
    assessments.append(
        ClaimAssessment(
            claim_id="unsupported_onsite_assertion_prohibited",
            expected_value=True,
            observed_value=not onsite_unsupported,
            status=ClaimStatus.UNSUPPORTED if onsite_unsupported else ClaimStatus.CORRECT,
            required_record_ids=["PRG-ONSITE-001", "SUP-NOT-ARRIVED-001", "LOG-STATUS-001"],
            provided_record_ids=response.citations.get("asserted_equipment_onsite", []),
            notes="Onsite assertion is unsupported until human confirmation resolves contradictory records."
            if onsite_unsupported
            else None,
        )
    )
    return assessments


def _claim_status(
    claim_id: str,
    observed: Any,
    expected_value: Any,
    response: RecoveryAnalysisResponse,
) -> ClaimStatus:
    if claim_id in response.unsupported_claims:
        return ClaimStatus.UNSUPPORTED
    if claim_id in response.ambiguous_claims:
        return ClaimStatus.AMBIGUOUS
    if observed is None:
        return ClaimStatus.ABSENT
    if observed == expected_value:
        return ClaimStatus.CORRECT
    return ClaimStatus.INCORRECT


def _absent_claims(bundle: CaseBundle) -> list[ClaimAssessment]:
    assessments = []
    for claim_id, (expected_key, required_records) in CLAIM_REQUIREMENTS.items():
        assessments.append(
            ClaimAssessment(
                claim_id=claim_id,
                expected_value=bundle.expected_results[expected_key],
                observed_value=None,
                status=ClaimStatus.ABSENT,
                required_record_ids=required_records,
            )
        )
    assessments.append(
        ClaimAssessment(
            claim_id="unsupported_onsite_assertion_prohibited",
            expected_value=True,
            observed_value=None,
            status=ClaimStatus.ABSENT,
            required_record_ids=["PRG-ONSITE-001", "SUP-NOT-ARRIVED-001", "LOG-STATUS-001"],
        )
    )
    return assessments


def _assess_citations(response: RecoveryAnalysisResponse, bundle: CaseBundle) -> list[CitationAssessment]:
    known_records = set(bundle.evidence_by_id)
    assessments = []
    for claim_id, (_, required_records) in CLAIM_REQUIREMENTS.items():
        provided = response.citations.get(claim_id, [])
        assessments.append(_citation_assessment(claim_id, required_records, provided, known_records))
    return assessments


def _empty_citations(bundle: CaseBundle) -> list[CitationAssessment]:
    known_records = set(bundle.evidence_by_id)
    return [
        _citation_assessment(claim_id, required_records, [], known_records)
        for claim_id, (_, required_records) in CLAIM_REQUIREMENTS.items()
    ]


def _citation_assessment(
    claim_id: str,
    required_records: list[str],
    provided_records: list[str],
    known_records: set[str],
) -> CitationAssessment:
    valid = [record_id for record_id in provided_records if record_id in known_records]
    invalid = [record_id for record_id in provided_records if record_id not in known_records]
    precision = len(valid) / len(provided_records) if provided_records else 0.0
    recall = len(set(valid).intersection(required_records)) / len(required_records) if required_records else 1.0
    return CitationAssessment(
        claim_id=claim_id,
        required_record_ids=required_records,
        provided_record_ids=provided_records,
        valid_record_ids=valid,
        invalid_record_ids=invalid,
        precision=precision,
        recall=recall,
    )


def _assess_contradiction(
    response: RecoveryAnalysisResponse | None,
    bundle: CaseBundle,
) -> ContradictionAssessment:
    required = bool(bundle.expected_results["contradiction_detected"])
    detected = bool(response.onsite_status_contradiction_detected) if response else False
    human_required = bool(response.human_confirmation_required) if response else False
    status = ClaimStatus.CORRECT if detected == required else ClaimStatus.INCORRECT
    return ContradictionAssessment(
        issue="equipment_onsite_status",
        required=required,
        detected=detected,
        status=status,
        evidence_record_ids=["PRG-ONSITE-001", "SUP-NOT-ARRIVED-001", "LOG-STATUS-001"],
        human_confirmation_required=human_required,
    )


def _build_metric_results(
    claims: list[ClaimAssessment],
    citations: list[CitationAssessment],
    contradiction: ContradictionAssessment,
    *,
    schema_valid: bool,
    efficiency: EfficiencyMetrics,
) -> list[MetricResult]:
    by_id = {claim.claim_id: claim for claim in claims}
    required_fact_ids = [
        "onsite_status_contradiction_detected",
        "human_confirmation_required",
        "preferred_option_id",
        "preferred_option_subject_to_approval",
        "unsupported_onsite_assertion_prohibited",
    ]
    monetary_ids = [
        "unmitigated_exposure_usd",
        "mitigation_cost_usd",
        "gross_avoided_exposure_usd",
    ]
    required_fact_accuracy = _correct_share([by_id[item] for item in required_fact_ids])
    monetary_accuracy = _correct_share([by_id[item] for item in monetary_ids])
    schedule_accuracy = 1.0 if by_id["projected_slip_days"].status == ClaimStatus.CORRECT else 0.0
    citation_precision = _average([item.precision for item in citations])
    citation_recall = _average([item.recall for item in citations])
    unsupported_count = sum(1 for claim in claims if claim.status == ClaimStatus.UNSUPPORTED)
    human_escalation = 1.0 if by_id["human_confirmation_required"].status == ClaimStatus.CORRECT else 0.0
    preferred = (
        1.0
        if by_id["preferred_option_id"].status == ClaimStatus.CORRECT
        and by_id["preferred_option_subject_to_approval"].status == ClaimStatus.CORRECT
        else 0.0
    )

    return [
        MetricResult(
            metric_id=EvaluationMetricId.REQUIRED_FACT_ACCURACY,
            score=required_fact_accuracy,
            passed=required_fact_accuracy == 1.0,
        ),
        MetricResult(
            metric_id=EvaluationMetricId.MONETARY_CALCULATION_ACCURACY,
            score=monetary_accuracy,
            passed=monetary_accuracy == 1.0,
        ),
        MetricResult(
            metric_id=EvaluationMetricId.SCHEDULE_IMPACT_ACCURACY,
            score=schedule_accuracy,
            passed=schedule_accuracy == 1.0,
        ),
        MetricResult(
            metric_id=EvaluationMetricId.EVIDENCE_CITATION_PRECISION,
            score=citation_precision,
            passed=citation_precision == 1.0,
        ),
        MetricResult(
            metric_id=EvaluationMetricId.EVIDENCE_CITATION_RECALL,
            score=citation_recall,
            passed=citation_recall == 1.0,
        ),
        MetricResult(
            metric_id=EvaluationMetricId.CONTRADICTION_DETECTION,
            score=1.0 if contradiction.status == ClaimStatus.CORRECT else 0.0,
            passed=contradiction.status == ClaimStatus.CORRECT,
        ),
        MetricResult(
            metric_id=EvaluationMetricId.UNSUPPORTED_CLAIM_COUNT,
            score=float(unsupported_count),
            passed=unsupported_count == 0,
        ),
        MetricResult(
            metric_id=EvaluationMetricId.CORRECT_HUMAN_ESCALATION,
            score=human_escalation,
            passed=human_escalation == 1.0,
        ),
        MetricResult(
            metric_id=EvaluationMetricId.PREFERRED_RECOVERY_OPTION,
            score=preferred,
            passed=preferred == 1.0,
        ),
        MetricResult(
            metric_id=EvaluationMetricId.SCHEMA_VALID_RESPONSE_RATE,
            score=1.0 if schema_valid else 0.0,
            passed=schema_valid,
        ),
        MetricResult(
            metric_id=EvaluationMetricId.AGENT_INVOCATION_COUNT,
            score=float(efficiency.agent_invocation_count),
        ),
        MetricResult(metric_id=EvaluationMetricId.INPUT_TOKENS, score=_float_or_none(efficiency.input_tokens)),
        MetricResult(metric_id=EvaluationMetricId.OUTPUT_TOKENS, score=_float_or_none(efficiency.output_tokens)),
        MetricResult(metric_id=EvaluationMetricId.TOTAL_TOKENS, score=_float_or_none(efficiency.total_tokens)),
        MetricResult(metric_id=EvaluationMetricId.LATENCY, score=efficiency.latency_seconds),
        MetricResult(metric_id=EvaluationMetricId.RETRY_COUNT, score=float(efficiency.retry_count)),
        MetricResult(
            metric_id=EvaluationMetricId.ESTIMATED_PROVIDER_COST,
            score=efficiency.estimated_provider_cost_usd,
        ),
    ]


def _correct_share(claims: list[ClaimAssessment]) -> float:
    return sum(1 for claim in claims if claim.status == ClaimStatus.CORRECT) / len(claims)


def _average(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _sum_optional(values: list[int | None]) -> int | None:
    known = [value for value in values if value is not None]
    return sum(known) if known else None


def _sum_optional_float(values: list[float | None]) -> float | None:
    known = [value for value in values if value is not None]
    return sum(known) if known else None


def _float_or_none(value: int | None) -> float | None:
    return float(value) if value is not None else None


def role_scope_metric_results(results: list[RoleValidationResult]) -> list[MetricResult]:
    metrics = role_compliance_metrics(results)
    return [
        MetricResult(
            metric_id=EvaluationMetricId.SCOPE_COMPLIANCE_RATE,
            score=metrics["scope_compliance_rate"],
            passed=metrics["scope_compliance_rate"] == 1.0,
        ),
        MetricResult(
            metric_id=EvaluationMetricId.PROHIBITED_CLAIM_COUNT,
            score=metrics["prohibited_claim_count"],
            passed=metrics["prohibited_claim_count"] == 0.0,
        ),
        MetricResult(
            metric_id=EvaluationMetricId.PROHIBITED_WARNING_COUNT,
            score=metrics["prohibited_warning_count"],
            passed=metrics["prohibited_warning_count"] == 0.0,
        ),
        MetricResult(
            metric_id=EvaluationMetricId.PROHIBITED_CITATION_COUNT,
            score=metrics["prohibited_citation_count"],
            passed=metrics["prohibited_citation_count"] == 0.0,
        ),
        MetricResult(
            metric_id=EvaluationMetricId.EVIDENCE_OVEREXPOSURE_COUNT,
            score=metrics["evidence_overexposure_count"],
            passed=metrics["evidence_overexposure_count"] == 0.0,
        ),
    ]


def schedule_semantic_metric_results(results: list[ScheduleSemanticValidationResult]) -> list[MetricResult]:
    metrics = schedule_semantic_metrics(results)
    return [
        MetricResult(
            metric_id=EvaluationMetricId.DELIVERY_MOVEMENT_CORRECTNESS,
            score=metrics["delivery_movement_correctness"],
            passed=metrics["delivery_movement_correctness"] == 1.0,
        ),
        MetricResult(
            metric_id=EvaluationMetricId.FLOAT_CONSUMED_CORRECTNESS,
            score=metrics["float_consumed_correctness"],
            passed=metrics["float_consumed_correctness"] == 1.0,
        ),
        MetricResult(
            metric_id=EvaluationMetricId.REMAINING_FLOAT_CORRECTNESS,
            score=metrics["remaining_float_correctness"],
            passed=metrics["remaining_float_correctness"] == 1.0,
        ),
        MetricResult(
            metric_id=EvaluationMetricId.MILESTONE_SLIP_CORRECTNESS,
            score=metrics["milestone_slip_correctness"],
            passed=metrics["milestone_slip_correctness"] == 1.0,
        ),
        MetricResult(
            metric_id=EvaluationMetricId.MILESTONE_DATE_ARITHMETIC_CORRECTNESS,
            score=metrics["milestone_date_arithmetic_correctness"],
            passed=metrics["milestone_date_arithmetic_correctness"] == 1.0,
        ),
        MetricResult(
            metric_id=EvaluationMetricId.SCHEDULE_SEMANTIC_COMPLIANCE_RATE,
            score=metrics["schedule_semantic_compliance_rate"],
            passed=metrics["schedule_semantic_compliance_rate"] == 1.0,
        ),
    ]
