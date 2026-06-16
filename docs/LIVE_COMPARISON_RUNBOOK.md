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
`schedule-semantic-validation.json` before continuing.

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
specialists rather than defaulting to every role.

## 7. Offline Comparison

```bash
PYTHONPATH=src python -m project_recovery_council compare-live \
  --generalist <generalist-path> \
  --fixed-chain <fixed-chain-path> \
  --dynamic-council <dynamic-council-path>
```

The comparison command makes no network calls. It refuses incomplete or
artifact-invalid runs unless `--allow-incomplete` is supplied for diagnostics.

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

## Before Commit

Live artifacts are local generated outputs. Before committing:

```bash
git status --short
git diff --cached --name-only | grep '^experiment-artifacts/live/' || true
git diff --cached --name-only | grep '^experiment-artifacts/live-comparisons/' || true
```

No live artifacts should be staged unless intentionally adding a sanitized
example.
