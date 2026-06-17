# Live Comparison Runbook

This runbook executes the three AI competition variants one at a time. It does
not run the deterministic oracle as an AI competitor, and it does not launch the
full matrix automatically.

## Preconditions

- Install the project or run commands with `PYTHONPATH=src`.
- Choose one explicit Qwen model ID for all three runs.
- Configure the API key through an environment variable, normally:

```bash
export DASHSCOPE_API_KEY="<your-api-key>"
```

Provider charges may apply. Do not paste real secrets into source files,
documentation, tests, or committed artifacts.

## 1. Single Generalist

```bash
PYTHONPATH=src python -m project_recovery_council live-variant \
  --variant single_generalist \
  --model qwen-plus \
  --allow-network
```

Save the printed artifact path as `<generalist-path>`.

## 2. Inspect And Validate

```bash
PYTHONPATH=src python -m project_recovery_council inspect-experiment <generalist-path>
```

Continue only if inspection passes and `final-variant-result.json` has
`completed: true`.

## 3. Fixed Expert Chain

```bash
PYTHONPATH=src python -m project_recovery_council live-variant \
  --variant fixed_expert_chain \
  --model qwen-plus \
  --allow-network
```

Save the printed artifact path as `<fixed-chain-path>`.

## 4. Inspect And Validate

```bash
PYTHONPATH=src python -m project_recovery_council inspect-experiment <fixed-chain-path>
```

Review `selected-evidence-records.json`, `role-validation-results.json`,
`domain-semantic-validation-results.json`, and
`schedule-semantic-validation.json` before continuing. Also inspect
`validated-findings-envelope.json`, `excluded-findings.json`,
`synthesis-input.json`, and `recommendation-authorization-state.json` to confirm
validated claims and citations reached the planner and that recommendation is
separate from authorization. When human confirmation is required and the onsite
contradiction is unresolved, `recommendation-authorization-state.json` must show
`authorization_status: blocked_pending_human_confirmation`,
`blocking_human_request: HDR-ONSITE-001`, and
`unresolved_contradictions: ["equipment_onsite_status"]`.

## 5. Dynamic Expert Council

```bash
PYTHONPATH=src python -m project_recovery_council live-variant \
  --variant dynamic_expert_council \
  --model qwen-plus \
  --allow-network
```

Save the printed artifact path as `<dynamic-council-path>`.

## 6. Inspect And Validate

```bash
PYTHONPATH=src python -m project_recovery_council inspect-experiment <dynamic-council-path>
```

Review `routing-decisions.json` to confirm the Director selected relevant
specialists rather than defaulting to every role. Then review the synthesis
handoff artifacts to confirm excluded findings did not enter normal synthesis.
Check that final preferred-option and approval-condition citations were
preserved or deterministically merged from validated findings before comparing
runs.

Also review `arbitration-decisions.json`. ArbiterAgent should be skipped when
there is no substantive disagreement among eligible validated findings, when all
findings were excluded by deterministic validation, or when the only unresolved
issue is the human onsite-status evidence gate. Skipped arbitration should show
`arbiter_required: false` and should not add a provider invocation.

## 7. Offline Comparison

```bash
PYTHONPATH=src python -m project_recovery_council compare-live \
  --generalist <generalist-path> \
  --fixed-chain <fixed-chain-path> \
  --dynamic-council <dynamic-council-path>
```

The comparison command makes no network calls. It refuses incomplete or
artifact-invalid runs unless `--allow-incomplete` is supplied for diagnostics.

In the comparison report, role-scope compliance and specialized semantic
validation are `N/A` for the single GeneralistAgent run. They are applicable
only to specialist invocations where the corresponding validators ran.

## Optional Run Controls

Use these controls for smaller, bounded live experiments:

```bash
PYTHONPATH=src python -m project_recovery_council live-variant \
  --variant single_generalist \
  --model qwen-plus \
  --allow-network \
  --max-invocation-count 1 \
  --max-total-input-tokens 20000 \
  --max-total-output-tokens 8000 \
  --max-elapsed-seconds 120 \
  --max-retries-per-invocation 1
```

If a limit is exceeded, the runner preserves completed artifacts, marks the run
incomplete, records the limit in `final-variant-result.json`, and exits
nonzero.

## Diagnostic Derived Rebuild

When a live run completed provider execution but failed derived artifact
validation, preserve that run unchanged and rebuild only the deterministic
derived artifacts into a new directory:

```bash
PYTHONPATH=src python -m project_recovery_council rebuild-derived-artifacts \
  experiment-artifacts/live/<run-id> \
  --output experiment-artifacts/live-diagnostics/<run-id>-derived
```

This command makes zero provider calls. The derived output is labeled
diagnostic and non-empirical, records source artifact hashes, and is rejected by
normal `compare-live` unless diagnostic overrides are used.

## Before Commit

Live artifacts are local generated outputs. Before committing:

```bash
git status --short
git diff --cached --name-only | grep '^experiment-artifacts/live/' || true
git diff --cached --name-only | grep '^experiment-artifacts/live-comparisons/' || true
```

No live artifacts should be staged unless intentionally adding a sanitized
example.
