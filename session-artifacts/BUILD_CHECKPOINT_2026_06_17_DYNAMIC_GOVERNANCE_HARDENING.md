# Build Checkpoint: Dynamic Governance Hardening

Date: 2026-06-17

Git base: `5b288a1ca803ca95ea9119bde1f96c121bafaf4e`

## Scope

This checkpoint hardens the controlled live dynamic council path after a live
`dynamic_expert_council` run completed provider execution but failed final
artifact validation. The change preserves the failed run as failed and keeps
all live execution opt-in.

## Changes

- Unified fixed-chain and dynamic-council specialist validation through the same
  deterministic normalization, role-scope, semantic-validation, handoff, and
  authorization-state builders.
- Added deterministic `CommercialExpert` semantic validation for delay exposure
  rate, slip, unmitigated exposure, mitigation cost, and avoided exposure.
- Preserved valid `avoided_exposure_usd=147000` findings while rejecting an
  incorrect `gross_avoided_exposure_usd=195000` field.
- Added explicit observed aliases and canonical keys for dynamic
  ScheduleExpert, CommercialExpert, EvidenceAuditor, and RiskExpert outputs.
- Added compact EvidenceAuditor and Arbiter governance payloads.
- Added deterministic Arbiter invocation policy that skips arbitration when no
  substantive eligible disagreement exists.
- Added live diagnostic rebuild support through `rebuild-derived-artifacts`
  without provider calls or source-run mutation.
- Added dynamic governance artifacts and efficiency metrics.
- Updated docs and ADR-0015.

## Verification

- `python -m pytest tests/test_dynamic_council_governance.py tests/test_live_variant_runner.py tests/test_validated_findings_handoff.py tests/test_claim_normalization.py tests/test_schedule_semantics.py tests/test_qwen_evaluation.py`
  - `75 passed in 1.11s`
- `python -m pytest`
  - `153 passed, 1 skipped in 6.91s`
- `git diff --check`
  - passed with no output
- `PYTHONPATH=src python -m project_recovery_council check-schema-drift`
  - `schema drift check passed`
- `PYTHONPATH=src python -m project_recovery_council validate-prompts`
  - `prompt validation passed`

## Live Network

No live network request was made during this checkpoint.

## Preservation

Prior live artifacts were not modified. Frozen `schemas/v1` contracts and the
deterministic oracle were not modified.
