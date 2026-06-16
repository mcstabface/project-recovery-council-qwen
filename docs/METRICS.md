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

## Schedule Semantic Metrics

Schedule semantic metrics apply to `ScheduleExpert` outputs after schema
validation and role-scope validation. They do not rewrite provider output; they
record deterministic arithmetic agreement or disagreement with the schedule
evidence.

- `delivery_movement_correctness`: whether reported delivery movement matches
  the baseline-to-forecast delivery date delta.
- `float_consumed_correctness`: whether reported consumed float equals
  `min(delivery_movement_days, available_total_float_days)`.
- `remaining_float_correctness`: whether reported remaining float equals
  `max(available_total_float_days - delivery_movement_days, 0)` and is not
  negative.
- `milestone_slip_correctness`: whether reported net milestone slip equals
  `max(delivery_movement_days - available_total_float_days, 0)`.
- `milestone_date_arithmetic_correctness`: whether the reported forecast
  milestone date equals the baseline milestone date plus the reported net slip.
- `schedule_semantic_compliance_rate`: the share of ScheduleExpert semantic
  validations that pass all checked schedule rules.
