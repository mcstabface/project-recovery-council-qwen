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
- persisted workflow state
- run summary
- replay input
- run artifact manifest

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

- sequence number
- event type
- actor
- action
- timestamp
- summary
- evidence references
- metadata

Audit events are not private reasoning logs.

## Workflow State

Workflow state is represented outside the case contract in the local execution
context and in the persisted `workflow-state.json` artifact. Allowed stages are:

- `initialized`
- `validating`
- `triaging`
- `expert_analysis`
- `contradiction_review`
- `awaiting_human_decision`
- `recovery_planning`
- `awaiting_final_approval`
- `completed`
- `failed`

Transitions are validated before state changes. This keeps case lifecycle
semantics explicit without embedding orchestration-specific mutable state inside
expert findings.

`workflow-state.json` is versioned as
`project-recovery-council.persisted-workflow-state.v1`. Incompatible versions
fail clearly and are not silently migrated.

## Recommendation Approval

`FinalRecommendation` now carries optional confidence and an `approval_status`.
The local workflow creates a draft recommendation after human confirmation and
then records deterministic final approval before creating the authorized final
recommendation.

## Run Artifact Manifest

Each run writes `artifact-manifest.json` using
`project-recovery-council.run-artifacts.v1`. Manifest entries include relative
path, media type, schema identifier, SHA-256 checksum, generation timestamp, and
required/optional status.
