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
| `float_consumed_days` | `installation_total_float_consumed_days` |
| `remaining_float_days` | `installation_total_float_remaining_days` |
| `remaining_total_float_days` | `installation_total_float_remaining_days` |
| `remaining_float_after_delivery_shift_days` | `installation_total_float_remaining_days` |
| `remaining_total_float_after_delivery_shift_days` | `installation_total_float_remaining_days` |
| `projected_milestone_slip_days` | `forecast_milestone_slip_days` |
| `baseline_milestone_date` | `milestone_baseline_date` |
| `forecast_milestone_date` | `milestone_forecast_date_without_intervention` |
| `contractual_milestone_id` | `milestone_id` |
| `forecast_milestone_date_without_intervention` | `milestone_forecast_date_without_intervention` |
| `contractual_milestone_baseline_date` | `milestone_baseline_date` |
| `contractual_milestone_forecast_without_intervention` | `milestone_forecast_date_without_intervention` |
| `successor_dependency_effects` | `successor_dependency_effect` |

Already canonical keys are retained unchanged.
`float_consumption_status`, `delivery_movement_direction`,
`installation_activity_id`, and `equipment_id` are canonical ScheduleExpert
claim keys, not aliases.

## CommercialExpert v1 Aliases

| Raw key | Canonical key |
| --- | --- |
| `contractual_delay_exposure_usd_per_day` | `delay_exposure_usd_per_day` |
| `unmitigated_delay_exposure_usd` | `unmitigated_exposure_usd` |
| `net_avoided_exposure_usd` | `avoided_exposure_usd` |

`forecast_milestone_slip_days`, `mitigation_cost_usd`, and
`gross_avoided_exposure_usd` are supported canonical CommercialExpert claim
keys. `avoided_exposure_usd` is a canonical key used for the valid net avoided
exposure when a provider distinguishes net from gross avoided exposure.

## EvidenceAuditor And RiskExpert v1 Keys

EvidenceAuditor supports explicit audit claim IDs for the synthetic case:

- `C-ONSITE-ASSERTION`
- `C-MILESTONE-SLIP-13D`
- `C-DELAY-EXPOSURE-15K-USD-PER-DAY`
- `C-UNMITIGATED-EXPOSURE-195K-USD`
- `C-ACCEL-COST-48K-USD`

Observed live audit IDs are normalized into that explicit registry:

| Raw key | Canonical key |
| --- | --- |
| `claim-onsite-assertion` | `C-ONSITE-ASSERTION` |
| `claim-milestone-slip-13-days` | `C-MILESTONE-SLIP-13D` |
| `claim-delay-exposure-15000-per-day` | `C-DELAY-EXPOSURE-15K-USD-PER-DAY` |
| `claim-unmitigated-exposure-195000` | `C-UNMITIGATED-EXPOSURE-195K-USD` |
| `claim-accelerated-logistics-cost-48000` | `C-ACCEL-COST-48K-USD` |

RiskExpert supports `onsite_status_conflict`, `recovery_approval_risk`,
`milestone_slip_impact`,
`conflicting_onsite_status_requires_human_confirmation`,
`recovery_option_approval_blocked`, and
`escalation_required_for_milestone_integrity`, `escalation_requirement`, and
`milestone_slip_exposure` in addition to the earlier risk claim keys.

EvidenceAuditor also supports explicit typed support assessment keys observed
in dynamic council runs: `delay_exposure_usd_per_day_support`,
`delivery_shift_days_support`, `equipment_onsite_claim_conflict`,
`forecast_milestone_slip_days_support`, and
`installation_total_float_consumed_days_support`.

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
