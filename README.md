# Project Recovery Council

Project Recovery Council is a governed case-management foundation for
investigating project-delivery exceptions. This repository currently contains a
deterministic, provider-independent architecture slice for a synthetic major
equipment delay case.

This run does not build the full application. It establishes:

- strict case and expert contracts
- source-cited synthetic evidence fixtures
- deterministic validation utilities
- narrow expert interfaces and deterministic stubs
- deterministic local workflow runner and CLI
- persistent pause/resume artifacts
- versioned JSON Schemas under `schemas/v1/`
- expected results for the demonstration case
- tests and process artifacts

## Boundaries

- Synthetic data only.
- No external system connections.
- No UiPath runtime implementation.
- No LLM provider SDK.
- No web framework.
- Python 3.12 or later.
- MIT licensed.

## Demonstration Case

The synthetic case is in `sample-data/equipment-delay-case/`.

Core facts:

- equipment delivery moved 21 calendar days later than baseline
- installation had 8 days total float
- milestone slip without intervention is 13 days
- contractual exposure is 15000 USD per calendar day
- unmitigated exposure is 195000 USD
- accelerated logistics costs 48000 USD
- gross avoided exposure before secondary effects is 147000 USD
- progress reporting says the equipment is onsite
- supplier and logistics records say it has not arrived
- human confirmation is required before final recovery authorization

## Repository Layout

```text
docs/                         Architecture and case documentation
decisions/                    Architecture decision records
sample-data/equipment-delay-case/
                               Synthetic evidence pack and expected results
src/project_recovery_council/ Contracts, interfaces, stubs, workflow, validators
schemas/v1/                   Versioned JSON Schemas and schema catalog
tests/                        Deterministic test suite
session-artifacts/            Build checkpoint and run manifest
```

## Local Workflow CLI

From an installed environment:

```bash
python -m project_recovery_council validate
python -m project_recovery_council start
python -m project_recovery_council status session-artifacts/runs/equipment-delay-paused
python -m project_recovery_council decide session-artifacts/runs/equipment-delay-paused --request-id HDR-ONSITE-001 --decision equipment_not_onsite --actor demo-reviewer
python -m project_recovery_council resume session-artifacts/runs/equipment-delay-paused
python -m project_recovery_council approve session-artifacts/runs/equipment-delay-paused --actor demo-approver
python -m project_recovery_council inspect session-artifacts/runs/equipment-delay-paused
python -m project_recovery_council run
python -m project_recovery_council run --inject-commercial-failure
python -m project_recovery_council replay session-artifacts/runs/equipment-delay-standard
python -m project_recovery_council export-schemas
```

From this source tree without installing first:

```bash
PYTHONPATH=src python -m project_recovery_council validate
PYTHONPATH=src python -m project_recovery_council start
PYTHONPATH=src python -m project_recovery_council status session-artifacts/runs/equipment-delay-paused
PYTHONPATH=src python -m project_recovery_council decide session-artifacts/runs/equipment-delay-paused --request-id HDR-ONSITE-001 --decision equipment_not_onsite --actor demo-reviewer
PYTHONPATH=src python -m project_recovery_council resume session-artifacts/runs/equipment-delay-paused
PYTHONPATH=src python -m project_recovery_council approve session-artifacts/runs/equipment-delay-paused --actor demo-approver
PYTHONPATH=src python -m project_recovery_council inspect session-artifacts/runs/equipment-delay-paused
PYTHONPATH=src python -m project_recovery_council run
PYTHONPATH=src python -m project_recovery_council run --inject-commercial-failure
PYTHONPATH=src python -m project_recovery_council replay session-artifacts/runs/equipment-delay-standard
PYTHONPATH=src python -m project_recovery_council export-schemas
```

Workflow runs write inspectable artifacts under:

```text
session-artifacts/runs/<run-id>/
```

Each run includes `workflow-state.json`, `artifact-manifest.json`,
`run-summary.json`, `audit-events.json`, `expert-findings.json`,
`contradictions.json`, `human-decisions.json`, `human-decision-requests.json`,
`draft-recommendation.json`, `final-recommendation.json`, and
`replay-input.json`.

## Local Execution Flow

The local runner loads the synthetic case bundle, validates deterministic source
facts, lets the Director select required experts from case facts, executes
specialists through the expert adapter boundary, and pauses for human
confirmation when contradictory onsite-status evidence is found. A separate
process can record the decision, resume execution to the final approval gate,
record final approval, and complete the case.

`run` remains a convenience demo command that explicitly simulates both human
actions and completes the case in one invocation. `start`, `decide`, `resume`,
and `approve` are the persistent pause/resume lifecycle commands.

The default Director selects `ScheduleExpert`, `CommercialExpert`,
`EvidenceAuditor`, `RiskExpert`, and `RecoveryPlanner` for the equipment-delay
case. With `--inject-commercial-failure`, the commercial expert fails on the
first attempt, the Director authorizes one retry, and both attempts are preserved
in the audit trail.

## Contract Schemas And Artifact Inspection

Public JSON Schemas are exported in `schemas/v1/`. The schema catalog is
`schemas/v1/schema-catalog.json`.

Run artifact directories can be inspected with:

```bash
PYTHONPATH=src python -m project_recovery_council inspect session-artifacts/runs/<run-id>
```

Inspection checks required files, JSON parsing, Pydantic contract validation,
SHA-256 checksums, ordered audit sequences, evidence references, pending gates,
and completion claims.

## Run Tests

```bash
python -m pytest
```

The test configuration adds `src/` to the Python path.

## Integration Direction

Future work can attach LLM-backed experts or UiPath Maestro orchestration behind
the existing interfaces. Those integrations must preserve the local contracts,
source-level evidence citations, audit history, human gates, and deterministic
expected-result fixtures.
