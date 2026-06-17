# ADR-0013: Validated Findings Synthesis Handoff

## Status

Accepted

## Context

A live fixed expert chain produced strong specialist findings, but
RecoveryPlanner abstained because it interpreted "human confirmation required
before authorization" as "no recovery recommendation can be made." The same run
also reported poor role-scope compliance because observed CommercialExpert,
EvidenceAuditor, and RiskExpert claim keys were not yet part of the explicit
role policies.

The planner handoff also contained verbose raw specialist response context,
which forced the synthesis model to reconstruct canonical claims, citations,
and governance status from large provider outputs.

## Decision

Add a deterministic validated-findings handoff:

- normalize specialist claim keys before synthesis
- validate role scope and domain semantics before eligibility
- preserve invalid findings in excluded artifacts
- pass only compact canonical eligible findings to RecoveryPlanner
- propagate citations per canonical claim
- write synthesis input and recommendation/authorization state artifacts

Recommendation and authorization are modeled separately. Human confirmation may
block final authorization while still allowing an evidence-supported recovery
recommendation. RecoveryPlanner should abstain only when validated evidence is
insufficient to form a recommendation.

Update role policy and normalization for observed live CommercialExpert,
EvidenceAuditor, RiskExpert, and ScheduleExpert outputs.

## Consequences

Future fixed-chain and dynamic-council runs should be more robust against
planner omission caused by verbose handoff or approval-gate ambiguity.
Specialist governance remains enforceable because invalid findings are visible
but excluded from normal synthesis.

The deterministic oracle and frozen v1 schemas remain unchanged. Prior live
artifacts are not modified.

## Non-Goals

- No live provider calls during this change.
- No automatic correction or rewriting of provider outputs.
- No weakening of evidence scoping.
- No claim-key fuzzy matching.
