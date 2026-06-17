import json
from pathlib import Path
from typing import Any

import pytest

from project_recovery_council.experiment_artifacts import validate_experiment_artifacts
from project_recovery_council.experiment_contracts import (
    ARBITER_RESPONSE_SCHEMA,
    DIRECTOR_ROUTING_RESPONSE_SCHEMA,
    RECOVERY_ANALYSIS_RESPONSE_SCHEMA,
    SPECIALIST_FINDING_RESPONSE_SCHEMA,
    AgentRole,
    ExperimentVariant,
)
from project_recovery_council.fixtures import load_equipment_delay_case
from project_recovery_council.live_variant_runner import (
    LiveRunControls,
    compare_live_variant_runs,
    run_controlled_live_variant,
)
from project_recovery_council.model_client import FailureKind, FinishStatus, ModelFailure, ModelRequest, ModelResult
from project_recovery_council.qwen_config import QwenProviderConfig
from project_recovery_council.serialization import read_json, write_json
from project_recovery_council.workflow import DEFAULT_CASE_PATH


DUMMY_SECRET = "dummy-live-variant-secret"


class QueueModelClient:
    provider = "mock-qwen"

    def __init__(self, responses: list[dict[str, Any] | ModelResult]) -> None:
        self.responses = list(responses)
        self.requests: list[ModelRequest] = []

    def generate(self, request: ModelRequest) -> ModelResult:
        self.requests.append(request)
        response = self.responses.pop(0)
        if isinstance(response, ModelResult):
            return response
        return model_result(request, response)


class SteppedClock:
    def __init__(self, values: list[float]) -> None:
        self.values = list(values)

    def __call__(self) -> float:
        if len(self.values) > 1:
            return self.values.pop(0)
        return self.values[0]


def config() -> QwenProviderConfig:
    return QwenProviderConfig(
        api_key_env_var="DASHSCOPE_API_KEY",
        base_url="https://example.invalid/compatible-mode/v1",
        model_identifier="explicit-test-model",
        request_timeout_seconds=3.0,
        maximum_retries=1,
        temperature=0.0,
    )


def model_result(
    request: ModelRequest,
    parsed_response: dict[str, Any],
    *,
    input_tokens: int = 10,
    output_tokens: int = 5,
    retry_count: int = 0,
) -> ModelResult:
    return ModelResult(
        parsed_response=parsed_response,
        raw_response_text=json.dumps(parsed_response, sort_keys=True),
        model_identifier=request.model_identifier,
        provider="mock-qwen",
        input_token_count=input_tokens,
        output_token_count=output_tokens,
        total_token_count=input_tokens + output_tokens,
        latency_seconds=0.25,
        finish_status=FinishStatus.COMPLETED,
        retry_count=retry_count,
        provider_metadata={"network_attempted": False, "provider_request_id": f"req-{len(request.correlation_id)}"},
        simulated=True,
    )


def failed_result(request: ModelRequest, *, status: FinishStatus = FinishStatus.FAILED, retry_count: int = 0) -> ModelResult:
    return ModelResult(
        parsed_response=None,
        raw_response_text=None,
        model_identifier=request.model_identifier,
        provider="mock-qwen",
        finish_status=status,
        retry_count=retry_count,
        validation_errors=["mock failure"],
        failure=ModelFailure(
            kind=FailureKind.TIMEOUT if status == FinishStatus.TIMEOUT else FailureKind.RATE_LIMIT,
            error_type="MockFailure",
            message="mock failure",
            retryable=False,
        ),
        provider_metadata={"network_attempted": False},
        simulated=True,
    )


def malformed_result() -> ModelResult:
    return ModelResult(
        parsed_response={"not": "a recovery response"},
        raw_response_text='{"not":"a recovery response"}',
        model_identifier="explicit-test-model",
        provider="mock-qwen",
        input_token_count=3,
        output_token_count=2,
        total_token_count=5,
        latency_seconds=0.1,
        finish_status=FinishStatus.COMPLETED,
        validation_errors=["schema validation failed"],
        provider_metadata={"network_attempted": False},
        simulated=True,
    )


def provider_error_result() -> ModelResult:
    return ModelResult(
        parsed_response=None,
        raw_response_text=None,
        model_identifier="explicit-test-model",
        provider="mock-qwen",
        finish_status=FinishStatus.FAILED,
        retry_count=0,
        validation_errors=["provider error"],
        failure=ModelFailure(
            kind=FailureKind.PROVIDER_ERROR,
            error_type="MockProviderError",
            message="provider returned an error",
            retryable=False,
        ),
        provider_metadata={"network_attempted": False, "provider_status": 500},
        simulated=True,
    )


def recovery_response(agent_role: str = AgentRole.RECOVERY_PLANNER.value) -> dict[str, Any]:
    return {
        "schema_version": RECOVERY_ANALYSIS_RESPONSE_SCHEMA,
        "agent_role": agent_role,
        "status": "completed",
        "projected_slip_days": 13,
        "unmitigated_exposure_usd": 195000,
        "mitigation_cost_usd": 48000,
        "gross_avoided_exposure_usd": 147000,
        "onsite_status_contradiction_detected": True,
        "asserted_equipment_onsite": False,
        "human_confirmation_required": True,
        "preferred_option_id": "REC-ACCEL-LOGISTICS",
        "preferred_option_subject_to_approval": True,
        "citations": {
            "projected_slip_days": ["SCH-DELIVERY-001"],
            "unmitigated_exposure_usd": ["SCH-DELIVERY-001", "COST-SUMMARY-001", "CTR-DELAY-001"],
            "mitigation_cost_usd": ["COST-SUMMARY-001"],
            "gross_avoided_exposure_usd": ["COST-SUMMARY-001", "CTR-DELAY-001"],
            "onsite_status_contradiction_detected": [
                "PRG-ONSITE-001",
                "SUP-NOT-ARRIVED-001",
                "LOG-STATUS-001",
            ],
            "human_confirmation_required": ["PRG-ONSITE-001", "SUP-NOT-ARRIVED-001", "LOG-STATUS-001"],
            "preferred_option_id": ["COST-SUMMARY-001", "SCH-DELIVERY-001"],
            "preferred_option_subject_to_approval": [
                "COST-SUMMARY-001",
                "PRG-ONSITE-001",
                "SUP-NOT-ARRIVED-001",
                "LOG-STATUS-001",
            ],
        },
        "unsupported_claims": [],
        "ambiguous_claims": [],
        "concise_rationale": "Accelerated logistics avoids net delay exposure but requires human confirmation.",
    }


def schedule_response(**overrides: Any) -> dict[str, Any]:
    claims = {
        "delivery_baseline_date": "2026-07-01",
        "delivery_forecast_date": "2026-07-22",
        "delivery_movement_days": 21,
        "installation_total_float_days": 8,
        "installation_total_float_consumed_days": 8,
        "remaining_total_float_days": 0,
        "float_consumption_status": "fully_consumed",
        "milestone_baseline_date": "2026-08-15",
        "milestone_forecast_date_without_intervention": "2026-08-28",
        "forecast_milestone_slip_days": 13,
    }
    claims.update(overrides)
    return specialist_response(AgentRole.SCHEDULE_EXPERT.value, claims)


def specialist_response(agent_role: str, claims: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": SPECIALIST_FINDING_RESPONSE_SCHEMA,
        "agent_role": agent_role,
        "status": "completed",
        "claims": claims,
        "citations": {key: ["SCH-DELIVERY-001"] for key in claims},
        "unsupported_claims": [],
        "warnings": [],
    }


def commercial_response() -> dict[str, Any]:
    return specialist_response(
        AgentRole.COMMERCIAL_EXPERT.value,
        {
            "projected_milestone_slip_days": 13,
            "delay_exposure_usd_per_day": 15000,
            "unmitigated_exposure_usd": 195000,
            "mitigation_cost_usd": 48000,
            "gross_avoided_exposure_usd": 147000,
        },
    )


def auditor_response() -> dict[str, Any]:
    return specialist_response(
        AgentRole.EVIDENCE_AUDITOR.value,
        {"claim_support": "citations checked", "contradiction": "onsite status unresolved"},
    )


def risk_response() -> dict[str, Any]:
    return specialist_response(
        AgentRole.RISK_EXPERT.value,
        {"risk": "delay exposure and onsite contradiction", "human_escalation_required": True},
    )


def director_response(*, selected: list[str] | None = None) -> dict[str, Any]:
    selected_roles = selected or [
        AgentRole.SCHEDULE_EXPERT.value,
        AgentRole.COMMERCIAL_EXPERT.value,
        AgentRole.RISK_EXPERT.value,
    ]
    return {
        "schema_version": DIRECTOR_ROUTING_RESPONSE_SCHEMA,
        "agent_role": AgentRole.DIRECTOR.value,
        "status": "completed",
        "selected_experts": selected_roles,
        "routing_rationale": "Schedule, commercial, and risk facts are needed.",
        "skipped_experts": {},
        "citations": {"routing": ["SCH-DELIVERY-001", "COST-SUMMARY-001"]},
    }


def arbiter_response() -> dict[str, Any]:
    return {
        "schema_version": ARBITER_RESPONSE_SCHEMA,
        "agent_role": AgentRole.ARBITER.value,
        "status": "completed",
        "resolved_disagreements": [],
        "unresolved_disagreements": [],
        "preserved_provenance_record_ids": ["SCH-DELIVERY-001"],
        "concise_rationale": "No unresolved specialist disagreement.",
    }


def run_variant(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    variant: ExperimentVariant,
    responses: list[dict[str, Any] | ModelResult],
    *,
    experiment_id: str,
    controls: LiveRunControls | None = None,
    time_func=None,
) -> tuple[Path, QueueModelClient]:
    monkeypatch.setenv("DASHSCOPE_API_KEY", DUMMY_SECRET)
    client = QueueModelClient(responses)
    path = run_controlled_live_variant(
        variant=variant,
        config=config(),
        allow_network=True,
        controls=controls,
        artifacts_root=tmp_path / "live",
        experiment_id=experiment_id,
        client=client,
        time_func=time_func or (lambda: 0.0),
    )
    return path, client


def test_successful_generalist_run_full_evidence_and_artifacts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path, client = run_variant(
        tmp_path,
        monkeypatch,
        ExperimentVariant.SINGLE_GENERALIST,
        [recovery_response(AgentRole.GENERALIST.value)],
        experiment_id="generalist-ok",
    )
    bundle = load_equipment_delay_case(DEFAULT_CASE_PATH)
    selected = read_json(path / "selected-evidence-records.json")[0]["record_ids"]

    assert validate_experiment_artifacts(path).passed is True
    assert read_json(path / "final-variant-result.json")["completed"] is True
    assert set(selected) == set(bundle.evidence_by_id)
    assert [request.metadata["agent_role"] for request in client.requests] == [AgentRole.GENERALIST.value]


def test_live_generalist_limitations_and_specialist_metrics_are_not_applicable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path, _client = run_variant(
        tmp_path,
        monkeypatch,
        ExperimentVariant.SINGLE_GENERALIST,
        [recovery_response(AgentRole.GENERALIST.value)],
        experiment_id="generalist-applicability",
    )
    final = read_json(path / "final-variant-result.json")
    evaluation = read_json(path / "evaluation-results.json")["report"]

    assert not any("Offline fixtures are simulated outputs" in item for item in evaluation["limitations"])
    assert any("One live run per variant is not statistically significant" in item for item in evaluation["limitations"])
    assert any("Hosted-model outputs may vary" in item for item in evaluation["limitations"])
    assert final["role_scope_compliance"]["status"] == "not_applicable"
    assert final["role_scope_compliance"]["score"] is None
    assert final["role_scope_compliance_rate"] is None
    assert final["semantic_validation_compliance"]["status"] == "not_applicable"
    assert final["semantic_validation_compliance"]["score"] is None
    assert final["semantic_validation_compliance_rate"] is None


def test_successful_fixed_chain_order_filtering_and_artifacts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path, client = run_variant(
        tmp_path,
        monkeypatch,
        ExperimentVariant.FIXED_EXPERT_CHAIN,
        [schedule_response(), commercial_response(), auditor_response(), risk_response(), recovery_response()],
        experiment_id="fixed-ok",
    )

    assert validate_experiment_artifacts(path).passed is True
    assert [request.metadata["agent_role"] for request in client.requests] == [
        AgentRole.SCHEDULE_EXPERT.value,
        AgentRole.COMMERCIAL_EXPERT.value,
        AgentRole.EVIDENCE_AUDITOR.value,
        AgentRole.RISK_EXPERT.value,
        AgentRole.RECOVERY_PLANNER.value,
    ]
    selected = read_json(path / "selected-evidence-records.json")
    schedule_records = next(item for item in selected if item["agent_role"] == AgentRole.SCHEDULE_EXPERT.value)
    assert schedule_records["record_ids"] == ["CASE-INTAKE-001", "SCH-DELIVERY-001"]
    commercial_semantic = read_json(path / "domain-semantic-validation-results.json")[1]
    assert commercial_semantic["implemented"] is True
    assert commercial_semantic["validator"] == "CommercialExpertSemanticValidator.v1"


def test_specialist_compliance_metrics_remain_applicable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path, _client = run_variant(
        tmp_path,
        monkeypatch,
        ExperimentVariant.FIXED_EXPERT_CHAIN,
        [schedule_response(), commercial_response(), auditor_response(), risk_response(), recovery_response()],
        experiment_id="fixed-applicability",
    )
    final = read_json(path / "final-variant-result.json")

    assert final["role_scope_compliance"]["applicable"] is True
    assert final["role_scope_compliance"]["status"] in {"passed", "failed"}
    assert final["role_scope_compliance"]["score"] is not None
    assert final["role_scope_compliance_rate"] == final["role_scope_compliance"]["score"]
    assert final["semantic_validation_compliance"]["applicable"] is True
    assert final["semantic_validation_compliance"]["status"] == "passed"
    assert final["semantic_validation_compliance"]["score"] == 1.0
    assert final["semantic_validation_compliance_rate"] == 1.0


def test_successful_dynamic_council_uses_director_selection(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path, client = run_variant(
        tmp_path,
        monkeypatch,
        ExperimentVariant.DYNAMIC_EXPERT_COUNCIL,
        [
            director_response(selected=[AgentRole.SCHEDULE_EXPERT.value, AgentRole.COMMERCIAL_EXPERT.value]),
            schedule_response(),
            commercial_response(),
            auditor_response(),
            recovery_response(),
        ],
        experiment_id="dynamic-ok",
    )
    routing = read_json(path / "routing-decisions.json")[0]

    assert validate_experiment_artifacts(path).passed is True
    assert routing["selected_agent_roles"] == [AgentRole.SCHEDULE_EXPERT.value, AgentRole.COMMERCIAL_EXPERT.value]
    assert [request.metadata["agent_role"] for request in client.requests] == [
        AgentRole.DIRECTOR.value,
        AgentRole.SCHEDULE_EXPERT.value,
        AgentRole.COMMERCIAL_EXPERT.value,
        AgentRole.EVIDENCE_AUDITOR.value,
        AgentRole.RECOVERY_PLANNER.value,
    ]
    arbitration = read_json(path / "arbitration-decisions.json")[0]
    assert arbitration["arbiter_required"] is False


def test_unknown_director_role_rejected_without_guessing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path, client = run_variant(
        tmp_path,
        monkeypatch,
        ExperimentVariant.DYNAMIC_EXPERT_COUNCIL,
        [director_response(selected=["UnknownExpert"])],
        experiment_id="dynamic-unknown-role",
    )
    result = read_json(path / "final-variant-result.json")

    assert validate_experiment_artifacts(path).passed is True
    assert result["completed"] is False
    assert "unknown" in result["failure_reason"].lower()
    assert len(client.requests) == 1


def test_invocation_limit_stop_preserves_incomplete_artifacts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path, client = run_variant(
        tmp_path,
        monkeypatch,
        ExperimentVariant.FIXED_EXPERT_CHAIN,
        [schedule_response(), commercial_response(), auditor_response()],
        experiment_id="fixed-invocation-limit",
        controls=LiveRunControls(max_invocation_count=2),
    )
    result = read_json(path / "final-variant-result.json")

    assert validate_experiment_artifacts(path).passed is True
    assert result["completed"] is False
    assert result["stopped_by_limit"] == "max_invocation_count"
    assert len(client.requests) == 2


def test_token_limit_stop_preserves_artifacts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path, _client = run_variant(
        tmp_path,
        monkeypatch,
        ExperimentVariant.SINGLE_GENERALIST,
        [recovery_response(AgentRole.GENERALIST.value)],
        experiment_id="generalist-token-limit",
        controls=LiveRunControls(max_total_input_tokens=1),
    )
    result = read_json(path / "final-variant-result.json")

    assert validate_experiment_artifacts(path).passed is True
    assert result["completed"] is False
    assert result["stopped_by_limit"] == "max_total_input_tokens"


def test_elapsed_limit_stop_preserves_artifacts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path, _client = run_variant(
        tmp_path,
        monkeypatch,
        ExperimentVariant.SINGLE_GENERALIST,
        [recovery_response(AgentRole.GENERALIST.value)],
        experiment_id="generalist-elapsed-limit",
        controls=LiveRunControls(max_elapsed_seconds=1.0),
        time_func=SteppedClock([0.0, 0.0, 2.0]),
    )
    result = read_json(path / "final-variant-result.json")

    assert result["completed"] is False
    assert result["stopped_by_limit"] == "max_elapsed_seconds"


def test_stop_after_invocation_behavior(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path, client = run_variant(
        tmp_path,
        monkeypatch,
        ExperimentVariant.FIXED_EXPERT_CHAIN,
        [schedule_response(), commercial_response()],
        experiment_id="fixed-stop-after",
        controls=LiveRunControls(stop_after_invocation=1),
    )
    result = read_json(path / "final-variant-result.json")

    assert result["completed"] is False
    assert result["stopped_by_limit"] == "stop_after_invocation"
    assert len(client.requests) == 1


def test_failed_timeout_and_exhausted_retry_are_recorded(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DASHSCOPE_API_KEY", DUMMY_SECRET)
    client = QueueModelClient([failed_result(ModelRequest(
        model_identifier="explicit-test-model",
        system_instructions="x",
        user_payload="x",
        expected_response_schema=RECOVERY_ANALYSIS_RESPONSE_SCHEMA,
        correlation_id="x",
    ), status=FinishStatus.TIMEOUT, retry_count=3)])
    path = run_controlled_live_variant(
        variant=ExperimentVariant.SINGLE_GENERALIST,
        config=config(),
        allow_network=True,
        controls=LiveRunControls(max_retries_per_invocation=1),
        artifacts_root=tmp_path / "live",
        experiment_id="generalist-timeout",
        client=client,
    )
    result = read_json(path / "final-variant-result.json")

    assert result["completed"] is False
    assert result["stopped_by_limit"] == "max_retries_per_invocation"
    assert "failed invocation" in result["failure_reason"]


def test_malformed_response_records_incomplete_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path, _client = run_variant(
        tmp_path,
        monkeypatch,
        ExperimentVariant.SINGLE_GENERALIST,
        [malformed_result()],
        experiment_id="generalist-malformed",
    )
    result = read_json(path / "final-variant-result.json")
    validation = read_json(path / "validation-results.json")[0]

    assert validate_experiment_artifacts(path).passed is True
    assert result["completed"] is False
    assert "not evaluable" in result["failure_reason"]
    assert validation["schema_valid"] is False


def test_provider_error_response_is_recorded(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path, _client = run_variant(
        tmp_path,
        monkeypatch,
        ExperimentVariant.SINGLE_GENERALIST,
        [provider_error_result()],
        experiment_id="generalist-provider-error",
    )
    result = read_json(path / "final-variant-result.json")
    validation = read_json(path / "validation-results.json")[0]

    assert validate_experiment_artifacts(path).passed is True
    assert result["completed"] is False
    assert "failed invocation" in result["failure_reason"]
    assert validation["failure"]["kind"] == "provider_error"


def test_rate_limit_retry_success_records_retry_count(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DASHSCOPE_API_KEY", DUMMY_SECRET)
    client = QueueModelClient([])

    def generate_with_retry(request: ModelRequest) -> ModelResult:
        client.requests.append(request)
        return model_result(request, recovery_response(AgentRole.GENERALIST.value), retry_count=1)

    client.generate = generate_with_retry  # type: ignore[method-assign]
    path = run_controlled_live_variant(
        variant=ExperimentVariant.SINGLE_GENERALIST,
        config=config(),
        allow_network=True,
        artifacts_root=tmp_path / "live",
        experiment_id="generalist-rate-limit-retry",
        client=client,
    )
    result = read_json(path / "final-variant-result.json")
    retry = read_json(path / "retry-history.json")[0]

    assert result["completed"] is True
    assert result["retry_count"] == 1
    assert retry["retry_count"] == 1


def test_schedule_semantic_failure_and_role_violation_are_preserved(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path, _client = run_variant(
        tmp_path,
        monkeypatch,
        ExperimentVariant.FIXED_EXPERT_CHAIN,
        [
            schedule_response(installation_total_float_consumed_days=13, equipment_onsite_status="onsite"),
            commercial_response(),
            auditor_response(),
            risk_response(),
            recovery_response(),
        ],
        experiment_id="fixed-validation-issues",
    )
    role_results = read_json(path / "role-validation-results.json")
    semantic = read_json(path / "schedule-semantic-validation.json")[0]

    assert any(result["valid"] is False for result in role_results)
    assert semantic["valid"] is False
    assert validate_experiment_artifacts(path).passed is True


def test_variant_artifact_validation_requires_schedule_semantic_validation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path, _client = run_variant(
        tmp_path,
        monkeypatch,
        ExperimentVariant.FIXED_EXPERT_CHAIN,
        [schedule_response(), commercial_response(), auditor_response(), risk_response(), recovery_response()],
        experiment_id="fixed-semantic-required",
    )
    manifest = read_json(path / "artifact-manifest.json")
    manifest["artifacts"] = [
        entry for entry in manifest["artifacts"] if entry["relative_path"] != "schedule-semantic-validation.json"
    ]
    write_json(path / "artifact-manifest.json", manifest)

    inspection = validate_experiment_artifacts(path)

    assert inspection.passed is False
    assert any("schedule-semantic-validation.json" in error for error in inspection.errors)


def test_live_comparison_generation_and_incomplete_rejection(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    generalist, _ = run_variant(
        tmp_path,
        monkeypatch,
        ExperimentVariant.SINGLE_GENERALIST,
        [recovery_response(AgentRole.GENERALIST.value)],
        experiment_id="compare-generalist",
    )
    fixed, _ = run_variant(
        tmp_path,
        monkeypatch,
        ExperimentVariant.FIXED_EXPERT_CHAIN,
        [schedule_response(), commercial_response(), auditor_response(), risk_response(), recovery_response()],
        experiment_id="compare-fixed",
    )
    dynamic, _ = run_variant(
        tmp_path,
        monkeypatch,
        ExperimentVariant.DYNAMIC_EXPERT_COUNCIL,
        [
            director_response(selected=[AgentRole.SCHEDULE_EXPERT.value, AgentRole.COMMERCIAL_EXPERT.value]),
            schedule_response(),
            commercial_response(),
            auditor_response(),
            recovery_response(),
        ],
        experiment_id="compare-dynamic",
    )

    comparison = compare_live_variant_runs(
        generalist_path=generalist,
        fixed_chain_path=fixed,
        dynamic_council_path=dynamic,
        output_root=tmp_path / "comparisons",
        comparison_id="comparison-ok",
    )
    report = read_json(comparison / "live-comparison-report.json")
    markdown = (comparison / "live-comparison-report.md").read_text(encoding="utf-8")

    assert report["rows"][0]["required_fact_accuracy"] == 1.0
    assert report["rows"][0]["role_scope_compliance"]["status"] == "not_applicable"
    assert report["rows"][0]["role_scope_compliance"]["score"] is None
    assert report["rows"][0]["semantic_validation_compliance"]["status"] == "not_applicable"
    assert report["rows"][0]["semantic_validation_compliance"]["score"] is None
    assert report["rows"][1]["role_scope_compliance"]["applicable"] is True
    assert report["rows"][1]["role_scope_compliance"]["score"] is not None
    assert report["rows"][1]["semantic_validation_compliance"]["status"] == "passed"
    assert "single_generalist | True | 1 | 1 | 1 | 1 |" in markdown
    assert "N/A | N/A" in markdown
    assert (comparison / "live-comparison-report.md").is_file()

    incomplete, _ = run_variant(
        tmp_path,
        monkeypatch,
        ExperimentVariant.FIXED_EXPERT_CHAIN,
        [schedule_response()],
        experiment_id="compare-incomplete",
        controls=LiveRunControls(stop_after_invocation=1),
    )
    with pytest.raises(ValueError, match="incomplete"):
        compare_live_variant_runs(
            generalist_path=generalist,
            fixed_chain_path=incomplete,
            dynamic_council_path=dynamic,
            output_root=tmp_path / "comparisons",
            comparison_id="comparison-reject",
        )


def test_generated_live_variant_artifacts_do_not_contain_dummy_secret(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path, _client = run_variant(
        tmp_path,
        monkeypatch,
        ExperimentVariant.SINGLE_GENERALIST,
        [recovery_response(AgentRole.GENERALIST.value)],
        experiment_id="secret-scan",
    )

    for artifact in path.rglob("*.json"):
        assert DUMMY_SECRET not in artifact.read_text(encoding="utf-8")
