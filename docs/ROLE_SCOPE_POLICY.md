# Role Scope Policy

Evidence access is enforced by code in `src/project_recovery_council/role_scope.py`.
Prompt instructions reinforce the policy but do not replace it.

## ScheduleExpert

May receive:

- schedule records
- minimal case identity and milestone references required to interpret schedule
  records

Must not receive:

- commercial cost records
- contract exposure records
- supplier arrival correspondence
- logistics arrival status
- onsite-status progress assertions
- recovery-option commercial data
- unrelated risk records

Allowed claim keys include:

- `milestone_id`
- `delivery_baseline_date`
- `delivery_forecast_date`
- `delivery_movement_days`
- `installation_total_float_days`
- `installation_total_float_consumed_days`
- `installation_total_float_remaining_days`
- `float_consumption_status`
- `delivery_movement_direction`
- `milestone_baseline_date`
- `milestone_forecast_date_without_intervention`
- `forecast_milestone_slip_days`
- `successor_testing_activity_id`
- `successor_dependency_effect`
- `equipment_id`

These keys cover baseline and forecast dates, delivery movement, available
installation float, float consumed, remaining float, projected milestone slip,
qualitative float consumption status, and successor dependency effects.
`delivery_movement_direction` must be one of `early`, `on_time`, or `late`
and is checked by schedule-semantic validation.

Supported aliases, such as `baseline_delivery_date`,
`forecast_delivery_date`, `remaining_float_after_delivery_shift_days`,
`remaining_total_float_days`,
`remaining_total_float_after_delivery_shift_days`, `float_consumed_days`,
`forecast_milestone_date`, `contractual_milestone_baseline_date`, and
`contractual_milestone_forecast_without_intervention`, are normalized before
role validation. They are not role-policy keys themselves.

Prohibited claims include equipment onsite conclusions, supplier/logistics
arrival conclusions, commercial exposure, mitigation cost, preferred recovery
option, final authorization, and human decision outcomes.

## CommercialExpert

May receive cost summary, contract excerpt, required schedule impact values, and
minimal case identity. It may not resolve onsite status or supplier/logistics
arrival facts.

Allowed claim keys include `delay_exposure_usd_per_day`,
`forecast_milestone_slip_days`, `unmitigated_exposure_usd`,
`mitigation_cost_usd`, `gross_avoided_exposure_usd`, and
`avoided_exposure_usd`. Observed aliases such as
`contractual_delay_exposure_usd_per_day`, `unmitigated_delay_exposure_usd`, and
`net_avoided_exposure_usd` are normalized before role validation.

CommercialExpert also receives deterministic commercial-semantic validation.
The validator accepts the valid avoided-exposure finding separately from an
incorrect gross avoided-exposure field; invalid commercial fields are preserved
but excluded from normal synthesis.

## EvidenceAuditor

May receive all evidence needed to compare conflicting claims and citation
support.

Supported audit claim IDs are explicit and versioned for the synthetic case:
`C-ONSITE-ASSERTION`, `C-MILESTONE-SLIP-13D`,
`C-DELAY-EXPOSURE-15K-USD-PER-DAY`, `C-UNMITIGATED-EXPOSURE-195K-USD`, and
`C-ACCEL-COST-48K-USD`. Observed lower-case live IDs such as
`claim-onsite-assertion` and `claim-unmitigated-exposure-195000` are aliases to
this registry. Arbitrary unknown audit claim IDs are not accepted as valid
role-policy keys.

Observed dynamic audit support keys are also explicit typed assessment keys:
`delay_exposure_usd_per_day_support`, `delivery_shift_days_support`,
`equipment_onsite_claim_conflict`, `forecast_milestone_slip_days_support`, and
`installation_total_float_consumed_days_support`. They are support records, not
permission for arbitrary free-form claim IDs.

## RiskExpert

May receive risk register records and relevant schedule/status/contradiction
records. It must not make commercial exposure or recovery-option preference
claims.

Allowed risk claim keys include `onsite_status_conflict`,
`recovery_approval_risk`, `milestone_slip_impact`,
`conflicting_onsite_status_requires_human_confirmation`,
`recovery_option_approval_blocked`, and
`escalation_required_for_milestone_integrity`, `escalation_requirement`, and
`milestone_slip_exposure`. A risk finding may state that authorization is
blocked pending human confirmation; it must not convert that gate into a
commercial recommendation or final approval decision.

## RecoveryPlanner

May receive validated specialist findings, approved or unresolved
contradictions, recovery options, and human decisions when available.

RecoveryPlanner synthesis receives the compact validated-findings envelope, not
verbose raw specialist provider responses. Recommendation and authorization are
separate: pending human confirmation blocks authorization, but it does not by
itself require abstaining from a recovery recommendation.

## DirectorAgent

May receive compact evidence metadata sufficient for routing.

## ArbiterAgent

May receive specialist findings, citations, identified disagreements, and only
the source evidence needed to resolve those disagreements.

## GeneralistAgent

May receive the full evidence bundle because that is the defined baseline
experiment design.

## Validation

Specialist validation order is:

- JSON schema validation
- deterministic claim-key normalization
- role-scope validation on normalized claims
- domain semantic validation on normalized claims

Role validation records:

- allowed claims
- prohibited claims
- allowed warnings
- prohibited warnings
- citation-policy violations
- evidence-scope violations
- concise findings

JSON schema validity does not imply role-scope validity.
Claim normalization validity does not imply role-scope validity.

## Schedule Semantic Validation

`ScheduleExpert` findings also receive deterministic schedule-semantic
validation in `src/project_recovery_council/schedule_semantics.py`. This is
separate from JSON schema validation and role-scope validation.

The validator checks the schedule arithmetic against `SCH-DELIVERY-001`:

- `delivery_movement_days` equals the difference between forecast and baseline
  delivery dates when both are present.
- `installation_total_float_consumed_days` equals
  `min(delivery_movement_days, installation_total_float_days)`.
- `installation_total_float_remaining_days` equals
  `max(installation_total_float_days - delivery_movement_days, 0)`.
- `forecast_milestone_slip_days` equals
  `max(delivery_movement_days - installation_total_float_days, 0)`.
- remaining float is never negative.
- consumed float never exceeds available float.
- `float_consumption_status` is one of `available`, `partially_consumed`, or
  `fully_consumed`.
- when consumed and remaining float are present, `float_consumption_status`
  agrees with those numeric fields.
- `delivery_movement_direction` is one of `early`, `on_time`, or `late` and
  agrees with the sign of `delivery_movement_days` when both are present.
- `milestone_forecast_date_without_intervention` equals
  `milestone_baseline_date + forecast_milestone_slip_days` when both dates are
  present.

For the synthetic case, the correct interpretation is 21 days of delivery
movement, 8 days of available installation total float, 8 days of float
consumed, 0 days of remaining float, and 13 days of net milestone slip.
