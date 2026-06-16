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
- `milestone_baseline_date`
- `milestone_forecast_date_without_intervention`
- `forecast_milestone_slip_days`
- `successor_testing_activity_id`
- `successor_dependency_effect`

These keys cover baseline and forecast dates, delivery movement, available
installation float, float consumed, remaining float, projected milestone slip,
qualitative float consumption status, and successor dependency effects.

Supported aliases, such as `baseline_delivery_date`,
`forecast_delivery_date`, `remaining_float_after_delivery_shift_days`,
`remaining_total_float_days`,
`contractual_milestone_baseline_date`, and
`contractual_milestone_forecast_without_intervention`, are normalized before
role validation. They are not role-policy keys themselves.

Prohibited claims include equipment onsite conclusions, supplier/logistics
arrival conclusions, commercial exposure, mitigation cost, preferred recovery
option, final authorization, and human decision outcomes.

## CommercialExpert

May receive cost summary, contract excerpt, required schedule impact values, and
minimal case identity. It may not resolve onsite status or supplier/logistics
arrival facts.

## EvidenceAuditor

May receive all evidence needed to compare conflicting claims and citation
support.

## RiskExpert

May receive risk register records and relevant schedule/status/contradiction
records. It must not make commercial exposure or recovery-option preference
claims.

## RecoveryPlanner

May receive validated specialist findings, approved or unresolved
contradictions, recovery options, and human decisions when available.

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
- `milestone_forecast_date_without_intervention` equals
  `milestone_baseline_date + forecast_milestone_slip_days` when both dates are
  present.

For the synthetic case, the correct interpretation is 21 days of delivery
movement, 8 days of available installation total float, 8 days of float
consumed, 0 days of remaining float, and 13 days of net milestone slip.
