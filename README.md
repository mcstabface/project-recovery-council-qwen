# Project Recovery Council - Qwen Agent Society Edition

Project Recovery Council is a governed case-management foundation for
investigating project-delivery exceptions. This repository is the Qwen Agent
Society competition adaptation of the deterministic reference implementation.
The deterministic implementation remains the ground-truth oracle and regression
baseline.

This edition establishes:

- strict case and expert contracts
- source-cited synthetic evidence fixtures
- deterministic validation utilities
- narrow expert interfaces and deterministic stubs
- deterministic local workflow runner and CLI
- persistent pause/resume artifacts
- versioned JSON Schemas under `schemas/v1/`
- schema drift checking
- canonical deterministic demo evidence
- expected results for the demonstration case
- provider-neutral model-client contracts
- disabled-by-default offline and live Qwen adapters
- offline simulated response fixtures
- prompt contracts for generalist, director, specialists, arbiter, and planner
- typed experiment variants and deterministic evaluation metrics
- role-scoped evidence filtering, deterministic claim normalization, and
  specialist semantic validation
- tests and process artifacts

## Boundaries

- Synthetic data only.
- No external system connections.
- No UiPath runtime implementation.
- No live Qwen calls unless explicitly requested with `--allow-network`.
- No provider credentials required.
- No network calls in tests.
- Offline fixtures are simulated outputs, not empirical model results.
- No web framework.
- Python 3.12 or later.
- MIT licensed.

## Demonstration Case

The synthetic case is in `sample-data/equipment-delay-case/`.

Core facts:

- equipment delivery moved 21 calendar days later than baseline
- installation had 8 days total float
- milestone slip without intervention is 13 days
- contractual exposure is 15000 USD per calendar day
- unmitigated exposure is 195000 USD
- accelerated logistics costs 48000 USD
- gross avoided exposure before secondary effects is 147000 USD
- progress reporting says the equipment is onsite
- supplier and logistics records say it has not arrived
- human confirmation is required before final recovery authorization

## Repository Layout

```text
docs/                         Architecture and case documentation
decisions/                    Architecture decision records
experiment-fixtures/          Simulated offline model responses for tests
experiment-artifacts/         Local generated experiment outputs
prompts/v1/                   Versioned competition prompt contracts
sample-data/equipment-delay-case/
                               Synthetic evidence pack and expected results
src/project_recovery_council/ Contracts, interfaces, stubs, workflow, validators
schemas/v1/                   Versioned JSON Schemas and schema catalog
tests/                        Deterministic test suite
session-artifacts/            Build checkpoint and run manifest
```

## Install Locally

```bash
python -m pip install -e ".[dev]"
```

After installation, the console command is available:

```bash
prc-qwen validate
prc-qwen evaluate-offline
prc-qwen compare-offline
prc-qwen validate-prompts
prc-qwen inspect-experiment experiment-artifacts/offline-strong_modular_council
prc-qwen live-smoke --model <model-id> --allow-network
prc-qwen live-variant --variant single_generalist --model <model-id> --allow-network
prc-qwen compare-live --generalist <path> --fixed-chain <path> --dynamic-council <path>
project-recovery-council validate
project-recovery-council demo
project-recovery-council inspect session-artifacts/canonical-demo
```

`python -m project_recovery_council ...` remains supported.

## Local Workflow CLI

From an installed environment:

```bash
python -m project_recovery_council validate
python -m project_recovery_council start
python -m project_recovery_council status session-artifacts/runs/equipment-delay-paused
python -m project_recovery_council decide session-artifacts/runs/equipment-delay-paused --request-id HDR-ONSITE-001 --decision equipment_not_onsite --actor demo-reviewer
python -m project_recovery_council resume session-artifacts/runs/equipment-delay-paused
python -m project_recovery_council approve session-artifacts/runs/equipment-delay-paused --actor demo-approver
python -m project_recovery_council inspect session-artifacts/runs/equipment-delay-paused
python -m project_recovery_council demo
python -m project_recovery_council run
python -m project_recovery_council run --inject-commercial-failure
python -m project_recovery_council replay session-artifacts/runs/equipment-delay-standard
python -m project_recovery_council export-schemas
python -m project_recovery_council check-schema-drift
python -m project_recovery_council evaluate-offline --fixture strong_modular_council
python -m project_recovery_council compare-offline
python -m project_recovery_council validate-prompts
python -m project_recovery_council inspect-experiment experiment-artifacts/offline-strong_modular_council
python -m project_recovery_council live-smoke --model <model-id> --allow-network
python -m project_recovery_council live-variant --variant single_generalist --model <model-id> --allow-network
```

From this source tree without installing first:

```bash
PYTHONPATH=src python -m project_recovery_council validate
PYTHONPATH=src python -m project_recovery_council start
PYTHONPATH=src python -m project_recovery_council status session-artifacts/runs/equipment-delay-paused
PYTHONPATH=src python -m project_recovery_council decide session-artifacts/runs/equipment-delay-paused --request-id HDR-ONSITE-001 --decision equipment_not_onsite --actor demo-reviewer
PYTHONPATH=src python -m project_recovery_council resume session-artifacts/runs/equipment-delay-paused
PYTHONPATH=src python -m project_recovery_council approve session-artifacts/runs/equipment-delay-paused --actor demo-approver
PYTHONPATH=src python -m project_recovery_council inspect session-artifacts/runs/equipment-delay-paused
PYTHONPATH=src python -m project_recovery_council demo
PYTHONPATH=src python -m project_recovery_council run
PYTHONPATH=src python -m project_recovery_council run --inject-commercial-failure
PYTHONPATH=src python -m project_recovery_council replay session-artifacts/runs/equipment-delay-standard
PYTHONPATH=src python -m project_recovery_council export-schemas
PYTHONPATH=src python -m project_recovery_council check-schema-drift
PYTHONPATH=src python -m project_recovery_council evaluate-offline --fixture strong_modular_council
PYTHONPATH=src python -m project_recovery_council compare-offline
PYTHONPATH=src python -m project_recovery_council validate-prompts
PYTHONPATH=src python -m project_recovery_council inspect-experiment experiment-artifacts/offline-strong_modular_council
PYTHONPATH=src python -m project_recovery_council live-smoke --model <model-id> --allow-network
PYTHONPATH=src python -m project_recovery_council live-variant --variant single_generalist --model <model-id> --allow-network
```

Workflow runs write inspectable artifacts under:

```text
session-artifacts/runs/<run-id>/
```

Each run includes `workflow-state.json`, `artifact-manifest.json`,
`run-summary.json`, `audit-events.json`, `expert-findings.json`,
`contradictions.json`, `human-decisions.json`, `human-decision-requests.json`,
`recovery-options.json`, `draft-recommendation.json`,
`final-recommendation.json`, and `replay-input.json`.

## Local Execution Flow

The local runner loads the synthetic case bundle, validates deterministic source
facts, lets the Director select required experts from case facts, executes
specialists through the expert adapter boundary, and pauses for human
confirmation when contradictory onsite-status evidence is found. A separate
process can record the decision, resume execution to the final approval gate,
record final approval, and complete the case.

`run` remains a convenience demo command that explicitly simulates both human
actions and completes the case in one invocation. `start`, `decide`, `resume`,
and `approve` are the persistent pause/resume lifecycle commands.

The default Director selects `ScheduleExpert`, `CommercialExpert`,
`EvidenceAuditor`, `RiskExpert`, and `RecoveryPlanner` for the equipment-delay
case. With `--inject-commercial-failure`, the commercial expert fails on the
first attempt, the Director authorizes one retry, and both attempts are preserved
in the audit trail.

## Contract Schemas And Artifact Inspection

Public JSON Schemas are exported in `schemas/v1/`. The schema catalog is
`schemas/v1/schema-catalog.json`.

Run artifact directories can be inspected with:

```bash
PYTHONPATH=src python -m project_recovery_council inspect session-artifacts/runs/<run-id>
```

Inspection checks required files, JSON parsing, Pydantic contract validation,
SHA-256 checksums, ordered audit sequences, evidence references, pending gates,
and completion claims.

Committed v1 schemas are frozen public artifacts. Use
`project-recovery-council check-schema-drift` before changing integration
contracts. Intentional schema changes must follow
`docs/SCHEMA_VERSIONING_POLICY.md`.

## Demo Evidence

The canonical completed evidence run is committed under:

```text
session-artifacts/canonical-demo/
```

Ad hoc runtime outputs under `session-artifacts/runs/` are useful for local
inspection but should not normally be committed.

The cross-platform demo script is:

```bash
python scripts/run_demo.py --replace-existing
```

Run creation fails if the target run directory already exists. Use
`--replace-existing` only for local deterministic regeneration.

## Qwen Competition Layer

The competition claim is tested through four typed variants:

- `deterministic_oracle`: the inherited deterministic expected-result source,
  not an AI competitor
- `single_generalist`: one model agent receives the full evidence package and
  returns the final recommendation directly
- `fixed_expert_chain`: all experts run in a fixed sequence, with final
  synthesis
- `dynamic_expert_council`: a Director dynamically selects experts, specialists
  work independently, an Evidence Auditor checks claims, an Arbiter preserves or
  resolves disagreement, and the Recovery Planner recommends the recovery path

Live Qwen execution is disabled by default. `DisabledQwenModelClient` returns a
typed configuration failure and records that no network call was attempted.
`OfflineModelClient` replays deterministic simulated fixtures from
`experiment-fixtures/offline-responses/v1/`.

Opt-in live Qwen execution is available only through explicit live commands.
Each live command requires `--allow-network`, a `--model <model-id>`, and
`DASHSCOPE_API_KEY` or a configured alternate key environment variable. Provider
charges may apply. Live artifacts are written under `experiment-artifacts/live/`
and are ignored by Git by default.

```bash
export DASHSCOPE_API_KEY="<your-api-key>"
PYTHONPATH=src python -m project_recovery_council live-smoke --model <model-id> --allow-network
PYTHONPATH=src python -m project_recovery_council live-agent --agent ScheduleExpert --model <model-id> --allow-network
PYTHONPATH=src python -m project_recovery_council live-variant --variant single_generalist --model <model-id> --allow-network
PYTHONPATH=src python -m project_recovery_council live-variant --variant fixed_expert_chain --model <model-id> --allow-network
PYTHONPATH=src python -m project_recovery_council live-variant --variant dynamic_expert_council --model <model-id> --allow-network
PYTHONPATH=src python -m project_recovery_council compare-live --generalist <path> --fixed-chain <path> --dynamic-council <path>
```

No live model identifier is hard-coded. Choose the model ID from the current
Alibaba Cloud Model Studio console or official documentation for the endpoint
you are using.

`live-variant` runs exactly one requested AI variant and never launches the
full comparison matrix automatically. It enforces `--allow-network`, explicit
model selection, no-overwrite artifact behavior, conservative call/token/time
limits, and a nonzero exit code when a limit stops the run before completion.
The manual comparison order is documented in
`docs/LIVE_COMPARISON_RUNBOOK.md`.

Specialist live invocations now use explicit evidence-access policy code before
prompt rendering. For example, `ScheduleExpert` receives schedule records plus
minimal case identity only; it does not receive supplier, logistics, progress,
cost, contract, unrelated risk, or recovery-option evidence. Live artifacts
record `selected-evidence-records.json` and `role-validation-results.json` for
standalone specialist invocations. A response may be JSON-schema valid while
still failing semantic role-scope validation.

Specialist claim keys are normalized deterministically after schema validation
and before role or domain semantic validation. Raw parsed provider output
remains in `parsed-structured-responses.json`; normalized output and trace
artifacts are written separately as `normalized-structured-responses.json`,
`claim-normalization-results.json`, and `claim-normalization-metrics.json`.
Supported aliases are explicit and documented in `docs/CLAIM_NORMALIZATION.md`;
conflicts are reported instead of silently resolved.

`ScheduleExpert` outputs also receive deterministic schedule-semantic
validation. For the synthetic case, 21 days of delivery movement consumes the
available 8 days of installation total float, leaves 0 days remaining float, and
produces a 13-day net milestone slip with `float_consumption_status` of
`fully_consumed`. Future live ScheduleExpert artifacts include
`schedule-semantic-validation.json` and `schedule-semantic-metrics.json`; prior
live artifacts are not retroactively modified.

Fixed-chain and dynamic-council synthesis now use a compact validated-findings
handoff. Canonical specialist claims, claim-attached citations, validation
status, warnings, unresolved contradictions, and human gates are passed to
RecoveryPlanner through `synthesis-input.json`; verbose raw provider responses
remain preserved for diagnostics but are not used as the planner handoff.
RecoveryPlanner is instructed to distinguish recommendation from
authorization: accelerated logistics can be recommended while final
authorization remains blocked pending human confirmation. Artifact inspection
now rejects a ready-for-authorization state when the final response still
requires human confirmation for an unresolved onsite-status contradiction.
Final preferred-option and approval-condition citations are deterministically
merged from validated specialist citations when the planner omits them.

Controlled live variant artifacts are written under
`experiment-artifacts/live/<experiment-id>/` and include execution plans,
selected evidence record IDs, prompt hashes, invocation records, parsed and raw
redacted responses, validation results, token usage, retry history, routing
decisions for dynamic council runs, final variant results, evaluation results,
reproducibility metadata, and a checksum manifest. Completed live runs can be
compared offline with `compare-live`; the comparison writes machine-readable
JSON and concise Markdown and refuses incomplete or invalid runs unless a
diagnostic override is supplied.

Live evaluation reports use live-provider limitation text, not offline fixture
warnings. Role-scope compliance and specialized semantic validation are marked
`not_applicable` for full-scope `GeneralistAgent` outputs; they are scored only
for specialist invocations where those validation layers actually ran.

Offline experiment outputs use:

```text
experiment-artifacts/<experiment-id>/
├── experiment-config.json
├── invocation-records.json
├── variant-results.json
├── evaluation-results.json
├── comparison-report.json
└── artifact-manifest.json
```

These outputs are manifest-backed with SHA-256 checksums and can be inspected
with `prc-qwen inspect-experiment <path>`.

## Run Tests

```bash
python -m pytest
```

The test configuration adds `src/` to the Python path.

## Integration Direction

Future work can attach live Qwen-backed experts or UiPath Maestro orchestration
behind the existing interfaces. Those integrations must preserve the local
contracts, source-level evidence citations, audit history, human gates,
deterministic expected-result fixtures, and offline regression tests.
