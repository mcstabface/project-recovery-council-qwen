# Build Checkpoint: Qwen Competition Adaptation

**Date:** 2026-06-16  
**Repository:** `project-recovery-council-qwen`  
**Status:** Complete for offline competition architecture pass

## Created Or Updated

- Preserved the deterministic Project Recovery Council implementation as the
  oracle and regression baseline.
- Renamed the distribution to `project-recovery-council-qwen`, retained the
  `project_recovery_council` import package, and added the `prc-qwen` console
  command while keeping `project-recovery-council`.
- Added provider-neutral model-client contracts with `OfflineModelClient` and
  `DisabledQwenModelClient`.
- Added typed competition contracts for variants, invocations, evaluation
  cases, claim/citation/contradiction assessments, efficiency metrics,
  comparisons, and experiment artifacts.
- Added versioned prompt contracts under `prompts/v1/`.
- Added simulated offline response fixtures under
  `experiment-fixtures/offline-responses/v1/`.
- Added deterministic offline evaluation and comparison helpers.
- Added manifest-backed experiment artifact writing and inspection.
- Added CLI commands: `evaluate-offline`, `compare-offline`,
  `validate-prompts`, and `inspect-experiment`.
- Added competition documentation and ADR-0005.
- Added tests for model clients, prompt catalog, experiment plans, evaluator,
  artifact validation, offline comparison, and new CLI commands.

## Verification Commands

```bash
python -m pytest
```

Initial result: `57 passed, 1 failed`. The failure was
`tests/test_contract_hardening.py::test_installed_console_entry_point`; Hatch
could not infer package files after the distribution rename because the import
package intentionally remains `project_recovery_council`.

Fix applied: explicit Hatch wheel package mapping:

```toml
[tool.hatch.build.targets.wheel]
packages = ["src/project_recovery_council"]
```

```bash
python -m pytest
```

Post-fix result: `58 passed in 6.20s`

```bash
PYTHONPATH=src python -m project_recovery_council validate-prompts
```

Result: `prompt validation passed`

```bash
PYTHONPATH=src python -m project_recovery_council compare-offline
```

Result:

```text
offline comparison: offline-comparison-v1
dynamic_expert_council:strong_modular_council required_fact_accuracy=1.0 schema=valid unsupported_claims=0
single_generalist:generalist_missed_onsite_contradiction required_fact_accuracy=0.2 schema=valid unsupported_claims=1
fixed_expert_chain:fixed_chain_result required_fact_accuracy=1.0 schema=valid unsupported_claims=0
```

```bash
PYTHONPATH=src python -m project_recovery_council evaluate-offline --fixture strong_modular_council --experiment-id offline-strong_modular_council
```

Result: `offline evaluation written: experiment-artifacts/offline-strong_modular_council`

```bash
PYTHONPATH=src python -m project_recovery_council inspect-experiment experiment-artifacts/offline-strong_modular_council
```

Result: `experiment artifact inspection passed`

```bash
python -m pytest
```

Final current-state result: `58 passed in 6.34s`

```bash
PYTHONPATH=src python -m project_recovery_council check-schema-drift
```

Result: `schema drift check passed`

## Offline Experiment Artifact

Generated:

```text
experiment-artifacts/offline-strong_modular_council/
├── experiment-config.json
├── invocation-records.json
├── variant-results.json
├── evaluation-results.json
├── comparison-report.json
└── artifact-manifest.json
```

## Remaining Limitations

- No live Qwen API access is implemented.
- No Alibaba Cloud deployment code is included.
- Offline fixtures are simulated outputs and cannot support real performance
  claims.
- Provider token, latency, and cost fields remain null unless a live provider
  reports them or explicit pricing is supplied.
- Evaluation currently targets the single synthetic equipment-delay case.

## Recommended Next Step

Implement an opt-in live Qwen adapter behind `ModelClient`, preserving disabled
default behavior, structured output validation, retry and timeout policy, token
accounting, secrets handling, and artifact reproducibility.
