# Case Model

## Contract Types

The foundation defines typed models for:

- `RecoveryCase`
- `CaseStatus`
- `CaseStage`
- `EvidenceRecord`
- `EvidenceReference`
- `Contradiction`
- `ExpertRequest`
- `ExpertFinding`
- `ExpertStatus`
- `ConfidenceAssessment`
- `HumanDecisionRequest`
- `HumanDecision`
- `RecoveryOption`
- `FinalRecommendation`
- `AuditEvent`

## Evidence References

Evidence references use:

- `record_id`
- `source_file`
- `locator`
- optional concise excerpt

This allows findings and recommendations to point to exact source records while
remaining independent of a document store or search system.

## Expert Findings

`ExpertFinding` supports:

- completed findings with confidence
- incomplete findings
- abstentions
- failures
- retry count
- assumptions
- warnings
- evidence references

This is enough for a Director to preserve specialist failure state without
inventing hidden side channels.

## Human Gate

Contradictory evidence can create a blocking `HumanDecisionRequest`. In the
demonstration case, onsite status remains unresolved because a progress report
claims the equipment is onsite while supplier and logistics records show it has
not arrived.

The `FinalRecommendation` contract rejects an authorized recommendation when
`human_decision_required` is true.

## Audit History

`AuditEvent` stores concise, append-only history:

- actor
- action
- timestamp
- summary
- evidence references
- metadata

Audit events are not private reasoning logs.

