"""Artifact writing and validation for competition experiment outputs."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import Field, TypeAdapter, ValidationError

from project_recovery_council.artifacts import ArtifactInspectionResult
from project_recovery_council.contracts import ContractModel
from project_recovery_council.experiment_contracts import (
    AgentInvocation,
    EvaluationReport,
    ExperimentComparison,
    ExperimentConfig,
)
from project_recovery_council.serialization import read_json, sha256_file, write_json


EXPERIMENT_ARTIFACT_CONTRACT_VERSION = "project-recovery-council.qwen.experiment-artifacts.v1"
DEFAULT_EXPERIMENT_ARTIFACT_ROOT = Path("experiment-artifacts")


class ExperimentArtifactEntry(ContractModel):
    name: str = Field(min_length=1)
    relative_path: str = Field(min_length=1)
    media_type: str = "application/json"
    schema_id: str = Field(min_length=1)
    sha256: str = Field(min_length=64, max_length=64)
    generated_at: str = Field(min_length=1)
    required: bool = True


class ExperimentArtifactManifest(ContractModel):
    artifact_contract_version: str = EXPERIMENT_ARTIFACT_CONTRACT_VERSION
    experiment_id: str = Field(min_length=1)
    case_id: str = Field(min_length=1)
    generated_at: str = Field(min_length=1)
    artifacts: list[ExperimentArtifactEntry] = Field(min_length=1)


LIST_ADAPTERS: dict[str, TypeAdapter[Any]] = {
    "project-recovery-council.qwen.agent-invocations.v1": TypeAdapter(list[AgentInvocation]),
}

MODEL_ADAPTERS: dict[str, type[ContractModel]] = {
    "project-recovery-council.qwen.experiment-config.v1": ExperimentConfig,
    "project-recovery-council.qwen.evaluation-report.v1": EvaluationReport,
    "project-recovery-council.qwen.experiment-comparison.v1": ExperimentComparison,
    "project-recovery-council.qwen.experiment-artifact-manifest.v1": ExperimentArtifactManifest,
}

GENERIC_JSON_SCHEMA_IDS = {
    "project-recovery-council.qwen.live-sanitized-provider-config.v1",
    "project-recovery-council.qwen.live-rendered-prompt-hashes.v1",
    "project-recovery-council.qwen.live-execution-plan.v1",
    "project-recovery-council.qwen.live-selected-evidence-records.v1",
    "project-recovery-council.qwen.live-role-validation-results.v1",
    "project-recovery-council.qwen.live-claim-normalization-results.v1",
    "project-recovery-council.qwen.live-normalized-structured-responses.v1",
    "project-recovery-council.qwen.live-schedule-semantic-validation.v1",
    "project-recovery-council.qwen.live-commercial-semantic-validation.v1",
    "project-recovery-council.qwen.live-evidence-auditor-validation-results.v1",
    "project-recovery-council.qwen.live-canonical-audit-findings.v1",
    "project-recovery-council.qwen.live-domain-semantic-validation-results.v1",
    "project-recovery-council.qwen.live-validated-findings-envelope.v1",
    "project-recovery-council.qwen.live-excluded-findings.v1",
    "project-recovery-council.qwen.live-synthesis-input.v1",
    "project-recovery-council.qwen.live-recommendation-authorization-state.v1",
    "project-recovery-council.qwen.live-schedule-semantic-metrics.v1",
    "project-recovery-council.qwen.live-commercial-semantic-metrics.v1",
    "project-recovery-council.qwen.live-synthesis-metrics.v1",
    "project-recovery-council.qwen.live-raw-provider-responses.v1",
    "project-recovery-council.qwen.live-parsed-structured-responses.v1",
    "project-recovery-council.qwen.live-validation-results.v1",
    "project-recovery-council.qwen.live-token-usage.v1",
    "project-recovery-council.qwen.live-retry-history.v1",
    "project-recovery-council.qwen.live-role-compliance-metrics.v1",
    "project-recovery-council.qwen.live-claim-normalization-metrics.v1",
    "project-recovery-council.qwen.live-routing-decisions.v1",
    "project-recovery-council.qwen.live-arbitration-decisions.v1",
    "project-recovery-council.qwen.live-governance-payloads.v1",
    "project-recovery-council.qwen.live-disagreement-records.v1",
    "project-recovery-council.qwen.live-final-variant-result.v1",
    "project-recovery-council.qwen.live-evaluation-results.v1",
    "project-recovery-council.qwen.live-comparison-report.v1",
    "project-recovery-council.qwen.live-efficiency-metrics.v1",
    "project-recovery-council.qwen.live-diagnostic-rebuild-metadata.v1",
    "project-recovery-council.qwen.live-reproducibility.v1",
}


def write_experiment_artifacts(
    *,
    experiment_id: str,
    case_id: str,
    config: ExperimentConfig,
    invocation_records: list[AgentInvocation],
    variant_results: dict[str, Any],
    evaluation_results: EvaluationReport,
    comparison_report: ExperimentComparison,
    artifacts_root: Path | str = DEFAULT_EXPERIMENT_ARTIFACT_ROOT,
) -> Path:
    root = Path(artifacts_root) / experiment_id
    root.mkdir(parents=True, exist_ok=True)
    files: list[tuple[str, str, Any]] = [
        ("experiment-config", "experiment-config.json", config),
        ("invocation-records", "invocation-records.json", invocation_records),
        ("variant-results", "variant-results.json", variant_results),
        ("evaluation-results", "evaluation-results.json", evaluation_results),
        ("comparison-report", "comparison-report.json", comparison_report),
    ]
    for _, filename, payload in files:
        write_json(root / filename, payload)

    generated_at = _now()
    entries = []
    for name, filename, _ in files:
        path = root / filename
        entries.append(
            ExperimentArtifactEntry(
                name=name,
                relative_path=filename,
                schema_id=_schema_id_for(filename),
                sha256=sha256_file(path),
                generated_at=generated_at,
            )
        )
    manifest = ExperimentArtifactManifest(
        experiment_id=experiment_id,
        case_id=case_id,
        generated_at=generated_at,
        artifacts=entries,
    )
    write_json(root / "artifact-manifest.json", manifest)
    return root


def validate_experiment_artifacts(path: Path | str) -> ArtifactInspectionResult:
    root = Path(path)
    manifest_path = root / "artifact-manifest.json"
    if not manifest_path.exists():
        return ArtifactInspectionResult(
            run_path=root.as_posix(),
            passed=False,
            errors=["missing artifact-manifest.json"],
        )
    try:
        manifest = ExperimentArtifactManifest.model_validate(read_json(manifest_path))
    except (json.JSONDecodeError, ValidationError, ValueError) as exc:
        return ArtifactInspectionResult(
            run_path=root.as_posix(),
            passed=False,
            errors=[f"invalid artifact-manifest.json: {exc}"],
        )

    errors: list[str] = []
    loaded_payloads: dict[str, Any] = {}
    for entry in manifest.artifacts:
        artifact_path = root / entry.relative_path
        if entry.required and not artifact_path.exists():
            errors.append(f"missing required artifact: {entry.relative_path}")
            continue
        if not artifact_path.exists():
            continue
        if sha256_file(artifact_path) != entry.sha256:
            errors.append(f"checksum mismatch: {entry.relative_path}")
        try:
            payload = read_json(artifact_path)
        except json.JSONDecodeError as exc:
            errors.append(f"invalid JSON in {entry.relative_path}: {exc}")
            continue
        loaded_payloads[entry.relative_path] = payload
        try:
            _validate_payload(entry.schema_id, payload)
        except (ValidationError, ValueError) as exc:
            errors.append(f"schema validation failed for {entry.relative_path}: {exc}")
    errors.extend(_validate_live_specialist_artifacts(loaded_payloads))
    errors.extend(_validate_live_synthesis_handoff_artifacts(loaded_payloads))
    return ArtifactInspectionResult(run_path=root.as_posix(), passed=not errors, errors=errors)


def _validate_payload(schema_id: str, payload: Any) -> None:
    if schema_id in LIST_ADAPTERS:
        LIST_ADAPTERS[schema_id].validate_python(payload)
        return
    if schema_id == "project-recovery-council.qwen.variant-results.v1":
        if not isinstance(payload, dict):
            raise ValueError("variant results must be a JSON object")
        return
    if schema_id in GENERIC_JSON_SCHEMA_IDS:
        if not isinstance(payload, (dict, list)):
            raise ValueError("live artifact payload must be a JSON object or array")
        return
    model = MODEL_ADAPTERS.get(schema_id)
    if model is None:
        raise ValueError(f"unknown schema id: {schema_id}")
    model.model_validate(payload)


def _schema_id_for(filename: str) -> str:
    return {
        "experiment-config.json": "project-recovery-council.qwen.experiment-config.v1",
        "execution-plan.json": "project-recovery-council.qwen.live-execution-plan.v1",
        "invocation-records.json": "project-recovery-council.qwen.agent-invocations.v1",
        "variant-results.json": "project-recovery-council.qwen.variant-results.v1",
        "evaluation-results.json": "project-recovery-council.qwen.evaluation-report.v1",
        "comparison-report.json": "project-recovery-council.qwen.experiment-comparison.v1",
        "sanitized-provider-config.json": "project-recovery-council.qwen.live-sanitized-provider-config.v1",
        "rendered-prompt-hashes.json": "project-recovery-council.qwen.live-rendered-prompt-hashes.v1",
        "selected-evidence-records.json": "project-recovery-council.qwen.live-selected-evidence-records.v1",
        "role-validation-results.json": "project-recovery-council.qwen.live-role-validation-results.v1",
        "claim-normalization-results.json": "project-recovery-council.qwen.live-claim-normalization-results.v1",
        "normalized-structured-responses.json": (
            "project-recovery-council.qwen.live-normalized-structured-responses.v1"
        ),
        "schedule-semantic-validation.json": "project-recovery-council.qwen.live-schedule-semantic-validation.v1",
        "commercial-semantic-validation.json": "project-recovery-council.qwen.live-commercial-semantic-validation.v1",
        "evidence-auditor-validation-results.json": (
            "project-recovery-council.qwen.live-evidence-auditor-validation-results.v1"
        ),
        "canonical-audit-findings.json": "project-recovery-council.qwen.live-canonical-audit-findings.v1",
        "domain-semantic-validation-results.json": (
            "project-recovery-council.qwen.live-domain-semantic-validation-results.v1"
        ),
        "validated-findings-envelope.json": "project-recovery-council.qwen.live-validated-findings-envelope.v1",
        "excluded-findings.json": "project-recovery-council.qwen.live-excluded-findings.v1",
        "synthesis-input.json": "project-recovery-council.qwen.live-synthesis-input.v1",
        "recommendation-authorization-state.json": (
            "project-recovery-council.qwen.live-recommendation-authorization-state.v1"
        ),
        "schedule-semantic-metrics.json": "project-recovery-council.qwen.live-schedule-semantic-metrics.v1",
        "commercial-semantic-metrics.json": "project-recovery-council.qwen.live-commercial-semantic-metrics.v1",
        "synthesis-metrics.json": "project-recovery-council.qwen.live-synthesis-metrics.v1",
        "raw-provider-responses.json": "project-recovery-council.qwen.live-raw-provider-responses.v1",
        "parsed-structured-responses.json": "project-recovery-council.qwen.live-parsed-structured-responses.v1",
        "validation-results.json": "project-recovery-council.qwen.live-validation-results.v1",
        "token-usage.json": "project-recovery-council.qwen.live-token-usage.v1",
        "retry-history.json": "project-recovery-council.qwen.live-retry-history.v1",
        "role-compliance-metrics.json": "project-recovery-council.qwen.live-role-compliance-metrics.v1",
        "claim-normalization-metrics.json": "project-recovery-council.qwen.live-claim-normalization-metrics.v1",
        "routing-decisions.json": "project-recovery-council.qwen.live-routing-decisions.v1",
        "arbitration-decisions.json": "project-recovery-council.qwen.live-arbitration-decisions.v1",
        "governance-payloads.json": "project-recovery-council.qwen.live-governance-payloads.v1",
        "disagreement-records.json": "project-recovery-council.qwen.live-disagreement-records.v1",
        "final-variant-result.json": "project-recovery-council.qwen.live-final-variant-result.v1",
        "live-comparison-report.json": "project-recovery-council.qwen.live-comparison-report.v1",
        "reproducibility.json": "project-recovery-council.qwen.live-reproducibility.v1",
        "efficiency-metrics.json": "project-recovery-council.qwen.live-efficiency-metrics.v1",
        "diagnostic-rebuild-metadata.json": "project-recovery-council.qwen.live-diagnostic-rebuild-metadata.v1",
    }[filename]


def _validate_live_specialist_artifacts(loaded_payloads: dict[str, Any]) -> list[str]:
    invocations = loaded_payloads.get("invocation-records.json")
    if not isinstance(invocations, list):
        return []
    specialist_invocation_ids = [
        invocation.get("invocation_id")
        for invocation in invocations
        if isinstance(invocation, dict)
        and invocation.get("agent_role")
        in {"ScheduleExpert", "CommercialExpert", "EvidenceAuditor", "RiskExpert"}
    ]
    if not specialist_invocation_ids:
        return []
    errors: list[str] = []
    selected = loaded_payloads.get("selected-evidence-records.json")
    role_results = loaded_payloads.get("role-validation-results.json")
    normalization_results = loaded_payloads.get("claim-normalization-results.json")
    normalized_responses = loaded_payloads.get("normalized-structured-responses.json")
    parsed_responses = loaded_payloads.get("parsed-structured-responses.json")
    schedule_results = loaded_payloads.get("schedule-semantic-validation.json")
    commercial_results = loaded_payloads.get("commercial-semantic-validation.json")
    evidence_auditor_results = loaded_payloads.get("evidence-auditor-validation-results.json")
    canonical_audit_findings = loaded_payloads.get("canonical-audit-findings.json")
    if not isinstance(selected, list) or not selected:
        errors.append("standalone specialist live artifacts require selected-evidence-records.json")
    if not isinstance(role_results, list) or not role_results:
        errors.append("standalone specialist live artifacts require role-validation-results.json")
    if not isinstance(normalization_results, list) or not normalization_results:
        errors.append("standalone specialist live artifacts require claim-normalization-results.json")
    if not isinstance(normalized_responses, list) or not normalized_responses:
        errors.append("standalone specialist live artifacts require normalized-structured-responses.json")
    schedule_invocation_ids = [
        invocation.get("invocation_id")
        for invocation in invocations
        if isinstance(invocation, dict)
        and invocation.get("agent_role") == "ScheduleExpert"
    ]
    if schedule_invocation_ids and (not isinstance(schedule_results, list) or not schedule_results):
        errors.append("standalone ScheduleExpert live artifacts require schedule-semantic-validation.json")
    commercial_invocation_ids = [
        invocation.get("invocation_id")
        for invocation in invocations
        if isinstance(invocation, dict)
        and invocation.get("agent_role") == "CommercialExpert"
    ]
    if commercial_invocation_ids and (not isinstance(commercial_results, list) or not commercial_results):
        errors.append("CommercialExpert live artifacts require commercial-semantic-validation.json")
    evidence_auditor_invocation_ids = [
        invocation.get("invocation_id")
        for invocation in invocations
        if isinstance(invocation, dict)
        and invocation.get("agent_role") == "EvidenceAuditor"
    ]
    if evidence_auditor_invocation_ids and (
        not isinstance(evidence_auditor_results, list) or not evidence_auditor_results
    ):
        errors.append("EvidenceAuditor live artifacts require evidence-auditor-validation-results.json")
    if evidence_auditor_invocation_ids and (
        not isinstance(canonical_audit_findings, list)
    ):
        errors.append("EvidenceAuditor live artifacts require canonical-audit-findings.json")
    selected_ids = {
        item.get("invocation_id")
        for item in selected or []
        if isinstance(item, dict)
    }
    role_result_ids = {
        item.get("invocation_id")
        for item in role_results or []
        if isinstance(item, dict)
    }
    normalization_result_ids = {
        item.get("invocation_id")
        for item in normalization_results or []
        if isinstance(item, dict)
    }
    normalized_response_ids = {
        item.get("invocation_id")
        for item in normalized_responses or []
        if isinstance(item, dict)
    }
    schedule_result_ids = {
        item.get("invocation_id")
        for item in schedule_results or []
        if isinstance(item, dict)
    }
    for invocation_id in specialist_invocation_ids:
        if invocation_id not in selected_ids:
            errors.append(f"missing selected evidence record entry for {invocation_id}")
        if invocation_id not in role_result_ids:
            errors.append(f"missing role validation result for {invocation_id}")
        if invocation_id not in normalization_result_ids:
            errors.append(f"missing claim normalization result for {invocation_id}")
        if invocation_id not in normalized_response_ids:
            errors.append(f"missing normalized structured response for {invocation_id}")
    for invocation_id in schedule_invocation_ids:
        if invocation_id not in schedule_result_ids:
            errors.append(f"missing schedule semantic validation result for {invocation_id}")
    errors.extend(
        _validate_claim_normalization_artifacts(
            specialist_invocation_ids=specialist_invocation_ids,
            parsed_responses=parsed_responses,
            normalization_results=normalization_results,
            normalized_responses=normalized_responses,
        )
    )
    return errors


def _validate_claim_normalization_artifacts(
    *,
    specialist_invocation_ids: list[str],
    parsed_responses: Any,
    normalization_results: Any,
    normalized_responses: Any,
) -> list[str]:
    if not all(isinstance(payload, list) for payload in [parsed_responses, normalization_results, normalized_responses]):
        return []
    errors: list[str] = []
    parsed_by_id = {
        item.get("invocation_id"): item.get("parsed_response")
        for item in parsed_responses
        if isinstance(item, dict)
    }
    normalization_by_id = {
        item.get("invocation_id"): item
        for item in normalization_results
        if isinstance(item, dict)
    }
    normalized_by_id = {
        item.get("invocation_id"): item.get("normalized_response")
        for item in normalized_responses
        if isinstance(item, dict)
    }
    for invocation_id in specialist_invocation_ids:
        parsed = parsed_by_id.get(invocation_id)
        normalization = normalization_by_id.get(invocation_id)
        normalized = normalized_by_id.get(invocation_id)
        if not isinstance(parsed, dict) or not isinstance(normalization, dict) or not isinstance(normalized, dict):
            continue
        if parsed.get("agent_role") == "EvidenceAuditor" and _has_nested_auditor_claims(parsed):
            continue
        parsed_claims = parsed.get("claims", {})
        raw_claims = normalization.get("raw_claims", {})
        normalized_claims = normalization.get("normalized_claims", {})
        normalized_response_claims = normalized.get("claims", {})
        if parsed_claims != raw_claims:
            errors.append(f"claim normalization raw_claims do not match parsed response for {invocation_id}")
        if normalized_response_claims != normalized_claims:
            errors.append(f"normalized response claims do not match normalization result for {invocation_id}")
        conflicts = normalization.get("conflicts", [])
        if conflicts and normalization.get("valid") is True:
            errors.append(f"claim normalization conflicts must invalidate normalization for {invocation_id}")
        conflicted_keys = {
            conflict.get("canonical_key")
            for conflict in conflicts
            if isinstance(conflict, dict)
        }
        for alias in normalization.get("applied_aliases", []):
            if not isinstance(alias, dict):
                continue
            raw_key = alias.get("raw_key")
            canonical_key = alias.get("canonical_key")
            if raw_key not in raw_claims:
                errors.append(f"applied alias {raw_key} is missing from raw_claims for {invocation_id}")
            if canonical_key not in normalized_claims and canonical_key not in conflicted_keys:
                errors.append(
                    f"applied alias {raw_key} does not trace to normalized claim {canonical_key} for {invocation_id}"
                )
    return errors


def _validate_live_synthesis_handoff_artifacts(loaded_payloads: dict[str, Any]) -> list[str]:
    invocations = loaded_payloads.get("invocation-records.json")
    if not isinstance(invocations, list):
        return []
    has_specialists = any(
        isinstance(invocation, dict)
        and invocation.get("agent_role")
        in {"ScheduleExpert", "CommercialExpert", "EvidenceAuditor", "RiskExpert"}
        for invocation in invocations
    )
    has_synthesis = any(
        isinstance(invocation, dict)
        and invocation.get("agent_role") in {"RecoveryPlanner", "ArbiterAgent"}
        for invocation in invocations
    )
    if not (has_specialists and has_synthesis):
        return []
    errors: list[str] = []
    envelope = loaded_payloads.get("validated-findings-envelope.json")
    excluded = loaded_payloads.get("excluded-findings.json")
    synthesis_inputs = loaded_payloads.get("synthesis-input.json")
    recommendation_state = loaded_payloads.get("recommendation-authorization-state.json")
    parsed_responses = loaded_payloads.get("parsed-structured-responses.json")
    for filename, payload, expected_type in [
        ("validated-findings-envelope.json", envelope, list),
        ("excluded-findings.json", excluded, list),
        ("synthesis-input.json", synthesis_inputs, list),
        ("recommendation-authorization-state.json", recommendation_state, dict),
    ]:
        if not isinstance(payload, expected_type):
            errors.append(f"live specialist synthesis artifacts require {filename}")
    if not isinstance(envelope, list) or not isinstance(excluded, list):
        return errors
    specialist_invocation_ids = {
        invocation.get("invocation_id")
        for invocation in invocations
        if isinstance(invocation, dict)
        and invocation.get("agent_role")
        in {"ScheduleExpert", "CommercialExpert", "EvidenceAuditor", "RiskExpert"}
    }
    for item in envelope:
        if not isinstance(item, dict):
            continue
        if item.get("invocation_id") not in specialist_invocation_ids:
            errors.append(f"validated finding references unknown specialist invocation {item.get('invocation_id')}")
        if item.get("eligible_for_synthesis") is not True:
            errors.append(f"validated finding must be eligible for synthesis: {item.get('canonical_claim_key')}")
        if not item.get("canonical_claim_key"):
            errors.append("validated finding missing canonical_claim_key")
    for item in excluded:
        if not isinstance(item, dict):
            continue
        if item.get("eligible_for_synthesis") is not False:
            errors.append(f"excluded finding must not be eligible for synthesis: {item.get('canonical_claim_key')}")
        if not item.get("exclusion_reason"):
            errors.append(f"excluded finding missing exclusion_reason: {item.get('canonical_claim_key')}")
    if isinstance(synthesis_inputs, list) and synthesis_inputs:
        latest_input = synthesis_inputs[-1]
        if isinstance(latest_input, dict) and isinstance(recommendation_state, dict):
            input_state = latest_input.get("recommendation_authorization_state")
            if isinstance(input_state, dict) and input_state != recommendation_state:
                errors.append("recommendation-authorization-state.json does not match latest synthesis input")
            if recommendation_state.get("recommendation_available") is True and not recommendation_state.get("recommended_option_id"):
                errors.append("available recommendation requires recommended_option_id")
            final_response = _latest_recovery_response(parsed_responses)
            if (
                isinstance(final_response, dict)
                and final_response.get("human_confirmation_required") is True
                and final_response.get("onsite_status_contradiction_detected") is True
            ):
                if recommendation_state.get("authorization_status") == "ready_for_authorization":
                    errors.append(
                        "authorization cannot be ready while human confirmation is required and onsite contradiction is unresolved"
                    )
                if not recommendation_state.get("blocking_human_request"):
                    errors.append("blocked authorization requires blocking_human_request")
                if "equipment_onsite_status" not in recommendation_state.get("unresolved_contradictions", []):
                    errors.append("blocked authorization requires unresolved equipment_onsite_status contradiction")
    return errors


def _latest_recovery_response(parsed_responses: Any) -> dict[str, Any] | None:
    if not isinstance(parsed_responses, list):
        return None
    for item in reversed(parsed_responses):
        if not isinstance(item, dict):
            continue
        response = item.get("parsed_response")
        if isinstance(response, dict) and response.get("schema_version") == "project-recovery-council.qwen.recovery-analysis-response.v1":
            return response
    return None


def _has_nested_auditor_claims(payload: dict[str, Any]) -> bool:
    claims = payload.get("claims")
    citations = payload.get("citations")
    return (
        isinstance(claims, dict)
        and isinstance(citations, dict)
        and any(isinstance(value, dict) for value in claims.values())
        and any(isinstance(value, dict) for value in citations.values())
    )


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
