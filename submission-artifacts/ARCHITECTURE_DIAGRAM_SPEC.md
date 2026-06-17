# Architecture Diagram Specification

## Purpose

Show how the dynamic Qwen expert council turns source evidence into a governed
project recovery recommendation without treating the model as the only control
point.

## Diagram Elements

- Case evidence bundle
- DirectorAgent
- selected experts:
  - ScheduleExpert
  - CommercialExpert
  - RiskExpert
- EvidenceAuditor
- optional ArbiterAgent
- validated-findings envelope
- RecoveryPlanner
- human approval gate
- final recommendation
- audit artifacts and evaluation report

## Visual Notes

- Use one horizontal flow from evidence to recommendation.
- Show role-scoped evidence going into each specialist.
- Show EvidenceAuditor checking specialist claims and citations.
- Show ArbiterAgent as conditional, not always invoked.
- Show the human approval gate after recommendation, not before
  recommendation.
- Show audit artifacts as a side output from every stage.

## Mermaid Source

```mermaid
flowchart LR
    Evidence[Case evidence bundle<br/>Synthetic equipment-delay records] --> Director[DirectorAgent<br/>routing decision]
    Director --> Schedule[ScheduleExpert<br/>schedule arithmetic]
    Director --> Commercial[CommercialExpert<br/>exposure arithmetic]
    Director --> Risk[RiskExpert<br/>human gate and risk]

    Evidence -->|role-scoped records| Schedule
    Evidence -->|role-scoped records| Commercial
    Evidence -->|role-scoped records| Risk

    Schedule --> Auditor[EvidenceAuditor<br/>claim and citation audit]
    Commercial --> Auditor
    Risk --> Auditor
    Evidence -->|cited source records only| Auditor

    Auditor --> Envelope[Validated-findings envelope<br/>eligible and excluded findings]
    Envelope --> Disagreement{Substantive disagreement?}
    Disagreement -->|yes| Arbiter[ArbiterAgent<br/>preserve or resolve disagreement]
    Disagreement -->|no| Planner[RecoveryPlanner]
    Arbiter --> Planner

    Planner --> Recommendation[Final recommendation<br/>REC-ACCEL-LOGISTICS]
    Recommendation --> Gate[Human approval gate<br/>HDR-ONSITE-001]
    Gate --> Auth[Authorization state<br/>blocked pending confirmation]

    Director -.-> Artifacts[Audit artifacts<br/>invocations, prompts, validation, metrics]
    Schedule -.-> Artifacts
    Commercial -.-> Artifacts
    Risk -.-> Artifacts
    Auditor -.-> Artifacts
    Envelope -.-> Artifacts
    Planner -.-> Artifacts
```

## Caption

Dynamic routing reduces unnecessary specialist calls, but the important control
is the governed handoff: scoped evidence, structured responses, deterministic
validation, audited citations, and a human authorization gate.
