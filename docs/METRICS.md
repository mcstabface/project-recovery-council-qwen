# Metrics

The evaluator grades structured claims and citation record IDs, not prose.

Required deterministic checks:

- 13-day projected slip
- 195000 USD unmitigated exposure
- 48000 USD mitigation cost
- 147000 USD gross avoided exposure
- onsite-status contradiction detected
- unsupported onsite assertion prohibited
- human confirmation required
- accelerated logistics preferred subject to approval

## Metric Catalog

- required-fact accuracy
- monetary-calculation accuracy
- schedule-impact accuracy
- evidence citation precision
- evidence citation recall
- contradiction detection
- unsupported claim count
- correct human escalation
- preferred recovery option
- schema-valid response rate
- agent invocation count
- input tokens
- output tokens
- total tokens
- latency
- retry count
- estimated provider cost when explicit pricing is supplied
- scope compliance rate
- prohibited claim count
- prohibited warning count
- prohibited citation count
- evidence overexposure count
- delivery movement correctness
- float consumed correctness
- remaining float correctness
- milestone slip correctness
- milestone date arithmetic correctness
- schedule semantic compliance rate
- claim normalization success rate
- alias application count
- unknown claim key count
- claim alias conflict count
- specialist finding retention rate
- citation propagation rate
- validated claim utilization rate
- recommendation correctness
- authorization gate correctness
- recommendation with pending approval correctness
- synthesis omission count

Provider pricing is never invented. Offline fixtures leave provider token,
latency, and cost values null unless a fixture or provider explicitly supplies
them.

## Claim Statuses

Claims are classified as `absent`, `correct`, `incorrect`, `unsupported`, or
`ambiguous`. Citation precision and recall are computed against stable source
record IDs in the synthetic evidence bundle.

## Role-Scope Metrics

Role-scope validation is separate from JSON schema validation. A specialist
response can be schema-valid but role-invalid when it makes claims outside its
authority, emits prohibited warnings, cites prohibited records, or received
overexposed evidence.

The scope metrics are intended to show whether modular experts remain narrower
and more governable than a generalist.

Role-scope compliance is not applicable to full-scope `GeneralistAgent`
outputs. Live reports represent that as `applicable: false`,
`status: not_applicable`, and `score: null`; they do not convert it to 1.0 or
0.0.

## Claim Normalization Metrics

Claim normalization metrics apply between schema validation and role-scope
validation. They are reported separately from role and semantic correctness.

- `claim_normalization_success_rate`: the share of normalization results with
  no alias conflicts.
- `alias_application_count`: the number of explicit supported aliases mapped to
  canonical claim keys.
- `unknown_claim_key_count`: the number of claim keys that were neither
  canonical nor supported aliases.
- `claim_alias_conflict_count`: the number of canonical claim keys that had
  conflicting raw values from a canonical key or aliases.

## Schedule Semantic Metrics

Schedule semantic metrics apply to `ScheduleExpert` outputs after schema
validation and role-scope validation. They do not rewrite provider output; they
record deterministic arithmetic agreement or disagreement with the schedule
evidence.

Specialized schedule semantic validation is not applicable when no
`ScheduleExpert` invocation ran, including a single `GeneralistAgent` live
variant. Live reports represent that as `N/A`.

- `delivery_movement_correctness`: whether reported delivery movement matches
  the baseline-to-forecast delivery date delta.
- `float_consumed_correctness`: whether reported consumed float equals
  `min(delivery_movement_days, available_total_float_days)`.
- `remaining_float_correctness`: whether reported remaining float equals
  `max(available_total_float_days - delivery_movement_days, 0)` and is not
  negative.
- `float_consumption_status`: when present, the status must be one of
  `available`, `partially_consumed`, or `fully_consumed`, and must agree with
  reported consumed and remaining float values.
- `delivery_movement_direction`: when present, the status must be one of
  `early`, `on_time`, or `late`, and must agree with the sign of reported
  delivery movement.
- `milestone_slip_correctness`: whether reported net milestone slip equals
  `max(delivery_movement_days - available_total_float_days, 0)`.
- `milestone_date_arithmetic_correctness`: whether the reported forecast
  milestone date equals the baseline milestone date plus the reported net slip.
- `schedule_semantic_compliance_rate`: the share of ScheduleExpert semantic
  validations that pass all checked schedule rules.

## Live Comparison Metrics

`compare-live` reports one row per completed live AI variant:

- `single_generalist`
- `fixed_expert_chain`
- `dynamic_expert_council`

Each row includes model configuration, case ID, completion status, total
invocation count, required-fact accuracy, schedule correctness, commercial
correctness, citation precision and recall, contradiction detection,
unsupported claim count, correct human escalation, preferred recovery option,
schema-valid response rate, role-scope compliance, semantic-validation
compliance, provider-reported token totals, aggregate latency, retry count, and
any stopped-by-limit status.

The comparison is descriptive. One live run per variant is not statistically
significant, and the deterministic oracle remains the expected-result source
rather than an AI competitor.

Comparison reports distinguish `passed`, `failed`, `not_applicable`, and
`unavailable` for role-scope and specialized semantic validation. Markdown
renders `not_applicable` as `N/A`.

## Synthesis Handoff Metrics

Fixed-chain and dynamic-council runs compute synthesis handoff metrics after the
validated-findings envelope is built:

- `specialist_finding_retention_rate`: eligible findings divided by all
  normalized specialist findings.
- `citation_propagation_rate`: eligible findings that carry citations divided
  by all eligible findings.
- `validated_claim_utilization_rate`: required final recommendation fields that
  were populated when eligible specialist findings supported them.
- `recommendation_correctness`: whether the final recommendation selected
  `REC-ACCEL-LOGISTICS`.
- `authorization_gate_correctness`: whether pending or blocked authorization is
  preserved when human confirmation is required.
- `recommendation_with_pending_approval_correctness`: whether the planner
  completed a recommendation while keeping approval subject to the unresolved
  human gate.
- `synthesis_omission_count`: final recommendation fields omitted despite
  eligible specialist findings.

Pending authorization is not counted as recommendation failure. It is a
separate governance state.

Artifact inspection also checks recommendation/authorization consistency for
live synthesis runs. If a final response says human confirmation is required
and the onsite-status contradiction is detected, the authorization state must
record `blocked_pending_human_confirmation`, `HDR-ONSITE-001`, and the
unresolved `equipment_onsite_status` contradiction unless a recorded human
decision has cleared the gate.
