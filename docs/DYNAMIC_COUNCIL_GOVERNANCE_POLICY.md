# Dynamic Council Governance Policy

The dynamic council is allowed to reduce expert calls through Director routing,
but it must not use a different deterministic validation path from the fixed
expert chain.

## Root-Cause Trace

The failed live run `live-variant-dynamic_expert_council-20260617T120357Z`
completed provider execution but failed final artifact validation. The
deterministic processing defects were:

- dynamic specialist responses were not being retained through the same
  normalization, role-scope, semantic-validation, and synthesis-handoff behavior
  expected by the fixed chain
- CommercialExpert had no domain semantic validator, so an incorrect
  `gross_avoided_exposure_usd=195000` could not be distinguished from the valid
  `net_avoided_exposure_usd=147000`
- support-only EvidenceAuditor findings were treated as substantive
  disagreements rather than verification records
- EvidenceAuditor live output can be a coherent nested per-agent audit matrix,
  which must not be forced into the generic flat specialist contract
- ArbiterAgent was invoked even when no eligible findings disagreed
- governance prompts carried more accumulated context than required for audit
  and arbitration
- derived authorization state correctly failed validation when no validated
  recommendation evidence survived

The prior failed live artifacts remain unchanged and are not relabeled as
successful.

## Shared Deterministic Processing

Fixed-chain and dynamic-council specialists both flow through:

- `LiveVariantRun._validate_specialist`
- `normalize_claim_keys`
- `validate_role_scope`
- `validate_schedule_semantics` for `ScheduleExpert`
- `validate_commercial_semantics` for `CommercialExpert`
- `build_synthesis_handoff`
- `build_recommendation_authorization_state`

Tests assert that sanitized specialist outputs produce identical normalized
claims in fixed and dynamic variants.

## Commercial Semantic Validation

`CommercialExpert` validation checks the deterministic commercial arithmetic
against the synthetic case:

- `delay_exposure_usd_per_day = 15000`
- `forecast_milestone_slip_days = 13`
- `unmitigated_exposure_usd = delay_exposure_usd_per_day *
  forecast_milestone_slip_days`
- `mitigation_cost_usd = 48000`
- avoided exposure is `unmitigated_exposure_usd - mitigation_cost_usd = 147000`

`net_avoided_exposure_usd` is normalized to `avoided_exposure_usd`. An incorrect
`gross_avoided_exposure_usd` remains visible but is excluded from normal
synthesis when it fails semantic validation.

## Arbiter Invocation Policy

ArbiterAgent runs only for a substantive disagreement among eligible validated
findings. A substantive disagreement requires at least two eligible findings in
the same normalized issue domain with conflicting values, support statuses, or
recommendations.

ArbiterAgent is skipped when:

- all findings were excluded by deterministic validation
- no normalized issue domain contains conflicting eligible values
- support-only audit assessments simply verify claims
- the only unresolved issue is the human onsite-status evidence gate
- validation software rejected an output shape

Skipped arbitration is recorded in `arbitration-decisions.json` with
`arbiter_required: false`, an `arbiter_skip_reason`, and no provider invocation.

## Compact Governance Payloads

EvidenceAuditor receives normalized specialist claims, claim-attached
citations, validation status, cited source evidence, and known contradiction
candidates. It does not receive raw provider histories or full prompt text.

EvidenceAuditor returns
`project-recovery-council.qwen.evidence-auditor-response.v1`, with claim
assessments grouped by audited agent and claim key. Nested responses are
converted to canonical audit findings. A `supported` assessment may reinforce
the corresponding specialist finding. `contradicted`, `unsupported`, and
`insufficient_evidence` assessments remain visible and cite their source
records, but they are excluded from positive synthesis and can make the audited
specialist claim disputed or ineligible.

ArbiterAgent, when required, receives only disagreement records, conflicting
eligible findings, citations, limited supporting evidence, and human-gate
status.

`governance-payloads.json` records serialized payload bytes, normalized
specialist finding count, selected evidence-record count, citation count, and
flags for raw provider envelopes, prior rendered prompts, and repeated schemas.
Compact EvidenceAuditor and Arbiter payloads must keep those three inclusion
flags false.

## Failed-Run Diagnostics

Failed empirical runs preserve provider outputs and validation errors. They are
not usable for normal `compare-live` unless a diagnostic override is supplied.

`rebuild-derived-artifacts <run-path> --output <new-derived-path>` creates a
no-network diagnostic replay by reprocessing persisted invocation records. The
derived output records source artifact hashes and `provider_calls_made: 0`, and
marks itself as non-empirical.
