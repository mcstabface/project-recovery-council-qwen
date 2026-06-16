# ADR-0007: Agent Evidence Scope and Semantic Validation

## Status

Accepted

## Context

A successful live `ScheduleExpert` invocation returned schema-valid schedule
facts but also produced an onsite-status contradiction warning outside the
role's declared scope. The same standalone specialist invocation was labeled as
`single_generalist`, which blurred experiment variant and invocation purpose.

## Decision

Add explicit evidence-access policy code and semantic role validation:

- filter evidence before prompt rendering by agent role
- record selected evidence record IDs in invocation metadata and artifacts
- distinguish `invocation_purpose` from experiment variant
- validate specialist claims, warnings, citations, and selected evidence against
  role policy
- preserve provider output unchanged and report violations separately

`ScheduleExpert` receives only schedule records plus minimal case identity. It
must not receive or independently analyze onsite-status, supplier/logistics,
commercial, recovery-option, authorization, or human-decision evidence.

## Consequences

A provider response can now be schema-valid but role-invalid. Future comparison
reports can distinguish broad generalist behavior from narrower, governable
specialist behavior through scope-compliance metrics.
