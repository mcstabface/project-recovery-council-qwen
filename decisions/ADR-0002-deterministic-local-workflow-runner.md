# ADR-0002: Deterministic Local Workflow Runner

**Status:** Accepted  
**Date:** 2026-06-16  
**Decision Owner:** Project Recovery Council maintainers

---

## Context

The foundation slice defined contracts, deterministic validators, expert
interfaces, stubs, and a synthetic equipment-delay case. The next required step
is to exercise that modular architecture end to end without adding UiPath, LLM
providers, web frameworks, or external connectors.

The workflow must be replayable, inspectable from artifacts, and explicit about
human gates, retries, and audit history.

---

## Decision

Add a standalone local orchestration layer with:

- explicit workflow stages and validated transitions
- deterministic audit event recording with injectable clock behavior
- rule-based Director expert selection from case facts
- specialist stub execution outside the stubs themselves
- human decision pause/resume behavior
- deterministic commercial-expert first-attempt failure injection
- one Director-authorized retry
- machine-readable run artifacts and replay comparison
- standard-library CLI commands for validate, run, failure-injection run, and
  replay

The runner remains local and provider-independent.

---

## Consequences

The repository now has a deterministic end-to-end execution path that can be
tested and replayed before production orchestration is introduced. Audit events
make expert selection, requests, failures, retries, human decisions, final
approval, and completion inspectable without application logs.

The workflow still is not a production case-management service. It is a local
execution engine and replay contract.

---

## Alternatives Considered

- Put orchestration logic inside expert stubs. Rejected because stubs should
  remain replaceable specialist implementations.
- Add UiPath Maestro orchestration now. Rejected because this run must remain
  standalone.
- Use a CLI framework dependency. Rejected because `argparse` is sufficient for
  the local commands.

---

## Invariants Touched

- Deterministic fixture replay
- Evidence-grounded expert output
- Human confirmation for unresolved contradictions
- Explicit retry and failure state
- Ordered audit history
- Integration independence

---

## Follow-up Work

- Export JSON Schemas for contracts and artifact files.
- Add a formal replay acceptance checklist.
- Add persisted case snapshots if future workflows require mutation history.

