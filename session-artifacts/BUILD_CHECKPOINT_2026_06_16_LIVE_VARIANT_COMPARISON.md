# Build Checkpoint: Controlled Live Variant Comparison

**Date:** 2026-06-16  
**Repository:** `project-recovery-council-qwen`  
**Status:** Complete for controlled one-variant live execution and offline live comparison

## Context

The repository already supported live Qwen smoke tests, standalone live
specialist execution, evidence scoping, claim normalization, role-scope
validation, ScheduleExpert semantic validation, artifact redaction, and live
artifact inspection. This checkpoint adds the controlled live runner for the
three AI competition variants without running live network calls or modifying
prior live artifacts.

## Created Or Updated

- Added `live_variant_runner.py` for controlled execution of:
  - `single_generalist`
  - `fixed_expert_chain`
  - `dynamic_expert_council`
- Added `compare-live`, a no-network comparison command for three completed
  live variant directories.
- Added conservative live-run controls for invocation count, token totals,
  elapsed time, retry count, stop-after-invocation, and no-overwrite behavior.
- Added live variant artifacts for execution plans, prompt hashes, selected
  evidence, parsed and raw redacted responses, validation results, retry
  history, token usage, routing decisions, disagreement records, final variant
  results, evaluation results, reproducibility metadata, and manifests.
- Extended artifact inspection to require normalization, role validation, and
  ScheduleExpert semantic validation artifacts for live specialist invocations.
- Updated fixed-chain planning to run ScheduleExpert, CommercialExpert,
  EvidenceAuditor, RiskExpert, and RecoveryPlanner in order.
- Added mocked tests for successful and failed live variant paths, dynamic
  Director routing, budget stops, incomplete artifact preservation, comparison
  generation, incomplete comparison rejection, CLI safety, and secret absence.
- Updated README, live setup, provider plan, experiment design, metrics,
  runbook, and ADR-0011.

## Safeguards

Every live variant run requires:

- `--allow-network`
- explicit `--model`
- credentials before any provider client is used
- one requested variant only
- no overwrite without `--replace-existing`

The runner stops future invocations and preserves completed artifacts when a
limit is exceeded. Incomplete runs return nonzero through the CLI and record the
stopping limit in `final-variant-result.json`.

## Verification Commands

```bash
python -m pytest tests/test_live_variant_runner.py tests/test_qwen_live_cli.py tests/test_qwen_prompts_and_plans.py tests/test_schedule_semantics.py
```

Result: `38 passed in 2.57s`

```bash
python -m pytest
```

Result: `129 passed, 1 skipped in 8.92s`

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

- Only ScheduleExpert has a specialized domain semantic validator.
- `compare-live` is descriptive and does not claim statistical significance
  from one run per variant.
- Provider cost estimation remains omitted unless explicit pricing is supplied.
- Automatic live matrix execution remains intentionally unsupported.

## Exact First Manual Live Command

```bash
export DASHSCOPE_API_KEY="<your-api-key>"
PYTHONPATH=src python -m project_recovery_council live-variant \
  --variant single_generalist \
  --model qwen-plus \
  --allow-network
```
