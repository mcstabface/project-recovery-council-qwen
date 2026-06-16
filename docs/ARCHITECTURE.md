# Architecture

## System Boundary

Project Recovery Council is currently a local Python package plus deterministic
fixtures. The boundary is intentionally narrow:

- local filesystem evidence fixtures
- Pydantic contracts
- standard-library validation utilities
- abstract expert interfaces
- deterministic stubs for contract tests
- local orchestration layer and CLI

No runtime code connects to external systems.

## Conceptual Flow

1. A `RecoveryCase` enters the system with cited evidence records.
2. The workflow runner validates the fixture bundle and records audit events.
3. The `Director` selects required experts from case facts and records concise
   routing rationale.
4. The runner creates scoped `ExpertRequest` packets and executes the selected
   specialists.
5. Experts return `ExpertFinding` objects with concise conclusions, evidence,
   confidence, assumptions, warnings, and retry or failure state.
6. The `EvidenceAuditor` detects contradictory evidence.
7. Unresolved contradictions create a `HumanDecisionRequest` and pause the
   workflow in `awaiting_human_decision`.
8. A deterministic simulated human decision can resume the workflow.
9. The `RecoveryPlanner` builds draft and final recommendations within the
   boundaries.
10. Audit history and run artifacts are written for replay.

## Orchestration Layer

The orchestration layer is explicit and separate from expert stubs:

- `state.py` defines workflow states, selections, context, and transition
  validation.
- `audit.py` emits ordered immutable audit events with deterministic timestamps.
- `director.py` contains rule-based local expert selection and retry approval.
- `workflow.py` runs validation, triage, expert execution, contradiction review,
  human decision pause/resume, recovery planning, final approval, and completion.
- `serialization.py` writes JSON artifacts and compares replay equivalence.
- `runner.py` and `__main__.py` expose local run, validate, and replay commands.

Workflow stages are:

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

Invalid transitions raise `WorkflowTransitionError`.

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

For the current case, `RuleBasedDirector` selects:

- `ScheduleExpert`: delivery forecast moved later than baseline.
- `CommercialExpert`: delay exposure and mitigation economics exist.
- `EvidenceAuditor`: progress and logistics evidence conflict.
- `RiskExpert`: risk register flags the unresolved status conflict.
- `RecoveryPlanner`: accelerated logistics option is available subject to
  approval.

## Governance Invariants

- Findings must cite source-level evidence.
- Contradictory source records must not be collapsed into unsupported claims.
- Human confirmation gates block final authorization when evidence conflicts.
- Expert failures and retries are represented in the same public finding model
  as successful findings.
- Schemas store conclusions, assumptions, warnings, citations, and rationales.
  They do not store unrestricted reasoning traces.
- Expected results are deterministic and machine-readable.
- Replay comparison ignores timestamps and run-specific identifiers while
  comparing logical findings, audit event ordering, decisions, contradictions,
  and final recommendation content.

## Future Integration Points

UiPath Maestro can later orchestrate the same interfaces as case-governance and
work-routing infrastructure. LLM providers can later implement specialist expert
logic behind the ABCs. Both integrations should preserve fixture replay and
contract validation.
