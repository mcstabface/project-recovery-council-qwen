import json
from pathlib import Path
from typing import Any

import pytest

from project_recovery_council.claim_normalization import normalize_claim_keys, normalize_response_payload
from project_recovery_council.evaluation import role_scope_metric_results
from project_recovery_council.experiment_artifacts import validate_experiment_artifacts
from project_recovery_council.experiment_contracts import (
    AgentRole,
    EvaluationMetricId,
    SPECIALIST_FINDING_RESPONSE_SCHEMA,
    SpecialistFindingResponse,
)
from project_recovery_council.fixtures import load_equipment_delay_case
from project_recovery_council.live_experiments import run_live_agent
from project_recovery_council.model_client import FinishStatus
from project_recovery_council.prompt_rendering import render_agent_prompt
from project_recovery_council.qwen_client import HttpResponse, QwenModelClient
from project_recovery_council.qwen_config import QwenProviderConfig
from project_recovery_council.role_scope import (
    InvocationPurpose,
    role_compliance_metrics,
    select_evidence_for_role,
    selected_evidence_record_ids,
    validate_role_scope,
    validate_specialist_response,
)
from project_recovery_council.serialization import read_json


FIXTURE_PATH = Path(__file__).parents[1] / "sample-data" / "equipment-delay-case"
DUMMY_SECRET = "dummy-scope-secret"


class MockTransport:
    def __init__(self, response: HttpResponse) -> None:
        self.response = response
        self.calls: list[dict[str, Any]] = []

    def post_json(self, *, url: str, headers: dict[str, str], payload: dict[str, Any], timeout_seconds: float):
        self.calls.append({"url": url, "headers": headers, "payload": payload, "timeout_seconds": timeout_seconds})
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
        headers={"x-request-id": "scope-test-request"},
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


def valid_schedule_response() -> dict[str, Any]:
    return {
        "schema_version": SPECIALIST_FINDING_RESPONSE_SCHEMA,
        "agent_role": AgentRole.SCHEDULE_EXPERT.value,
        "status": "completed",
        "claims": {
            "delivery_movement_days": 21,
            "forecast_milestone_slip_days": 13,
            "successor_dependency_effect": "Successor testing follows installation completion.",
        },
        "citations": {
            "delivery_movement_days": ["SCH-DELIVERY-001"],
            "forecast_milestone_slip_days": ["SCH-DELIVERY-001"],
        },
        "unsupported_claims": [],
        "warnings": ["Schedule conclusions depend on supplied schedule data."],
    }


def test_schedule_expert_evidence_filtering() -> None:
    bundle = load_equipment_delay_case(FIXTURE_PATH)
    ids = selected_evidence_record_ids(bundle, AgentRole.SCHEDULE_EXPERT.value)

    assert "CASE-INTAKE-001" in ids
    assert "SCH-DELIVERY-001" in ids
    assert "COST-SUMMARY-001" not in ids
    assert "CTR-DELAY-001" not in ids
    assert "SUP-NOT-ARRIVED-001" not in ids
    assert "LOG-STATUS-001" not in ids
    assert "PRG-ONSITE-001" not in ids
    assert all(record.record_type in {"case_intake", "schedule_record"} for record in select_evidence_for_role(bundle, AgentRole.SCHEDULE_EXPERT.value))


def test_commercial_expert_evidence_filtering() -> None:
    bundle = load_equipment_delay_case(FIXTURE_PATH)
    ids = selected_evidence_record_ids(bundle, AgentRole.COMMERCIAL_EXPERT.value)

    assert {"CASE-INTAKE-001", "SCH-DELIVERY-001", "COST-SUMMARY-001", "CTR-DELAY-001"} <= set(ids)
    assert "SUP-NOT-ARRIVED-001" not in ids
    assert "LOG-STATUS-001" not in ids
    assert "PRG-ONSITE-001" not in ids


def test_evidence_auditor_and_generalist_access() -> None:
    bundle = load_equipment_delay_case(FIXTURE_PATH)
    auditor_ids = set(selected_evidence_record_ids(bundle, AgentRole.EVIDENCE_AUDITOR.value))
    generalist_ids = set(selected_evidence_record_ids(bundle, AgentRole.GENERALIST.value))
    all_ids = set(bundle.evidence_by_id)

    assert {"PRG-ONSITE-001", "SUP-NOT-ARRIVED-001", "LOG-STATUS-001"} <= auditor_ids
    assert generalist_ids == all_ids


def test_schedule_prompt_receives_only_scoped_evidence() -> None:
    bundle = load_equipment_delay_case(FIXTURE_PATH)
    prompt = render_agent_prompt(
        bundle=bundle,
        agent_role=AgentRole.SCHEDULE_EXPERT.value,
        expected_response_schema=SPECIALIST_FINDING_RESPONSE_SCHEMA,
        correlation_id="scope-prompt",
        experiment_variant="dynamic_expert_council",
        invocation_purpose=InvocationPurpose.STANDALONE_LIVE_AGENT,
    )

    assert "SCH-DELIVERY-001" in prompt
    assert "SUP-NOT-ARRIVED-001" not in prompt
    assert "LOG-STATUS-001" not in prompt
    assert "COST-SUMMARY-001" not in prompt
    assert '"invocation_purpose": "standalone_live_agent"' in prompt


def test_schedule_expert_valid_schedule_only_response_is_role_valid() -> None:
    bundle = load_equipment_delay_case(FIXTURE_PATH)
    response = SpecialistFindingResponse.model_validate(valid_schedule_response())
    result = validate_specialist_response(
        role=AgentRole.SCHEDULE_EXPERT.value,
        invocation_id="INV-SCHEDULE-VALID",
        response=response,
        selected_record_ids=selected_evidence_record_ids(bundle, AgentRole.SCHEDULE_EXPERT.value),
        bundle=bundle,
    )

    assert result.valid is True
    assert "delivery_movement_days" in result.allowed_claims
    assert result.prohibited_claims == []
    assert result.prohibited_warnings == []


def test_dynamic_schedule_identifier_scope_drift_fixture_is_role_valid() -> None:
    bundle = load_equipment_delay_case(FIXTURE_PATH)
    payload = read_json(Path(__file__).parent / "fixtures" / "dynamic_schedule_scope_drift_response.json")
    normalization = normalize_claim_keys(
        invocation_id="INV-DYNAMIC-SCHEDULE-SCOPE-DRIFT",
        role=AgentRole.SCHEDULE_EXPERT.value,
        response_payload=payload,
    )
    normalized = normalize_response_payload(payload, normalization)
    result = validate_role_scope(
        role=AgentRole.SCHEDULE_EXPERT.value,
        invocation_id="INV-DYNAMIC-SCHEDULE-SCOPE-DRIFT",
        response_payload=normalized,
        selected_record_ids=["CASE-INTAKE-001", "SCH-DELIVERY-001"],
        bundle=bundle,
    )

    assert normalization.valid is True
    assert normalization.normalized_claims["milestone_id"] == "MS-COMMISSIONING-READY"
    assert normalization.normalized_claims["installation_activity_id"] == "A-4200"
    assert result.valid is True
    assert result.prohibited_claims == []


def test_schedule_expert_onsite_warning_detected_as_scope_violation() -> None:
    bundle = load_equipment_delay_case(FIXTURE_PATH)
    payload = valid_schedule_response()
    payload["warnings"] = ["Onsite-status contradiction remains unresolved."]
    response = SpecialistFindingResponse.model_validate(payload)

    result = validate_specialist_response(
        role=AgentRole.SCHEDULE_EXPERT.value,
        invocation_id="INV-SCHEDULE-ONSITE-WARNING",
        response=response,
        selected_record_ids=selected_evidence_record_ids(bundle, AgentRole.SCHEDULE_EXPERT.value),
        bundle=bundle,
    )

    assert result.valid is False
    assert result.prohibited_warnings
    assert "onsite_status" in result.prohibited_warnings[0]


def test_schedule_expert_commercial_claim_detected_as_scope_violation() -> None:
    bundle = load_equipment_delay_case(FIXTURE_PATH)
    payload = valid_schedule_response()
    payload["claims"]["unmitigated_exposure_usd"] = 195000
    response = SpecialistFindingResponse.model_validate(payload)

    result = validate_specialist_response(
        role=AgentRole.SCHEDULE_EXPERT.value,
        invocation_id="INV-SCHEDULE-COMMERCIAL",
        response=response,
        selected_record_ids=selected_evidence_record_ids(bundle, AgentRole.SCHEDULE_EXPERT.value),
        bundle=bundle,
    )

    assert result.valid is False
    assert any("unmitigated_exposure_usd" in item for item in result.prohibited_claims)


def test_prohibited_citation_source_detected() -> None:
    bundle = load_equipment_delay_case(FIXTURE_PATH)
    payload = valid_schedule_response()
    payload["citations"]["projected_milestone_slip_days"] = ["SCH-DELIVERY-001", "LOG-STATUS-001"]
    response = SpecialistFindingResponse.model_validate(payload)

    result = validate_specialist_response(
        role=AgentRole.SCHEDULE_EXPERT.value,
        invocation_id="INV-SCHEDULE-BAD-CITATION",
        response=response,
        selected_record_ids=selected_evidence_record_ids(bundle, AgentRole.SCHEDULE_EXPERT.value),
        bundle=bundle,
    )

    assert result.valid is False
    assert any("LOG-STATUS-001" in item for item in result.citation_policy_violations)


def test_schema_valid_but_role_invalid_response() -> None:
    bundle = load_equipment_delay_case(FIXTURE_PATH)
    payload = valid_schedule_response()
    payload["warnings"] = ["Supplier and logistics records show the equipment is not onsite."]
    response = SpecialistFindingResponse.model_validate(payload)

    result = validate_specialist_response(
        role=AgentRole.SCHEDULE_EXPERT.value,
        invocation_id="INV-SCHEMA-VALID-ROLE-INVALID",
        response=response,
        selected_record_ids=selected_evidence_record_ids(bundle, AgentRole.SCHEDULE_EXPERT.value),
        bundle=bundle,
    )

    assert response.status == "completed"
    assert result.valid is False


def test_evidence_overexposure_detection() -> None:
    bundle = load_equipment_delay_case(FIXTURE_PATH)
    selected = selected_evidence_record_ids(bundle, AgentRole.SCHEDULE_EXPERT.value) + ["SUP-NOT-ARRIVED-001"]

    result = validate_role_scope(
        role=AgentRole.SCHEDULE_EXPERT.value,
        invocation_id="INV-OVEREXPOSED",
        response_payload=valid_schedule_response(),
        selected_record_ids=selected,
        bundle=bundle,
    )

    assert result.valid is False
    assert any("SUP-NOT-ARRIVED-001" in item for item in result.evidence_scope_violations)


def test_role_compliance_metric_aggregation() -> None:
    bundle = load_equipment_delay_case(FIXTURE_PATH)
    valid = validate_role_scope(
        role=AgentRole.SCHEDULE_EXPERT.value,
        invocation_id="INV-VALID",
        response_payload=valid_schedule_response(),
        selected_record_ids=selected_evidence_record_ids(bundle, AgentRole.SCHEDULE_EXPERT.value),
        bundle=bundle,
    )
    invalid = validate_role_scope(
        role=AgentRole.SCHEDULE_EXPERT.value,
        invocation_id="INV-INVALID",
        response_payload={**valid_schedule_response(), "warnings": ["Equipment is not onsite."]},
        selected_record_ids=selected_evidence_record_ids(bundle, AgentRole.SCHEDULE_EXPERT.value),
        bundle=bundle,
    )

    metrics = role_compliance_metrics([valid, invalid])
    metric_results = role_scope_metric_results([valid, invalid])

    assert metrics["scope_compliance_rate"] == 0.5
    assert metrics["prohibited_warning_count"] == 1.0
    assert any(item.metric_id == EvaluationMetricId.SCOPE_COMPLIANCE_RATE and item.score == 0.5 for item in metric_results)


def test_standalone_live_agent_metadata_and_artifacts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DASHSCOPE_API_KEY", DUMMY_SECRET)
    transport = MockTransport(provider_response(valid_schedule_response()))
    client = QwenModelClient(config(), transport=transport, sleep_func=lambda _: None)

    run_path = run_live_agent(
        agent_role=AgentRole.SCHEDULE_EXPERT.value,
        config=config(),
        allow_network=True,
        artifacts_root=tmp_path / "live",
        experiment_id="standalone-schedule",
        client=client,
    )

    assert validate_experiment_artifacts(run_path).passed is True
    invocations = read_json(run_path / "invocation-records.json")
    experiment_config = read_json(run_path / "experiment-config.json")
    assert invocations[0]["invocation_purpose"] == "standalone_live_agent"
    assert experiment_config["invocation_purpose"] == "standalone_live_agent"
    assert invocations[0]["variant"] != "single_generalist"
    assert invocations[0]["request"]["metadata"]["invocation_purpose"] == "standalone_live_agent"
    assert invocations[0]["request"]["metadata"]["experiment_variant"] is None
    selected = read_json(run_path / "selected-evidence-records.json")
    assert selected[0]["record_ids"] == ["CASE-INTAKE-001", "SCH-DELIVERY-001"]
    role_results = read_json(run_path / "role-validation-results.json")
    assert role_results[0]["valid"] is True
    assert transport.calls
    payload_text = json.dumps(transport.calls[0]["payload"])
    assert "SCH-DELIVERY-001" in payload_text
    assert "SUP-NOT-ARRIVED-001" not in payload_text
