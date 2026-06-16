# Build Checkpoint: Opt-In Live Qwen Provider

**Date:** 2026-06-16  
**Repository:** `project-recovery-council-qwen`  
**Status:** Complete for opt-in live provider integration pass

## Created Or Updated

- Added typed `QwenProviderConfig` with API-key environment variable name,
  base URL, explicit model identifier, timeout, retry/backoff, temperature,
  optional seed, structured-output mode, region label, and metadata tags.
- Added centralized redaction for API keys, authorization headers, credential
  fields, and known secret values.
- Added deterministic live prompt rendering and prompt/schema hashing.
- Added `QwenModelClient` behind the `ModelClient` boundary with injectable
  HTTP transport, timeout handling, retries, rate-limit handling, local schema
  validation, token accounting, provider request ID capture, redacted raw
  response metadata, and structured-output mode recording.
- Added opt-in live execution helpers for one smoke request, one named agent,
  and the `single_generalist` live variant.
- Added live artifact writing under `experiment-artifacts/live/<experiment-id>/`
  with sanitized provider configuration, invocation records, prompt hashes,
  redacted raw responses, parsed responses, validation results, usage, retry
  history, reproducibility metadata, and manifest checksums.
- Added `.gitignore` rule for `experiment-artifacts/live/`.
- Added live CLI commands: `live-smoke`, `live-agent`, and `live-variant`.
- Added mocked unit tests and an opt-in skipped live-integration marker.
- Updated README, live provider docs, experiment design docs, artifact
  redaction docs, and ADR-0006.

## Verification Commands

```bash
python -m pytest tests/test_qwen_live_client.py tests/test_qwen_live_cli.py tests/test_qwen_live_integration.py
```

Result: `13 passed, 1 skipped in 0.81s`

```bash
python -m pytest
```

First full-suite result: `71 passed, 1 skipped in 7.70s`

```bash
PYTHONPATH=src python -m project_recovery_council live-smoke --model explicit-test-model
```

Result: exit code `1`; failed before network with
`live execution requires --allow-network`.

```bash
env -u DASHSCOPE_API_KEY PYTHONPATH=src python -m project_recovery_council live-smoke --model explicit-test-model --allow-network
```

Result: exit code `1`; failed before network with
`missing required credential environment variable: DASHSCOPE_API_KEY`.

```bash
PYTHONPATH=src python -m project_recovery_council check-schema-drift
```

Result: `schema drift check passed`

```bash
PYTHONPATH=src python -m project_recovery_council validate-prompts
```

Result: `prompt validation passed`

```bash
PYTHONPATH=src python -m project_recovery_council compare-offline
```

Result:

```text
offline comparison: offline-comparison-v1
dynamic_expert_council:strong_modular_council required_fact_accuracy=1.0 schema=valid unsupported_claims=0
single_generalist:generalist_missed_onsite_contradiction required_fact_accuracy=0.2 schema=valid unsupported_claims=1
fixed_expert_chain:fixed_chain_result required_fact_accuracy=1.0 schema=valid unsupported_claims=0
```

```bash
python -m pytest
```

Final current-state result: `71 passed, 1 skipped in 7.95s`

## Network Status

No real network request was made during this pass. The live client tests used a
mock transport, and CLI live checks stopped before request execution.

## Remaining Limitations

- No real Qwen smoke test was executed.
- `live-variant` currently supports only `single_generalist`.
- Provider-enforced JSON Schema support is configurable but not claimed as the
  default; the default live mode is prompt-requested JSON plus local Pydantic
  validation.
- No provider pricing is encoded or estimated without explicit pricing input.
- No Alibaba Cloud deployment proof is included.

## Manual Smoke Command

```bash
export DASHSCOPE_API_KEY="<your-api-key>"
PYTHONPATH=src python -m project_recovery_council live-smoke \
  --model <model-id> \
  --allow-network
```
