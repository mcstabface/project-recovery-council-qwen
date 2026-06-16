"""Centralized redaction for provider secrets and credential-like values."""

from __future__ import annotations

from typing import Any


REDACTION_TOKEN = "[REDACTED]"

SECRET_KEY_FRAGMENTS = (
    "api_key",
    "apikey",
    "authorization",
    "access_token",
    "secret",
    "credential",
    "password",
    "bearer",
)

NON_SECRET_KEY_NAMES = {
    "api_key_env_var",
    "api_key_present",
}


def redact_text(value: str, secrets: list[str] | None = None) -> str:
    redacted = value
    for secret in secrets or []:
        if secret:
            redacted = redacted.replace(secret, REDACTION_TOKEN)
    return redacted


def redact_value(value: Any, secrets: list[str] | None = None) -> Any:
    if isinstance(value, str):
        return redact_text(value, secrets)
    if isinstance(value, dict):
        return {
            str(key): _redact_secret_field(str(key), item, secrets)
            if _looks_secret(str(key)) and _normalize_key(str(key)) not in NON_SECRET_KEY_NAMES
            else redact_value(item, secrets)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_value(item, secrets) for item in value]
    if isinstance(value, tuple):
        return [redact_value(item, secrets) for item in value]
    return value


def _looks_secret(key: str) -> bool:
    normalized = _normalize_key(key)
    return any(fragment in normalized for fragment in SECRET_KEY_FRAGMENTS)


def _normalize_key(key: str) -> str:
    return key.lower().replace("-", "_")


def _redact_secret_field(key: str, value: Any, secrets: list[str] | None) -> Any:
    if _normalize_key(key) == "authorization":
        return REDACTION_TOKEN
    if isinstance(value, str):
        return redact_text(value, secrets) if secrets else REDACTION_TOKEN
    return REDACTION_TOKEN
