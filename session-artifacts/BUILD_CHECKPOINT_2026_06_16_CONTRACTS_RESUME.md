# Project Recovery Council Contract Hardening And Resume Checkpoint

**Date:** 2026-06-16  
**System / Subsystem:** Public contracts, persistent workflow resume, artifact validation  
**Status:** Complete and tests passing  
**Scope:** JSON Schemas, adapter boundary, resumable human gates, run artifact contract, replay acceptance, UiPath mapping

---

## 1. Objective

Harden Project Recovery Council for platform-neutral integration by exporting
versioned schemas, introducing a neutral expert adapter, making human-gated
workflow execution resumable across process invocations, and validating run
artifacts with a formal contract.

---

## 2. Completed Work

- Exported v1 JSON Schemas under `schemas/v1/`.
- Added `schema-catalog.json` with schema IDs, titles, versions, paths,
  producers, consumers, and compatibility notes.
- Added `ExpertAdapter`, `DeterministicExpertAdapter`, and disabled
  `ExternalExpertAdapter`.
- Added persisted `workflow-state.json` with version, stage, selections,
  requests, attempts, findings, contradictions, decisions, recommendations,
  approval state, audit position, and failure information.
- Refactored workflow so core execution pauses at human decision and final
  approval gates.
- Added CLI lifecycle commands: `start`, `status`, `decide`, `resume`,
  `approve`, `inspect`, and `export-schemas`.
- Added `artifact-manifest.json` and deterministic inspection rules.
- Added replay acceptance profile.
- Added UiPath Maestro mapping document with explicit unverified assumptions.
- Added tests for schemas, adapters, persistent resume, CLI lifecycle,
  artifact validation, tamper detection, and replay profile.

---

## 3. Verified Behavior

Full test suite:

```text
python -m pytest
```

Result:

```text
37 passed in 1.03s
```

Schema export:

```text
PYTHONPATH=src python -m project_recovery_council export-schemas
schemas exported: schemas/v1
schema count: 15
```

Persistent lifecycle:

```text
PYTHONPATH=src python -m project_recovery_council start --run-id paused-contract-demo
run started: session-artifacts/runs/paused-contract-demo
stage: awaiting_human_decision

PYTHONPATH=src python -m project_recovery_council decide session-artifacts/runs/paused-contract-demo --request-id HDR-ONSITE-001 --decision equipment_not_onsite --actor demo-reviewer
decision recorded: HDR-ONSITE-001
stage: awaiting_human_decision

PYTHONPATH=src python -m project_recovery_council resume session-artifacts/runs/paused-contract-demo
run resumed: session-artifacts/runs/paused-contract-demo
stage: awaiting_final_approval

PYTHONPATH=src python -m project_recovery_council approve session-artifacts/runs/paused-contract-demo --actor demo-approver
approval recorded: demo-approver
stage: completed
```

Inspection and replay:

```text
PYTHONPATH=src python -m project_recovery_council inspect session-artifacts/runs/paused-contract-demo
artifact inspection passed

PYTHONPATH=src python -m project_recovery_council replay session-artifacts/runs/complete-contract-demo --run-id complete-contract-demo-replay
replay completed: session-artifacts/runs/complete-contract-demo-replay
logically equivalent: true
```

---

## 4. Files / Areas Touched

- `schemas/v1/`
- `src/project_recovery_council/adapters.py`
- `src/project_recovery_council/artifacts.py`
- `src/project_recovery_council/persistence.py`
- `src/project_recovery_council/schemas.py`
- `src/project_recovery_council/workflow.py`
- `src/project_recovery_council/runner.py`
- `src/project_recovery_council/__main__.py`
- `src/project_recovery_council/state.py`
- `src/project_recovery_council/serialization.py`
- `src/project_recovery_council/audit.py`
- `tests/test_contract_hardening.py`
- `docs/RUN_ARTIFACT_CONTRACT.md`
- `docs/UIPATH_MAESTRO_MAPPING.md`
- `docs/REPLAY_ACCEPTANCE_PROFILE.json`
- `decisions/ADR-0003-versioned-contracts-and-resumable-workflows.md`
- `session-artifacts/runs/awaiting-human-contract-demo/`
- `session-artifacts/runs/awaiting-approval-contract-demo/`
- `session-artifacts/runs/paused-contract-demo/`
- `session-artifacts/runs/complete-contract-demo/`
- `session-artifacts/runs/complete-contract-demo-replay/`

---

## 5. Architectural Notes

- The core workflow no longer auto-supplies human decisions.
- The `run` command remains a complete demo path that explicitly simulates both
  human actions.
- Persisted state is the resume boundary; old artifacts are not migrated.
- Artifact inspection validates operational claims independently of logs.
- The UiPath document is a mapping and assumptions list, not an implementation.

---

## 6. Known Issues

- No schema drift test compares regenerated schemas byte-for-byte to checked-in
  schemas.
- No migration policy exists for future v2 schemas.
- Run IDs remain caller-controlled and repeated use overwrites the same run
  directory.
- Artifact inspection uses Pydantic validation rather than an independent JSON
  Schema validation library.
- External adapter remains intentionally disabled.

---

## 7. Next Action

Add schema drift tests and a contract migration policy before any integration or
v2 schema work.

---

## 8. Resume Prompt

```text
Resume Project Recovery Council from session-artifacts/BUILD_CHECKPOINT_2026_06_16_CONTRACTS_RESUME.md. Continue by adding schema drift tests and a contract migration policy, keeping the project standalone.
```

