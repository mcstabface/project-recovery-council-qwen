# Claim Normalization

Claim normalization is deterministic code in
`src/project_recovery_council/claim_normalization.py`. It runs after JSON schema
validation and before role-scope or domain semantic validation for specialist
outputs.

Normalization does not mutate raw provider output. Raw parsed responses remain
available in `parsed-structured-responses.json`. Normalized responses are stored
separately in `normalized-structured-responses.json`, and normalization
decisions are stored in `claim-normalization-results.json`.

## ScheduleExpert v1 Aliases

| Raw key | Canonical key |
| --- | --- |
| `baseline_delivery_date` | `delivery_baseline_date` |
| `forecast_delivery_date` | `delivery_forecast_date` |
| `delivery_shift_days` | `delivery_movement_days` |
| `float_consumption_days` | `installation_total_float_consumed_days` |
| `remaining_float_days` | `installation_total_float_remaining_days` |
| `remaining_float_after_delivery_shift_days` | `installation_total_float_remaining_days` |
| `projected_milestone_slip_days` | `forecast_milestone_slip_days` |
| `contractual_milestone_baseline_date` | `milestone_baseline_date` |
| `contractual_milestone_forecast_without_intervention` | `milestone_forecast_date_without_intervention` |
| `successor_dependency_effects` | `successor_dependency_effect` |

Already canonical keys are retained unchanged.

## Conflict Rules

If a canonical key and one or more aliases provide equivalent values,
normalization succeeds and records the alias applications.

If a canonical key and alias disagree, or if multiple aliases for the same
canonical key disagree, normalization fails. The raw values are preserved in the
conflict record and no value is silently selected for that canonical key.

Unknown claim keys remain in `raw_claims` and `normalized_claims`. They are
reported in `unknown_claim_keys` and continue into role-scope validation, where
they are prohibited unless the role policy explicitly permits them.

## Metrics

Normalization emits:

- `claim_normalization_success_rate`
- `alias_application_count`
- `unknown_claim_key_count`
- `claim_alias_conflict_count`

These metrics are separate from schema validity, role-scope compliance, and
schedule semantic correctness.
