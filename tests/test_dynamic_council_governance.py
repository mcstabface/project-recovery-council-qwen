import json
from pathlib import Path
from typing import Any

import pytest

from project_recovery_council.claim_normalization import normalize_claim_keys, normalize_response_payload
from project_recovery_council.commercial_semantics import validate_commercial_semantics
from project_recovery_council.experiment_artifacts import validate_experiment_artifacts
from project_recovery_council.experiment_contracts import (
    ARBITER_RESPONSE_SCHEMA,
    DIRECTOR_ROUTING_RESPONSE_SCHEMA,
    EVIDENCE_AUDITOR_RESPONSE_SCHEMA,
    RECOVERY_ANALYSIS_RESPONSE_SCHEMA,
    SPECIALIST_FINDING_RESPONSE_SCHEMA,
    AgentRole,
    ExperimentVariant,
)
from project_recovery_council.fixtures import load_equipment_delay_case
from project_recovery_council.live_variant_runner import (
    compare_live_variant_runs,
    rebuild_derived_artifacts,
    run_controlled_live_variant,
)
from project_recovery_council.model_client import FinishStatus, ModelRequest, ModelResult
from project_recovery_council.qwen_config import QwenProviderConfig
from project_recovery_council.role_scope import selected_evidence_record_ids, validate_role_scope
from project_recovery_council.serialization import read_json, sha256_file, write_json
from project_recovery_council.workflow import DEFAULT_CASE_PATH


DUMMY_SECRET = "dummy-dynamic-governance-secret"


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
        "citations": citations or {key: ["SCH-DELIVERY-001"] for key in claims},
        "unsupported_claims": [],
        "warnings": [],
    }


def director_response(selected: list[str] | None = None) -> dict[str, Any]:
    return {
        "schema_version": DIRECTOR_ROUTING_RESPONSE_SCHEMA,
        "agent_role": AgentRole.DIRECTOR.value,
        "status": "completed",
        "selected_experts": selected
        or [AgentRole.COMMERCIAL_EXPERT.value, AgentRole.RISK_EXPERT.value, AgentRole.SCHEDULE_EXPERT.value],
        "routing_rationale": "Commercial, risk, and schedule specialists are relevant.",
        "skipped_experts": {},
        "citations": {"routing": ["SCH-DELIVERY-001", "COST-SUMMARY-001", "RISK-001"]},
    }


def observed_dynamic_schedule() -> dict[str, Any]:
    return specialist_response(
        AgentRole.SCHEDULE_EXPERT.value,
        {
            "delivery_baseline_date": "2026-07-01",
            "delivery_forecast_date": "2026-07-22",
            "delivery_movement_days": 21,
            "installation_total_float_days": 8,
            "installation_total_float_consumed_days": 8,
            "remaining_float_after_delivery_shift_days": 0,
            "baseline_milestone_date": "2026-08-15",
            "forecast_milestone_date": "2026-08-28",
            "forecast_milestone_slip_days": 13,
        },
    )


def observed_dynamic_commercial() -> dict[str, Any]:
    return specialist_response(
        AgentRole.COMMERCIAL_EXPERT.value,
        {
            "contractual_delay_exposure_usd_per_day": 15000,
            "forecast_milestone_slip_days": 13,
            "unmitigated_exposure_usd": 195000,
            "mitigation_cost_usd": 48000,
            "gross_avoided_exposure_usd": 195000,
            "net_avoided_exposure_usd": 147000,
        },
        {
            "contractual_delay_exposure_usd_per_day": ["COST-SUMMARY-001", "CTR-DELAY-001"],
            "forecast_milestone_slip_days": ["SCH-DELIVERY-001"],
            "unmitigated_exposure_usd": ["SCH-DELIVERY-001", "COST-SUMMARY-001", "CTR-DELAY-001"],
            "mitigation_cost_usd": ["COST-SUMMARY-001"],
            "gross_avoided_exposure_usd": ["COST-SUMMARY-001", "CTR-DELAY-001"],
            "net_avoided_exposure_usd": ["COST-SUMMARY-001", "CTR-DELAY-001"],
        },
    )


def observed_dynamic_risk() -> dict[str, Any]:
    return specialist_response(
        AgentRole.RISK_EXPERT.value,
        {
            "escalation_requirement": "human confirmation required before authorization",
            "milestone_slip_exposure": "13-day milestone slip creates exposure risk",
            "onsite_status_conflict": "onsite status remains unresolved",
            "recovery_approval_risk": "approval blocked pending human confirmation",
        },
        {
            "escalation_requirement": ["PRG-ONSITE-001", "SUP-NOT-ARRIVED-001", "LOG-STATUS-001"],
            "milestone_slip_exposure": ["SCH-DELIVERY-001", "RISK-001"],
            "onsite_status_conflict": ["PRG-ONSITE-001", "SUP-NOT-ARRIVED-001", "LOG-STATUS-001"],
            "recovery_approval_risk": ["PRG-ONSITE-001", "SUP-NOT-ARRIVED-001", "LOG-STATUS-001"],
        },
    )


def observed_dynamic_auditor() -> dict[str, Any]:
    return {
        "schema_version": EVIDENCE_AUDITOR_RESPONSE_SCHEMA,
        "agent_role": AgentRole.EVIDENCE_AUDITOR.value,
        "status": "completed",
        "claims": {
            AgentRole.COMMERCIAL_EXPERT.value: {
                "delay_exposure_usd_per_day": {"support_status": "supported", "observed_value": 15000},
                "unmitigated_exposure_usd": {"support_status": "supported", "observed_value": 195000},
                "mitigation_cost_usd": {"support_status": "supported", "observed_value": 48000},
                "avoided_exposure_usd": {"support_status": "supported", "observed_value": 147000},
            },
            AgentRole.RISK_EXPERT.value: {
                "onsite_status_conflict": {"support_status": "supported"},
                "recovery_approval_risk": {"support_status": "supported"},
            },
            AgentRole.SCHEDULE_EXPERT.value: {
                "delivery_movement_days": {"support_status": "supported", "observed_value": 21},
                "forecast_milestone_slip_days": {"support_status": "supported", "observed_value": 13},
                "installation_total_float_consumed_days": {"support_status": "supported", "observed_value": 8},
            },
        },
        "citations": {
            AgentRole.COMMERCIAL_EXPERT.value: {
                "delay_exposure_usd_per_day": ["COST-SUMMARY-001", "CTR-DELAY-001"],
                "unmitigated_exposure_usd": ["SCH-DELIVERY-001", "COST-SUMMARY-001", "CTR-DELAY-001"],
                "mitigation_cost_usd": ["COST-SUMMARY-001"],
                "avoided_exposure_usd": ["COST-SUMMARY-001", "CTR-DELAY-001"],
            },
            AgentRole.RISK_EXPERT.value: {
                "onsite_status_conflict": ["PRG-ONSITE-001", "SUP-NOT-ARRIVED-001", "LOG-STATUS-001"],
                "recovery_approval_risk": ["PRG-ONSITE-001", "SUP-NOT-ARRIVED-001", "LOG-STATUS-001"],
            },
            AgentRole.SCHEDULE_EXPERT.value: {
                "delivery_movement_days": ["SCH-DELIVERY-001"],
                "forecast_milestone_slip_days": ["SCH-DELIVERY-001"],
                "installation_total_float_consumed_days": ["SCH-DELIVERY-001"],
            },
        },
        "unsupported_claims": [],
        "warnings": [],
        "abstention_reason": None,
    }


def recovery_response() -> dict[str, Any]:
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
        },
        "unsupported_claims": [],
        "ambiguous_claims": [],
        "concise_rationale": "Recommend accelerated logistics while authorization remains blocked.",
    }


def arbiter_response() -> dict[str, Any]:
    return {
        "schema_version": ARBITER_RESPONSE_SCHEMA,
        "agent_role": AgentRole.ARBITER.value,
        "status": "completed",
        "resolved_disagreements": [],
        "unresolved_disagreements": [],
        "preserved_provenance_record_ids": ["SCH-DELIVERY-001"],
        "concise_rationale": "Disagreement preserved.",
    }


def run_dynamic(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, responses: list[dict[str, Any]], experiment_id: str):
    monkeypatch.setenv("DASHSCOPE_API_KEY", DUMMY_SECRET)
    client = QueueModelClient(responses)
    path = run_controlled_live_variant(
        variant=ExperimentVariant.DYNAMIC_EXPERT_COUNCIL,
        config=config(),
        allow_network=True,
        artifacts_root=tmp_path / "live",
        experiment_id=experiment_id,
        client=client,
    )
    return path, client


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


def scrub_invocation_ids(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: scrub_invocation_ids(item) for key, item in value.items() if key != "original_invocation_id"}
    if isinstance(value, list):
        return [scrub_invocation_ids(item) for item in value]
    return value


def test_observed_dynamic_specialist_outputs_are_role_valid() -> None:
    assert_role_valid(AgentRole.SCHEDULE_EXPERT.value, observed_dynamic_schedule())
    assert_role_valid(AgentRole.RISK_EXPERT.value, observed_dynamic_risk())


def test_commercial_semantic_validation_rejects_bad_gross_but_preserves_valid_net() -> None:
    bundle = load_equipment_delay_case(DEFAULT_CASE_PATH)
    payload = observed_dynamic_commercial()
    normalization = normalize_claim_keys(
        invocation_id="INV-COMMERCIAL",
        role=AgentRole.COMMERCIAL_EXPERT.value,
        response_payload=payload,
    )
    normalized = normalize_response_payload(payload, normalization)
    result = validate_commercial_semantics(
        invocation_id="INV-COMMERCIAL",
        response_payload=normalized,
        bundle=bundle,
    )

    assert normalized["claims"]["avoided_exposure_usd"] == 147000
    assert result.valid is False
    assert "avoided_exposure_usd" in result.valid_claim_keys
    assert "gross_avoided_exposure_usd" in result.invalid_claim_keys
    assert any("gross_avoided_exposure_usd expected 147000" in item for item in result.semantic_violations)


def test_fixed_and_dynamic_specialists_share_validation_processing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DASHSCOPE_API_KEY", DUMMY_SECRET)
    fixed_client = QueueModelClient(
        [observed_dynamic_schedule(), observed_dynamic_commercial(), observed_dynamic_auditor(), observed_dynamic_risk(), recovery_response()]
    )
    fixed_path = run_controlled_live_variant(
        variant=ExperimentVariant.FIXED_EXPERT_CHAIN,
        config=config(),
        allow_network=True,
        artifacts_root=tmp_path / "live",
        experiment_id="shared-fixed",
        client=fixed_client,
    )
    dynamic_path, _ = run_dynamic(
        tmp_path,
        monkeypatch,
        [
            director_response(),
            observed_dynamic_commercial(),
            observed_dynamic_risk(),
            observed_dynamic_schedule(),
            observed_dynamic_auditor(),
            recovery_response(),
        ],
        "shared-dynamic",
    )

    fixed_normalized = {
        item["normalized_response"]["agent_role"]: item["normalized_response"]["claims"]
        for item in read_json(fixed_path / "normalized-structured-responses.json")
    }
    dynamic_normalized = {
        item["normalized_response"]["agent_role"]: item["normalized_response"]["claims"]
        for item in read_json(dynamic_path / "normalized-structured-responses.json")
    }

    assert scrub_invocation_ids(fixed_normalized) == scrub_invocation_ids(dynamic_normalized)


def test_arbiter_skipped_when_no_substantive_disagreement(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path, client = run_dynamic(
        tmp_path,
        monkeypatch,
        [
            director_response(),
            observed_dynamic_commercial(),
            observed_dynamic_risk(),
            observed_dynamic_schedule(),
            observed_dynamic_auditor(),
            recovery_response(),
        ],
        "dynamic-no-disagreement",
    )
    arbitration = read_json(path / "arbitration-decisions.json")[0]

    assert arbitration["arbiter_required"] is False
    assert AgentRole.ARBITER.value not in [request.metadata["agent_role"] for request in client.requests]
    assert "human" in arbitration["arbiter_skip_reason"] or "no substantive" in arbitration["arbiter_skip_reason"]


def test_arbiter_skipped_when_all_findings_invalid(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    invalid_schedule = observed_dynamic_schedule()
    invalid_schedule["claims"]["equipment_onsite_status"] = "onsite"
    path, client = run_dynamic(
        tmp_path,
        monkeypatch,
        [
            director_response(selected=[AgentRole.SCHEDULE_EXPERT.value]),
            invalid_schedule,
            observed_dynamic_auditor(),
            recovery_response(),
        ],
        "dynamic-invalid-findings",
    )
    arbitration = read_json(path / "arbitration-decisions.json")[0]

    assert arbitration["arbiter_required"] is False
    assert AgentRole.ARBITER.value not in [request.metadata["agent_role"] for request in client.requests]


def test_arbiter_invoked_for_genuine_eligible_disagreement(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    auditor_conflict = {
        "schema_version": EVIDENCE_AUDITOR_RESPONSE_SCHEMA,
        "agent_role": AgentRole.EVIDENCE_AUDITOR.value,
        "status": "completed",
        "claims": {
            AgentRole.SCHEDULE_EXPERT.value: {
                "forecast_milestone_slip_days": {
                    "support_status": "supported",
                    "observed_value": 14,
                }
            }
        },
        "citations": {
            AgentRole.SCHEDULE_EXPERT.value: {
                "forecast_milestone_slip_days": ["SCH-DELIVERY-001"],
            }
        },
        "unsupported_claims": [],
        "warnings": [],
        "abstention_reason": None,
    }
    path, client = run_dynamic(
        tmp_path,
        monkeypatch,
        [
            director_response(selected=[AgentRole.SCHEDULE_EXPERT.value]),
            observed_dynamic_schedule(),
            auditor_conflict,
            arbiter_response(),
            recovery_response(),
        ],
        "dynamic-real-disagreement",
    )
    arbitration = read_json(path / "arbitration-decisions.json")[0]
    arbiter_payload = next(item for item in read_json(path / "governance-payloads.json") if item["agent_role"] == AgentRole.ARBITER.value)

    assert arbitration["arbiter_required"] is True
    assert AgentRole.ARBITER.value in [request.metadata["agent_role"] for request in client.requests]
    assert arbiter_payload["payload_size_characters"] > 0


def test_compact_governance_payloads_exclude_raw_provider_history(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _path, client = run_dynamic(
        tmp_path,
        monkeypatch,
        [
            director_response(),
            observed_dynamic_commercial(),
            observed_dynamic_risk(),
            observed_dynamic_schedule(),
            observed_dynamic_auditor(),
            recovery_response(),
        ],
        "dynamic-compact-payloads",
    )
    auditor_prompt = next(request.user_payload for request in client.requests if request.metadata["agent_role"] == AgentRole.EVIDENCE_AUDITOR.value)
    planner_prompt = next(request.user_payload for request in client.requests if request.metadata["agent_role"] == AgentRole.RECOVERY_PLANNER.value)

    assert "parsed_response" not in auditor_prompt
    assert "raw_response_text" not in auditor_prompt
    assert "system_instructions" not in auditor_prompt
    assert "parsed_response" not in planner_prompt


def test_diagnostic_rebuild_preserves_source_and_uses_no_network(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source, _client = run_dynamic(
        tmp_path,
        monkeypatch,
        [
            director_response(),
            observed_dynamic_commercial(),
            observed_dynamic_risk(),
            observed_dynamic_schedule(),
            observed_dynamic_auditor(),
            recovery_response(),
        ],
        "dynamic-source",
    )
    before_hash = sha256_file(source / "invocation-records.json")
    derived = rebuild_derived_artifacts(
        source_run_path=source,
        output_path=tmp_path / "derived" / "dynamic-source-derived",
    )
    metadata = read_json(derived / "diagnostic-rebuild-metadata.json")
    summary = read_json(derived / "final-variant-result.json")

    assert sha256_file(source / "invocation-records.json") == before_hash
    assert metadata["provider_calls_made"] == 0
    assert metadata["diagnostic_replay"] is True
    assert summary["diagnostic_replay"] is True
    assert summary["empirical_result_usable_for_comparison"] is False
    assert validate_experiment_artifacts(derived).passed is True


def test_compare_live_rejects_failed_or_diagnostic_dynamic_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DASHSCOPE_API_KEY", DUMMY_SECRET)
    generalist_client = QueueModelClient([recovery_response()])
    generalist = run_controlled_live_variant(
        variant=ExperimentVariant.SINGLE_GENERALIST,
        config=config(),
        allow_network=True,
        artifacts_root=tmp_path / "live",
        experiment_id="generalist-ok",
        client=generalist_client,
    )
    fixed_client = QueueModelClient(
        [observed_dynamic_schedule(), observed_dynamic_commercial(), observed_dynamic_auditor(), observed_dynamic_risk(), recovery_response()]
    )
    fixed = run_controlled_live_variant(
        variant=ExperimentVariant.FIXED_EXPERT_CHAIN,
        config=config(),
        allow_network=True,
        artifacts_root=tmp_path / "live",
        experiment_id="fixed-ok",
        client=fixed_client,
    )
    dynamic, _ = run_dynamic(
        tmp_path,
        monkeypatch,
        [
            director_response(),
            observed_dynamic_commercial(),
            observed_dynamic_risk(),
            observed_dynamic_schedule(),
            observed_dynamic_auditor(),
            recovery_response(),
        ],
        "dynamic-for-diagnostic",
    )
    diagnostic = rebuild_derived_artifacts(
        source_run_path=dynamic,
        output_path=tmp_path / "derived" / "dynamic-diagnostic",
    )

    with pytest.raises(ValueError, match="not usable|not comparable"):
        compare_live_variant_runs(
            generalist_path=generalist,
            fixed_chain_path=fixed,
            dynamic_council_path=diagnostic,
            output_root=tmp_path / "comparisons",
        )

    final = read_json(dynamic / "final-variant-result.json")
    final["derived_artifact_validation_failed"] = True
    final["artifact_validation_errors"] = ["synthetic validation failure"]
    final["empirical_result_usable_for_comparison"] = False
    write_json(dynamic / "final-variant-result.json", final)
    _refresh_manifest(dynamic, "final-variant-result.json")

    with pytest.raises(ValueError, match="not usable|not comparable"):
        compare_live_variant_runs(
            generalist_path=generalist,
            fixed_chain_path=fixed,
            dynamic_council_path=dynamic,
            output_root=tmp_path / "comparisons",
            comparison_id="reject-failed-original",
        )


def _refresh_manifest(path: Path, filename: str) -> None:
    manifest = read_json(path / "artifact-manifest.json")
    for entry in manifest["artifacts"]:
        if entry["relative_path"] == filename:
            entry["sha256"] = sha256_file(path / filename)
    write_json(path / "artifact-manifest.json", manifest)
