# Validated Findings Handoff

Fixed-chain and dynamic-council live runs pass a compact validated-findings
envelope to synthesis agents. The goal is to preserve specialist governance
while avoiding verbose raw provider-response handoff to RecoveryPlanner.

## Envelope Fields

Each finding records:

- `case_id`
- `source_agent`
- `invocation_id`
- `claim_id`
- `canonical_claim_key`
- `value`
- `citations`
- `schema_valid`
- `normalization_valid`
- `role_scope_valid`
- `semantic_validation_status`
- `assumptions`
- `warnings`
- `contradiction_status`
- `eligible_for_synthesis`
- `exclusion_reason`

Only findings that pass required validation are eligible for normal synthesis.
Invalid findings remain visible in `excluded-findings.json` but are not included
in the planner's normal validated claim set.

## Artifacts

Future fixed-chain and dynamic-council runs write:

- `validated-findings-envelope.json`
- `excluded-findings.json`
- `synthesis-input.json`
- `recommendation-authorization-state.json`
- `synthesis-metrics.json`

`parsed-structured-responses.json` still preserves raw parsed provider output
for diagnostics. `synthesis-input.json` is the compact planner handoff and does
not include raw prompts or raw specialist response blocks.

## Citation Propagation

Citations are attached per canonical claim. Alias citations are mapped onto the
canonical claim key, and embedded citation lists in structured audit claim
values are preserved.

RecoveryPlanner should not reconstruct citations from prose. Required final
citations are carried in the synthesis input:

- projected slip: `SCH-DELIVERY-001`
- unmitigated exposure: `SCH-DELIVERY-001`, `COST-SUMMARY-001`,
  `CTR-DELAY-001`
- mitigation cost: `COST-SUMMARY-001`
- avoided exposure: `COST-SUMMARY-001`, `CTR-DELAY-001`
- onsite contradiction and human gate: `PRG-ONSITE-001`,
  `SUP-NOT-ARRIVED-001`, `LOG-STATUS-001`
- preferred option: `COST-SUMMARY-001`, `SCH-DELIVERY-001`,
  `LOG-STATUS-001` where relevant

## Recommendation Versus Authorization

The planner handoff explicitly separates recommendation from authorization:

- a recovery option may be recommended when validated evidence supports it
- final authorization may remain blocked by an unresolved human gate
- human confirmation required does not require planner abstention
- approval-pending recommendations should set `preferred_option_subject_to_approval`
  and `human_confirmation_required`

RecoveryPlanner should abstain only when there is insufficient validated
evidence to form a recommendation.

## Metrics

Synthesis metrics track finding retention, citation propagation, validated
claim utilization, recommendation correctness, authorization gate correctness,
recommendation-with-pending-approval correctness, and synthesis omissions.
