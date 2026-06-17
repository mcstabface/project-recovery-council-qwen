"""Deterministic semantic validation for CommercialExpert findings."""

from __future__ import annotations

from typing import Any

from pydantic import Field

from project_recovery_council.contracts import ContractModel
from project_recovery_council.fixtures import CaseBundle


class CommercialSemanticValidationResult(ContractModel):
    invocation_id: str = Field(min_length=1)
    valid: bool
    checked_fields: list[str] = Field(default_factory=list)
    semantic_violations: list[str] = Field(default_factory=list)
    expected_values: dict[str, Any] = Field(default_factory=dict)
    observed_values: dict[str, Any] = Field(default_factory=dict)
    valid_claim_keys: list[str] = Field(default_factory=list)
    invalid_claim_keys: list[str] = Field(default_factory=list)
    concise_findings: list[str] = Field(default_factory=list)


def validate_commercial_semantics(
    *,
    invocation_id: str,
    response_payload: dict[str, Any] | None,
    bundle: CaseBundle,
) -> CommercialSemanticValidationResult:
    claims = response_payload.get("claims", {}) if response_payload else {}
    if not isinstance(claims, dict):
        claims = {}
    cost = bundle.evidence_by_id["COST-SUMMARY-001"].fields
    expected_delay_rate = int(cost["delay_exposure_usd_per_day"])
    expected_slip = int(cost["unmitigated_delay_days"])
    expected_unmitigated = expected_delay_rate * expected_slip
    expected_mitigation = int(cost["accelerated_logistics_cost_usd"])
    expected_avoided = expected_unmitigated - expected_mitigation
    expected = {
        "delay_exposure_usd_per_day": expected_delay_rate,
        "forecast_milestone_slip_days": expected_slip,
        "unmitigated_exposure_usd": expected_unmitigated,
        "mitigation_cost_usd": expected_mitigation,
        "avoided_exposure_usd": expected_avoided,
        "gross_avoided_exposure_usd": expected_avoided,
    }
    observed = {
        key: claims[key]
        for key in [
            "delay_exposure_usd_per_day",
            "forecast_milestone_slip_days",
            "projected_milestone_slip_days",
            "unmitigated_exposure_usd",
            "mitigation_cost_usd",
            "avoided_exposure_usd",
            "gross_avoided_exposure_usd",
        ]
        if key in claims
    }
    checked: list[str] = []
    violations: list[str] = []
    valid_keys: set[str] = set()
    invalid_keys: set[str] = set()

    _check_int(
        claims,
        "delay_exposure_usd_per_day",
        expected_delay_rate,
        checked,
        violations,
        valid_keys,
        invalid_keys,
    )
    slip_key = "forecast_milestone_slip_days" if "forecast_milestone_slip_days" in claims else "projected_milestone_slip_days"
    _check_int(claims, slip_key, expected_slip, checked, violations, valid_keys, invalid_keys)
    _check_int(
        claims,
        "unmitigated_exposure_usd",
        expected_unmitigated,
        checked,
        violations,
        valid_keys,
        invalid_keys,
    )
    _check_int(claims, "mitigation_cost_usd", expected_mitigation, checked, violations, valid_keys, invalid_keys)
    _check_int(claims, "avoided_exposure_usd", expected_avoided, checked, violations, valid_keys, invalid_keys)
    _check_int(
        claims,
        "gross_avoided_exposure_usd",
        expected_avoided,
        checked,
        violations,
        valid_keys,
        invalid_keys,
    )

    rate = _int_or_none(claims.get("delay_exposure_usd_per_day"))
    slip = _int_or_none(claims.get("forecast_milestone_slip_days", claims.get("projected_milestone_slip_days")))
    unmitigated = _int_or_none(claims.get("unmitigated_exposure_usd"))
    mitigation = _int_or_none(claims.get("mitigation_cost_usd"))
    avoided = _int_or_none(claims.get("avoided_exposure_usd"))
    gross = _int_or_none(claims.get("gross_avoided_exposure_usd"))
    if rate is not None and slip is not None and unmitigated is not None:
        checked.append("unmitigated_exposure_arithmetic")
        expected_from_inputs = rate * slip
        if unmitigated != expected_from_inputs:
            violations.append(
                f"unmitigated_exposure_usd expected {expected_from_inputs} from delay rate and slip, observed {unmitigated}"
            )
            invalid_keys.add("unmitigated_exposure_usd")
    if unmitigated is not None and mitigation is not None:
        checked.append("avoided_exposure_arithmetic")
        expected_from_inputs = unmitigated - mitigation
        for key, value in [("avoided_exposure_usd", avoided), ("gross_avoided_exposure_usd", gross)]:
            if value is not None and value != expected_from_inputs:
                violations.append(f"{key} expected {expected_from_inputs}, observed {value}")
                invalid_keys.add(key)
            elif value is not None:
                valid_keys.add(key)

    valid = not violations
    concise = ["commercial semantic validation passed"] if valid else [f"commercial semantic violations: {len(violations)}"]
    return CommercialSemanticValidationResult(
        invocation_id=invocation_id,
        valid=valid,
        checked_fields=list(dict.fromkeys(checked)),
        semantic_violations=list(dict.fromkeys(violations)),
        expected_values=expected,
        observed_values=observed,
        valid_claim_keys=sorted(valid_keys - invalid_keys),
        invalid_claim_keys=sorted(invalid_keys),
        concise_findings=concise,
    )


def commercial_semantic_metrics(results: list[CommercialSemanticValidationResult]) -> dict[str, float]:
    if not results:
        return {
            "commercial_semantic_compliance_rate": 1.0,
            "delay_exposure_rate_correctness": 1.0,
            "unmitigated_exposure_correctness": 1.0,
            "mitigation_cost_correctness": 1.0,
            "avoided_exposure_correctness": 1.0,
        }
    return {
        "commercial_semantic_compliance_rate": sum(1 for result in results if result.valid) / len(results),
        "delay_exposure_rate_correctness": _field_correct_rate(results, "delay_exposure_usd_per_day"),
        "unmitigated_exposure_correctness": _field_correct_rate(results, "unmitigated_exposure_usd"),
        "mitigation_cost_correctness": _field_correct_rate(results, "mitigation_cost_usd"),
        "avoided_exposure_correctness": min(
            _field_correct_rate(results, "avoided_exposure_usd"),
            _field_correct_rate(results, "gross_avoided_exposure_usd"),
        ),
    }


def _check_int(
    claims: dict[str, Any],
    key: str,
    expected: int,
    checked: list[str],
    violations: list[str],
    valid_keys: set[str],
    invalid_keys: set[str],
) -> None:
    if key not in claims:
        return
    checked.append(key)
    observed = _int_or_none(claims.get(key))
    if observed != expected:
        violations.append(f"{key} expected {expected}, observed {claims.get(key)}")
        invalid_keys.add(key)
    else:
        valid_keys.add(key)


def _field_correct_rate(results: list[CommercialSemanticValidationResult], field: str) -> float:
    checked = [result for result in results if field in result.checked_fields]
    if not checked:
        return 1.0
    correct = [
        result
        for result in checked
        if field not in result.invalid_claim_keys
        and not any(field in violation for violation in result.semantic_violations)
    ]
    return len(correct) / len(checked)


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
