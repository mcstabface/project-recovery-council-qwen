# ADR-0009: Versioned Claim-Key Normalization

## Status

Accepted

## Context

A scoped live `ScheduleExpert` invocation passed evidence scoping and schedule
semantic validation, but role validation failed because the model used
semantically equivalent claim keys:

- `remaining_float_after_delivery_shift_days`
- `contractual_milestone_baseline_date`
- `contractual_milestone_forecast_without_intervention`

The canonical role-policy keys are:

- `installation_total_float_remaining_days`
- `milestone_baseline_date`
- `milestone_forecast_date_without_intervention`

Treating supported aliases as role violations makes the system brittle, while
allowing arbitrary fuzzy matching would weaken auditability.

## Decision

Add a deterministic, versioned claim-key normalization layer:

- raw provider responses remain unchanged
- supported aliases are mapped to canonical claim keys using explicit tables
- unknown keys remain visible and continue into role-scope validation
- canonical-plus-alias values are accepted only when equivalent
- conflicting aliases invalidate normalization and preserve raw values
- role-scope and schedule-semantic validators consume normalized claims
- live artifacts record normalization results, normalized responses, and
  normalization metrics separately from raw parsed responses

No fuzzy matching and no LLM-based normalization are allowed.

## Consequences

Live specialists can use known semantically equivalent key names without
creating false role-policy failures. At the same time, unknown or conflicting
claim keys stay inspectable and cannot be silently converted into accepted
claims. A response may now be schema-valid but normalization-invalid,
role-invalid, or domain-semantically invalid.
