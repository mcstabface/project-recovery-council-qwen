import json
from pathlib import Path
from typing import Any

import pytest

from project_recovery_council.experiment_artifacts import validate_experiment_artifacts
from project_recovery_council.experiment_contracts import LIVE_SMOKE_RESPONSE_SCHEMA
from project_recovery_council.live_experiments import run_live_smoke
from project_recovery_council.model_client import FailureKind, FinishStatus, ModelRequest
from project_recovery_council.qwen_client import HttpResponse, QwenModelClient, QwenTimeoutError
from project_recovery_council.qwen_config import QwenProviderConfig, StructuredOutputMode
from project_recovery_council.redaction import redact_value
from project_recovery_council.serialization import read_json


DUMMY_SECRET = "dummy-secret-value-for-redaction"


class MockTransport:
    def __init__(self, responses: list[HttpResponse | Exception]) -> None:
        self.responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    def post_json(self, *, url: str, headers: dict[str, str], payload: dict[str, Any], timeout_seconds: float):
        self.calls.append(
            {
                "url": url,
                "headers": headers,
                "payload": payload,
                "timeout_seconds": timeout_seconds,
            }
        )
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def config(**kwargs) -> QwenProviderConfig:
    values = {
        "api_key_env_var": "DASHSCOPE_API_KEY",
        "base_url": "https://example.invalid/compatible-mode/v1",
        "model_identifier": "explicit-test-model",
        "request_timeout_seconds": 3.0,
        "maximum_retries": 1,
        "temperature": 0.0,
    }
    values.update(kwargs)
    return QwenProviderConfig(**values)


def request() -> ModelRequest:
    return ModelRequest(
        model_identifier="explicit-test-model",
        system_instructions="Return JSON only.",
        user_payload="small smoke prompt",
        expected_response_schema=LIVE_SMOKE_RESPONSE_SCHEMA,
        correlation_id="test-correlation",
    )


def provider_response(content: dict[str, Any], *, status_code: int = 200, usage: dict[str, int] | None = None):
    body = {
        "id": "chatcmpl-test",
        "choices": [
            {
                "message": {"role": "assistant", "content": json.dumps(content)},
                "finish_reason": "stop",
            }
        ],
    }
    if usage is not None:
        body["usage"] = usage
    return HttpResponse(
        status_code=status_code,
        headers={"x-request-id": "req-test-123"},
        body=json.dumps(body),
    )


def smoke_content() -> dict[str, Any]:
    return {
        "schema_version": LIVE_SMOKE_RESPONSE_SCHEMA,
        "status": "ok",
        "model_identifier": "explicit-test-model",
        "short_message": "reachable",
    }


def test_missing_credential_rejected_before_network(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    transport = MockTransport([provider_response(smoke_content())])

    result = QwenModelClient(config(), transport=transport, sleep_func=lambda _: None).generate(request())

    assert result.finish_status == FinishStatus.CONFIGURATION_ERROR
    assert result.failure.kind == FailureKind.CONFIGURATION_ERROR
    assert result.provider_metadata["network_attempted"] is False
    assert transport.calls == []


def test_secret_redaction_centralized() -> None:
    payload = {
        "Authorization": f"Bearer {DUMMY_SECRET}",
        "nested": {"api_key": DUMMY_SECRET, "safe": f"prefix-{DUMMY_SECRET}"},
    }

    redacted = redact_value(payload, [DUMMY_SECRET])

    assert DUMMY_SECRET not in json.dumps(redacted)
    assert redacted["Authorization"] == "[REDACTED]"
    assert redacted["nested"]["api_key"] == "[REDACTED]"


def test_successful_structured_response_token_accounting_and_request_id(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DASHSCOPE_API_KEY", DUMMY_SECRET)
    transport = MockTransport(
        [
            provider_response(
                smoke_content(),
                usage={"prompt_tokens": 11, "completion_tokens": 7, "total_tokens": 18},
            )
        ]
    )

    result = QwenModelClient(config(), transport=transport, sleep_func=lambda _: None).generate(request())

    assert result.finish_status == FinishStatus.COMPLETED
    assert result.parsed_response["status"] == "ok"
    assert result.input_token_count == 11
    assert result.output_token_count == 7
    assert result.total_token_count == 18
    assert result.provider_metadata["provider_request_id"] == "req-test-123"
    assert result.provider_metadata["network_attempted"] is True
    assert DUMMY_SECRET not in json.dumps(result.provider_metadata)


def test_prompted_json_fallback_does_not_send_response_format(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DASHSCOPE_API_KEY", DUMMY_SECRET)
    transport = MockTransport([provider_response(smoke_content())])
    client = QwenModelClient(
        config(structured_output_mode=StructuredOutputMode.PROMPTED_JSON),
        transport=transport,
        sleep_func=lambda _: None,
    )

    result = client.generate(request())

    assert result.finish_status == FinishStatus.COMPLETED
    assert "response_format" not in transport.calls[0]["payload"]
    assert result.provider_metadata["requested_structured_output_mode"] == "prompted_json"
    assert result.provider_metadata["actual_structured_output_mode"] == "prompted_json"


def test_provider_json_object_mode_records_and_sends_response_format(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DASHSCOPE_API_KEY", DUMMY_SECRET)
    transport = MockTransport([provider_response(smoke_content())])
    client = QwenModelClient(
        config(structured_output_mode=StructuredOutputMode.PROVIDER_JSON_OBJECT),
        transport=transport,
        sleep_func=lambda _: None,
    )

    result = client.generate(request())

    assert result.finish_status == FinishStatus.COMPLETED
    assert transport.calls[0]["payload"]["response_format"] == {"type": "json_object"}
    assert result.provider_metadata["requested_structured_output_mode"] == "provider_json_object"


def test_schema_validation_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DASHSCOPE_API_KEY", DUMMY_SECRET)
    bad_content = {"schema_version": LIVE_SMOKE_RESPONSE_SCHEMA, "status": "ok"}
    transport = MockTransport([provider_response(bad_content)])

    result = QwenModelClient(config(), transport=transport, sleep_func=lambda _: None).generate(request())

    assert result.finish_status == FinishStatus.VALIDATION_ERROR
    assert result.failure.kind == FailureKind.SCHEMA_ERROR
    assert result.validation_errors


def test_timeout_retry_then_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DASHSCOPE_API_KEY", DUMMY_SECRET)
    transport = MockTransport([QwenTimeoutError("timed out"), provider_response(smoke_content())])

    result = QwenModelClient(config(maximum_retries=1), transport=transport, sleep_func=lambda _: None).generate(request())

    assert result.finish_status == FinishStatus.COMPLETED
    assert result.retry_count == 1
    assert len(transport.calls) == 2


def test_rate_limit_retries_and_records_history(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DASHSCOPE_API_KEY", DUMMY_SECRET)
    transport = MockTransport(
        [
            HttpResponse(status_code=429, headers={"x-request-id": "rl-1"}, body='{"error":"rate limited"}'),
            provider_response(smoke_content()),
        ]
    )

    result = QwenModelClient(config(maximum_retries=1), transport=transport, sleep_func=lambda _: None).generate(request())

    assert result.finish_status == FinishStatus.COMPLETED
    assert result.retry_count == 1
    assert result.provider_metadata["retry_history"][0]["event"] == "rate_limit"


def test_retry_exhaustion(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DASHSCOPE_API_KEY", DUMMY_SECRET)
    transport = MockTransport(
        [
            HttpResponse(status_code=429, headers={"x-request-id": "rl-1"}, body='{"error":"rate limited"}'),
            HttpResponse(status_code=429, headers={"x-request-id": "rl-2"}, body='{"error":"rate limited"}'),
        ]
    )

    result = QwenModelClient(config(maximum_retries=1), transport=transport, sleep_func=lambda _: None).generate(request())

    assert result.finish_status == FinishStatus.FAILED
    assert result.failure.kind == FailureKind.RATE_LIMIT
    assert result.retry_count == 1
    assert len(transport.calls) == 2


def test_provider_error_response(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DASHSCOPE_API_KEY", DUMMY_SECRET)
    transport = MockTransport(
        [HttpResponse(status_code=400, headers={"x-request-id": "bad-1"}, body='{"error":"bad request"}')]
    )

    result = QwenModelClient(config(), transport=transport, sleep_func=lambda _: None).generate(request())

    assert result.finish_status == FinishStatus.FAILED
    assert result.failure.kind == FailureKind.PROVIDER_ERROR
    assert result.provider_metadata["http_status"] == 400
    assert result.provider_metadata["provider_request_id"] == "bad-1"


def test_live_artifact_path_isolated_overwrite_protected_and_redacted(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DASHSCOPE_API_KEY", DUMMY_SECRET)
    content = smoke_content()
    response = provider_response(content)
    body = json.loads(response.body)
    body["secret_echo"] = DUMMY_SECRET
    transport = MockTransport([HttpResponse(status_code=200, headers=response.headers, body=json.dumps(body))])
    client = QwenModelClient(config(), transport=transport, sleep_func=lambda _: None)

    run_path = run_live_smoke(
        config=config(),
        allow_network=True,
        artifacts_root=tmp_path / "live",
        experiment_id="live-redaction-test",
        client=client,
    )

    assert run_path == tmp_path / "live" / "live-redaction-test"
    assert validate_experiment_artifacts(run_path).passed is True
    for path in run_path.rglob("*.json"):
        assert DUMMY_SECRET not in path.read_text(encoding="utf-8")

    second_transport = MockTransport([provider_response(content)])
    second_client = QwenModelClient(config(), transport=second_transport, sleep_func=lambda _: None)
    with pytest.raises(FileExistsError):
        run_live_smoke(
            config=config(),
            allow_network=True,
            artifacts_root=tmp_path / "live",
            experiment_id="live-redaction-test",
            client=second_client,
        )
    assert second_transport.calls == []

    sanitized = read_json(run_path / "sanitized-provider-config.json")
    assert sanitized["api_key_present"] is True
    assert "authorization" not in json.dumps(sanitized).lower()
