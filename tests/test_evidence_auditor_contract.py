import json
from typing import Any

import pytest
from pydantic import ValidationError

from project_recovery_council.evidence_auditor import (
    audit_findings_to_response_payload,
    validate_and_convert_evidence_auditor_response,
)
from project_recovery_council.experiment_contracts import (
    EVIDENCE_AUDITOR_RESPONSE_SCHEMA,
    SPECIALIST_FINDING_RESPONSE_SCHEMA,
    AgentRole,
    EvidenceAuditorResponse,
    SpecialistFindingResponse,
)
from project_recovery_council.fixtures import load_equipment_delay_case
from project_recovery_council.workflow import DEFAULT_CASE_PATH


def observed_nested_auditor_response(*, schema_version: str = SPECIALIST_FINDING_RESPONSE_SCHEMA) -> dict[str, Any]:
    return {
        "schema_version": schema_version,
        "agent_role": AgentRole.EVIDENCE_AUDITOR.value,
        "status": "completed",
        "claims": {
            AgentRole.COMMERCIAL_EXPERT.value: {
                "delay_exposure_usd_per_day": {
                    "support_status": "supported",
                    "rationale": "Contract and cost summary support the daily exposure.",
                    "observed_value": 15000,
                    "expected_value": 15000,
                }
            },
            AgentRole.RISK_EXPERT.value: {
                "milestone_slip_forecast": {
                    "support_status": "unsupported",
                    "rationale": "RiskExpert is outside quantitative schedule-forecast scope.",
                    "observed_value": 13,
                    "validation_reference": "role_scope_policy.v1",
                }
            },
            AgentRole.SCHEDULE_EXPERT.value: {
                "installation_total_float_consumed_days": {
                    "support_status": "contradicted",
                    "rationale": "Available float is 8 days, so consumed float cannot be 13.",
                    "observed_value": 13,
                    "expected_value": 8,
                    "validation_reference": "ScheduleExpertSemanticValidator.v1",
                },
                "installation_total_float_remaining_days": {
                    "support_status": "contradicted",
                    "rationale": "Remaining float cannot be negative.",
                    "observed_value": -5,
                    "expected_value": 0,
                    "validation_reference": "ScheduleExpertSemanticValidator.v1",
                },
                "forecast_milestone_slip_days": {
                    "support_status": "supported",
                    "rationale": "The net milestone slip is 13 days after float absorption.",
                    "observed_value": 13,
                    "expected_value": 13,
                },
            },
        },
        "citations": {
            AgentRole.COMMERCIAL_EXPERT.value: {
                "delay_exposure_usd_per_day": ["COST-SUMMARY-001", "CTR-DELAY-001"]
            },
            AgentRole.RISK_EXPERT.value: {
                "milestone_slip_forecast": []
            },
            AgentRole.SCHEDULE_EXPERT.value: {
                "installation_total_float_consumed_days": ["SCH-DELIVERY-001"],
                "installation_total_float_remaining_days": ["SCH-DELIVERY-001"],
                "forecast_milestone_slip_days": ["SCH-DELIVERY-001"],
            },
        },
        "unsupported_claims": ["RiskExpert.milestone_slip_forecast"],
        "warnings": [],
        "abstention_reason": None,
    }


def test_nested_auditor_response_fails_generic_specialist_contract() -> None:
    with pytest.raises(ValidationError):
        SpecialistFindingResponse.model_validate(observed_nested_auditor_response())


def test_nested_auditor_response_passes_dedicated_contract_and_aligns_keys() -> None:
    response = EvidenceAuditorResponse.model_validate(observed_nested_auditor_response())

    assert response.schema_version == EVIDENCE_AUDITOR_RESPONSE_SCHEMA
    assert response.assessments_by_agent[AgentRole.SCHEDULE_EXPERT.value][
        "installation_total_float_consumed_days"
    ].support_status == "contradicted"
    assert set(response.claims) == set(response.citations)
    for agent, claims in response.claims.items():
        assert set(claims) == set(response.citations[agent])


def test_auditor_conversion_preserves_substantive_assessments() -> None:
    bundle = load_equipment_delay_case(DEFAULT_CASE_PATH)
    result = validate_and_convert_evidence_auditor_response(
        invocation_id="INV-AUDIT",
        response_payload=observed_nested_auditor_response(),
        bundle=bundle,
        original_claim_sources={
            (AgentRole.SCHEDULE_EXPERT.value, "installation_total_float_consumed_days"): "INV-SCHEDULE",
            (AgentRole.SCHEDULE_EXPERT.value, "installation_total_float_remaining_days"): "INV-SCHEDULE",
            (AgentRole.SCHEDULE_EXPERT.value, "forecast_milestone_slip_days"): "INV-SCHEDULE",
        },
    )

    by_key = {
        (finding.audited_agent, finding.audited_claim_key): finding
        for finding in result.canonical_findings
    }
    consumed = by_key[(AgentRole.SCHEDULE_EXPERT.value, "installation_total_float_consumed_days")]
    remaining = by_key[(AgentRole.SCHEDULE_EXPERT.value, "installation_total_float_remaining_days")]
    risk = by_key[(AgentRole.RISK_EXPERT.value, "milestone_slip_forecast")]
    supported = by_key[(AgentRole.SCHEDULE_EXPERT.value, "forecast_milestone_slip_days")]

    assert result.valid is True
    assert consumed.support_status == "contradicted"
    assert consumed.expected_value == 8
    assert consumed.eligible_for_synthesis is False
    assert consumed.original_invocation_id == "INV-SCHEDULE"
    assert remaining.support_status == "contradicted"
    assert remaining.observed_value == -5
    assert risk.support_status == "unsupported"
    assert risk.citations == []
    assert risk.eligible_for_synthesis is False
    assert supported.support_status == "supported"
    assert supported.eligible_for_synthesis is True


def test_auditor_conversion_preserves_raw_response_separately() -> None:
    payload = observed_nested_auditor_response()
    bundle = load_equipment_delay_case(DEFAULT_CASE_PATH)
    result = validate_and_convert_evidence_auditor_response(
        invocation_id="INV-AUDIT",
        response_payload=payload,
        bundle=bundle,
    )
    normalized = audit_findings_to_response_payload(response_payload=payload, validation=result)

    assert payload["claims"][AgentRole.SCHEDULE_EXPERT.value]["installation_total_float_consumed_days"][
        "support_status"
    ] == "contradicted"
    assert "ScheduleExpert.installation_total_float_consumed_days" in normalized["claims"]
    assert json.dumps(payload, sort_keys=True) != json.dumps(normalized, sort_keys=True)


def test_unknown_audited_agent_fails() -> None:
    payload = observed_nested_auditor_response()
    payload["claims"]["UnknownExpert"] = {"claim": {"support_status": "supported"}}
    payload["citations"]["UnknownExpert"] = {"claim": []}

    with pytest.raises(ValidationError, match="unknown audited agent"):
        EvidenceAuditorResponse.model_validate(payload)


def test_invalid_support_status_fails() -> None:
    payload = observed_nested_auditor_response()
    payload["claims"][AgentRole.SCHEDULE_EXPERT.value]["forecast_milestone_slip_days"][
        "support_status"
    ] = "partly_true"

    with pytest.raises(ValidationError):
        EvidenceAuditorResponse.model_validate(payload)


def test_missing_matching_citation_entry_fails() -> None:
    payload = observed_nested_auditor_response()
    del payload["citations"][AgentRole.SCHEDULE_EXPERT.value]["forecast_milestone_slip_days"]

    with pytest.raises(ValidationError, match="matching claim keys"):
        EvidenceAuditorResponse.model_validate(payload)
