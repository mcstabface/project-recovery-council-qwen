# Build Checkpoint: Validated Findings Synthesis Handoff

**Date:** 2026-06-17  
**Repository:** `project-recovery-council-qwen`  
**Status:** Complete for specialist handoff, role policy correction, and recommendation-versus-authorization semantics

## Context

A live fixed expert chain produced strong specialist findings, but
RecoveryPlanner abstained after treating pending human confirmation as a reason
not to recommend a recovery option. The same run also showed role-policy gaps
for observed CommercialExpert, EvidenceAuditor, and RiskExpert claim keys.

This checkpoint changes the synthesis handoff and reporting artifacts only. It
does not run live provider calls, change frozen schemas, alter prior live
artifacts, weaken evidence scoping, or change the deterministic oracle.

## Created Or Updated

- Added `src/project_recovery_council/synthesis_handoff.py`.
- Added validated finding, excluded finding, synthesis input, recommendation
  authorization state, and synthesis metric contracts.
- Added future live artifacts:
  - `validated-findings-envelope.json`
  - `excluded-findings.json`
  - `synthesis-input.json`
  - `recommendation-authorization-state.json`
  - `synthesis-metrics.json`
- Updated RecoveryPlanner handoff to use compact validated findings rather than
  verbose raw specialist provider responses.
- Added recommendation-versus-authorization semantics: recommendation may be
  completed while authorization remains blocked pending human confirmation.
- Added explicit normalization and role-policy support for observed
  CommercialExpert, EvidenceAuditor, RiskExpert, and ScheduleExpert keys.
- Added synthesis metrics for finding retention, citation propagation,
  validated claim utilization, recommendation correctness, authorization gate
  correctness, recommendation-with-pending-approval correctness, and synthesis
  omission count.
- Updated documentation and ADR-0013.

## Verification Commands

```bash
python -m pytest tests/test_validated_findings_handoff.py tests/test_live_variant_runner.py tests/test_role_scope_policy.py tests/test_claim_normalization.py tests/test_schedule_semantics.py
```

Result: `62 passed in 0.76s`

```bash
python -m pytest tests/test_qwen_artifacts_and_cli.py tests/test_qwen_evaluation.py
```

Result: `11 passed in 0.87s`

```bash
python -m pytest
```

Result: `136 passed, 1 skipped in 6.74s`

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
- Only ScheduleExpert has a specialized domain semantic validator.
- The handoff does not rewrite model output; it records and excludes invalid
  findings rather than correcting them.

## Recommended Next Fixed-Chain Live Command

```bash
export DASHSCOPE_API_KEY="<your-api-key>"
PYTHONPATH=src python -m project_recovery_council live-variant \
  --variant fixed_expert_chain \
  --model qwen-plus \
  --allow-network
```
