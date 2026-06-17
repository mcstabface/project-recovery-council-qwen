# ADR-0014: Authorization State And Final Citation Propagation

## Status

Accepted

## Context

A second live fixed expert chain produced the required facts and the correct
recovery recommendation, but the generated live artifacts still reported
`authorization_status` as `ready_for_authorization` even though human
confirmation was required and the onsite-status contradiction was unresolved.
The same run showed remaining role-policy misses for observed ScheduleExpert,
EvidenceAuditor, and RiskExpert claim shapes, and the final recommendation
omitted propagated citations for preferred-option and approval-condition
claims.

## Decision

Harden the live synthesis layer with deterministic rules:

- authorization remains `blocked_pending_human_confirmation` when the onsite
  contradiction is unresolved and no recorded human decision resolves
  `HDR-ONSITE-001`
- `blocking_human_request` and `equipment_onsite_status` unresolved
  contradiction metadata are required in that blocked state
- artifact inspection rejects a ready authorization state when the final
  response still requires human confirmation for the unresolved onsite
  contradiction
- final preferred-option and approval-condition citations are merged from
  validated specialist findings using configured final-field citation
  requirements
- raw provider text remains preserved; citation augmentation affects accepted
  final structured responses used for evaluation

The explicit v1 claim registry now includes observed ScheduleExpert aliases,
observed EvidenceAuditor lower-case claim IDs mapped to canonical audit claim
IDs, and observed RiskExpert human-gate claim keys. Arbitrary audit claim IDs
remain prohibited.

## Consequences

Future fixed-chain and dynamic-council live runs should report authorization
state consistently with the human gate and should retain final recommendation
citations even when the planner does not repeat every propagated citation.
Role-scope compliance should reflect legitimate observed specialist outputs
instead of policy gaps.

The deterministic oracle, frozen v1 schemas, and prior live artifacts remain
unchanged.

## Non-Goals

- No live provider calls during this change.
- No provider-output rewriting to hide raw responses.
- No fuzzy or model-based claim-key normalization.
- No automatic clearing of the human gate without a recorded human decision.
