# Build Checkpoint: Claim-Key Normalization

**Date:** 2026-06-16  
**Repository:** `project-recovery-council-qwen`  
**Status:** Complete for deterministic specialist claim-key normalization

## Context

A new scoped live `ScheduleExpert` invocation succeeded with correct evidence
scope, valid citations, and correct schedule arithmetic, but role validation
failed because the provider used semantically equivalent claim keys:

- `remaining_float_after_delivery_shift_days`
- `contractual_milestone_baseline_date`
- `contractual_milestone_forecast_without_intervention`

The canonical keys are:

- `installation_total_float_remaining_days`
- `milestone_baseline_date`
- `milestone_forecast_date_without_intervention`

This checkpoint adds deterministic normalization without making live network
calls, modifying frozen schemas, changing prior live artifacts, or mutating raw
provider output.

## Created Or Updated

- Added `claim_normalization.py` with versioned canonical keys, explicit
  aliases, alias application records, conflict detection, unknown-key tracking,
  normalized payload construction, and normalization metrics.
- Updated ScheduleExpert role policy to rely on canonical claim keys.
- Wired live specialist validation order as schema validation, claim
  normalization, role-scope validation, then domain semantic validation.
- Added live artifacts:
  `claim-normalization-results.json`,
  `normalized-structured-responses.json`, and
  `claim-normalization-metrics.json`.
- Extended artifact inspection to require normalization artifacts for
  standalone specialist live runs and to verify traceability from raw parsed
  claims to normalized claims.
- Added normalization metrics:
  `claim_normalization_success_rate`, `alias_application_count`,
  `unknown_claim_key_count`, and `claim_alias_conflict_count`.
- Added tests for canonical pass-through, requested aliases, raw versus
  normalized payload preservation, equal and conflicting aliases, unknown keys,
  role and schedule validation on normalized claims, live artifact inspection,
  and mocked no-network execution.
- Updated README, role-scope policy, experiment design, metrics, live setup,
  claim normalization documentation, and ADR-0009.

## Verification Commands

```bash
python -m pytest tests/test_claim_normalization.py tests/test_schedule_semantics.py tests/test_role_scope_policy.py
```

Result: `36 passed in 0.26s`

```bash
python -m pytest
```

Result: `107 passed, 1 skipped in 6.98s`

```bash
PYTHONPATH=src python -m project_recovery_council check-schema-drift
```

Result: `schema drift check passed`

```bash
PYTHONPATH=src python -m project_recovery_council validate-prompts
```

Result: `prompt validation passed`

## Network Status

No live network request was made during this pass. Live-path tests used mocked
transport boundaries only.

## Known Limitations

- Normalization is explicit and versioned; unsupported aliases remain unknown
  until added deliberately.
- Only claim keys are normalized. Raw provider responses and prior live
  artifacts remain unchanged.
- Full live variant comparison remains deferred.

## Recommended Next Live Invocation

Run one standalone ScheduleExpert invocation to verify alias normalization in
the live artifact path:

```bash
export DASHSCOPE_API_KEY="<your-api-key>"
PYTHONPATH=src python -m project_recovery_council live-agent \
  --agent ScheduleExpert \
  --model qwen-plus \
  --allow-network
```
