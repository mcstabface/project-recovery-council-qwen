# Build Checkpoint: Role Scope Hardening

**Date:** 2026-06-16  
**Repository:** `project-recovery-council-qwen`  
**Status:** Complete for evidence scoping and semantic role validation pass

## Context

A real live `ScheduleExpert` invocation against `qwen-plus` completed and
validated, but exposed two integration defects:

- `ScheduleExpert` received the complete evidence bundle and produced an
  onsite-status contradiction warning outside schedule scope.
- The standalone specialist invocation was labeled with
  `experiment_variant=single_generalist`.

This checkpoint hardens the integration without running live network calls.

## Created Or Updated

- Added central role evidence policy in `role_scope.py`.
- Added role-scoped evidence selection before prompt rendering.
- Added `invocation_purpose` metadata to invocation records and experiment
  config.
- Added semantic role validation separate from JSON schema validation.
- Added scope-compliance metrics and role validation metric helpers.
- Added live artifact files for future specialist runs:
  `selected-evidence-records.json` and `role-validation-results.json`.
- Updated live artifact validation to require those files for standalone
  specialist live artifacts.
- Added tests for ScheduleExpert/CommercialExpert/EvidenceAuditor/Generalist
  evidence filtering, specialist role validation, evidence overexposure,
  role-compliance metrics, metadata, and artifact validation.
- Updated README, experiment design, prompt architecture, metrics, live setup,
  role-scope docs, and ADR-0007.

## Verification Commands

```bash
python -m pytest tests/test_role_scope_policy.py tests/test_qwen_live_client.py tests/test_qwen_live_cli.py tests/test_qwen_live_integration.py
```

Result: `25 passed, 1 skipped in 0.64s`

```bash
python -m pytest
```

Result: `83 passed, 1 skipped in 5.82s`

```bash
PYTHONPATH=src python -m project_recovery_council check-schema-drift
```

Result: `schema drift check passed`

```bash
PYTHONPATH=src python -m project_recovery_council validate-prompts
```

Result: `prompt validation passed`

```bash
PYTHONPATH=src python -m project_recovery_council compare-offline
```

Result:

```text
offline comparison: offline-comparison-v1
dynamic_expert_council:strong_modular_council required_fact_accuracy=1.0 schema=valid unsupported_claims=0
single_generalist:generalist_missed_onsite_contradiction required_fact_accuracy=0.2 schema=valid unsupported_claims=1
fixed_expert_chain:fixed_chain_result required_fact_accuracy=1.0 schema=valid unsupported_claims=0
```

```bash
PYTHONPATH=src python -m project_recovery_council live-agent --agent ScheduleExpert --model qwen-plus
```

Result: exit code `1`; failed before network with
`live execution requires --allow-network`.

## Network Status

No real network request was made during this pass.

## Known Limitations

- Prior live artifacts, if any, are not retroactively modified or certified.
- `live-variant` still supports only `single_generalist`.
- Role validation is deterministic and conservative; it may need refinement as
  real provider outputs reveal additional phrasing patterns.

## Recommended Next Live Invocation

Run one standalone ScheduleExpert invocation with the hardened scoping:

```bash
export DASHSCOPE_API_KEY="<your-api-key>"
PYTHONPATH=src python -m project_recovery_council live-agent \
  --agent ScheduleExpert \
  --model qwen-plus \
  --allow-network
```
