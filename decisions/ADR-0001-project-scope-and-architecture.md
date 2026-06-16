# ADR-0001: Project Scope and Architecture

**Status:** Accepted  
**Date:** 2026-06-16  
**Decision Owner:** Project Recovery Council maintainers

---

## Context

Project Recovery Council needs a competition-quality foundation for governed
project exception investigations. The first case concerns a synthetic major
equipment delivery delay. The future system may use LLM-backed experts and
UiPath Maestro orchestration, but the initial implementation must be standalone,
deterministic, and free of external integrations.

---

## Decision

Create a local Python 3.12+ package with:

- Pydantic public contracts
- source-cited synthetic fixtures
- deterministic validation functions
- abstract expert interfaces
- deterministic stubs for contract tests
- process artifacts documenting build state and limitations

No LLM SDK, web framework, UiPath-specific runtime, or external connector will
be added in this slice.

---

## Consequences

This makes contract behavior testable before orchestration or AI behavior is
introduced. Future integrations must adapt to these contracts instead of
changing case semantics ad hoc.

The tradeoff is that the current repository is not yet a complete case
application. It is a governed foundation and replayable demonstration fixture.

---

## Alternatives Considered

- Build a full application immediately. Rejected because the core contracts and
  governance gates need to stabilize first.
- Add an LLM-backed Director now. Rejected because provider independence is a
  stated requirement for this run.
- Model only documents and expected outputs. Rejected because specialist failure,
  retry, confidence, and human-gate behavior must be explicit contracts.

---

## Invariants Touched

- Evidence-grounded findings
- Human confirmation for unresolved contradictions
- Preserved audit history
- Deterministic fixture replay
- Integration independence

---

## Follow-up Work

- Add a deterministic workflow runner.
- Add schema export for integration review.
- Add richer audit event persistence once workflow execution exists.

