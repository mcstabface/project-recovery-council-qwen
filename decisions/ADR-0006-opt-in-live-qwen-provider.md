# ADR-0006: Opt-In Live Qwen Provider

## Status

Accepted

## Context

The repository needs a controlled live Qwen path for smoke tests and later
competition experiments, while preserving offline installation, import,
testing, and deterministic reference behavior.

## Decision

Add `QwenModelClient` behind the existing `ModelClient` boundary. The client is
never the default. Live execution is available only through explicit commands
that require `--allow-network`, an explicit `--model`, and a configured API key
environment variable.

Use the official Alibaba Cloud Model Studio OpenAI-compatible chat endpoint as
the live HTTP interface. Do not hard-code a live model ID. Read secrets from
environment variables only. Redact API keys and authorization material from all
stored metadata and artifacts.

Structured output proceeds in this order:

1. provider JSON Schema mode when explicitly configured
2. provider JSON-object mode when explicitly configured
3. prompt-requested strict JSON with local Pydantic validation

Because provider-enforced JSON Schema support is model and endpoint dependent,
the default live mode is prompt-requested JSON plus local validation.

## Consequences

The normal test suite remains offline and credential-free. Live artifacts are
isolated under `experiment-artifacts/live/` and ignored by Git. The smoke path
can verify authentication, endpoint reachability, model availability,
structured response handling, local validation, token usage when returned,
redaction, and artifact inspection with one small request.
