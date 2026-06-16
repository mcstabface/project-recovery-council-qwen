# ADR-0011: Controlled Live Variant Comparison

## Status

Accepted

## Context

The Qwen Agent Society adaptation needs live execution paths for three AI
competition variants:

- `single_generalist`
- `fixed_expert_chain`
- `dynamic_expert_council`

The deterministic oracle remains the expected-result source and regression
baseline, not an AI competitor. Live execution must be explicit because provider
requests may incur cost, hosted model behavior is not perfectly reproducible,
and normal tests must never require credentials or network access.

The prior live path covered smoke tests and standalone specialist invocations.
The next step is one controlled live variant runner and an offline comparison
command that consumes completed live artifacts.

## Decision

Implement `live-variant` as an opt-in, one-variant-at-a-time command. It
requires `--allow-network`, explicit `--model`, credentials, and no-overwrite
artifact behavior. It supports:

- one GeneralistAgent invocation for `single_generalist`
- fixed ScheduleExpert, CommercialExpert, EvidenceAuditor, RiskExpert, and
  RecoveryPlanner execution for `fixed_expert_chain`
- Director routing, selected specialist execution, EvidenceAuditor checking,
  Arbiter reconciliation, and RecoveryPlanner recommendation for
  `dynamic_expert_council`

All variants share the same case, provider configuration, model identifier,
temperature, seed when supplied, expected-result oracle, and deterministic
evaluation rules. Specialist evidence remains role-filtered by policy code.

Each specialist invocation runs schema validation, deterministic claim-key
normalization, role-scope validation, and domain semantic validation where
implemented. ScheduleExpert currently has the specialized semantic validator;
other specialist roles record that no specialized semantic validator exists.

Add conservative run controls:

- maximum invocation count
- maximum total input and output tokens when provider usage is available
- maximum elapsed seconds
- maximum retries per invocation
- optional stop-after-invocation

When a limit is exceeded, stop future invocations, preserve completed
artifacts, mark the run incomplete, record the stopping limit, and return a
nonzero CLI exit code.

Add `compare-live` as a no-network command that reads completed live run
directories for all three AI variants and writes machine-readable JSON plus
concise Markdown. It refuses incomplete or artifact-invalid runs unless a
diagnostic override is supplied.

## Consequences

The repository can now produce comparable live artifacts for all three AI
variants without making live execution the default and without running the
whole matrix automatically. The comparison remains descriptive and must not be
used to claim statistical significance from one run per variant.

The implementation preserves raw provider responses separately from normalized
responses and validation results. Prior live artifacts are not modified or
retroactively certified.

## Non-Goals

- No automatic live experiment matrix execution.
- No provider pricing assumptions.
- No Alibaba Cloud deployment proof.
- No frozen v1 schema changes.
- No live network calls during unit tests.
