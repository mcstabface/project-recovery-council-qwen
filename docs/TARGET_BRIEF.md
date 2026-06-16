# Project Recovery Council Target Brief

## Status

Active foundation brief.

## Objective

Create a standalone deterministic foundation for a modular expert system that
can investigate project-delivery exceptions without relying on UiPath, an LLM
provider, or external project systems.

## Scope

This slice creates architecture, contracts, fixtures, validators, tests, and
process artifacts for a single synthetic equipment-delay case.

## Non-Goals

- Do not connect to project systems, communication tools, document stores, or
  orchestration platforms.
- Do not add LLM SDKs.
- Do not add a web framework.
- Do not implement production UiPath Maestro behavior.
- Do not include real customer, vendor, employee, or proprietary project data.

## Expected Outputs

- Python package under `src/project_recovery_council/`
- typed public contracts
- deterministic validation functions
- narrow expert interfaces
- synthetic evidence pack under `sample-data/equipment-delay-case/`
- machine-readable expected results
- automated tests
- build checkpoint and run manifest

## Verification

Run:

```bash
python -m pytest
```

Review fixture consistency, expected results, and process artifacts before
declaring the build ready.

