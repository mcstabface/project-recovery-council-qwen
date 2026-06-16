# Role Scope Policy

Evidence access is enforced by code in `src/project_recovery_council/role_scope.py`.
Prompt instructions reinforce the policy but do not replace it.

## ScheduleExpert

May receive:

- schedule records
- minimal case identity and milestone references required to interpret schedule
  records

Must not receive:

- commercial cost records
- contract exposure records
- supplier arrival correspondence
- logistics arrival status
- onsite-status progress assertions
- recovery-option commercial data
- unrelated risk records

Allowed claims include baseline and forecast dates, delivery movement, float
consumption, remaining float, projected milestone slip, and successor dependency
effects.

Prohibited claims include equipment onsite conclusions, supplier/logistics
arrival conclusions, commercial exposure, mitigation cost, preferred recovery
option, final authorization, and human decision outcomes.

## CommercialExpert

May receive cost summary, contract excerpt, required schedule impact values, and
minimal case identity. It may not resolve onsite status or supplier/logistics
arrival facts.

## EvidenceAuditor

May receive all evidence needed to compare conflicting claims and citation
support.

## RiskExpert

May receive risk register records and relevant schedule/status/contradiction
records. It must not make commercial exposure or recovery-option preference
claims.

## RecoveryPlanner

May receive validated specialist findings, approved or unresolved
contradictions, recovery options, and human decisions when available.

## DirectorAgent

May receive compact evidence metadata sufficient for routing.

## ArbiterAgent

May receive specialist findings, citations, identified disagreements, and only
the source evidence needed to resolve those disagreements.

## GeneralistAgent

May receive the full evidence bundle because that is the defined baseline
experiment design.

## Validation

Role validation records:

- allowed claims
- prohibited claims
- allowed warnings
- prohibited warnings
- citation-policy violations
- evidence-scope violations
- concise findings

JSON schema validity does not imply role-scope validity.
