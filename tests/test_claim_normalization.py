import json
from pathlib import Path
from typing import Any

import pytest

from project_recovery_council.claim_normalization import (
    claim_normalization_metrics,
    normalize_claim_keys,
    normalize_response_payload,
)
from project_recovery_council.experiment_artifacts import validate_experiment_artifacts
from project_recovery_council.experiment_contracts import AgentRole, SPECIALIST_FINDING_RESPONSE_SCHEMA
from project_recovery_council.fixtures import load_equipment_delay_case
from project_recovery_council.live_experiments import run_live_agent
from project_recovery_council.qwen_client import HttpResponse, QwenModelClient
from project_recovery_council.qwen_config import QwenProviderConfig
from project_recovery_council.role_scope import selected_evidence_record_ids, validate_role_scope
from project_recovery_council.schedule_semantics import validate_schedule_semantics
from project_recovery_council.serialization import read_json, write_json


FIXTURE_PATH = Path(__file__).parents[1] / "sample-data" / "equipment-delay-case"
DUMMY_SECRET = "dummy-normalization-secret"


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
        headers={"x-request-id": "claim-normalization-test"},
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


def canonical_schedule_response(**overrides: Any) -> dict[str, Any]:
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
    return _specialist_payload(claims)


def alias_schedule_response(**overrides: Any) -> dict[str, Any]:
    claims = {
        "milestone_id": "MS-COMMISSIONING-READY",
        "baseline_delivery_date": "2026-07-01",
        "forecast_delivery_date": "2026-07-22",
        "delivery_movement_days": 21,
        "installation_total_float_days": 8,
        "installation_total_float_consumed_days": 8,
        "remaining_float_after_delivery_shift_days": 0,
        "float_consumption_status": "fully_consumed",
        "delivery_movement_direction": "late",
        "contractual_milestone_baseline_date": "2026-08-15",
        "contractual_milestone_forecast_without_intervention": "2026-08-28",
        "forecast_milestone_slip_days": 13,
        "successor_testing_activity_id": "A-4300",
        "successor_dependency_effect": "Successor testing follows installation completion.",
    }
    claims.update(overrides)
    return _specialist_payload(claims)


def _specialist_payload(claims: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": SPECIALIST_FINDING_RESPONSE_SCHEMA,
        "agent_role": AgentRole.SCHEDULE_EXPERT.value,
        "status": "completed",
        "claims": claims,
        "citations": {key: ["SCH-DELIVERY-001"] for key in claims},
        "unsupported_claims": [],
        "warnings": ["Schedule conclusions depend on supplied schedule data."],
    }


def normalize(payload: dict[str, Any], invocation_id: str = "INV-NORMALIZE"):
    return normalize_claim_keys(
        invocation_id=invocation_id,
        role=AgentRole.SCHEDULE_EXPERT.value,
        response_payload=payload,
    )


def test_canonical_keys_pass_unchanged() -> None:
    payload = canonical_schedule_response()
    result = normalize(payload)

    assert result.valid is True
    assert result.raw_claims == payload["claims"]
    assert result.normalized_claims == payload["claims"]
    assert result.applied_aliases == []
    assert result.unknown_claim_keys == []


def test_each_schedule_alias_maps_to_canonical_key() -> None:
    payload = alias_schedule_response()
    result = normalize(payload)
    aliases = {item.raw_key: item.canonical_key for item in result.applied_aliases}

    assert aliases["baseline_delivery_date"] == "delivery_baseline_date"
    assert aliases["forecast_delivery_date"] == "delivery_forecast_date"
    assert aliases["remaining_float_after_delivery_shift_days"] == "installation_total_float_remaining_days"
    payload_with_consumed_alias = alias_schedule_response(float_consumed_days=8)
    consumed_result = normalize(payload_with_consumed_alias)
    consumed_aliases = {item.raw_key: item.canonical_key for item in consumed_result.applied_aliases}

    assert consumed_aliases["float_consumed_days"] == "installation_total_float_consumed_days"
    payload_with_total_float = alias_schedule_response(
        remaining_float_after_delivery_shift_days=0,
        remaining_total_float_days=0,
    )
    total_float_result = normalize(payload_with_total_float)
    total_float_aliases = {item.raw_key: item.canonical_key for item in total_float_result.applied_aliases}

    assert total_float_aliases["remaining_total_float_days"] == "installation_total_float_remaining_days"
    assert aliases["contractual_milestone_baseline_date"] == "milestone_baseline_date"
    assert (
        aliases["contractual_milestone_forecast_without_intervention"]
        == "milestone_forecast_date_without_intervention"
    )
    assert result.normalized_claims["delivery_baseline_date"] == "2026-07-01"
    assert result.normalized_claims["installation_total_float_remaining_days"] == 0


def test_observed_schedule_remaining_float_alias_maps_to_canonical_key() -> None:
    payload = alias_schedule_response(
        remaining_float_after_delivery_shift_days=0,
        remaining_total_float_after_delivery_shift_days=0,
    )
    result = normalize(payload)
    aliases = {item.raw_key: item.canonical_key for item in result.applied_aliases}

    assert result.valid is True
    assert aliases["remaining_total_float_after_delivery_shift_days"] == "installation_total_float_remaining_days"
    assert result.normalized_claims["installation_total_float_remaining_days"] == 0


def test_evidence_auditor_claim_id_aliases_are_explicitly_versioned() -> None:
    payload = {
        "schema_version": SPECIALIST_FINDING_RESPONSE_SCHEMA,
        "agent_role": AgentRole.EVIDENCE_AUDITOR.value,
        "status": "completed",
        "claims": {
            "claim-onsite-assertion": {"assessment": "contradicted"},
            "claim-milestone-slip-13-days": {"assessment": "supported"},
            "claim-delay-exposure-15000-per-day": {"assessment": "supported"},
            "claim-unmitigated-exposure-195000": {"assessment": "supported"},
            "claim-accelerated-logistics-cost-48000": {"assessment": "supported"},
        },
        "citations": {},
        "unsupported_claims": [],
        "warnings": [],
    }
    result = normalize_claim_keys(
        invocation_id="INV-AUDITOR-ALIASES",
        role=AgentRole.EVIDENCE_AUDITOR.value,
        response_payload=payload,
    )

    assert result.valid is True
    assert result.unknown_claim_keys == []
    assert set(result.normalized_claims) == {
        "C-ONSITE-ASSERTION",
        "C-MILESTONE-SLIP-13D",
        "C-DELAY-EXPOSURE-15K-USD-PER-DAY",
        "C-UNMITIGATED-EXPOSURE-195K-USD",
        "C-ACCEL-COST-48K-USD",
    }


def test_raw_response_remains_unchanged_and_normalized_response_uses_canonical_keys() -> None:
    payload = alias_schedule_response()
    original_claims = dict(payload["claims"])
    result = normalize(payload)
    normalized = normalize_response_payload(payload, result)

    assert payload["claims"] == original_claims
    assert "remaining_float_after_delivery_shift_days" in payload["claims"]
    assert "remaining_float_after_delivery_shift_days" not in normalized["claims"]
    assert normalized["claims"]["installation_total_float_remaining_days"] == 0


def test_equal_canonical_plus_alias_values_pass() -> None:
    payload = alias_schedule_response(installation_total_float_remaining_days=0)
    result = normalize(payload)

    assert result.valid is True
    assert result.normalized_claims["installation_total_float_remaining_days"] == 0
    assert any(
        item.raw_key == "remaining_float_after_delivery_shift_days"
        and item.canonical_key == "installation_total_float_remaining_days"
        for item in result.applied_aliases
    )


def test_conflicting_canonical_plus_alias_values_fail() -> None:
    payload = alias_schedule_response(installation_total_float_remaining_days=2)
    result = normalize(payload)

    assert result.valid is False
    assert "installation_total_float_remaining_days" not in result.normalized_claims
    assert result.conflicts[0].canonical_key == "installation_total_float_remaining_days"


def test_conflicting_aliases_fail() -> None:
    payload = alias_schedule_response(remaining_float_days=2)
    result = normalize(payload)

    assert result.valid is False
    assert result.conflicts[0].canonical_key == "installation_total_float_remaining_days"
    assert {"remaining_float_after_delivery_shift_days", "remaining_float_days"} <= set(result.conflicts[0].raw_keys)


def test_unknown_keys_remain_visible_and_role_prohibited() -> None:
    bundle = load_equipment_delay_case(FIXTURE_PATH)
    payload = alias_schedule_response(equipment_onsite_status="not onsite")
    result = normalize(payload)
    normalized = normalize_response_payload(payload, result)
    role = validate_role_scope(
        role=AgentRole.SCHEDULE_EXPERT.value,
        invocation_id="INV-UNKNOWN",
        response_payload=normalized,
        selected_record_ids=selected_evidence_record_ids(bundle, AgentRole.SCHEDULE_EXPERT.value),
        bundle=bundle,
    )

    assert "equipment_onsite_status" in result.unknown_claim_keys
    assert "equipment_onsite_status" in normalized["claims"]
    assert role.valid is False
    assert any("equipment_onsite_status" in item for item in role.prohibited_claims)


def test_role_validation_passes_latest_live_response_shape_after_normalization() -> None:
    bundle = load_equipment_delay_case(FIXTURE_PATH)
    payload = alias_schedule_response(
        remaining_float_after_delivery_shift_days=0,
        remaining_total_float_days=0,
        float_consumption_status="fully_consumed",
    )
    result = normalize(payload, invocation_id="INV-LIVE-SHAPE")
    normalized = normalize_response_payload(payload, result)
    role = validate_role_scope(
        role=AgentRole.SCHEDULE_EXPERT.value,
        invocation_id="INV-LIVE-SHAPE",
        response_payload=normalized,
        selected_record_ids=selected_evidence_record_ids(bundle, AgentRole.SCHEDULE_EXPERT.value),
        bundle=bundle,
    )

    assert result.valid is True
    assert role.valid is True
    assert "installation_total_float_remaining_days" in role.allowed_claims
    assert "float_consumption_status" in role.allowed_claims
    assert "milestone_baseline_date" in role.allowed_claims
    assert "milestone_forecast_date_without_intervention" in role.allowed_claims


def test_schedule_semantic_validation_passes_for_normalized_live_response_shape() -> None:
    bundle = load_equipment_delay_case(FIXTURE_PATH)
    payload = alias_schedule_response(
        remaining_float_after_delivery_shift_days=0,
        remaining_total_float_days=0,
        float_consumption_status="fully_consumed",
    )
    result = normalize(payload, invocation_id="INV-LIVE-SEMANTIC")
    normalized = normalize_response_payload(payload, result)
    semantic = validate_schedule_semantics(
        invocation_id="INV-LIVE-SEMANTIC",
        response_payload=normalized,
        bundle=bundle,
    )

    assert semantic.valid is True
    assert semantic.observed_values["installation_total_float_remaining_days"] == 0
    assert semantic.observed_values["float_consumption_status"] == "fully_consumed"
    assert semantic.observed_values["milestone_forecast_date_without_intervention"] == "2026-08-28"


def test_claim_normalization_metric_aggregation() -> None:
    valid = normalize(alias_schedule_response(), invocation_id="INV-VALID")
    invalid = normalize(alias_schedule_response(installation_total_float_remaining_days=2), invocation_id="INV-BAD")

    metrics = claim_normalization_metrics([valid, invalid])

    assert metrics["claim_normalization_success_rate"] == 0.5
    assert metrics["alias_application_count"] >= 6.0
    assert metrics["claim_alias_conflict_count"] == 1.0


def test_live_artifacts_preserve_raw_and_normalized_responses(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DASHSCOPE_API_KEY", DUMMY_SECRET)
    transport = MockTransport(provider_response(alias_schedule_response()))
    client = QwenModelClient(
        config(),
        transport=transport,
        sleep_func=lambda _: None,
    )

    run_path = run_live_agent(
        agent_role=AgentRole.SCHEDULE_EXPERT.value,
        config=config(),
        allow_network=True,
        artifacts_root=tmp_path / "live",
        experiment_id="claim-normalization-artifact",
        client=client,
    )

    assert len(transport.calls) == 1
    assert validate_experiment_artifacts(run_path).passed is True
    parsed = read_json(run_path / "parsed-structured-responses.json")[0]["parsed_response"]
    normalized = read_json(run_path / "normalized-structured-responses.json")[0]["normalized_response"]
    normalization = read_json(run_path / "claim-normalization-results.json")[0]
    metrics = read_json(run_path / "claim-normalization-metrics.json")

    assert "remaining_float_after_delivery_shift_days" in parsed["claims"]
    assert "remaining_float_after_delivery_shift_days" not in normalized["claims"]
    assert normalized["claims"]["installation_total_float_remaining_days"] == 0
    assert normalization["raw_claims"] == parsed["claims"]
    assert normalization["normalized_claims"] == normalized["claims"]
    assert metrics["claim_normalization_success_rate"] == 1.0


def test_artifact_inspection_requires_normalization_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DASHSCOPE_API_KEY", DUMMY_SECRET)
    client = QwenModelClient(
        config(),
        transport=MockTransport(provider_response(alias_schedule_response())),
        sleep_func=lambda _: None,
    )
    run_path = run_live_agent(
        agent_role=AgentRole.SCHEDULE_EXPERT.value,
        config=config(),
        allow_network=True,
        artifacts_root=tmp_path / "live",
        experiment_id="claim-normalization-required",
        client=client,
    )
    manifest = read_json(run_path / "artifact-manifest.json")
    manifest["artifacts"] = [
        entry for entry in manifest["artifacts"] if entry["relative_path"] != "claim-normalization-results.json"
    ]
    write_json(run_path / "artifact-manifest.json", manifest)

    inspection = validate_experiment_artifacts(run_path)

    assert inspection.passed is False
    assert any("claim-normalization-results.json" in error for error in inspection.errors)
