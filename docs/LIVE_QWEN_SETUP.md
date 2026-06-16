# Live Qwen Setup

Live Qwen execution is opt-in. Normal installation, imports, tests, offline
commands, and deterministic workflows do not require credentials and do not make
network calls.

## API Key

Create a Model Studio API key in Alibaba Cloud and expose it through an
environment variable. The default variable is:

```bash
export DASHSCOPE_API_KEY="<your-api-key>"
```

Do not put real secrets in source files, shell history you plan to share,
documentation, tests, or committed artifacts. You can use another variable name
with `--api-key-env-var`.

## Endpoint And Region

The default base URL is the documented international OpenAI-compatible endpoint:

```text
https://dashscope-intl.aliyuncs.com/compatible-mode/v1
```

Use `--base-url` or `QWEN_BASE_URL` for another official endpoint. Record the
region or endpoint label with `--provider-region-label`.

Official reference:

- https://www.alibabacloud.com/help/en/model-studio/compatibility-of-openai-with-dashscope

## Model ID

No live model ID is defaulted. Pass the model explicitly:

```bash
PYTHONPATH=src python -m project_recovery_council live-smoke --model <model-id> --allow-network
```

Choose the model ID from the current Model Studio console or official endpoint
documentation for your account and region.

## Smoke Test

Run one minimal request:

```bash
PYTHONPATH=src python -m project_recovery_council live-smoke \
  --model <model-id> \
  --allow-network
```

The command prints the model and endpoint, warns that provider charges may
apply, validates the structured response locally, redacts artifacts, and writes
under `experiment-artifacts/live/<experiment-id>/`.

## Agent And Variant Commands

```bash
PYTHONPATH=src python -m project_recovery_council live-agent \
  --agent ScheduleExpert \
  --model <model-id> \
  --allow-network
```

```bash
PYTHONPATH=src python -m project_recovery_council live-variant \
  --variant single_generalist \
  --model <model-id> \
  --allow-network
```

`live-variant` runs only the named variant and never runs the full matrix
implicitly.

## Specialist Scope

Standalone specialist commands are recorded with
`invocation_purpose=standalone_live_agent`. They are not labeled as
`single_generalist`.

`ScheduleExpert` receives only schedule evidence and minimal case identity.
If it produces onsite-status, supplier/logistics, commercial, recovery-option,
authorization, or human-decision content, that output is preserved but marked as
role-scope invalid in `role-validation-results.json`.

Specialist claim keys are normalized after schema validation and before role or
domain semantic validation. Raw parsed output remains in
`parsed-structured-responses.json`; normalized output is written to
`normalized-structured-responses.json`. The normalization trace is written to
`claim-normalization-results.json`, and aggregate normalization metrics are
written to `claim-normalization-metrics.json`.

For `ScheduleExpert`, supported aliases include `baseline_delivery_date`,
`forecast_delivery_date`, `remaining_float_after_delivery_shift_days`,
`contractual_milestone_baseline_date`, and
`contractual_milestone_forecast_without_intervention`. Conflicting aliases do
not get silently resolved; they invalidate normalization while preserving raw
provider output.

## Artifact Handling

Live artifacts are ignored by Git:

```text
experiment-artifacts/live/
```

Before committing, verify no live artifacts are staged:

```bash
git status --short
git diff --cached --name-only | grep '^experiment-artifacts/live/' || true
```

## Cost Caution

Provider charges may apply to live requests. Keep smoke tests small and avoid
running variant experiments repeatedly without reviewing provider usage.
