from copy import deepcopy
from pathlib import Path

from project_recovery_council.evaluation import aggregate_efficiency_metrics, evaluate_model_result
from project_recovery_council.experiment_contracts import (
    ClaimStatus,
    EvaluationMetricId,
    ExperimentVariant,
    RECOVERY_ANALYSIS_RESPONSE_SCHEMA,
    SCHEMA_REGISTRY,
    SPECIALIST_FINDING_RESPONSE_SCHEMA,
    SpecialistFindingResponse,
)
from project_recovery_council.fixtures import load_equipment_delay_case
from project_recovery_council.model_client import FinishStatus, ModelRequest, ModelResult, OfflineModelClient
from project_recovery_council.offline_experiments import (
    evaluate_offline_fixture,
    load_offline_fixture,
    model_response_from_fixture,
)


FIXTURE_PATH = Path(__file__).parents[1] / "sample-data" / "equipment-delay-case"


def metric(report, metric_id: EvaluationMetricId) -> float | None:
    return next(item.score for item in report.metric_results if item.metric_id == metric_id)


def claim(report, claim_id: str):
    return next(item for item in report.claim_assessments if item.claim_id == claim_id)


def test_deterministic_evaluation_rules_pass_for_strong_modular_fixture() -> None:
    report = evaluate_offline_fixture("strong_modular_council", case_path=FIXTURE_PATH)

    assert report.schema_valid is True
    assert all(item.status == ClaimStatus.CORRECT for item in report.claim_assessments)
    assert metric(report, EvaluationMetricId.SCHEDULE_IMPACT_ACCURACY) == 1.0
    assert metric(report, EvaluationMetricId.MONETARY_CALCULATION_ACCURACY) == 1.0
    assert metric(report, EvaluationMetricId.CONTRADICTION_DETECTION) == 1.0
    assert metric(report, EvaluationMetricId.CORRECT_HUMAN_ESCALATION) == 1.0
    assert metric(report, EvaluationMetricId.PREFERRED_RECOVERY_OPTION) == 1.0


def test_generalist_fixture_scores_unsupported_onsite_assertion_and_bad_escalation() -> None:
    report = evaluate_offline_fixture("generalist_missed_onsite_contradiction", case_path=FIXTURE_PATH)

    assert claim(report, "unsupported_onsite_assertion_prohibited").status == ClaimStatus.UNSUPPORTED
    assert claim(report, "onsite_status_contradiction_detected").status == ClaimStatus.INCORRECT
    assert claim(report, "human_confirmation_required").status == ClaimStatus.INCORRECT
    assert metric(report, EvaluationMetricId.UNSUPPORTED_CLAIM_COUNT) == 1.0
    assert metric(report, EvaluationMetricId.CORRECT_HUMAN_ESCALATION) == 0.0


def test_citation_verification_flags_unknown_record_ids() -> None:
    fixture = load_offline_fixture("strong_modular_council")
    payload = deepcopy(fixture["response"])
    payload["citations"]["projected_slip_days"] = ["SCH-DELIVERY-001", "NO-SUCH-RECORD"]
    result = ModelResult(
        parsed_response=payload,
        raw_response_text="{}",
        model_identifier="offline",
        provider="offline-fixture",
        finish_status=FinishStatus.COMPLETED,
        simulated=True,
    )
    report = evaluate_model_result(
        result,
        variant=ExperimentVariant.DYNAMIC_EXPERT_COUNCIL,
        bundle=load_equipment_delay_case(FIXTURE_PATH),
        fixture_id="citation-test",
    )
    citation = next(item for item in report.citation_assessments if item.claim_id == "projected_slip_days")

    assert citation.invalid_record_ids == ["NO-SUCH-RECORD"]
    assert citation.precision == 0.5


def test_malformed_response_is_reported_without_claim_credit() -> None:
    report = evaluate_offline_fixture("malformed_structured_response", case_path=FIXTURE_PATH)

    assert report.schema_valid is False
    assert report.malformed_response is True
    assert all(item.status == ClaimStatus.ABSENT for item in report.claim_assessments)
    assert metric(report, EvaluationMetricId.SCHEMA_VALID_RESPONSE_RATE) == 0.0


def test_specialist_abstention_fixture_is_schema_valid_and_explicit() -> None:
    fixture = load_offline_fixture("specialist_abstention")
    request = ModelRequest(
        model_identifier="offline-qwen-placeholder",
        system_instructions="Use fixture only.",
        user_payload={},
        expected_response_schema=SPECIALIST_FINDING_RESPONSE_SCHEMA,
        correlation_id=fixture["correlation_id"],
        metadata={"fixture_id": fixture["fixture_id"]},
    )
    result = OfflineModelClient(
        {fixture["fixture_id"]: model_response_from_fixture(fixture)},
        schema_registry=SCHEMA_REGISTRY,
    ).generate(request)
    finding = SpecialistFindingResponse.model_validate(result.parsed_response)

    assert result.finish_status == FinishStatus.COMPLETED
    assert finding.status == "abstained"
    assert finding.abstention_reason.startswith("Risk register")


def test_disagreement_requiring_arbitration_is_preserved() -> None:
    report = evaluate_offline_fixture("disagreement_requires_arbitration", case_path=FIXTURE_PATH)

    assert report.schema_valid is True
    assert len(report.disagreements) == 1
    assert report.disagreements[0].requires_arbitration is True
    assert "PRG-ONSITE-001" in report.disagreements[0].evidence_record_ids


def test_efficiency_metrics_aggregate_only_reported_values_and_optional_pricing() -> None:
    result_a = ModelResult(
        model_identifier="qwen-a",
        provider="offline-fixture",
        finish_status=FinishStatus.COMPLETED,
        input_token_count=100,
        output_token_count=50,
        total_token_count=150,
        latency_seconds=1.25,
        retry_count=1,
        simulated=True,
    )
    result_b = ModelResult(
        model_identifier="qwen-b",
        provider="offline-fixture",
        finish_status=FinishStatus.COMPLETED,
        input_token_count=200,
        output_token_count=75,
        total_token_count=275,
        latency_seconds=2.0,
        retry_count=0,
        simulated=True,
    )

    metrics = aggregate_efficiency_metrics(
        [result_a, result_b],
        pricing_usd_per_1k_input_tokens=0.10,
        pricing_usd_per_1k_output_tokens=0.20,
    )

    assert metrics.agent_invocation_count == 2
    assert metrics.input_tokens == 300
    assert metrics.output_tokens == 125
    assert metrics.total_tokens == 425
    assert metrics.latency_seconds == 3.25
    assert metrics.retry_count == 1
    assert metrics.estimated_provider_cost_usd == 0.055
