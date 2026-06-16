# ADR-0008: Schedule Semantic Validation

## Status

Accepted

## Context

A scoped live `ScheduleExpert` invocation correctly received only
`CASE-INTAKE-001` and `SCH-DELIVERY-001`, but exposed two remaining defects.
The role policy treated valid schedule output fields as prohibited, and the
provider returned schema-valid schedule arithmetic that was inconsistent with
the deterministic reference case.

The correct schedule interpretation is:

- delivery movement: 21 days
- available installation total float: 8 days
- float consumed: 8 days
- remaining float: 0 days
- net milestone slip after float absorption: 13 days

## Decision

Allow the full set of legitimate `ScheduleExpert` schedule claim keys, including
milestone identifiers, delivery dates, installation float fields, milestone
dates, milestone slip, and successor dependency fields.

Add deterministic schedule-semantic validation separate from JSON schema
validation and role-scope validation. The validator checks reported schedule
values against `SCH-DELIVERY-001` and records expected values, observed values,
violations, and concise findings. It preserves provider output unchanged.

Future standalone live `ScheduleExpert` artifacts include
`schedule-semantic-validation.json`. Artifact inspection requires that file for
standalone live ScheduleExpert invocations.

## Consequences

A response can now be:

- JSON-schema valid
- role-scope valid
- schedule-semantically invalid

This distinction lets reports identify narrowly scoped specialists that still
make incorrect arithmetic claims. The deterministic oracle and frozen v1 schemas
remain unchanged.
