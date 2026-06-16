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

## Live Execution

Live execution is limited to one explicit command at a time:

- `live-smoke`: one small request validating authentication, reachability, model
  availability, structured response parsing, local schema validation, token
  accounting when returned, artifact redaction, and artifact inspection.
- `live-agent`: one named agent against the synthetic case.
- `live-variant`: one named experiment variant. The current implementation
  supports `single_generalist`; it does not run the full matrix implicitly.

Every live command requires `--allow-network`, a `--model <model-id>`, and a
configured API key environment variable. Live artifacts are isolated under
`experiment-artifacts/live/<experiment-id>/`.

Standalone live agents use `invocation_purpose=standalone_live_agent` in
request metadata, invocation records, and experiment config. This is distinct
from experiment variants such as `single_generalist`,
`fixed_expert_chain`, and `dynamic_expert_council`.

Specialist prompts are rendered from role-filtered evidence selected by policy
code. After schema validation, specialist claim keys are normalized with an
explicit versioned alias map. Role-scope validation then runs on normalized
claims and records whether claims, warnings, citations, and selected evidence
stayed within the declared role boundary.

Future specialist live artifacts include:

- `claim-normalization-results.json`
- `normalized-structured-responses.json`
- `claim-normalization-metrics.json`

Raw parsed provider output remains in `parsed-structured-responses.json`.

Standalone live `ScheduleExpert` invocations also run deterministic
schedule-semantic validation. Future artifacts for those invocations include
`schedule-semantic-validation.json` and `schedule-semantic-metrics.json`
alongside selected evidence and role validation results. The validation artifact
records expected and observed schedule values without modifying the provider
response.

Validation layers are intentionally distinct:

- JSON schema validation checks response shape.
- Claim-key normalization maps supported aliases to canonical claim keys and
  reports unknown keys or alias conflicts.
- Role-scope validation checks whether a specialist stayed inside its
  authorized evidence and claim boundary.
- Schedule-semantic validation checks whether `ScheduleExpert` arithmetic is
  consistent with `SCH-DELIVERY-001`, including qualitative
  `float_consumption_status` consistency when that claim is present.
