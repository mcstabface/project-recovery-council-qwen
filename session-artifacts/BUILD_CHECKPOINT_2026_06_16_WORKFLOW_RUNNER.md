# Project Recovery Council Workflow Runner Checkpoint

**Date:** 2026-06-16  
**System / Subsystem:** Deterministic local workflow runner  
**Status:** Complete and tests passing  
**Scope:** End-to-end local orchestration, audit events, human gate, retry behavior, CLI, replay artifacts

---

## 1. Objective

Build a deterministic, replayable local execution engine that exercises the
modular expert architecture end to end without UiPath, LLM providers, web
frameworks, or external connectors.

---

## 2. Completed Work

- Added explicit workflow states and transition validation.
- Added deterministic audit recorder with sequence numbers, event types, and
  injectable clock behavior.
- Added rule-based Director expert selection from case facts with concise
  routing rationale.
- Added local workflow runner for validation, triage, expert execution,
  contradiction review, human decision pause/resume, recovery planning, final
  approval, completion, and artifact writing.
- Added deterministic commercial-expert first-attempt failure injection.
- Added one Director-authorized retry path with both attempts preserved.
- Added JSON serialization helpers and logical replay comparison.
- Added standard-library CLI commands for `validate`, `run`, failure-injection
  `run`, and `replay`.
- Added workflow, artifact, replay, and CLI tests.
- Updated README, architecture, case model, development plan, and ADRs.
- Produced canonical run artifacts under `session-artifacts/runs/`.

---

## 3. Verified Behavior

Full test suite:

```text
python -m pytest
```

Result:

```text
29 passed in 0.46s
```

Canonical CLI artifact runs:

```text
PYTHONPATH=src python -m project_recovery_council run
run completed: session-artifacts/runs/equipment-delay-standard

PYTHONPATH=src python -m project_recovery_council run --inject-commercial-failure
run completed: session-artifacts/runs/equipment-delay-commercial-failure

PYTHONPATH=src python -m project_recovery_council replay session-artifacts/runs/equipment-delay-standard --run-id equipment-delay-standard-replay
replay completed: session-artifacts/runs/equipment-delay-standard-replay
logically equivalent: true
```

---

## 4. Files / Areas Touched

- `src/project_recovery_council/audit.py`
- `src/project_recovery_council/director.py`
- `src/project_recovery_council/runner.py`
- `src/project_recovery_council/serialization.py`
- `src/project_recovery_council/state.py`
- `src/project_recovery_council/workflow.py`
- `src/project_recovery_council/__main__.py`
- `src/project_recovery_council/__init__.py`
- `src/project_recovery_council/contracts.py`
- `src/project_recovery_council/stubs.py`
- `tests/test_workflow_runner.py`
- `tests/test_cli.py`
- `README.md`
- `docs/ARCHITECTURE.md`
- `docs/CASE_MODEL.md`
- `docs/DEVELOPMENT_PLAN.md`
- `decisions/ADR-0002-deterministic-local-workflow-runner.md`
- `session-artifacts/runs/equipment-delay-standard/`
- `session-artifacts/runs/equipment-delay-commercial-failure/`
- `session-artifacts/runs/equipment-delay-standard-replay/`

---

## 5. Architectural Notes

- Workflow logic is in the orchestration layer, not inside expert stubs.
- Director selection is dynamic for the current case facts.
- Human confirmation pauses authorization until a `HumanDecision` is supplied.
- Replay comparison ignores timestamps and run-specific identifiers while
  comparing logical event order, findings, decisions, contradictions, and final
  recommendation content.
- Audit events remain concise operational records, not reasoning traces.

---

## 6. Known Issues

- The CLI is intentionally small and source-tree usage requires `PYTHONPATH=src`
  unless the package is installed.
- Run IDs are caller-controlled; repeated runs with the same run ID overwrite
  that run directory.
- No JSON Schema export exists yet.
- No production persistence layer exists yet.
- No real human approval integration exists yet; demo decisions are simulated.

---

## 7. Next Action

Add JSON Schema exports and a formal replay acceptance checklist for the public
contracts and run artifacts.

---

## 8. Resume Prompt

```text
Resume Project Recovery Council from session-artifacts/BUILD_CHECKPOINT_2026_06_16_WORKFLOW_RUNNER.md. Continue by adding JSON Schema exports and a replay acceptance checklist for contracts and run artifacts without adding external integrations.
```
