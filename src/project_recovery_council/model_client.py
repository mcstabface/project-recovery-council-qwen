"""Provider-neutral structured model client contracts.

The competition adaptation keeps live providers behind this boundary. Offline
tests can exercise structured parsing and validation without credentials or
network access.
"""

from __future__ import annotations

import json
from enum import StrEnum
from time import perf_counter
from typing import Any, Protocol

from pydantic import BaseModel, Field, ValidationError

from project_recovery_council.contracts import ContractModel


class FinishStatus(StrEnum):
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CONFIGURATION_ERROR = "configuration_error"
    VALIDATION_ERROR = "validation_error"


class FailureKind(StrEnum):
    CONFIGURATION_ERROR = "configuration_error"
    PROVIDER_ERROR = "provider_error"
    TIMEOUT = "timeout"
    VALIDATION_ERROR = "validation_error"
    MISSING_FIXTURE = "missing_fixture"


class ModelClientConfigurationError(RuntimeError):
    """Raised by future live clients when provider configuration is invalid."""


class ModelFailure(ContractModel):
    """Typed failure representation for a model invocation."""

    kind: FailureKind
    error_type: str = Field(min_length=1)
    message: str = Field(min_length=1)
    retryable: bool = False


class ModelRequest(ContractModel):
    """Structured request accepted by any model provider adapter."""

    model_identifier: str = Field(min_length=1)
    system_instructions: str = Field(min_length=1)
    user_payload: Any
    expected_response_schema: str = Field(min_length=1)
    generation_parameters: dict[str, Any] = Field(default_factory=dict)
    correlation_id: str = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ModelResult(ContractModel):
    """Structured result produced by a model provider adapter."""

    parsed_response: dict[str, Any] | None = None
    raw_response_text: str | None = None
    model_identifier: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    input_token_count: int | None = Field(default=None, ge=0)
    output_token_count: int | None = Field(default=None, ge=0)
    total_token_count: int | None = Field(default=None, ge=0)
    latency_seconds: float | None = Field(default=None, ge=0.0)
    finish_status: FinishStatus
    retry_count: int = Field(default=0, ge=0)
    validation_errors: list[str] = Field(default_factory=list)
    provider_metadata: dict[str, Any] = Field(default_factory=dict)
    failure: ModelFailure | None = None
    simulated: bool = False


class ModelClient(Protocol):
    """Protocol implemented by offline, disabled, and future live clients."""

    provider: str

    def generate(self, request: ModelRequest) -> ModelResult:
        """Generate a structured result for a request."""


SchemaRegistry = dict[str, type[BaseModel]]


class OfflineModelClient:
    """Deterministic fixture-backed model client used by tests and local demos."""

    provider = "offline-fixture"

    def __init__(
        self,
        responses: dict[str, Any],
        *,
        schema_registry: SchemaRegistry | None = None,
    ) -> None:
        self._responses = dict(responses)
        self._schema_registry = schema_registry or {}

    def generate(self, request: ModelRequest) -> ModelResult:
        started = perf_counter()
        fixture_key = str(request.metadata.get("fixture_id") or request.correlation_id)
        if fixture_key not in self._responses:
            return self._failure_result(
                request,
                FailureKind.MISSING_FIXTURE,
                "MissingOfflineFixture",
                f"no offline response fixture found for {fixture_key}",
                perf_counter() - started,
            )

        fixture = self._responses[fixture_key]
        raw_text = fixture if isinstance(fixture, str) else json.dumps(fixture, sort_keys=True)
        try:
            parsed = json.loads(raw_text)
        except json.JSONDecodeError as exc:
            return self._failure_result(
                request,
                FailureKind.VALIDATION_ERROR,
                "JSONDecodeError",
                f"offline response is not valid JSON: {exc}",
                perf_counter() - started,
                raw_response_text=raw_text,
            )
        if not isinstance(parsed, dict):
            return self._failure_result(
                request,
                FailureKind.VALIDATION_ERROR,
                "ResponseShapeError",
                "offline response must be a JSON object",
                perf_counter() - started,
                raw_response_text=raw_text,
            )

        validation_errors: list[str] = []
        model = self._schema_registry.get(request.expected_response_schema)
        if model is not None:
            try:
                validated = model.model_validate(parsed)
                parsed = validated.model_dump(mode="json")
            except ValidationError as exc:
                validation_errors = [str(error) for error in exc.errors()]
                return ModelResult(
                    parsed_response=parsed,
                    raw_response_text=raw_text,
                    model_identifier=request.model_identifier,
                    provider=self.provider,
                    latency_seconds=None,
                    finish_status=FinishStatus.VALIDATION_ERROR,
                    retry_count=0,
                    validation_errors=validation_errors,
                    provider_metadata={"fixture_key": fixture_key},
                    failure=ModelFailure(
                        kind=FailureKind.VALIDATION_ERROR,
                        error_type="ValidationError",
                        message="offline response failed expected schema validation",
                        retryable=False,
                    ),
                    simulated=True,
                )

        return ModelResult(
            parsed_response=parsed,
            raw_response_text=raw_text,
            model_identifier=request.model_identifier,
            provider=self.provider,
            latency_seconds=None,
            finish_status=FinishStatus.COMPLETED,
            retry_count=0,
            validation_errors=validation_errors,
            provider_metadata={"fixture_key": fixture_key},
            simulated=True,
        )

    def _failure_result(
        self,
        request: ModelRequest,
        kind: FailureKind,
        error_type: str,
        message: str,
        latency_seconds: float,
        *,
        raw_response_text: str | None = None,
    ) -> ModelResult:
        return ModelResult(
            raw_response_text=raw_response_text,
            model_identifier=request.model_identifier,
            provider=self.provider,
            latency_seconds=None,
            finish_status=FinishStatus.VALIDATION_ERROR
            if kind == FailureKind.VALIDATION_ERROR
            else FinishStatus.FAILED,
            retry_count=0,
            validation_errors=[message],
            provider_metadata={"measured_parse_latency_seconds": latency_seconds},
            failure=ModelFailure(
                kind=kind,
                error_type=error_type,
                message=message,
                retryable=False,
            ),
            simulated=True,
        )


class DisabledQwenModelClient:
    """Non-networking placeholder for future live Qwen integration."""

    provider = "qwen"

    def generate(self, request: ModelRequest) -> ModelResult:
        message = (
            "Live Qwen execution is disabled in this repository state. "
            "Use OfflineModelClient fixtures until provider credentials and "
            "network policy are explicitly configured."
        )
        return ModelResult(
            model_identifier=request.model_identifier,
            provider=self.provider,
            finish_status=FinishStatus.CONFIGURATION_ERROR,
            retry_count=0,
            validation_errors=[message],
            provider_metadata={
                "live_provider_enabled": False,
                "network_attempted": False,
                "correlation_id": request.correlation_id,
            },
            failure=ModelFailure(
                kind=FailureKind.CONFIGURATION_ERROR,
                error_type=ModelClientConfigurationError.__name__,
                message=message,
                retryable=False,
            ),
            simulated=False,
        )
