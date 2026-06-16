from pathlib import Path

from project_recovery_council.experiment_contracts import RECOVERY_ANALYSIS_RESPONSE_SCHEMA, SCHEMA_REGISTRY
from project_recovery_council.model_client import (
    DisabledQwenModelClient,
    FailureKind,
    FinishStatus,
    ModelRequest,
    OfflineModelClient,
)
from project_recovery_council.offline_experiments import load_offline_fixture, model_response_from_fixture


FIXTURE_PATH = Path(__file__).parents[1] / "sample-data" / "equipment-delay-case"


def test_offline_model_client_returns_schema_valid_fixture_response() -> None:
    fixture = load_offline_fixture("strong_modular_council")
    request = ModelRequest(
        model_identifier="offline-qwen-placeholder",
        system_instructions="Use fixture only.",
        user_payload={"case_id": "PRC-EQ-DELAY-001"},
        expected_response_schema=RECOVERY_ANALYSIS_RESPONSE_SCHEMA,
        correlation_id=fixture["correlation_id"],
        metadata={"fixture_id": fixture["fixture_id"]},
    )
    client = OfflineModelClient(
        {fixture["fixture_id"]: model_response_from_fixture(fixture)},
        schema_registry=SCHEMA_REGISTRY,
    )

    result = client.generate(request)

    assert result.finish_status == FinishStatus.COMPLETED
    assert result.parsed_response["projected_slip_days"] == 13
    assert result.input_token_count is None
    assert result.latency_seconds is None
    assert result.simulated is True


def test_offline_model_client_reports_malformed_structured_response() -> None:
    fixture = load_offline_fixture("malformed_structured_response")
    request = ModelRequest(
        model_identifier="offline-qwen-placeholder",
        system_instructions="Use fixture only.",
        user_payload={"case_id": "PRC-EQ-DELAY-001"},
        expected_response_schema=RECOVERY_ANALYSIS_RESPONSE_SCHEMA,
        correlation_id=fixture["correlation_id"],
        metadata={"fixture_id": fixture["fixture_id"]},
    )
    client = OfflineModelClient(
        {fixture["fixture_id"]: model_response_from_fixture(fixture)},
        schema_registry=SCHEMA_REGISTRY,
    )

    result = client.generate(request)

    assert result.finish_status == FinishStatus.VALIDATION_ERROR
    assert result.failure.kind == FailureKind.VALIDATION_ERROR
    assert result.validation_errors


def test_disabled_qwen_client_returns_typed_configuration_failure_without_network() -> None:
    request = ModelRequest(
        model_identifier="qwen-live-disabled",
        system_instructions="Would call Qwen in a later run.",
        user_payload={"case_id": "PRC-EQ-DELAY-001"},
        expected_response_schema=RECOVERY_ANALYSIS_RESPONSE_SCHEMA,
        correlation_id="disabled-qwen-test",
    )

    result = DisabledQwenModelClient().generate(request)

    assert result.finish_status == FinishStatus.CONFIGURATION_ERROR
    assert result.failure.kind == FailureKind.CONFIGURATION_ERROR
    assert result.failure.error_type == "ModelClientConfigurationError"
    assert result.provider_metadata["network_attempted"] is False
    assert result.provider_metadata["live_provider_enabled"] is False
