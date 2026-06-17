# Build Checkpoint: EvidenceAuditor Contract

Date: 2026-06-17

Git base: `dffc2cc64618baa4e53732744605629a17cb9a52`

## Scope

This checkpoint fixes a live dynamic-council response-contract mismatch where
EvidenceAuditor returned a coherent nested per-agent audit matrix that did not
fit the generic flat specialist response contract. It also makes live
comparison artifact requirements variant-aware for historical completed
single-generalist runs.

## Changes

- Added experiment-layer
  `project-recovery-council.qwen.evidence-auditor-response.v1`.
- Added typed nested audit assessments with explicit support statuses and
  matching nested citations.
- Added deterministic conversion from EvidenceAuditor responses into canonical
  audit findings.
- Preserved contradicted and unsupported audit assessments while excluding them
  from positive synthesis evidence.
- Kept generic specialist parsing unchanged for ordinary specialists.
- Updated fixed-chain and dynamic plans, prompt catalog, prompt text, and live
  runners to select the dedicated EvidenceAuditor schema.
- Added EvidenceAuditor validation and canonical audit finding artifacts.
- Added compact EvidenceAuditor payload accounting in governance payloads.
- Made `compare-live` variant-aware so specialist synthesis artifacts are not
  applicable to completed `single_generalist` runs.
- Preserved the deterministic onsite human gate in recommendation authorization
  state using source evidence; model output cannot clear the gate.
- Updated documentation and ADR-0016.

## Verification

- `python -m pytest tests/test_evidence_auditor_contract.py tests/test_live_variant_runner.py tests/test_dynamic_council_governance.py tests/test_qwen_prompts_and_plans.py tests/test_validated_findings_handoff.py`
  - `46 passed in 1.41s`
- `python -m pytest`
  - `163 passed, 1 skipped in 7.28s`
- `PYTHONPATH=src python -m project_recovery_council check-schema-drift`
  - `schema drift check passed`
- `PYTHONPATH=src python -m project_recovery_council validate-prompts`
  - `prompt validation passed`
- `git diff --check`
  - passed with no output

## Live Network

No live network request was made during this checkpoint.

## Preservation

Prior live artifacts were not modified. Frozen `schemas/v1` contracts and the
deterministic oracle were not modified. The failed dynamic live run remains
failed and non-comparable unless diagnostic overrides are used.
