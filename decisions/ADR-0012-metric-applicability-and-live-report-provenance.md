# ADR-0012: Metric Applicability and Live Report Provenance

## Status

Accepted

## Context

A real live `single_generalist` run completed successfully, but two reporting
issues appeared:

- the live evaluation report reused offline-fixture limitation text
- the full-scope GeneralistAgent result reported role-scope and specialized
  semantic validation as 1.0, even though those specialist validation layers did
  not apply

The deterministic evaluation scores were correct and must not be changed.

## Decision

Evaluation reports now carry provenance-specific limitation text. Offline
fixtures retain the simulated-output limitation. Live provider evaluations use
only live-accurate limitations:

- one run per variant is not statistically significant
- hosted-model outputs may vary
- provider cost is unavailable unless explicit pricing is supplied

Live variant summaries and comparison rows now use a typed metric applicability
representation for role-scope and specialized semantic validation:

- `applicable`
- `status`: `passed`, `failed`, `not_applicable`, or `unavailable`
- optional `score`
- optional `reason`

For `single_generalist`, role-scope and specialized semantic validation are
reported as `not_applicable` with `score: null`. Specialist variants preserve
their actual validation scores.

## Consequences

Live Generalist reporting no longer overstates specialist governance checks as
passes. Comparison reports can distinguish passed, failed, not applicable, and
unavailable states without converting N/A to 0.0 or 1.0.

Prior live artifacts are not modified or retroactively corrected.

## Non-Goals

- No deterministic expected-result changes.
- No frozen v1 schema changes.
- No live network calls.
- No provider cost estimation without explicit pricing.
