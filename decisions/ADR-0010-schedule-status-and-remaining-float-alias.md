# ADR-0010: Schedule Status and Remaining Float Alias

## Status

Accepted

## Context

A live scoped `ScheduleExpert` invocation passed evidence scoping and schedule
semantic validation, but role validation failed on two legitimate schedule
claim keys:

- `remaining_total_float_days`
- `float_consumption_status`

The first is a provider synonym for the canonical remaining-float key. The
second is a qualitative schedule status that should be allowed, but only with a
bounded vocabulary and deterministic consistency checks.

## Decision

Add the explicit alias:

- `remaining_total_float_days` -> `installation_total_float_remaining_days`

Add `float_consumption_status` as a canonical `ScheduleExpert` claim key.
Permit only:

- `available`
- `partially_consumed`
- `fully_consumed`

When numeric consumed and remaining float values are present, validate status
consistency:

- remaining float equals available float and consumed float equals 0 means
  `available`
- remaining float is greater than 0 and consumed float is greater than 0 means
  `partially_consumed`
- remaining float equals 0 means `fully_consumed`

Raw provider output remains unchanged; normalization and semantic validation
artifacts record the deterministic interpretation.

## Consequences

Known live ScheduleExpert phrasing no longer creates a false role-policy
failure, while invalid or inconsistent qualitative status claims are still
detected by schedule semantic validation. Frozen v1 schemas remain unchanged.
