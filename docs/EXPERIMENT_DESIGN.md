# Experiment Design

## Variants

`deterministic_oracle` reads deterministic expected results and canonical
evidence. It is the expected-result source and is not counted as an AI
competitor.

`single_generalist` runs one model invocation using `GeneralistAgent.v1`. The
agent receives the complete evidence package and returns the final structured
analysis directly.

`fixed_expert_chain` runs `ScheduleExpert`, `CommercialExpert`,
`EvidenceAuditor`, `RiskExpert`, `RecoveryPlanner`, and `ArbiterAgent` in a
fixed order. No dynamic routing is allowed.

`dynamic_expert_council` runs `DirectorAgent` first. The Director selects only
relevant experts. Independent specialist findings are checked by the Evidence
Auditor, reconciled by the Arbiter, and turned into a recommendation by the
Recovery Planner.

## Output Artifacts

Experiment outputs use:

```text
experiment-artifacts/<experiment-id>/
├── experiment-config.json
├── invocation-records.json
├── variant-results.json
├── evaluation-results.json
├── comparison-report.json
└── artifact-manifest.json
```

The manifest records SHA-256 checksums and schema identifiers for each artifact.

## Offline Execution

`prc-qwen evaluate-offline` replays one simulated fixture and writes experiment
artifacts. `prc-qwen compare-offline` compares simulated fixtures for local
contract checks. Neither command requires credentials or network access.
