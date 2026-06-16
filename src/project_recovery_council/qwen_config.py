"""Typed live Qwen provider configuration."""

from __future__ import annotations

import os
from enum import StrEnum
from typing import Any
from urllib.parse import urlparse

from pydantic import Field, model_validator

from project_recovery_council.contracts import ContractModel


DEFAULT_QWEN_API_KEY_ENV = "DASHSCOPE_API_KEY"
DEFAULT_QWEN_BASE_URL = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"


class StructuredOutputMode(StrEnum):
    PROVIDER_JSON_SCHEMA = "provider_json_schema"
    PROVIDER_JSON_OBJECT = "provider_json_object"
    PROMPTED_JSON = "prompted_json"


class RetryBackoffConfig(ContractModel):
    initial_seconds: float = Field(default=0.5, ge=0.0)
    multiplier: float = Field(default=2.0, ge=1.0)
    max_seconds: float = Field(default=8.0, ge=0.0)


class QwenProviderConfig(ContractModel):
    api_key_env_var: str = Field(default=DEFAULT_QWEN_API_KEY_ENV, min_length=1)
    base_url: str = Field(default=DEFAULT_QWEN_BASE_URL, min_length=1)
    model_identifier: str = Field(min_length=1)
    request_timeout_seconds: float = Field(default=30.0, gt=0.0)
    maximum_retries: int = Field(default=2, ge=0)
    retry_backoff: RetryBackoffConfig = Field(default_factory=RetryBackoffConfig)
    temperature: float = Field(default=0.0, ge=0.0)
    seed: int | None = None
    structured_output_mode: StructuredOutputMode = StructuredOutputMode.PROMPTED_JSON
    provider_region_label: str = Field(default="intl-compatible", min_length=1)
    experiment_metadata_tags: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def normalize_base_url(self) -> "QwenProviderConfig":
        parsed = urlparse(self.base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("base_url must be an absolute HTTP(S) URL")
        return self

    @property
    def endpoint_host(self) -> str:
        return urlparse(self.base_url).netloc

    @property
    def chat_completions_url(self) -> str:
        return f"{self.base_url.rstrip('/')}/chat/completions"

    def read_api_key(self) -> str | None:
        value = os.environ.get(self.api_key_env_var)
        return value if value else None

    def sanitized(self) -> dict[str, Any]:
        return {
            "api_key_env_var": self.api_key_env_var,
            "api_key_present": self.read_api_key() is not None,
            "base_url": self.base_url,
            "endpoint_host": self.endpoint_host,
            "model_identifier": self.model_identifier,
            "request_timeout_seconds": self.request_timeout_seconds,
            "maximum_retries": self.maximum_retries,
            "retry_backoff": self.retry_backoff.model_dump(mode="json"),
            "temperature": self.temperature,
            "seed": self.seed,
            "structured_output_mode": self.structured_output_mode.value,
            "provider_region_label": self.provider_region_label,
            "experiment_metadata_tags": dict(self.experiment_metadata_tags),
        }


def qwen_config_from_env(
    *,
    model_identifier: str,
    api_key_env_var: str | None = None,
    base_url: str | None = None,
    request_timeout_seconds: float | None = None,
    maximum_retries: int | None = None,
    retry_initial_seconds: float | None = None,
    retry_multiplier: float | None = None,
    retry_max_seconds: float | None = None,
    temperature: float | None = None,
    seed: int | None = None,
    structured_output_mode: StructuredOutputMode | str | None = None,
    provider_region_label: str | None = None,
    experiment_metadata_tags: dict[str, str] | None = None,
) -> QwenProviderConfig:
    retry_backoff = RetryBackoffConfig(
        initial_seconds=_float_env("QWEN_RETRY_INITIAL_SECONDS", retry_initial_seconds, 0.5),
        multiplier=_float_env("QWEN_RETRY_MULTIPLIER", retry_multiplier, 2.0),
        max_seconds=_float_env("QWEN_RETRY_MAX_SECONDS", retry_max_seconds, 8.0),
    )
    return QwenProviderConfig(
        api_key_env_var=api_key_env_var or os.environ.get("QWEN_API_KEY_ENV_VAR", DEFAULT_QWEN_API_KEY_ENV),
        base_url=base_url or os.environ.get("QWEN_BASE_URL", DEFAULT_QWEN_BASE_URL),
        model_identifier=model_identifier,
        request_timeout_seconds=_float_env("QWEN_REQUEST_TIMEOUT_SECONDS", request_timeout_seconds, 30.0),
        maximum_retries=_int_env("QWEN_MAXIMUM_RETRIES", maximum_retries, 2),
        retry_backoff=retry_backoff,
        temperature=_float_env("QWEN_TEMPERATURE", temperature, 0.0),
        seed=seed if seed is not None else _optional_int_env("QWEN_SEED"),
        structured_output_mode=StructuredOutputMode(
            structured_output_mode or os.environ.get("QWEN_STRUCTURED_OUTPUT_MODE", StructuredOutputMode.PROMPTED_JSON)
        ),
        provider_region_label=provider_region_label or os.environ.get("QWEN_PROVIDER_REGION_LABEL", "intl-compatible"),
        experiment_metadata_tags=experiment_metadata_tags or {},
    )


def _float_env(name: str, explicit: float | None, default: float) -> float:
    if explicit is not None:
        return explicit
    value = os.environ.get(name)
    return float(value) if value else default


def _int_env(name: str, explicit: int | None, default: int) -> int:
    if explicit is not None:
        return explicit
    value = os.environ.get(name)
    return int(value) if value else default


def _optional_int_env(name: str) -> int | None:
    value = os.environ.get(name)
    return int(value) if value else None
