# ADR-0016: Dedicated EvidenceAuditor Contract

## Status

Accepted

## Context

A live `dynamic_expert_council` run reached the EvidenceAuditor provider call
and received a coherent nested audit matrix. The response grouped assessments
by audited agent and claim key:

- `CommercialExpert`
- `RiskExpert`
- `ScheduleExpert`

The generic `specialist-finding-response.v1` contract expects flat
`claims: map[string, any]` and `citations: map[string, list[string]`. The live
auditor response instead returned nested citation objects such as
`citations["ScheduleExpert"]["forecast_milestone_slip_days"]`. Pydantic
therefore rejected the response even though the substantive audit was useful.

The same iteration exposed a separate comparison issue: historical completed
`single_generalist` runs can validly lack later specialist-only synthesis
artifacts such as `synthesis-metrics.json`.

## Decision

EvidenceAuditor now uses an experiment-layer contract:

```text
project-recovery-council.qwen.evidence-auditor-response.v1
```

The contract validates nested per-agent claim assessments and matching nested
citations. It accepts only known audited agent roles and support statuses of
`supported`, `contradicted`, `unsupported`, or `insufficient_evidence`.

Validated auditor output is converted into canonical audit findings that
preserve audited agent, audited claim key, canonical claim key, support status,
citations, observed and expected values, rationale, source invocation ID, and
relationship to the original specialist finding when available.

Contradicted, unsupported, and insufficient-evidence assessments remain
visible and can make an original finding disputed or ineligible. They are not
promoted into positive synthesis evidence.

The generic specialist contract remains unchanged for ordinary specialists.
Frozen domain schemas under `schemas/v1/` remain unchanged.

`compare-live` artifact requirements are now variant-aware. Specialist-only
synthesis artifacts are not applicable to `single_generalist` runs, including
historical completed runs that predate those artifacts, but remain required for
completed specialist variants that reached synthesis.

## Consequences

The observed live EvidenceAuditor shape can validate without weakening schema
checks. The deterministic pipeline can preserve useful audit findings, exclude
contradicted or unsupported findings from synthesis, and retain the original
raw provider response unchanged for diagnostics.

Live comparisons can include historical valid generalist runs without
mistaking absent specialist artifacts for failed run data.

## Non-Goals

- No changes to frozen domain schemas.
- No live provider calls during this change.
- No relabeling of failed empirical runs as successful.
- No arbitrary free-form audit claim IDs.
- No weakening of artifact validation for failed or incomplete dynamic runs.
