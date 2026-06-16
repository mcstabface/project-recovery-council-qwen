"""Offline fixture execution for competition experiments."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from project_recovery_council.experiment_artifacts import write_experiment_artifacts
from project_recovery_council.evaluation import evaluate_model_result
from project_recovery_council.experiment_contracts import (
    AgentInvocation,
    ComparisonMetricRow,
    EvaluationReport,
    ExperimentComparison,
    ExperimentConfig,
    ExperimentVariant,
    SCHEMA_REGISTRY,
)
from project_recovery_council.experiments import DEFAULT_QWEN_MODEL_IDENTIFIER, build_experiment_plan
from project_recovery_council.fixtures import load_equipment_delay_case
from project_recovery_council.model_client import ModelRequest, ModelResult, OfflineModelClient
from project_recovery_council.serialization import read_json
from project_recovery_council.workflow import DEFAULT_CASE_PATH


OFFLINE_FIXTURE_ROOT = Path(__file__).parents[2] / "experiment-fixtures" / "offline-responses" / "v1"

DEFAULT_COMPARISON_FIXTURES = [
    "strong_modular_council",
    "generalist_missed_onsite_contradiction",
    "fixed_chain_result",
]


def list_offline_fixture_ids() -> list[str]:
    return sorted(path.stem for path in OFFLINE_FIXTURE_ROOT.glob("*.json"))


def load_offline_fixture(fixture_id: str) -> dict[str, Any]:
    path = OFFLINE_FIXTURE_ROOT / f"{fixture_id}.json"
    if not path.is_file():
        raise ValueError(f"unknown offline fixture: {fixture_id}")
    payload = read_json(path)
    if not isinstance(payload, dict):
        raise ValueError(f"offline fixture must be a JSON object: {path.as_posix()}")
    return payload


def model_response_from_fixture(fixture: dict[str, Any]) -> Any:
    return fixture.get("raw_response_text", fixture.get("response"))


def evaluate_offline_fixture(
    fixture_id: str,
    *,
    case_path: Path | str = DEFAULT_CASE_PATH,
) -> EvaluationReport:
    fixture, bundle, _request, result = invoke_offline_fixture(fixture_id, case_path=case_path)
    return evaluate_model_result(
        result,
        variant=ExperimentVariant(fixture["variant"]),
        bundle=bundle,
        fixture_id=fixture_id,
    )


def invoke_offline_fixture(
    fixture_id: str,
    *,
    case_path: Path | str = DEFAULT_CASE_PATH,
) -> tuple[dict[str, Any], Any, ModelRequest, ModelResult]:
    fixture = load_offline_fixture(fixture_id)
    bundle = load_equipment_delay_case(case_path)
    request = ModelRequest(
        model_identifier=DEFAULT_QWEN_MODEL_IDENTIFIER,
        system_instructions="Offline fixture replay. No provider call.",
        user_payload={"case_id": bundle.case.case_id},
        expected_response_schema=str(fixture["response_schema"]),
        correlation_id=str(fixture["correlation_id"]),
        metadata={"fixture_id": fixture_id, "simulated_output": True},
    )
    client = OfflineModelClient(
        {fixture_id: model_response_from_fixture(fixture)},
        schema_registry=SCHEMA_REGISTRY,
    )
    result = client.generate(request)
    return fixture, bundle, request, result


def compare_offline_fixtures(
    fixture_ids: list[str] | None = None,
    *,
    case_path: Path | str = DEFAULT_CASE_PATH,
    comparison_id: str = "offline-comparison-v1",
) -> ExperimentComparison:
    selected = fixture_ids or DEFAULT_COMPARISON_FIXTURES
    reports = [evaluate_offline_fixture(fixture_id, case_path=case_path) for fixture_id in selected]
    rows = []
    for report in reports:
        metric_scores = {metric.metric_id.value: metric.score for metric in report.metric_results}
        unsupported = next(
            int(metric.score or 0)
            for metric in report.metric_results
            if metric.metric_id.value == "unsupported_claim_count"
        )
        rows.append(
            ComparisonMetricRow(
                variant=report.variant,
                fixture_id=report.fixture_id,
                metric_scores=metric_scores,
                schema_valid=report.schema_valid,
                unsupported_claim_count=unsupported,
                simulated=True,
            )
        )
    return ExperimentComparison(
        comparison_id=comparison_id,
        case_id=reports[0].evaluation_case.case_id if reports else "unknown",
        ai_competitor_variants=[
            ExperimentVariant.SINGLE_GENERALIST,
            ExperimentVariant.FIXED_EXPERT_CHAIN,
            ExperimentVariant.DYNAMIC_EXPERT_COUNCIL,
        ],
        rows=rows,
        limitations=[
            "Comparison uses deterministic simulated offline fixtures only.",
            "No real Qwen calls, credentials, token accounting, latency, or provider pricing are used.",
            "The deterministic oracle remains the expected-result source and is not an AI competitor.",
        ],
    )


def build_offline_artifact_payloads(
    fixture_id: str,
    *,
    case_path: Path | str = DEFAULT_CASE_PATH,
    experiment_id: str | None = None,
) -> tuple[ExperimentConfig, list[AgentInvocation], dict[str, Any], EvaluationReport, ExperimentComparison]:
    fixture, bundle, request, result = invoke_offline_fixture(fixture_id, case_path=case_path)
    variant = ExperimentVariant(fixture["variant"])
    plan = build_experiment_plan(variant)
    report = evaluate_model_result(result, variant=variant, bundle=bundle, fixture_id=fixture_id)
    selected_experiment_id = experiment_id or f"offline-{fixture_id}"
    config = ExperimentConfig(
        experiment_id=selected_experiment_id,
        case_id=bundle.case.case_id,
        fixture_id=fixture_id,
        variant=variant,
        execution_plan=plan,
        live_provider_enabled=False,
        simulated_outputs=True,
    )
    agent_role = _agent_role_from_fixture(fixture)
    invocation = AgentInvocation(
        invocation_id=f"INV-{fixture_id}",
        variant=variant,
        agent_role=agent_role,
        prompt_id=f"{agent_role}.v1",
        request=request,
        result=result,
    )
    variant_results = {
        "fixture_id": fixture_id,
        "label": fixture.get("label"),
        "simulated_output": True,
        "variant": variant.value,
        "response_schema": fixture.get("response_schema"),
        "parsed_response": result.parsed_response,
        "finish_status": result.finish_status.value,
        "validation_errors": result.validation_errors,
    }
    comparison = compare_offline_reports([report], comparison_id=f"{selected_experiment_id}-single-report")
    return config, [invocation], variant_results, report, comparison


def write_offline_evaluation_artifacts(
    fixture_id: str,
    *,
    case_path: Path | str = DEFAULT_CASE_PATH,
    artifacts_root: Path | str = "experiment-artifacts",
    experiment_id: str | None = None,
) -> Path:
    selected_experiment_id = experiment_id or f"offline-{fixture_id}"
    config, invocations, variant_results, report, comparison = build_offline_artifact_payloads(
        fixture_id,
        case_path=case_path,
        experiment_id=selected_experiment_id,
    )
    return write_experiment_artifacts(
        experiment_id=selected_experiment_id,
        case_id=config.case_id,
        config=config,
        invocation_records=invocations,
        variant_results=variant_results,
        evaluation_results=report,
        comparison_report=comparison,
        artifacts_root=artifacts_root,
    )


def compare_offline_reports(
    reports: list[EvaluationReport],
    *,
    comparison_id: str = "offline-comparison-v1",
) -> ExperimentComparison:
    rows = []
    for report in reports:
        metric_scores = {metric.metric_id.value: metric.score for metric in report.metric_results}
        unsupported = next(
            int(metric.score or 0)
            for metric in report.metric_results
            if metric.metric_id.value == "unsupported_claim_count"
        )
        rows.append(
            ComparisonMetricRow(
                variant=report.variant,
                fixture_id=report.fixture_id,
                metric_scores=metric_scores,
                schema_valid=report.schema_valid,
                unsupported_claim_count=unsupported,
                simulated=True,
            )
        )
    return ExperimentComparison(
        comparison_id=comparison_id,
        case_id=reports[0].evaluation_case.case_id if reports else "unknown",
        ai_competitor_variants=[
            ExperimentVariant.SINGLE_GENERALIST,
            ExperimentVariant.FIXED_EXPERT_CHAIN,
            ExperimentVariant.DYNAMIC_EXPERT_COUNCIL,
        ],
        rows=rows,
        limitations=[
            "Comparison uses deterministic simulated offline fixtures only.",
            "No real Qwen performance result is claimed.",
            "The deterministic oracle remains the expected-result source and is not an AI competitor.",
        ],
    )


def _agent_role_from_fixture(fixture: dict[str, Any]) -> str:
    response = fixture.get("response")
    if isinstance(response, dict) and isinstance(response.get("agent_role"), str):
        return response["agent_role"]
    if fixture.get("variant") == ExperimentVariant.SINGLE_GENERALIST.value:
        return "GeneralistAgent"
    return "RecoveryPlanner"
