# ADR-0003: Versioned Contracts and Resumable Workflows

**Status:** Accepted  
**Date:** 2026-06-16  
**Decision Owner:** Project Recovery Council maintainers

---

## Context

The local workflow runner can execute the synthetic equipment-delay case end to
end, but integration hardening requires stable public schemas, durable pause and
resume behavior, and inspectable run artifacts. The system must remain
standalone and must not add UiPath SDK code, LLM providers, web frameworks,
databases, or external connectors.

---

## Decision

Introduce v1 public JSON Schemas, a persisted workflow state artifact, a run
artifact manifest, a platform-neutral expert adapter boundary, and lifecycle CLI
commands for `start`, `status`, `decide`, `resume`, `approve`, and `inspect`.

The core workflow now pauses at human gates and final approval gates. Simulated
human decisions are retained only through explicit demo/test paths.

---

## Consequences

Workflow runs can now stop and resume across separate Python processes using
only JSON artifacts. Run artifact inspection can validate checksums, required
files, JSON parsing, Pydantic contracts, evidence references, audit ordering,
pending gates, and completion claims.

The tradeoff is that v1 schema compatibility is exact only. Incompatible schema
versions fail clearly and are not silently migrated.

---

## Alternatives Considered

- Add a database for persisted state. Rejected because the local reference must
  remain standalone.
- Add UiPath Maestro implementation now. Rejected because platform behavior has
  not yet been validated.
- Keep automatic human simulation as core behavior. Rejected because persistent
  human gates must be explicit and resumable.
- Use vendor-specific expert adapter fields. Rejected because the boundary must
  remain platform-neutral.

---

## Invariants Touched

- Versioned public contracts
- Deterministic fixture replay
- Human confirmation for unresolved contradictions
- Ordered audit history
- Explicit retry and failure state
- Integration independence

---

## Follow-up Work

- Add schema drift tests comparing generated schemas to checked-in schemas.
- Define migration policy before any v2 contracts.
- Build a human-readable artifact index for reviewer ergonomics.

