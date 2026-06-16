import json
from pathlib import Path
from typing import Any

import pytest

from project_recovery_council.evaluation import schedule_semantic_metric_results
from project_recovery_council.experiment_artifacts import validate_experiment_artifacts
from project_recovery_council.experiment_contracts import (
    AgentRole,
    EvaluationMetricId,
    SPECIALIST_FINDING_RESPONSE_SCHEMA,
    SpecialistFindingResponse,
)
from project_recovery_council.fixtures import load_equipment_delay_case
from project_recovery_council.live_experiments import run_live_agent
from project_recovery_council.qwen_client import HttpResponse, QwenModelClient
from project_recovery_council.qwen_config import QwenProviderConfig
from project_recovery_council.role_scope import (
    get_role_scope_policy,
    selected_evidence_record_ids,
    validate_specialist_response,
)
from project_recovery_council.schedule_semantics import (
    schedule_semantic_metrics,
    validate_schedule_semantics,
)
from project_recovery_council.serialization import read_json, write_json


FIXTURE_PATH = Path(__file__).parents[1] / "sample-data" / "equipment-delay-case"
DUMMY_SECRET = "dummy-schedule-secret"


class MockTransport:
    def __init__(self, response: HttpResponse) -> None:
        self.response = response
        self.calls: list[dict[str, Any]] = []

    def post_json(self, *, url: str, headers: dict[str, str], payload: dict[str, Any], timeout_seconds: float):
        self.calls.append({"url": url, "headers": headers, "payload": payload})
        return self.response


def config() -> QwenProviderConfig:
    return QwenProviderConfig(
        api_key_env_var="DASHSCOPE_API_KEY",
        base_url="https://example.invalid/compatible-mode/v1",
        model_identifier="explicit-test-model",
    )


def provider_response(content: dict[str, Any]) -> HttpResponse:
    return HttpResponse(
        status_code=200,
        headers={"x-request-id": "schedule-semantic-test"},
        body=json.dumps(
            {
                "choices": [
                    {
                        "message": {"role": "assistant", "content": json.dumps(content)},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 25, "completion_tokens": 20, "total_tokens": 45},
            }
        ),
    )


def schedule_response(**overrides: Any) -> dict[str, Any]:
    claims = {
        "milestone_id": "MS-COMMISSIONING-READY",
        "delivery_baseline_date": "2026-07-01",
        "delivery_forecast_date": "2026-07-22",
        "delivery_movement_days": 21,
        "installation_total_float_days": 8,
        "installation_total_float_consumed_days": 8,
        "installation_total_float_remaining_days": 0,
        "milestone_baseline_date": "2026-08-15",
        "milestone_forecast_date_without_intervention": "2026-08-28",
        "forecast_milestone_slip_days": 13,
        "successor_testing_activity_id": "A-4300",
        "successor_dependency_effect": "Successor testing follows installation completion.",
    }
    claims.update(overrides)
    return {
        "schema_version": SPECIALIST_FINDING_RESPONSE_SCHEMA,
        "agent_role": AgentRole.SCHEDULE_EXPERT.value,
        "status": "completed",
        "claims": claims,
        "citations": {key: ["SCH-DELIVERY-001"] for key in claims},
        "unsupported_claims": [],
        "warnings": ["Schedule conclusions depend on supplied schedule data."],
    }


def test_new_schedule_claim_keys_are_allowed() -> None:
    allowed = set(get_role_scope_policy(AgentRole.SCHEDULE_EXPERT.value).allowed_claim_keys)

    for key in [
        "milestone_id",
        "delivery_baseline_date",
        "delivery_forecast_date",
        "delivery_movement_days",
        "installation_total_float_days",
        "installation_total_float_consumed_days",
        "installation_total_float_remaining_days",
        "float_consumption_status",
        "milestone_baseline_date",
        "milestone_forecast_date_without_intervention",
        "forecast_milestone_slip_days",
        "successor_testing_activity_id",
        "successor_dependency_effect",
    ]:
        assert key in allowed


def test_allowed_qualitative_float_consumption_status() -> None:
    bundle = load_equipment_delay_case(FIXTURE_PATH)
    response = SpecialistFindingResponse.model_validate(schedule_response(float_consumption_status="fully_consumed"))

    result = validate_specialist_response(
        role=AgentRole.SCHEDULE_EXPERT.value,
        invocation_id="INV-FLOAT-STATUS-ALLOWED",
        response=response,
        selected_record_ids=selected_evidence_record_ids(bundle, AgentRole.SCHEDULE_EXPERT.value),
        bundle=bundle,
    )

    assert result.valid is True
    assert "float_consumption_status" in result.allowed_claims


def test_prohibited_commercial_and_onsite_claims_remain_prohibited() -> None:
    bundle = load_equipment_delay_case(FIXTURE_PATH)
    payload = schedule_response(unmitigated_exposure_usd=195000, equipment_onsite_status="not onsite")
    response = SpecialistFindingResponse.model_validate(payload)

    result = validate_specialist_response(
        role=AgentRole.SCHEDULE_EXPERT.value,
        invocation_id="INV-PROHIBITED",
        response=response,
        selected_record_ids=selected_evidence_record_ids(bundle, AgentRole.SCHEDULE_EXPERT.value),
        bundle=bundle,
    )

    assert result.valid is False
    assert any("unmitigated_exposure_usd" in item for item in result.prohibited_claims)
    assert any("equipment_onsite_status" in item for item in result.prohibited_claims)


def test_correct_21_8_13_schedule_arithmetic_passes() -> None:
    result = validate_schedule_semantics(
        invocation_id="INV-SCHEDULE-OK",
        response_payload=schedule_response(float_consumption_status="fully_consumed"),
        bundle=load_equipment_delay_case(FIXTURE_PATH),
    )

    assert result.valid is True
    assert result.expected_values["delivery_movement_days"] == 21
    assert result.expected_values["installation_total_float_consumed_days"] == 8
    assert result.expected_values["installation_total_float_remaining_days"] == 0
    assert result.expected_values["float_consumption_status"] == "fully_consumed"
    assert result.expected_values["forecast_milestone_slip_days"] == 13


def test_correct_fully_consumed_status_passes() -> None:
    result = validate_schedule_semantics(
        invocation_id="INV-FLOAT-STATUS-OK",
        response_payload=schedule_response(float_consumption_status="fully_consumed"),
        bundle=load_equipment_delay_case(FIXTURE_PATH),
    )

    assert result.valid is True
    assert "float_consumption_status" in result.checked_fields


def test_inconsistent_float_consumption_status_fails() -> None:
    result = validate_schedule_semantics(
        invocation_id="INV-FLOAT-STATUS-BAD",
        response_payload=schedule_response(float_consumption_status="available"),
        bundle=load_equipment_delay_case(FIXTURE_PATH),
    )

    assert result.valid is False
    assert any("float_consumption_status expected fully_consumed" in item for item in result.semantic_violations)


def test_invalid_float_consumption_status_fails() -> None:
    result = validate_schedule_semantics(
        invocation_id="INV-FLOAT-STATUS-INVALID",
        response_payload=schedule_response(float_consumption_status="exhausted"),
        bundle=load_equipment_delay_case(FIXTURE_PATH),
    )

    assert result.valid is False
    assert any("float_consumption_status must be one of" in item for item in result.semantic_violations)


def test_float_consumed_13_fails() -> None:
    result = validate_schedule_semantics(
        invocation_id="INV-FLOAT-CONSUMED-BAD",
        response_payload=schedule_response(installation_total_float_consumed_days=13),
        bundle=load_equipment_delay_case(FIXTURE_PATH),
    )

    assert result.valid is False
    assert any("installation_total_float_consumed_days expected 8" in item for item in result.semantic_violations)
    assert any("must not exceed available float" in item for item in result.semantic_violations)


def test_remaining_float_negative_fails() -> None:
    result = validate_schedule_semantics(
        invocation_id="INV-REMAINING-FLOAT-BAD",
        response_payload=schedule_response(installation_total_float_remaining_days=-5),
        bundle=load_equipment_delay_case(FIXTURE_PATH),
    )

    assert result.valid is False
    assert any("expected 0" in item for item in result.semantic_violations)
    assert any("must never be negative" in item for item in result.semantic_violations)


def test_milestone_slip_13_and_date_arithmetic_pass() -> None:
    result = validate_schedule_semantics(
        invocation_id="INV-MILESTONE-DATE-OK",
        response_payload=schedule_response(),
        bundle=load_equipment_delay_case(FIXTURE_PATH),
    )

    assert result.valid is True
    assert "forecast_milestone_slip_days" in result.checked_fields
    assert "milestone_forecast_date_without_intervention" in result.checked_fields


def test_inconsistent_milestone_forecast_date_fails() -> None:
    result = validate_schedule_semantics(
        invocation_id="INV-MILESTONE-DATE-BAD",
        response_payload=schedule_response(milestone_forecast_date_without_intervention="2026-08-29"),
        bundle=load_equipment_delay_case(FIXTURE_PATH),
    )

    assert result.valid is False
    assert any("milestone_forecast_date_without_intervention expected 2026-08-28" in item for item in result.semantic_violations)


def test_schema_valid_but_schedule_semantic_invalid() -> None:
    response = SpecialistFindingResponse.model_validate(
        schedule_response(
            installation_total_float_consumed_days=13,
            installation_total_float_remaining_days=-5,
        )
    )
    result = validate_schedule_semantics(
        invocation_id="INV-SCHEMA-VALID-SEMANTIC-INVALID",
        response_payload=response.model_dump(mode="json"),
        bundle=load_equipment_delay_case(FIXTURE_PATH),
    )

    assert response.status == "completed"
    assert result.valid is False


def test_role_valid_but_schedule_semantic_invalid() -> None:
    bundle = load_equipment_delay_case(FIXTURE_PATH)
    response = SpecialistFindingResponse.model_validate(schedule_response(installation_total_float_consumed_days=13))
    role = validate_specialist_response(
        role=AgentRole.SCHEDULE_EXPERT.value,
        invocation_id="INV-ROLE-VALID",
        response=response,
        selected_record_ids=selected_evidence_record_ids(bundle, AgentRole.SCHEDULE_EXPERT.value),
        bundle=bundle,
    )
    semantic = validate_schedule_semantics(
        invocation_id="INV-ROLE-VALID",
        response_payload=response.model_dump(mode="json"),
        bundle=bundle,
    )

    assert role.valid is True
    assert semantic.valid is False


def test_schedule_semantic_metric_aggregation() -> None:
    bundle = load_equipment_delay_case(FIXTURE_PATH)
    valid = validate_schedule_semantics(
        invocation_id="INV-VALID",
        response_payload=schedule_response(),
        bundle=bundle,
    )
    invalid = validate_schedule_semantics(
        invocation_id="INV-INVALID",
        response_payload=schedule_response(installation_total_float_consumed_days=13),
        bundle=bundle,
    )

    metrics = schedule_semantic_metrics([valid, invalid])
    metric_results = schedule_semantic_metric_results([valid, invalid])

    assert metrics["schedule_semantic_compliance_rate"] == 0.5
    assert metrics["float_consumed_correctness"] == 0.5
    assert any(
        item.metric_id == EvaluationMetricId.SCHEDULE_SEMANTIC_COMPLIANCE_RATE and item.score == 0.5
        for item in metric_results
    )


def test_live_schedule_artifacts_include_semantic_validation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DASHSCOPE_API_KEY", DUMMY_SECRET)
    client = QwenModelClient(
        config(),
        transport=MockTransport(provider_response(schedule_response())),
        sleep_func=lambda _: None,
    )

    run_path = run_live_agent(
        agent_role=AgentRole.SCHEDULE_EXPERT.value,
        config=config(),
        allow_network=True,
        artifacts_root=tmp_path / "live",
        experiment_id="schedule-semantic-artifact",
        client=client,
    )

    assert validate_experiment_artifacts(run_path).passed is True
    semantic = read_json(run_path / "schedule-semantic-validation.json")
    metrics = read_json(run_path / "schedule-semantic-metrics.json")
    assert semantic[0]["valid"] is True
    assert metrics["schedule_semantic_compliance_rate"] == 1.0


def test_artifact_validation_requires_schedule_semantic_validation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DASHSCOPE_API_KEY", DUMMY_SECRET)
    client = QwenModelClient(
        config(),
        transport=MockTransport(provider_response(schedule_response())),
        sleep_func=lambda _: None,
    )
    run_path = run_live_agent(
        agent_role=AgentRole.SCHEDULE_EXPERT.value,
        config=config(),
        allow_network=True,
        artifacts_root=tmp_path / "live",
        experiment_id="schedule-semantic-required",
        client=client,
    )
    manifest = read_json(run_path / "artifact-manifest.json")
    manifest["artifacts"] = [
        entry for entry in manifest["artifacts"] if entry["relative_path"] != "schedule-semantic-validation.json"
    ]
    write_json(run_path / "artifact-manifest.json", manifest)

    inspection = validate_experiment_artifacts(run_path)

    assert inspection.passed is False
    assert any("schedule-semantic-validation.json" in error for error in inspection.errors)
