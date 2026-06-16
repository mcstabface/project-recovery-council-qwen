# Build Checkpoint: Schedule Semantic Validation

**Date:** 2026-06-16  
**Repository:** `project-recovery-council-qwen`  
**Status:** Complete for ScheduleExpert policy correction and deterministic schedule semantic validation

## Context

A scoped live `ScheduleExpert` invocation correctly received only
`CASE-INTAKE-001` and `SCH-DELIVERY-001`, but exposed two remaining policy
defects:

- legitimate schedule claim keys were marked as prohibited
- schema-valid schedule arithmetic reported consumed float of 13 days and
  remaining float of -5 days, inconsistent with the deterministic reference
  case

This checkpoint corrects the role policy and adds deterministic arithmetic
validation without running live network calls, modifying frozen schemas, or
changing prior live artifacts.

## Created Or Updated

- Added `schedule_semantics.py` with `ScheduleSemanticValidationResult`,
  deterministic ScheduleExpert semantic validation, and schedule semantic metric
  aggregation.
- Expanded ScheduleExpert allowed claim keys in `role_scope.py` to include
  milestone identifiers, delivery dates, installation float fields, milestone
  dates, slip, and successor dependency fields.
- Added schedule semantic metric IDs and metric-result helpers.
- Added future live artifact outputs for `schedule-semantic-validation.json`
  and `schedule-semantic-metrics.json`.
- Updated artifact inspection to require schedule semantic validation for
  standalone live ScheduleExpert invocations.
- Added tests for allowed schedule keys, prohibited non-schedule claims,
  21/8/13 arithmetic, malformed schedule arithmetic, schema-valid but
  schedule-invalid responses, role-valid but schedule-invalid responses,
  schedule metrics, and artifact validation.
- Updated README, role-scope policy, experiment design, metrics docs, and
  ADR-0008.

## Deterministic Schedule Interpretation

For `SCH-DELIVERY-001`:

- delivery movement: 21 days
- available installation total float: 8 days
- float consumed: 8 days
- remaining float: 0 days
- milestone slip without intervention: 13 days

The validator preserves provider output unchanged and records violations
separately.

## Verification Commands

```bash
python -m pytest tests/test_schedule_semantics.py tests/test_role_scope_policy.py
```

Result: `24 passed in 0.30s`

```bash
python -m pytest
```

Result: `95 passed, 1 skipped in 7.56s`

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

- Prior live artifacts are not modified or retroactively certified.
- The schedule semantic validator currently targets deterministic
  `ScheduleExpert` fields for the synthetic equipment-delay case.
- Live variant comparison is still intentionally deferred.

## Recommended Next Live Invocation

Run one standalone ScheduleExpert invocation to verify the corrected role policy
and schedule semantic artifact:

```bash
export DASHSCOPE_API_KEY="<your-api-key>"
PYTHONPATH=src python -m project_recovery_council live-agent \
  --agent ScheduleExpert \
  --model qwen-plus \
  --allow-network
```
