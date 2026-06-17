# Experiment Design

## Variants

`deterministic_oracle` reads deterministic expected results and canonical
evidence. It is the expected-result source and is not counted as an AI
competitor.

`single_generalist` runs one model invocation using `GeneralistAgent.v1`. The
agent receives the complete evidence package and returns the final structured
analysis directly.

`fixed_expert_chain` runs `ScheduleExpert`, `CommercialExpert`,
`EvidenceAuditor`, `RiskExpert`, and `RecoveryPlanner` in a fixed order. No
dynamic routing is allowed. The final RecoveryPlanner synthesis receives
validated specialist findings and validation records rather than the complete
raw evidence bundle.

`dynamic_expert_council` runs `DirectorAgent` first. The Director receives
compact routing evidence, selects only relevant executable specialists, and
records selected roles, skipped roles, routing rationale, and routing evidence
record IDs. Independent specialist findings are checked by the Evidence
Auditor, validation issues or disagreements are passed to the Arbiter, and the
Recovery Planner produces the final recommendation.

The Director cannot silently select every expert by default. Unknown or
unsupported selected roles fail the run clearly rather than being guessed.

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
- `live-variant`: one named AI experiment variant. Supported variants are
  `single_generalist`, `fixed_expert_chain`, and `dynamic_expert_council`. The
  command never runs the full matrix implicitly.
- `compare-live`: a no-network comparison command that consumes three completed
  live variant directories and writes a combined JSON and Markdown report.

Every live execution command requires `--allow-network`, a `--model <model-id>`,
and a configured API key environment variable. Live artifacts are isolated
under `experiment-artifacts/live/<experiment-id>/`. The comparison command reads
existing artifacts only and makes no network calls.

## Live Variant Safeguards

`live-variant` enforces conservative defaults:

- maximum invocation count: 8
- maximum total input tokens: 100000, when provider usage is available
- maximum total output tokens: 50000, when provider usage is available
- maximum elapsed seconds: 300
- maximum retries per invocation: 2
- optional `--stop-after-invocation N`
- no overwrite without `--replace-existing`

When a limit is exceeded, the runner stops further invocations, preserves
completed artifacts, marks the experiment incomplete, records the stopping
limit, and returns a nonzero exit code through the CLI.

Standalone live agents use `invocation_purpose=standalone_live_agent` in
request metadata, invocation records, and experiment config. This is distinct
from experiment variants such as `single_generalist`,
`fixed_expert_chain`, and `dynamic_expert_council`.

Specialist prompts are rendered from role-filtered evidence selected by policy
code. After schema validation, specialist claim keys are normalized with an
explicit versioned alias map. Role-scope validation then runs on normalized
claims and records whether claims, warnings, citations, and selected evidence
stayed within the declared role boundary.

Live variant artifacts include:

- `experiment-config.json`
- `execution-plan.json`
- `rendered-prompt-hashes.json`
- `invocation-records.json`
- `selected-evidence-records.json`
- `parsed-structured-responses.json`
- `raw-provider-responses.json`
- `validation-results.json`
- `token-usage.json`
- `retry-history.json`
- `routing-decisions.json` for dynamic council runs
- `disagreement-records.json`
- `final-variant-result.json`
- `evaluation-results.json`
- `reproducibility.json`
- `artifact-manifest.json`

Specialist live artifacts additionally include:

- `claim-normalization-results.json`
- `normalized-structured-responses.json`
- `role-validation-results.json`
- `domain-semantic-validation-results.json`
- `claim-normalization-metrics.json`

Raw parsed provider output remains in `parsed-structured-responses.json`.

Live `ScheduleExpert` invocations also run deterministic schedule-semantic
validation. Future artifacts for those invocations include
`schedule-semantic-validation.json` and `schedule-semantic-metrics.json`
alongside selected evidence and role validation results. The validation artifact
records expected and observed schedule values without modifying the provider
response.

`compare-live` requires completed and artifact-valid single-generalist,
fixed-chain, and dynamic-council directories unless `--allow-incomplete` is
supplied for diagnostics. The report deliberately does not claim statistical
significance from one run per variant.

Live evaluation reports use live-provider limitations: one run is not
statistically significant, hosted-model outputs may vary, and provider cost is
unavailable unless explicit pricing is supplied. Offline fixture reports retain
the simulated-output limitation because those fixtures are not empirical Qwen
results.

`single_generalist` receives the full evidence bundle, so role-scope compliance
and specialized semantic validation are not applicable to that output. Live
comparison JSON records `applicable: false`, `status: not_applicable`, and
`score: null`; Markdown renders the values as `N/A`. Specialist variants retain
their actual compliance scores.

Validation layers are intentionally distinct:

- JSON schema validation checks response shape.
- Claim-key normalization maps supported aliases to canonical claim keys and
  reports unknown keys or alias conflicts.
- Role-scope validation checks whether a specialist stayed inside its
  authorized evidence and claim boundary.
- Schedule-semantic validation checks whether `ScheduleExpert` arithmetic is
  consistent with `SCH-DELIVERY-001`, including qualitative
  `float_consumption_status` consistency when that claim is present.
