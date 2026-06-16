# ADR-0005: Qwen Agent Society Experiment Architecture

## Status

Accepted

## Context

The inherited Project Recovery Council implementation is deterministic and
serves as the regression baseline for the synthetic equipment-delay case. The
competition adaptation needs to compare agent architectures without requiring
live credentials or network calls in the current run.

## Decision

Add a competition layer around the deterministic implementation:

- keep the Python import package as `project_recovery_council`
- change the distribution name to `project-recovery-council-qwen`
- add `prc-qwen` while retaining the inherited console command
- define provider-neutral `ModelClient` contracts
- implement `OfflineModelClient` and `DisabledQwenModelClient`
- store inspectable versioned prompts under `prompts/v1/`
- define typed experiment variants and evaluation models outside frozen v1
  schemas
- evaluate structured claims and source record IDs, not prose wording
- write experiment artifacts with SHA-256 manifests

## Consequences

The deterministic implementation remains stable and usable as the oracle. The
competition layer can evolve without breaking frozen v1 workflow schemas.
Offline fixtures provide repeatable tests but cannot be used as empirical Qwen
performance evidence. Live Qwen integration is deferred until credential,
structured-output, token accounting, retry, rate-limit, secret-handling, and
deployment requirements are designed.
