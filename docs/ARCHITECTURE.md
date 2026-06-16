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
- versioned schema export
- persisted run-state and artifact contract validation

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
8. A separate invocation records a human decision and another invocation resumes
   the workflow to final approval.
9. A final approval invocation completes the case.
10. Audit history and run artifacts are written for replay and inspection.

## Orchestration Layer

The orchestration layer is explicit and separate from expert stubs:

- `state.py` defines workflow states, selections, persisted workflow state, and
  transition validation.
- `audit.py` emits ordered immutable audit events with deterministic timestamps.
- `director.py` contains rule-based local expert selection and retry approval.
- `adapters.py` defines the platform-neutral expert execution adapter boundary.
- `workflow.py` runs validation, triage, expert execution, contradiction review,
  human decision pause/resume, recovery planning, final approval, and completion.
- `serialization.py` writes JSON artifacts and compares replay equivalence.
- `persistence.py` converts between in-memory workflow context and versioned
  persisted state.
- `artifacts.py` defines the run artifact manifest and validates run directories.
- `schemas.py` exports public JSON Schemas and the schema catalog.
- `runner.py` and `__main__.py` expose local validate, start, status, decide,
  resume, approve, inspect, run, replay, and schema export commands.

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

## Persistent Pause And Resume

`workflow-state.json` is the authoritative resumable state artifact. It contains
schema version, run ID, case ID, current stage, completed stages, selected
experts, expert requests and attempts, findings, contradictions, pending and
answered human requests, received decisions, recovery options, draft and final
recommendations, approval state, audit sequence position, audit events, and
failure information when present.

The workflow does not automatically provide human decisions in the core
lifecycle. The `run` command is a demo helper that explicitly opts into simulated
human decision and final approval.

## Expert Adapter Boundary

`ExpertAdapter` decouples orchestration from concrete expert execution. Adapter
results carry expert name, request ID, attempt number, status, structured result,
typed failure or timeout representation, correlation ID, and metadata for future
external orchestration.

Available adapters:

- `DeterministicExpertAdapter`: wraps local deterministic stubs.
- `ExternalExpertAdapter`: safely disabled placeholder that returns a typed
  failure and performs no network or SDK call.

The workflow calls the adapter boundary for ScheduleExpert, CommercialExpert,
RiskExpert, EvidenceAuditor, and RecoveryPlanner.

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
- Artifact inspection fails incomplete runs that claim completion and completed
  runs that lack final approval or final recommendation.

## Future Integration Points

UiPath Maestro can later orchestrate the same interfaces as case-governance and
work-routing infrastructure. LLM providers can later implement specialist expert
logic behind the ABCs. Both integrations should preserve fixture replay and
contract validation.
