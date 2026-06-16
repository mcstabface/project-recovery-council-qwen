# Build Checkpoint: Schedule Status and Remaining Float Alias

**Date:** 2026-06-16  
**Repository:** `project-recovery-council-qwen`  
**Status:** Complete for ScheduleExpert remaining-float alias and qualitative float status validation

## Context

A live scoped `ScheduleExpert` invocation passed evidence scoping and schedule
semantic validation, but role validation failed because two legitimate schedule
claim keys were not recognized:

- `remaining_total_float_days`
- `float_consumption_status`

This checkpoint makes the smallest policy and validation correction without
running live network calls, changing frozen schemas, modifying prior live
artifacts, or mutating raw provider output.

## Created Or Updated

- Added the explicit alias `remaining_total_float_days` to
  `installation_total_float_remaining_days`.
- Added `float_consumption_status` as a canonical ScheduleExpert claim key.
- Added deterministic semantic validation for `float_consumption_status`.
- Preserved raw parsed provider output behavior; normalization still writes a
  separate normalized payload.
- Updated tests for alias normalization, allowed qualitative status, correct
  `fully_consumed` status, inconsistent status detection, invalid status
  detection, and latest live-response shape through normalization, role
  validation, and schedule semantic validation.
- Updated README, claim normalization docs, role-scope policy, experiment
  design, metrics, live setup, and ADR-0010.

## Status Semantics

Allowed values:

- `available`
- `partially_consumed`
- `fully_consumed`

When numeric consumed and remaining float values are present:

- remaining float equals available float and consumed float equals 0 means
  `available`
- remaining float is greater than 0 and consumed float is greater than 0 means
  `partially_consumed`
- remaining float equals 0 means `fully_consumed`

## Verification Commands

```bash
python -m pytest
```

Result: `111 passed, 1 skipped in 6.05s`

```bash
PYTHONPATH=src python -m project_recovery_council check-schema-drift
```

Result: `schema drift check passed`

```bash
PYTHONPATH=src python -m project_recovery_council validate-prompts
```

Result: `prompt validation passed`

## Network Status

No live network request was made during this pass.

## Known Limitations

- The new alias is explicit; no fuzzy key matching was introduced.
- `float_consumption_status` is validated only when present.
- Prior live artifacts are not modified or retroactively certified.

## Recommended Next Live Invocation

Run one standalone ScheduleExpert invocation to verify the new alias and status
handling in live artifacts:

```bash
export DASHSCOPE_API_KEY="<your-api-key>"
PYTHONPATH=src python -m project_recovery_council live-agent \
  --agent ScheduleExpert \
  --model qwen-plus \
  --allow-network
```
