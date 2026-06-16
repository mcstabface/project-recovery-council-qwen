# Architecture

## System Boundary

Project Recovery Council is currently a local Python package plus deterministic
fixtures. The boundary is intentionally narrow:

- local filesystem evidence fixtures
- Pydantic contracts
- standard-library validation utilities
- abstract expert interfaces
- deterministic stubs for contract tests

No runtime code connects to external systems.

## Conceptual Flow

1. A `RecoveryCase` enters the system with cited evidence records.
2. The `Director` routes scoped `ExpertRequest` packets to specialist experts.
3. Experts return `ExpertFinding` objects with concise conclusions, evidence,
   confidence, assumptions, warnings, and retry or failure state.
4. The `EvidenceAuditor` detects contradictory evidence.
5. Unresolved contradictions create a `HumanDecisionRequest`.
6. The `RecoveryPlanner` builds a `FinalRecommendation` only within the contract
   boundaries.
7. Audit history is preserved as `AuditEvent` entries.

## Expert Interfaces

The initial specialist boundaries are:

- `Director`
- `ScheduleExpert`
- `CommercialExpert`
- `RiskExpert`
- `EvidenceAuditor`
- `RecoveryPlanner`

The interfaces are intentionally narrow so future implementations can be
deterministic, LLM-backed, or platform-orchestrated without changing the public
case contracts.

## Governance Invariants

- Findings must cite source-level evidence.
- Contradictory source records must not be collapsed into unsupported claims.
- Human confirmation gates block final authorization when evidence conflicts.
- Expert failures and retries are represented in the same public finding model
  as successful findings.
- Schemas store conclusions, assumptions, warnings, citations, and rationales.
  They do not store unrestricted reasoning traces.
- Expected results are deterministic and machine-readable.

## Future Integration Points

UiPath Maestro can later orchestrate the same interfaces as case-governance and
work-routing infrastructure. LLM providers can later implement specialist expert
logic behind the ABCs. Both integrations should preserve fixture replay and
contract validation.

