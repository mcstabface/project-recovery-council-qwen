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

Provider pricing is never invented. Offline fixtures leave provider token,
latency, and cost values null unless a fixture or provider explicitly supplies
them.

## Claim Statuses

Claims are classified as `absent`, `correct`, `incorrect`, `unsupported`, or
`ambiguous`. Citation precision and recall are computed against stable source
record IDs in the synthetic evidence bundle.
