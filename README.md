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
src/project_recovery_council/ Contracts, interfaces, stubs, validators
tests/                        Deterministic test suite
session-artifacts/            Build checkpoint and run manifest
```

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

