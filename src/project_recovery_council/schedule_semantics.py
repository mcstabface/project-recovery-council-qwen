"""Deterministic semantic validation for ScheduleExpert findings."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from pydantic import Field

from project_recovery_council.contracts import ContractModel
from project_recovery_council.fixtures import CaseBundle


class ScheduleSemanticValidationResult(ContractModel):
    invocation_id: str = Field(min_length=1)
    valid: bool
    checked_fields: list[str] = Field(default_factory=list)
    semantic_violations: list[str] = Field(default_factory=list)
    expected_values: dict[str, Any] = Field(default_factory=dict)
    observed_values: dict[str, Any] = Field(default_factory=dict)
    concise_findings: list[str] = Field(default_factory=list)


def validate_schedule_semantics(
    *,
    invocation_id: str,
    response_payload: dict[str, Any] | None,
    bundle: CaseBundle,
) -> ScheduleSemanticValidationResult:
    claims = response_payload.get("claims", {}) if response_payload else {}
    if not isinstance(claims, dict):
        claims = {}
    schedule = bundle.evidence_by_id["SCH-DELIVERY-001"]
    fields = schedule.fields
    baseline_delivery = _date(fields["baseline_delivery_date"])
    forecast_delivery = _date(fields["forecast_delivery_date"])
    available_float = int(fields["installation_total_float_days"])
    delivery_movement = (forecast_delivery - baseline_delivery).days
    float_consumed = min(delivery_movement, available_float)
    remaining_float = max(available_float - delivery_movement, 0)
    milestone_slip = max(delivery_movement - available_float, 0)
    milestone_baseline = _date(fields["contractual_milestone_baseline_date"])
    milestone_forecast = milestone_baseline + timedelta(days=milestone_slip)

    expected = {
        "delivery_movement_days": delivery_movement,
        "installation_total_float_consumed_days": float_consumed,
        "installation_total_float_remaining_days": remaining_float,
        "forecast_milestone_slip_days": milestone_slip,
        "milestone_forecast_date_without_intervention": milestone_forecast.isoformat(),
    }
    observed = {
        key: _observed_claim(claims, key)
        for key in [
            "delivery_movement_days",
            "installation_total_float_days",
            "installation_total_float_consumed_days",
            "installation_total_float_remaining_days",
            "forecast_milestone_slip_days",
            "delivery_baseline_date",
            "delivery_forecast_date",
            "milestone_baseline_date",
            "milestone_forecast_date_without_intervention",
        ]
        if _observed_claim(claims, key) is not None
    }
    checked: list[str] = []
    violations: list[str] = []

    observed_delivery = _int_or_none(_first_present(claims, ["delivery_movement_days", "delivery_shift_days"]))
    if observed_delivery is not None:
        checked.append("delivery_movement_days")
        if observed_delivery != delivery_movement:
            violations.append(f"delivery_movement_days expected {delivery_movement}, observed {observed_delivery}")

    observed_available_float = _int_or_none(_observed_claim(claims, "installation_total_float_days"))
    if observed_available_float is not None:
        checked.append("installation_total_float_days")
        if observed_available_float != available_float:
            violations.append(
                f"installation_total_float_days expected {available_float}, observed {observed_available_float}"
            )

    if observed_delivery is not None:
        expected_consumed = min(observed_delivery, available_float)
        expected_remaining = max(available_float - observed_delivery, 0)
        expected_slip = max(observed_delivery - available_float, 0)
    else:
        expected_consumed = float_consumed
        expected_remaining = remaining_float
        expected_slip = milestone_slip

    observed_consumed = _int_or_none(_observed_claim(claims, "installation_total_float_consumed_days"))
    if observed_consumed is not None:
        checked.append("installation_total_float_consumed_days")
        if observed_consumed != expected_consumed:
            violations.append(
                "installation_total_float_consumed_days "
                f"expected {expected_consumed}, observed {observed_consumed}"
            )
        if observed_consumed > available_float:
            violations.append(
                "installation_total_float_consumed_days must not exceed available float "
                f"({available_float}), observed {observed_consumed}"
            )

    observed_remaining = _int_or_none(
        _first_present(claims, ["installation_total_float_remaining_days", "remaining_float_days"])
    )
    if observed_remaining is not None:
        checked.append("installation_total_float_remaining_days")
        if observed_remaining != expected_remaining:
            violations.append(
                "installation_total_float_remaining_days "
                f"expected {expected_remaining}, observed {observed_remaining}"
            )
        if observed_remaining < 0:
            violations.append(
                f"installation_total_float_remaining_days must never be negative, observed {observed_remaining}"
            )

    observed_slip = _int_or_none(
        _first_present(claims, ["forecast_milestone_slip_days", "projected_milestone_slip_days"])
    )
    if observed_slip is not None:
        checked.append("forecast_milestone_slip_days")
        if observed_slip != expected_slip:
            violations.append(f"forecast_milestone_slip_days expected {expected_slip}, observed {observed_slip}")

    observed_baseline_delivery = _date_or_none(_first_present(claims, ["delivery_baseline_date", "baseline_delivery_date"]))
    observed_forecast_delivery = _date_or_none(_first_present(claims, ["delivery_forecast_date", "forecast_delivery_date"]))
    if observed_baseline_delivery is not None and observed_forecast_delivery is not None:
        checked.append("delivery_date_arithmetic")
        actual_delta = (observed_forecast_delivery - observed_baseline_delivery).days
        if observed_delivery is not None and actual_delta != observed_delivery:
            violations.append(
                "delivery_movement_days must equal forecast delivery minus baseline delivery "
                f"({actual_delta}), observed {observed_delivery}"
            )

    observed_milestone_baseline = _date_or_none(_observed_claim(claims, "milestone_baseline_date"))
    observed_milestone_forecast = _date_or_none(
        _observed_claim(claims, "milestone_forecast_date_without_intervention")
    )
    if observed_milestone_baseline is not None and observed_milestone_forecast is not None:
        checked.append("milestone_forecast_date_without_intervention")
        slip_for_date = observed_slip if observed_slip is not None else expected_slip
        expected_forecast_date = observed_milestone_baseline + timedelta(days=slip_for_date)
        if observed_milestone_forecast != expected_forecast_date:
            violations.append(
                "milestone_forecast_date_without_intervention expected "
                f"{expected_forecast_date.isoformat()}, observed {observed_milestone_forecast.isoformat()}"
            )

    valid = not violations
    concise = ["schedule semantic validation passed"] if valid else [f"schedule semantic violations: {len(violations)}"]
    return ScheduleSemanticValidationResult(
        invocation_id=invocation_id,
        valid=valid,
        checked_fields=checked,
        semantic_violations=violations,
        expected_values=expected,
        observed_values=observed,
        concise_findings=concise,
    )


def schedule_semantic_metrics(results: list[ScheduleSemanticValidationResult]) -> dict[str, float]:
    if not results:
        return {
            "delivery_movement_correctness": 1.0,
            "float_consumed_correctness": 1.0,
            "remaining_float_correctness": 1.0,
            "milestone_slip_correctness": 1.0,
            "milestone_date_arithmetic_correctness": 1.0,
            "schedule_semantic_compliance_rate": 1.0,
        }
    return {
        "delivery_movement_correctness": _field_correct_rate(results, "delivery_movement_days"),
        "float_consumed_correctness": _field_correct_rate(results, "installation_total_float_consumed_days"),
        "remaining_float_correctness": _field_correct_rate(results, "installation_total_float_remaining_days"),
        "milestone_slip_correctness": _field_correct_rate(results, "forecast_milestone_slip_days"),
        "milestone_date_arithmetic_correctness": _field_correct_rate(
            results,
            "milestone_forecast_date_without_intervention",
        ),
        "schedule_semantic_compliance_rate": sum(1 for result in results if result.valid) / len(results),
    }


def _field_correct_rate(results: list[ScheduleSemanticValidationResult], field: str) -> float:
    checked = [result for result in results if field in result.checked_fields]
    if not checked:
        return 1.0
    correct = [
        result
        for result in checked
        if not any(field in violation for violation in result.semantic_violations)
    ]
    return len(correct) / len(checked)


def _date(value: str) -> date:
    return date.fromisoformat(value)


def _date_or_none(value: Any) -> date | None:
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _int_or_none(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return None
    return None


def _observed_claim(claims: dict[str, Any], key: str) -> Any:
    return claims.get(key)


def _first_present(claims: dict[str, Any], keys: list[str]) -> Any:
    for key in keys:
        if key in claims:
            return claims[key]
    return None
