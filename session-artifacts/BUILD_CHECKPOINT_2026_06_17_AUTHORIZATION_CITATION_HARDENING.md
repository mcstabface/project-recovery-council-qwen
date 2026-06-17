# Build Checkpoint: Authorization State And Citation Hardening

Date: 2026-06-17

Git base: `dc1a308197c6d2eba506eb3c73346dfe8f5d6fe9`

## Scope

This checkpoint hardens the controlled live fixed-chain and council synthesis
path after a live fixed-chain run exposed three remaining issues:

- authorization state was marked ready despite unresolved onsite contradiction
  and required human confirmation
- observed live specialist claim aliases were not fully recognized
- final preferred-option and approval-condition citations were not propagated
  into the accepted final structured response

## Changes

- Added explicit ScheduleExpert aliases and canonical keys for observed live
  schedule output, including `float_consumed_days`,
  `delivery_movement_direction`, and `equipment_id`.
- Added deterministic schedule semantic validation for
  `delivery_movement_direction`.
- Added explicit EvidenceAuditor lower-case claim-ID aliases mapped to the
  versioned canonical audit claim registry.
- Added observed RiskExpert human-gate claim keys.
- Made recommendation/authorization state block on unresolved onsite
  contradiction until `HDR-ONSITE-001` is resolved by a recorded human decision.
- Added live artifact inspection checks for inconsistent ready authorization
  when final output still requires human confirmation.
- Added deterministic final citation merging from validated specialist findings
  for preferred option and approval-condition fields.
- Updated docs and ADR-0014.

## Verification

- `python -m pytest tests/test_validated_findings_handoff.py tests/test_claim_normalization.py tests/test_schedule_semantics.py tests/test_live_variant_runner.py tests/test_role_scope_policy.py`
  - `70 passed in 0.74s`
- `python -m pytest`
  - `144 passed, 1 skipped in 6.24s`
- `git diff --check`
  - passed with no output
- `PYTHONPATH=src python -m project_recovery_council check-schema-drift`
  - `schema drift check passed`
- `PYTHONPATH=src python -m project_recovery_council validate-prompts`
  - `prompt validation passed`

## Live Network

No live network request was made during this checkpoint.
