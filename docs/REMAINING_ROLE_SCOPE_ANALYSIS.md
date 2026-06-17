# Remaining Role-Scope Analysis

Source artifact:

```text
experiment-artifacts/live/live-variant-dynamic_expert_council-20260617T132007Z/role-validation-results.json
```

## Finding

The only invalid role-validation result in the selected empirical dynamic run
is:

```text
INV-live-variant-dynamic_expert_council-20260617T132007Z-04-scheduleexpert
```

Role:

```text
ScheduleExpert
```

Recorded invalid claims:

- `installation_activity_id: claim key outside role policy`
- `contractual_milestone_id: claim key outside role policy`

There were no prohibited warnings, citation-policy violations, or
evidence-scope violations.

## Classification

This is a policy false positive caused by explicit role-policy and alias drift.

`installation_activity_id` is a schedule identifier from
`SCH-DELIVERY-001`, which the ScheduleExpert was allowed to receive. It does
not make a commercial, onsite, recovery-option, authorization, or human-decision
claim.

`contractual_milestone_id` is a milestone identifier from the scoped schedule
and case-intake records. It is semantically equivalent to the already allowed
canonical ScheduleExpert key `milestone_id`.

## Correction

The offline validator now applies the smallest explicit correction:

- `contractual_milestone_id` -> `milestone_id`
- `installation_activity_id` is an allowed canonical ScheduleExpert claim key

The correction preserves existing role boundaries. ScheduleExpert remains
prohibited from making onsite-status, supplier-arrival, logistics-arrival,
commercial-exposure, mitigation-cost, preferred-option, final-authorization, or
human-decision claims.

## Regression Fixture

The sanitized parsed ScheduleExpert response shape is preserved as:

```text
tests/fixtures/dynamic_schedule_scope_drift_response.json
```

The fixture contains the exact offending structured response shape without a
raw provider envelope, request metadata, authorization header, or secret
material.

The regression test reruns the captured response through offline
normalization and role-scope validation. It verifies that:

- `contractual_milestone_id` normalizes to `milestone_id`
- `installation_activity_id` remains visible as a schedule identifier
- the response is role-valid after the explicit policy correction
- no prohibited claims are introduced

## Empirical Provenance

The original empirical artifact remains unchanged. Its recorded
`role_scope_compliance_rate` is still `0.75` because that was the validation
state at the time of the live run.

Submission materials should describe this as:

```text
Recorded dynamic role-scope compliance was 0.75. Post-run offline analysis
identified the failure as a policy false positive on schedule identifier keys,
not a substantive role violation.
```

The empirical result should not be relabeled as perfectly role-compliant unless
a new live run is executed and validates under the corrected policy.
