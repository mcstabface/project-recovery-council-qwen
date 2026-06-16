# UiPath Maestro Mapping

## Purpose

This document maps the local Project Recovery Council reference workflow to
anticipated UiPath Maestro concepts. It is a planning artifact only. No UiPath
SDK code or tested Maestro implementation exists in this repository.

## Concept Mapping

| Local Reference | Anticipated UiPath Concept | Notes |
|---|---|---|
| `RecoveryCase` | Maestro case | Case fields and evidence references should map to case data once exact Maestro case schema behavior is confirmed. |
| `WorkflowStage` | Case stage | Local stages should become governed case stages or workflow milestones. |
| Director routing | Agent/workflow routing | `RuleBasedDirector` is the local reference for deciding which specialist work is required. |
| `ExpertRequest` | Agent task input | Request payloads are narrow, cited, and versioned for handoff to an expert implementation. |
| `ExpertFinding` | Agent task output | Findings include status, confidence, evidence, assumptions, warnings, failure, and retry state. |
| `AuditEvent` | Case history or execution evidence | Audit events are concise and ordered; exact Maestro history/evidence APIs require confirmation. |
| `HumanDecisionRequest` | Action Center or human task | The onsite-status contradiction is the reference blocking human task. |
| `HumanDecision` | Human task result | Decisions should be recorded with actor, outcome, rationale, timestamp, and evidence. |
| `workflow-state.json` | Maestro-managed case state | Local persisted state defines the minimum state needed for deterministic resume. |
| Expert retry behavior | Workflow retry and exception handling | CommercialExpert failure injection is the local retry reference. |
| Final approval | Human approval task | Local `approve` command models the final authorization gate. |
| `artifact-manifest.json` | Submission and verification evidence | Manifest and checksums provide portable verification evidence. |
| `schemas/v1/` | Platform payload contracts | Frozen local schemas define the candidate integration payloads; exact Maestro schema constraints still require testing. |
| `session-artifacts/canonical-demo/` | Reference evidence package | Canonical local run can be used as sample evidence when testing case creation and review workflows. |

## Assumptions Requiring Confirmation

- Exact Maestro case-state data model and versioning behavior.
- Whether Action Center task payloads can preserve the same evidence references
  without transformation.
- How Maestro exposes ordered execution history and whether external audit event
  IDs should be generated locally or by the platform.
- How retry policy metadata is represented and surfaced to operators.
- Whether artifact manifests should be attached to a case, stored externally, or
  represented as case evidence.
- How human approval actors and timestamps are normalized by Maestro.
- Whether Maestro payload size limits or field naming rules require adapter-side
  transformations of the v1 schemas.
- Whether schema drift checks should run in the UiPath delivery pipeline or only
  in the source repository CI.

The local workflow should remain the deterministic reference until these
assumptions are tested with UiPath Labs access.
