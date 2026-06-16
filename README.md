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
tests/                        Deterministic test suite
session-artifacts/            Build checkpoint and run manifest
```

## Local Workflow CLI

From an installed environment:

```bash
python -m project_recovery_council validate
python -m project_recovery_council run
python -m project_recovery_council run --inject-commercial-failure
python -m project_recovery_council replay session-artifacts/runs/equipment-delay-standard
```

From this source tree without installing first:

```bash
PYTHONPATH=src python -m project_recovery_council validate
PYTHONPATH=src python -m project_recovery_council run
PYTHONPATH=src python -m project_recovery_council run --inject-commercial-failure
PYTHONPATH=src python -m project_recovery_council replay session-artifacts/runs/equipment-delay-standard
```

Workflow runs write inspectable artifacts under:

```text
session-artifacts/runs/<run-id>/
```

Each completed run includes `run-summary.json`, `audit-events.json`,
`expert-findings.json`, `contradictions.json`, `human-decisions.json`,
`final-recommendation.json`, and `replay-input.json`.

## Local Execution Flow

The local runner loads the synthetic case bundle, validates deterministic source
facts, lets the Director select required experts from case facts, executes
specialist stubs, pauses for human confirmation when contradictory onsite-status
evidence is found, resumes with a deterministic simulated human decision, records
final approval, and writes replayable artifacts.

The default Director selects `ScheduleExpert`, `CommercialExpert`,
`EvidenceAuditor`, `RiskExpert`, and `RecoveryPlanner` for the equipment-delay
case. With `--inject-commercial-failure`, the commercial expert fails on the
first attempt, the Director authorizes one retry, and both attempts are preserved
in the audit trail.

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
