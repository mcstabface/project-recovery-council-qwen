import json
from pathlib import Path
from typing import Any

import pytest

from project_recovery_council.claim_normalization import normalize_claim_keys, normalize_response_payload
from project_recovery_council.experiment_artifacts import validate_experiment_artifacts
from project_recovery_council.experiment_contracts import (
    RECOVERY_ANALYSIS_RESPONSE_SCHEMA,
    SPECIALIST_FINDING_RESPONSE_SCHEMA,
    AgentRole,
    EvaluationMetricId,
    ExperimentVariant,
)
from project_recovery_council.fixtures import load_equipment_delay_case
from project_recovery_council.live_variant_runner import run_controlled_live_variant
from project_recovery_council.model_client import FinishStatus, ModelRequest, ModelResult
from project_recovery_council.qwen_config import QwenProviderConfig
from project_recovery_council.role_scope import selected_evidence_record_ids, validate_role_scope
from project_recovery_council.serialization import read_json
from project_recovery_council.workflow import DEFAULT_CASE_PATH


DUMMY_SECRET = "dummy-handoff-secret"


class QueueModelClient:
    provider = "mock-qwen"

    def __init__(self, responses: list[dict[str, Any]]) -> None:
        self.responses = list(responses)
        self.requests: list[ModelRequest] = []

    def generate(self, request: ModelRequest) -> ModelResult:
        self.requests.append(request)
        response = self.responses.pop(0)
        return ModelResult(
            parsed_response=response,
            raw_response_text=json.dumps(response, sort_keys=True),
            model_identifier=request.model_identifier,
            provider=self.provider,
            input_token_count=10,
            output_token_count=5,
            total_token_count=15,
            latency_seconds=0.1,
            finish_status=FinishStatus.COMPLETED,
            provider_metadata={"network_attempted": False},
            simulated=True,
        )


def config() -> QwenProviderConfig:
    return QwenProviderConfig(
        api_key_env_var="DASHSCOPE_API_KEY",
        base_url="https://example.invalid/compatible-mode/v1",
        model_identifier="explicit-test-model",
        request_timeout_seconds=3.0,
        maximum_retries=1,
        temperature=0.0,
    )


def specialist_response(agent_role: str, claims: dict[str, Any], citations: dict[str, list[str]] | None = None) -> dict[str, Any]:
    return {
        "schema_version": SPECIALIST_FINDING_RESPONSE_SCHEMA,
        "agent_role": agent_role,
        "status": "completed",
        "claims": claims,
        "citations": citations or {},
        "unsupported_claims": [],
        "warnings": [],
    }


def observed_schedule_response() -> dict[str, Any]:
    return specialist_response(
        AgentRole.SCHEDULE_EXPERT.value,
        {
            "delivery_baseline_date": "2026-07-01",
            "delivery_forecast_date": "2026-07-22",
            "delivery_movement_days": 21,
            "installation_total_float_days": 8,
            "installation_total_float_consumed_days": 8,
            "remaining_total_float_after_delivery_shift_days": 0,
            "baseline_milestone_date": "2026-08-15",
            "forecast_milestone_date_without_intervention": "2026-08-28",
            "forecast_milestone_slip_days": 13,
        },
        {
            "delivery_movement_days": ["SCH-DELIVERY-001"],
            "remaining_total_float_after_delivery_shift_days": ["SCH-DELIVERY-001"],
            "forecast_milestone_slip_days": ["SCH-DELIVERY-001"],
        },
    )


def observed_commercial_response() -> dict[str, Any]:
    return specialist_response(
        AgentRole.COMMERCIAL_EXPERT.value,
        {
            "contractual_delay_exposure_usd_per_day": 15000,
            "forecast_milestone_slip_days": 13,
            "unmitigated_delay_exposure_usd": 195000,
            "mitigation_cost_usd": 48000,
            "gross_avoided_exposure_usd": 147000,
        },
        {
            "contractual_delay_exposure_usd_per_day": ["COST-SUMMARY-001", "CTR-DELAY-001"],
            "forecast_milestone_slip_days": ["SCH-DELIVERY-001"],
            "unmitigated_delay_exposure_usd": ["SCH-DELIVERY-001", "COST-SUMMARY-001", "CTR-DELAY-001"],
            "mitigation_cost_usd": ["COST-SUMMARY-001"],
            "gross_avoided_exposure_usd": ["COST-SUMMARY-001", "CTR-DELAY-001"],
        },
    )


def observed_auditor_response() -> dict[str, Any]:
    return specialist_response(
        AgentRole.EVIDENCE_AUDITOR.value,
        {
            "C-ONSITE-ASSERTION": {
                "assessment": "contradicted",
                "citations": ["PRG-ONSITE-001", "SUP-NOT-ARRIVED-001", "LOG-STATUS-001"],
            },
            "C-MILESTONE-SLIP-13D": {"assessment": "supported", "citations": ["SCH-DELIVERY-001"]},
            "C-DELAY-EXPOSURE-15K-USD-PER-DAY": {
                "assessment": "supported",
                "citations": ["COST-SUMMARY-001", "CTR-DELAY-001"],
            },
            "C-UNMITIGATED-EXPOSURE-195K-USD": {
                "assessment": "supported",
                "citations": ["SCH-DELIVERY-001", "COST-SUMMARY-001", "CTR-DELAY-001"],
            },
            "C-ACCEL-COST-48K-USD": {"assessment": "supported", "citations": ["COST-SUMMARY-001"]},
        },
    )


def observed_risk_response() -> dict[str, Any]:
    return specialist_response(
        AgentRole.RISK_EXPERT.value,
        {
            "onsite_status_conflict": "unresolved conflict between progress report and supplier/logistics records",
            "recovery_approval_risk": "human confirmation required before authorization",
            "milestone_slip_impact": "13-day milestone slip remains material",
        },
        {
            "onsite_status_conflict": ["PRG-ONSITE-001", "SUP-NOT-ARRIVED-001", "LOG-STATUS-001"],
            "recovery_approval_risk": ["PRG-ONSITE-001", "SUP-NOT-ARRIVED-001", "LOG-STATUS-001"],
            "milestone_slip_impact": ["SCH-DELIVERY-001", "RISK-001"],
        },
    )


def planner_completed_response() -> dict[str, Any]:
    return {
        "schema_version": RECOVERY_ANALYSIS_RESPONSE_SCHEMA,
        "agent_role": AgentRole.RECOVERY_PLANNER.value,
        "status": "completed",
        "projected_slip_days": 13,
        "unmitigated_exposure_usd": 195000,
        "mitigation_cost_usd": 48000,
        "gross_avoided_exposure_usd": 147000,
        "onsite_status_contradiction_detected": True,
        "asserted_equipment_onsite": False,
        "human_confirmation_required": True,
        "preferred_option_id": "REC-ACCEL-LOGISTICS",
        "preferred_option_subject_to_approval": True,
        "citations": {
            "projected_slip_days": ["SCH-DELIVERY-001"],
            "unmitigated_exposure_usd": ["SCH-DELIVERY-001", "COST-SUMMARY-001", "CTR-DELAY-001"],
            "mitigation_cost_usd": ["COST-SUMMARY-001"],
            "gross_avoided_exposure_usd": ["COST-SUMMARY-001", "CTR-DELAY-001"],
            "onsite_status_contradiction_detected": [
                "PRG-ONSITE-001",
                "SUP-NOT-ARRIVED-001",
                "LOG-STATUS-001",
            ],
            "human_confirmation_required": ["PRG-ONSITE-001", "SUP-NOT-ARRIVED-001", "LOG-STATUS-001"],
            "preferred_option_id": ["COST-SUMMARY-001", "SCH-DELIVERY-001"],
            "preferred_option_subject_to_approval": [
                "COST-SUMMARY-001",
                "SCH-DELIVERY-001",
                "PRG-ONSITE-001",
                "SUP-NOT-ARRIVED-001",
                "LOG-STATUS-001",
            ],
        },
        "unsupported_claims": [],
        "ambiguous_claims": [],
        "concise_rationale": "Recommend accelerated logistics, subject to human confirmation before authorization.",
    }


def planner_abstention_response() -> dict[str, Any]:
    return {
        "schema_version": RECOVERY_ANALYSIS_RESPONSE_SCHEMA,
        "agent_role": AgentRole.RECOVERY_PLANNER.value,
        "status": "abstained",
        "citations": {},
        "unsupported_claims": [],
        "ambiguous_claims": [],
        "abstention_reason": "Insufficient validated commercial evidence to form a recovery recommendation.",
    }


def assert_role_valid(role: str, payload: dict[str, Any]) -> dict[str, Any]:
    bundle = load_equipment_delay_case(DEFAULT_CASE_PATH)
    normalization = normalize_claim_keys(invocation_id="INV-TEST", role=role, response_payload=payload)
    normalized = normalize_response_payload(payload, normalization)
    result = validate_role_scope(
        role=role,
        invocation_id="INV-TEST",
        response_payload=normalized,
        selected_record_ids=selected_evidence_record_ids(bundle, role),
        bundle=bundle,
    )
    assert normalization.valid is True
    assert result.valid is True
    assert normalized is not None
    return normalized


def run_fixed_chain(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    responses: list[dict[str, Any]],
    *,
    experiment_id: str,
) -> tuple[Path, QueueModelClient]:
    monkeypatch.setenv("DASHSCOPE_API_KEY", DUMMY_SECRET)
    client = QueueModelClient(responses)
    path = run_controlled_live_variant(
        variant=ExperimentVariant.FIXED_EXPERT_CHAIN,
        config=config(),
        allow_network=True,
        artifacts_root=tmp_path / "live",
        experiment_id=experiment_id,
        client=client,
    )
    return path, client


def metric_score(report: dict[str, Any], metric_id: str) -> float | None:
    return next(item["score"] for item in report["metric_results"] if item["metric_id"] == metric_id)


def test_observed_specialist_outputs_are_role_valid() -> None:
    schedule = assert_role_valid(AgentRole.SCHEDULE_EXPERT.value, observed_schedule_response())
    commercial = assert_role_valid(AgentRole.COMMERCIAL_EXPERT.value, observed_commercial_response())
    auditor = assert_role_valid(AgentRole.EVIDENCE_AUDITOR.value, observed_auditor_response())
    risk = assert_role_valid(AgentRole.RISK_EXPERT.value, observed_risk_response())

    assert schedule["claims"]["installation_total_float_remaining_days"] == 0
    assert schedule["claims"]["milestone_baseline_date"] == "2026-08-15"
    assert schedule["claims"]["milestone_forecast_date_without_intervention"] == "2026-08-28"
    assert commercial["claims"]["delay_exposure_usd_per_day"] == 15000
    assert commercial["claims"]["unmitigated_exposure_usd"] == 195000
    assert "C-ONSITE-ASSERTION" in auditor["claims"]
    assert "recovery_approval_risk" in risk["claims"]


def test_validated_findings_envelope_retains_required_facts_and_citations(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path, client = run_fixed_chain(
        tmp_path,
        monkeypatch,
        [
            observed_schedule_response(),
            observed_commercial_response(),
            observed_auditor_response(),
            observed_risk_response(),
            planner_completed_response(),
        ],
        experiment_id="handoff-success",
    )
    envelope = read_json(path / "validated-findings-envelope.json")
    excluded = read_json(path / "excluded-findings.json")
    synthesis_inputs = read_json(path / "synthesis-input.json")
    state = read_json(path / "recommendation-authorization-state.json")
    synthesis_metrics = read_json(path / "synthesis-metrics.json")
    evaluation = read_json(path / "evaluation-results.json")["report"]
    planner_payload = client.requests[-1].user_payload

    assert validate_experiment_artifacts(path).passed is True
    keys = {finding["canonical_claim_key"] for finding in envelope}
    assert {
        "forecast_milestone_slip_days",
        "delay_exposure_usd_per_day",
        "unmitigated_exposure_usd",
        "mitigation_cost_usd",
        "gross_avoided_exposure_usd",
        "C-ONSITE-ASSERTION",
        "onsite_status_conflict",
        "recovery_approval_risk",
    }.issubset(keys)
    assert excluded == []
    unmitigated = next(finding for finding in envelope if finding["canonical_claim_key"] == "unmitigated_exposure_usd")
    assert unmitigated["citations"] == ["COST-SUMMARY-001", "CTR-DELAY-001", "SCH-DELIVERY-001"]
    assert state == synthesis_inputs[-1]["recommendation_authorization_state"]
    assert state["recommendation_available"] is True
    assert state["recommended_option_id"] == "REC-ACCEL-LOGISTICS"
    assert state["authorization_status"] == "blocked_pending_human_confirmation"
    assert state["blocking_human_request"] == "HDR-ONSITE-001"
    assert state["approval_required"] is True
    assert "parsed_response" not in planner_payload
    assert "system_instructions" not in planner_payload
    assert "Human confirmation blocks authorization, not the recommendation" in planner_payload
    assert synthesis_metrics["synthesis_omission_count"] == 0.0
    assert synthesis_metrics["recommendation_with_pending_approval_correctness"] == 1.0
    assert metric_score(evaluation, EvaluationMetricId.EVIDENCE_CITATION_RECALL.value) == 1.0


def test_invalid_findings_are_excluded_but_preserved(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    invalid_commercial = observed_commercial_response()
    invalid_commercial["claims"]["equipment_onsite_status"] = "onsite"
    invalid_commercial["citations"]["equipment_onsite_status"] = ["PRG-ONSITE-001"]

    path, _client = run_fixed_chain(
        tmp_path,
        monkeypatch,
        [
            observed_schedule_response(),
            invalid_commercial,
            observed_auditor_response(),
            observed_risk_response(),
            planner_abstention_response(),
        ],
        experiment_id="handoff-excluded",
    )
    excluded = read_json(path / "excluded-findings.json")
    state = read_json(path / "recommendation-authorization-state.json")
    final = read_json(path / "parsed-structured-responses.json")[-1]["parsed_response"]

    assert any(item["canonical_claim_key"] == "equipment_onsite_status" for item in excluded)
    assert all("role scope invalid" in item["exclusion_reason"] for item in excluded if item["source_agent"] == AgentRole.COMMERCIAL_EXPERT.value)
    assert state["recommendation_available"] is False
    assert final["status"] == "abstained"


def test_human_confirmation_does_not_force_recommendation_abstention(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path, _client = run_fixed_chain(
        tmp_path,
        monkeypatch,
        [
            observed_schedule_response(),
            observed_commercial_response(),
            observed_auditor_response(),
            observed_risk_response(),
            planner_completed_response(),
        ],
        experiment_id="handoff-recommendation-pending-approval",
    )
    final = read_json(path / "parsed-structured-responses.json")[-1]["parsed_response"]
    state = read_json(path / "recommendation-authorization-state.json")

    assert final["status"] == "completed"
    assert final["preferred_option_id"] == "REC-ACCEL-LOGISTICS"
    assert final["preferred_option_subject_to_approval"] is True
    assert final["human_confirmation_required"] is True
    assert state["authorization_status"] == "blocked_pending_human_confirmation"
