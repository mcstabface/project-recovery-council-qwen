"""Opt-in live Qwen client behind the provider-neutral ModelClient boundary."""

from __future__ import annotations

import json
import socket
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from time import perf_counter
from typing import Any, Callable, Protocol

from pydantic import ValidationError

from project_recovery_council.experiment_contracts import SCHEMA_REGISTRY
from project_recovery_council.model_client import (
    FailureKind,
    FinishStatus,
    ModelClientConfigurationError,
    ModelFailure,
    ModelRequest,
    ModelResult,
    SchemaRegistry,
)
from project_recovery_council.qwen_config import QwenProviderConfig, StructuredOutputMode
from project_recovery_council.redaction import redact_value


class QwenTransportError(RuntimeError):
    """Raised when the HTTP transport fails before a provider response exists."""


class QwenTimeoutError(TimeoutError):
    """Raised when the HTTP transport times out."""


@dataclass(frozen=True)
class HttpResponse:
    status_code: int
    headers: dict[str, str]
    body: str


class QwenTransport(Protocol):
    def post_json(
        self,
        *,
        url: str,
        headers: dict[str, str],
        payload: dict[str, Any],
        timeout_seconds: float,
    ) -> HttpResponse:
        """POST a JSON payload and return the provider response."""


class UrllibQwenTransport:
    """Small stdlib transport used only for explicit live commands."""

    def post_json(
        self,
        *,
        url: str,
        headers: dict[str, str],
        payload: dict[str, Any],
        timeout_seconds: float,
    ) -> HttpResponse:
        encoded = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=encoded,
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
                body = response.read().decode("utf-8")
                return HttpResponse(
                    status_code=int(response.status),
                    headers={str(key): str(value) for key, value in response.headers.items()},
                    body=body,
                )
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            return HttpResponse(
                status_code=int(exc.code),
                headers={str(key): str(value) for key, value in exc.headers.items()},
                body=body,
            )
        except (socket.timeout, TimeoutError) as exc:
            raise QwenTimeoutError(str(exc)) from exc
        except urllib.error.URLError as exc:
            if isinstance(exc.reason, socket.timeout):
                raise QwenTimeoutError(str(exc.reason)) from exc
            raise QwenTransportError(str(exc.reason)) from exc


class QwenModelClient:
    """Live Qwen-compatible client. It is never selected by default."""

    provider = "qwen"

    def __init__(
        self,
        config: QwenProviderConfig,
        *,
        transport: QwenTransport | None = None,
        schema_registry: SchemaRegistry | None = None,
        sleep_func: Callable[[float], None] = time.sleep,
    ) -> None:
        self.config = config
        self._transport = transport or UrllibQwenTransport()
        self._schema_registry = schema_registry or SCHEMA_REGISTRY
        self._sleep = sleep_func

    def generate(self, request: ModelRequest) -> ModelResult:
        api_key = self.config.read_api_key()
        if not api_key:
            return self._failure_result(
                request,
                kind=FailureKind.CONFIGURATION_ERROR,
                error_type=ModelClientConfigurationError.__name__,
                message=f"missing Qwen API key environment variable: {self.config.api_key_env_var}",
                finish_status=FinishStatus.CONFIGURATION_ERROR,
                network_attempted=False,
                retry_count=0,
                latency_seconds=None,
                retry_history=[],
            )

        payload = self._build_payload(request)
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }
        requested_mode = self.config.structured_output_mode
        retry_history: list[dict[str, Any]] = []
        started = perf_counter()
        network_attempted = False
        last_failure: ModelResult | None = None

        for attempt in range(self.config.maximum_retries + 1):
            try:
                network_attempted = True
                response = self._transport.post_json(
                    url=self.config.chat_completions_url,
                    headers=headers,
                    payload=payload,
                    timeout_seconds=self.config.request_timeout_seconds,
                )
            except QwenTimeoutError as exc:
                retry_history.append({"attempt": attempt + 1, "event": "timeout", "retryable": True})
                last_failure = self._failure_result(
                    request,
                    kind=FailureKind.TIMEOUT,
                    error_type=type(exc).__name__,
                    message="Qwen request timed out",
                    finish_status=FinishStatus.TIMEOUT,
                    network_attempted=network_attempted,
                    retry_count=attempt,
                    latency_seconds=perf_counter() - started,
                    retry_history=retry_history,
                )
                if attempt < self.config.maximum_retries:
                    self._sleep(self._backoff_seconds(attempt))
                    continue
                return last_failure
            except QwenTransportError as exc:
                retry_history.append({"attempt": attempt + 1, "event": "transport_error", "retryable": True})
                last_failure = self._failure_result(
                    request,
                    kind=FailureKind.TRANSPORT_ERROR,
                    error_type=type(exc).__name__,
                    message=str(exc),
                    finish_status=FinishStatus.FAILED,
                    network_attempted=network_attempted,
                    retry_count=attempt,
                    latency_seconds=perf_counter() - started,
                    retry_history=retry_history,
                )
                if attempt < self.config.maximum_retries:
                    self._sleep(self._backoff_seconds(attempt))
                    continue
                return last_failure

            status_code = response.status_code
            provider_request_id = _provider_request_id(response.headers)
            if status_code == 429:
                retry_history.append({"attempt": attempt + 1, "event": "rate_limit", "status_code": status_code})
                last_failure = self._provider_failure(
                    request,
                    response,
                    FailureKind.RATE_LIMIT,
                    "RateLimitError",
                    "Qwen provider returned HTTP 429 rate limit",
                    attempt,
                    perf_counter() - started,
                    network_attempted,
                    retry_history,
                    provider_request_id,
                    api_key,
                )
                if attempt < self.config.maximum_retries:
                    self._sleep(self._backoff_seconds(attempt))
                    continue
                return last_failure
            if status_code >= 500:
                retry_history.append({"attempt": attempt + 1, "event": "provider_5xx", "status_code": status_code})
                last_failure = self._provider_failure(
                    request,
                    response,
                    FailureKind.PROVIDER_ERROR,
                    "ProviderServerError",
                    f"Qwen provider returned HTTP {status_code}",
                    attempt,
                    perf_counter() - started,
                    network_attempted,
                    retry_history,
                    provider_request_id,
                    api_key,
                )
                if attempt < self.config.maximum_retries:
                    self._sleep(self._backoff_seconds(attempt))
                    continue
                return last_failure
            if status_code >= 400:
                retry_history.append({"attempt": attempt + 1, "event": "provider_4xx", "status_code": status_code})
                return self._provider_failure(
                    request,
                    response,
                    FailureKind.PROVIDER_ERROR,
                    "ProviderClientError",
                    f"Qwen provider returned HTTP {status_code}",
                    attempt,
                    perf_counter() - started,
                    network_attempted,
                    retry_history,
                    provider_request_id,
                    api_key,
                )

            return self._parse_success(
                request,
                response,
                retry_count=attempt,
                latency_seconds=perf_counter() - started,
                network_attempted=network_attempted,
                requested_mode=requested_mode,
                actual_mode=requested_mode,
                retry_history=retry_history,
                provider_request_id=provider_request_id,
                api_key=api_key,
                request_payload=payload,
            )

        if last_failure is not None:
            return last_failure
        return self._failure_result(
            request,
            kind=FailureKind.PROVIDER_ERROR,
            error_type="UnexpectedQwenClientState",
            message="Qwen client exhausted without response",
            finish_status=FinishStatus.FAILED,
            network_attempted=network_attempted,
            retry_count=self.config.maximum_retries,
            latency_seconds=perf_counter() - started,
            retry_history=retry_history,
        )

    def _build_payload(self, request: ModelRequest) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.config.model_identifier,
            "messages": [
                {"role": "system", "content": request.system_instructions},
                {"role": "user", "content": _user_payload_to_text(request.user_payload)},
            ],
            "temperature": self.config.temperature,
        }
        if self.config.seed is not None:
            payload["seed"] = self.config.seed
        if self.config.structured_output_mode == StructuredOutputMode.PROVIDER_JSON_OBJECT:
            payload["response_format"] = {"type": "json_object"}
        elif self.config.structured_output_mode == StructuredOutputMode.PROVIDER_JSON_SCHEMA:
            model = self._schema_registry.get(request.expected_response_schema)
            if model is not None:
                payload["response_format"] = {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "project_recovery_council_response",
                        "schema": model.model_json_schema(),
                    },
                }
        return payload

    def _parse_success(
        self,
        request: ModelRequest,
        response: HttpResponse,
        *,
        retry_count: int,
        latency_seconds: float,
        network_attempted: bool,
        requested_mode: StructuredOutputMode,
        actual_mode: StructuredOutputMode,
        retry_history: list[dict[str, Any]],
        provider_request_id: str | None,
        api_key: str,
        request_payload: dict[str, Any],
    ) -> ModelResult:
        try:
            provider_payload = json.loads(response.body)
        except json.JSONDecodeError as exc:
            return self._failure_result(
                request,
                kind=FailureKind.PARSING_ERROR,
                error_type="JSONDecodeError",
                message=f"provider response was not JSON: {exc}",
                finish_status=FinishStatus.FAILED,
                network_attempted=network_attempted,
                retry_count=retry_count,
                latency_seconds=latency_seconds,
                retry_history=retry_history,
                provider_response=response,
                provider_request_id=provider_request_id,
                secrets=[api_key],
            )

        content = _extract_message_content(provider_payload)
        if content is None:
            return self._failure_result(
                request,
                kind=FailureKind.PARSING_ERROR,
                error_type="ProviderResponseShapeError",
                message="provider response did not contain choices[0].message.content",
                finish_status=FinishStatus.FAILED,
                network_attempted=network_attempted,
                retry_count=retry_count,
                latency_seconds=latency_seconds,
                retry_history=retry_history,
                provider_response=response,
                provider_request_id=provider_request_id,
                secrets=[api_key],
            )
        raw_text = content if isinstance(content, str) else json.dumps(content, sort_keys=True)
        try:
            parsed = json.loads(raw_text) if isinstance(content, str) else content
        except json.JSONDecodeError as exc:
            return self._failure_result(
                request,
                kind=FailureKind.PARSING_ERROR,
                error_type="JSONDecodeError",
                message=f"assistant content was not valid JSON: {exc}",
                finish_status=FinishStatus.FAILED,
                network_attempted=network_attempted,
                retry_count=retry_count,
                latency_seconds=latency_seconds,
                retry_history=retry_history,
                raw_response_text=raw_text,
                provider_response=response,
                provider_request_id=provider_request_id,
                secrets=[api_key],
            )
        if not isinstance(parsed, dict):
            return self._failure_result(
                request,
                kind=FailureKind.PARSING_ERROR,
                error_type="ResponseShapeError",
                message="assistant JSON content must be an object",
                finish_status=FinishStatus.FAILED,
                network_attempted=network_attempted,
                retry_count=retry_count,
                latency_seconds=latency_seconds,
                retry_history=retry_history,
                raw_response_text=raw_text,
                provider_response=response,
                provider_request_id=provider_request_id,
                secrets=[api_key],
            )

        validation_errors: list[str] = []
        model = self._schema_registry.get(request.expected_response_schema)
        if model is not None:
            try:
                parsed = model.model_validate(parsed).model_dump(mode="json")
            except ValidationError as exc:
                validation_errors = [str(error) for error in exc.errors()]
                return ModelResult(
                    parsed_response=parsed,
                    raw_response_text=redact_value(raw_text, [api_key]),
                    model_identifier=self.config.model_identifier,
                    provider=self.provider,
                    input_token_count=_usage_value(provider_payload, "prompt_tokens"),
                    output_token_count=_usage_value(provider_payload, "completion_tokens"),
                    total_token_count=_usage_value(provider_payload, "total_tokens"),
                    latency_seconds=latency_seconds,
                    finish_status=FinishStatus.VALIDATION_ERROR,
                    retry_count=retry_count,
                    validation_errors=validation_errors,
                    provider_metadata=self._metadata(
                        network_attempted=network_attempted,
                        requested_mode=requested_mode,
                        actual_mode=actual_mode,
                        retry_history=retry_history,
                        provider_request_id=provider_request_id,
                        http_status=response.status_code,
                        provider_payload=provider_payload,
                        request_payload=request_payload,
                        secrets=[api_key],
                    ),
                    failure=ModelFailure(
                        kind=FailureKind.SCHEMA_ERROR,
                        error_type="ValidationError",
                        message="Qwen response failed expected schema validation",
                        retryable=False,
                    ),
                    simulated=False,
                )

        finish_reason = _finish_reason(provider_payload)
        return ModelResult(
            parsed_response=parsed,
            raw_response_text=redact_value(raw_text, [api_key]),
            model_identifier=self.config.model_identifier,
            provider=self.provider,
            input_token_count=_usage_value(provider_payload, "prompt_tokens"),
            output_token_count=_usage_value(provider_payload, "completion_tokens"),
            total_token_count=_usage_value(provider_payload, "total_tokens"),
            latency_seconds=latency_seconds,
            finish_status=FinishStatus.COMPLETED,
            retry_count=retry_count,
            validation_errors=[],
            provider_metadata=self._metadata(
                network_attempted=network_attempted,
                requested_mode=requested_mode,
                actual_mode=actual_mode,
                retry_history=retry_history,
                provider_request_id=provider_request_id,
                http_status=response.status_code,
                provider_payload=provider_payload,
                request_payload=request_payload,
                secrets=[api_key],
                finish_reason=finish_reason,
            ),
            simulated=False,
        )

    def _provider_failure(
        self,
        request: ModelRequest,
        response: HttpResponse,
        kind: FailureKind,
        error_type: str,
        message: str,
        retry_count: int,
        latency_seconds: float,
        network_attempted: bool,
        retry_history: list[dict[str, Any]],
        provider_request_id: str | None,
        api_key: str,
    ) -> ModelResult:
        return self._failure_result(
            request,
            kind=kind,
            error_type=error_type,
            message=message,
            finish_status=FinishStatus.FAILED,
            network_attempted=network_attempted,
            retry_count=retry_count,
            latency_seconds=latency_seconds,
            retry_history=retry_history,
            provider_response=response,
            provider_request_id=provider_request_id,
            secrets=[api_key],
        )

    def _failure_result(
        self,
        request: ModelRequest,
        *,
        kind: FailureKind,
        error_type: str,
        message: str,
        finish_status: FinishStatus,
        network_attempted: bool,
        retry_count: int,
        latency_seconds: float | None,
        retry_history: list[dict[str, Any]],
        raw_response_text: str | None = None,
        provider_response: HttpResponse | None = None,
        provider_request_id: str | None = None,
        secrets: list[str] | None = None,
    ) -> ModelResult:
        metadata: dict[str, Any] = {
            "network_attempted": network_attempted,
            "requested_structured_output_mode": self.config.structured_output_mode.value,
            "actual_structured_output_mode": self.config.structured_output_mode.value,
            "endpoint_host": self.config.endpoint_host,
            "provider_region_label": self.config.provider_region_label,
            "provider_request_id": provider_request_id,
            "retry_history": retry_history,
            "sanitized_provider_config": self.config.sanitized(),
        }
        if provider_response is not None:
            metadata["http_status"] = provider_response.status_code
            metadata["raw_provider_response"] = redact_value(provider_response.body, secrets)
            metadata["provider_headers"] = redact_value(provider_response.headers, secrets)
        return ModelResult(
            raw_response_text=redact_value(raw_response_text, secrets) if raw_response_text is not None else None,
            model_identifier=self.config.model_identifier,
            provider=self.provider,
            latency_seconds=latency_seconds,
            finish_status=finish_status,
            retry_count=retry_count,
            validation_errors=[message],
            provider_metadata=metadata,
            failure=ModelFailure(kind=kind, error_type=error_type, message=message, retryable=False),
            simulated=False,
        )

    def _metadata(
        self,
        *,
        network_attempted: bool,
        requested_mode: StructuredOutputMode,
        actual_mode: StructuredOutputMode,
        retry_history: list[dict[str, Any]],
        provider_request_id: str | None,
        http_status: int,
        provider_payload: dict[str, Any],
        request_payload: dict[str, Any],
        secrets: list[str],
        finish_reason: str | None = None,
    ) -> dict[str, Any]:
        return {
            "network_attempted": network_attempted,
            "requested_structured_output_mode": requested_mode.value,
            "actual_structured_output_mode": actual_mode.value,
            "endpoint_host": self.config.endpoint_host,
            "provider_region_label": self.config.provider_region_label,
            "provider_request_id": provider_request_id,
            "http_status": http_status,
            "finish_reason": finish_reason,
            "retry_history": retry_history,
            "sanitized_provider_config": self.config.sanitized(),
            "sanitized_request_payload": redact_value(request_payload, secrets),
            "raw_provider_response": redact_value(json.dumps(provider_payload, sort_keys=True), secrets),
        }

    def _backoff_seconds(self, attempt_zero_based: int) -> float:
        backoff = self.config.retry_backoff.initial_seconds * (
            self.config.retry_backoff.multiplier ** attempt_zero_based
        )
        return min(backoff, self.config.retry_backoff.max_seconds)


def _user_payload_to_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, indent=2, sort_keys=True, default=str)


def _extract_message_content(payload: dict[str, Any]) -> Any | None:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        return None
    first = choices[0]
    if not isinstance(first, dict):
        return None
    message = first.get("message")
    if not isinstance(message, dict):
        return None
    return message.get("content")


def _usage_value(payload: dict[str, Any], key: str) -> int | None:
    usage = payload.get("usage")
    if not isinstance(usage, dict):
        return None
    value = usage.get(key)
    return int(value) if isinstance(value, int) else None


def _finish_reason(payload: dict[str, Any]) -> str | None:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        return None
    value = choices[0].get("finish_reason")
    return str(value) if value is not None else None


def _provider_request_id(headers: dict[str, str]) -> str | None:
    for key in ("x-request-id", "x-dashscope-request-id", "request-id", "x-acs-request-id"):
        for header_key, value in headers.items():
            if header_key.lower() == key:
                return value
    return None
