# Build Checkpoint: Metric Applicability and Live Report Provenance

**Date:** 2026-06-17  
**Repository:** `project-recovery-council-qwen`  
**Status:** Complete for live report provenance and N/A specialist metric reporting

## Context

A real live `single_generalist` experiment completed successfully, but the
reporting layer reused offline fixture limitation text and represented
specialist-only validation layers as 1.0 for the full-scope GeneralistAgent.
This checkpoint corrects reporting only. It does not change deterministic
evaluation scores, frozen schemas, prior live artifacts, or provider behavior.

## Created Or Updated

- Added report provenance handling to `evaluate_model_result`.
- Updated live evaluation calls to use live-provider limitation text.
- Added typed metric applicability for live role-scope and specialized semantic
  validation reporting.
- Marked GeneralistAgent role-scope and specialized semantic validation as
  `not_applicable` with null score.
- Preserved actual specialist compliance scores for specialist variants.
- Updated live comparison JSON and Markdown so N/A renders as `N/A`.
- Added tests for live/offline limitation wording, Generalist N/A metrics,
  specialist applicability, and comparison rendering.
- Updated README, metrics, experiment design, live comparison runbook, and
  ADR-0012.

## Verification Commands

```bash
python -m pytest tests/test_live_variant_runner.py tests/test_qwen_evaluation.py
```

Result: `26 passed in 0.51s`

```bash
python -m pytest
```

Result: `132 passed, 1 skipped in 6.26s`

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

- Prior live artifacts are intentionally untouched.
- Only ScheduleExpert has a specialized semantic validator today.
- Existing old live artifacts may still contain the previous reporting shape
  until a new live run is executed.

## Recommended Next Live Command

```bash
export DASHSCOPE_API_KEY="<your-api-key>"
PYTHONPATH=src python -m project_recovery_council live-variant \
  --variant fixed_expert_chain \
  --model qwen-plus \
  --allow-network
```
