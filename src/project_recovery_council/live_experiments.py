"""Opt-in live Qwen smoke, agent, and single-variant execution helpers."""

from __future__ import annotations

import json
import shutil
import subprocess
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any

from project_recovery_council.claim_normalization import (
    ClaimNormalizationResult,
    claim_normalization_metrics,
    normalize_claim_keys,
    normalize_response_payload,
)
from project_recovery_council.evidence_auditor import (
    CanonicalAuditFinding,
    EvidenceAuditorValidationResult,
    audit_findings_to_response_payload,
    validate_and_convert_evidence_auditor_response,
)
from project_recovery_council.evaluation import evaluate_model_result
from project_recovery_council.experiment_artifacts import (
    ExperimentArtifactEntry,
    ExperimentArtifactManifest,
    validate_experiment_artifacts,
)
from project_recovery_council.experiment_contracts import (
    AgentInvocation,
    AgentRole,
    EVIDENCE_AUDITOR_RESPONSE_SCHEMA,
    EvaluationReport,
    ExperimentConfig,
    ExperimentVariant,
    LIVE_SMOKE_RESPONSE_SCHEMA,
    RECOVERY_ANALYSIS_RESPONSE_SCHEMA,
    SCHEMA_REGISTRY,
    SPECIALIST_FINDING_RESPONSE_SCHEMA,
)
from project_recovery_council.experiments import build_experiment_plan
from project_recovery_council.fixtures import CaseBundle, load_equipment_delay_case
from project_recovery_council.model_client import ModelRequest, ModelResult
from project_recovery_council.prompt_catalog import PROMPT_VERSION
from project_recovery_council.prompt_rendering import (
    render_agent_prompt,
    stable_sha256_model_schema,
    stable_sha256_text,
)
from project_recovery_council.qwen_client import QwenModelClient
from project_recovery_council.qwen_config import QwenProviderConfig
from project_recovery_council.redaction import redact_value
from project_recovery_council.role_scope import (
    InvocationPurpose,
    RoleValidationResult,
    role_compliance_metrics,
    selected_evidence_record_ids,
    validate_role_scope,
)
from project_recovery_council.schedule_semantics import (
    ScheduleSemanticValidationResult,
    schedule_semantic_metrics,
    validate_schedule_semantics,
)
from project_recovery_council.serialization import sha256_file, write_json
from project_recovery_council.workflow import DEFAULT_CASE_PATH


LIVE_ARTIFACT_ROOT = Path("experiment-artifacts") / "live"

AGENT_RESPONSE_SCHEMAS = {
    AgentRole.GENERALIST.value: RECOVERY_ANALYSIS_RESPONSE_SCHEMA,
    AgentRole.SCHEDULE_EXPERT.value: SPECIALIST_FINDING_RESPONSE_SCHEMA,
    AgentRole.COMMERCIAL_EXPERT.value: SPECIALIST_FINDING_RESPONSE_SCHEMA,
    AgentRole.EVIDENCE_AUDITOR.value: EVIDENCE_AUDITOR_RESPONSE_SCHEMA,
    AgentRole.RISK_EXPERT.value: SPECIALIST_FINDING_RESPONSE_SCHEMA,
    AgentRole.RECOVERY_PLANNER.value: RECOVERY_ANALYSIS_RESPONSE_SCHEMA,
    AgentRole.DIRECTOR.value: "project-recovery-council.qwen.director-routing-response.v1",
    AgentRole.ARBITER.value: "project-recovery-council.qwen.arbiter-response.v1",
}


def assert_live_ready(config: QwenProviderConfig, *, allow_network: bool) -> None:
    if not allow_network:
        raise ValueError("live execution requires --allow-network")
    if config.read_api_key() is None:
        raise ValueError(f"missing required credential environment variable: {config.api_key_env_var}")


def run_live_smoke(
    *,
    config: QwenProviderConfig,
    allow_network: bool,
    artifacts_root: Path | str = LIVE_ARTIFACT_ROOT,
    experiment_id: str | None = None,
    replace_existing: bool = False,
    client: QwenModelClient | None = None,
) -> Path:
    assert_live_ready(config, allow_network=allow_network)
    selected_id = experiment_id or _timestamped_id("live-smoke")
    _assert_live_artifact_path_writable(artifacts_root, selected_id, replace_existing=replace_existing)
    prompt = _render_smoke_prompt(config.model_identifier)
    request = ModelRequest(
        model_identifier=config.model_identifier,
        system_instructions="Return only the requested JSON object. Do not include private reasoning.",
        user_payload=prompt,
        expected_response_schema=LIVE_SMOKE_RESPONSE_SCHEMA,
        generation_parameters={"temperature": config.temperature, "seed": config.seed},
        correlation_id=selected_id,
        metadata={"command": "live-smoke", "prompt_version": "smoke-v1"},
    )
    selected_client = client or QwenModelClient(config, schema_registry=SCHEMA_REGISTRY)
    result = selected_client.generate(request)
    invocation = AgentInvocation(
        invocation_id=f"INV-{selected_id}",
        variant=ExperimentVariant.SINGLE_GENERALIST,
        invocation_purpose=InvocationPurpose.LIVE_SMOKE.value,
        agent_role="LiveSmoke",
        prompt_id="LiveSmoke.v1",
        request=request,
        result=result,
    )
    return write_live_artifacts(
        experiment_id=selected_id,
        case_id="live-smoke",
        config=config,
        prompt_records=[
            {
                "prompt_id": "LiveSmoke.v1",
                "prompt_sha256": stable_sha256_text(prompt),
                "schema_id": LIVE_SMOKE_RESPONSE_SCHEMA,
                "schema_sha256": stable_sha256_model_schema(SCHEMA_REGISTRY[LIVE_SMOKE_RESPONSE_SCHEMA]),
            }
        ],
        schedule_semantic_validation_results=[],
        invocations=[invocation],
        results=[result],
        evaluation_report=None,
        artifacts_root=artifacts_root,
        replace_existing=replace_existing,
    )


def run_live_agent(
    *,
    agent_role: str,
    config: QwenProviderConfig,
    allow_network: bool,
    case_path: Path | str = DEFAULT_CASE_PATH,
    artifacts_root: Path | str = LIVE_ARTIFACT_ROOT,
    experiment_id: str | None = None,
    replace_existing: bool = False,
    client: QwenModelClient | None = None,
) -> Path:
    assert_live_ready(config, allow_network=allow_network)
    if agent_role not in AGENT_RESPONSE_SCHEMAS:
        raise ValueError(f"unsupported live agent role: {agent_role}")
    bundle = load_equipment_delay_case(case_path)
    schema_id = AGENT_RESPONSE_SCHEMAS[agent_role]
    selected_id = experiment_id or _timestamped_id(f"live-agent-{agent_role}")
    _assert_live_artifact_path_writable(artifacts_root, selected_id, replace_existing=replace_existing)
    prompt = render_agent_prompt(
        bundle=bundle,
        agent_role=agent_role,
        expected_response_schema=schema_id,
        correlation_id=selected_id,
        experiment_variant=ExperimentVariant.DYNAMIC_EXPERT_COUNCIL,
        invocation_purpose=InvocationPurpose.STANDALONE_LIVE_AGENT,
    )
    selected_record_ids = selected_evidence_record_ids(bundle, agent_role)
    request = ModelRequest(
        model_identifier=config.model_identifier,
        system_instructions="You are a Project Recovery Council live agent. Return one JSON object only.",
        user_payload=prompt,
        expected_response_schema=schema_id,
        generation_parameters={"temperature": config.temperature, "seed": config.seed},
        correlation_id=selected_id,
        metadata={
            "command": "live-agent",
            "agent_role": agent_role,
            "prompt_version": PROMPT_VERSION,
            "invocation_purpose": InvocationPurpose.STANDALONE_LIVE_AGENT.value,
            "experiment_variant": None,
            "selected_evidence_record_ids": selected_record_ids,
        },
    )
    selected_client = client or QwenModelClient(config, schema_registry=SCHEMA_REGISTRY)
    result = selected_client.generate(request)
    invocation = AgentInvocation(
        invocation_id=f"INV-{selected_id}",
        variant=ExperimentVariant.DYNAMIC_EXPERT_COUNCIL,
        invocation_purpose=InvocationPurpose.STANDALONE_LIVE_AGENT.value,
        agent_role=agent_role,
        prompt_id=f"{agent_role}.{PROMPT_VERSION}",
        request=request,
        result=result,
    )
    evidence_auditor_validation_results: list[EvidenceAuditorValidationResult] = []
    canonical_audit_findings: list[CanonicalAuditFinding] = []
    if agent_role == AgentRole.EVIDENCE_AUDITOR.value:
        audit_result = validate_and_convert_evidence_auditor_response(
            invocation_id=invocation.invocation_id,
            response_payload=result.parsed_response,
            bundle=bundle,
        )
        normalized_payload = audit_findings_to_response_payload(
            response_payload=result.parsed_response,
            validation=audit_result,
        )
        raw_claims = result.parsed_response.get("claims", {}) if isinstance(result.parsed_response, dict) else {}
        normalized_claims = normalized_payload.get("claims", {}) if isinstance(normalized_payload, dict) else {}
        normalization = ClaimNormalizationResult(
            invocation_id=invocation.invocation_id,
            role=agent_role,
            raw_claims=raw_claims if isinstance(raw_claims, dict) else {},
            normalized_claims=normalized_claims if isinstance(normalized_claims, dict) else {},
            applied_aliases=[],
            unknown_claim_keys=[],
            conflicts=[],
            valid=audit_result.valid,
        )
        role_validation = RoleValidationResult(
            role=agent_role,
            invocation_id=invocation.invocation_id,
            valid=audit_result.valid,
            allowed_claims=[
                f"{finding.audited_agent}.{finding.audited_claim_key}"
                for finding in audit_result.canonical_findings
            ],
            prohibited_claims=[] if audit_result.valid else list(audit_result.errors),
            allowed_warnings=[],
            prohibited_warnings=[],
            citation_policy_violations=[],
            evidence_scope_violations=[],
            concise_findings=["evidence auditor response contract valid" if audit_result.valid else "evidence auditor response contract invalid"],
        )
        evidence_auditor_validation_results = [audit_result]
        canonical_audit_findings = list(audit_result.canonical_findings)
    else:
        normalization = normalize_claim_keys(
            invocation_id=invocation.invocation_id,
            role=agent_role,
            response_payload=result.parsed_response,
        )
        normalized_payload = normalize_response_payload(result.parsed_response, normalization)
        role_validation = validate_role_scope(
            role=agent_role,
            invocation_id=invocation.invocation_id,
            response_payload=normalized_payload,
            selected_record_ids=selected_record_ids,
            bundle=bundle,
        )
    schedule_validation = (
        validate_schedule_semantics(
            invocation_id=invocation.invocation_id,
            response_payload=normalized_payload,
            bundle=bundle,
        )
        if agent_role == AgentRole.SCHEDULE_EXPERT.value
        else None
    )
    report = _evaluation_for_result(result, bundle=bundle, fixture_id=selected_id)
    return write_live_artifacts(
        experiment_id=selected_id,
        case_id=bundle.case.case_id,
        config=config,
        prompt_records=[_prompt_record(agent_role, prompt, schema_id)],
        selected_evidence_records=[
            {"invocation_id": invocation.invocation_id, "agent_role": agent_role, "record_ids": selected_record_ids}
        ],
        role_validation_results=[role_validation],
        schedule_semantic_validation_results=[schedule_validation] if schedule_validation else [],
        claim_normalization_results=[normalization],
        normalized_structured_responses=[
            {
                "invocation_id": invocation.invocation_id,
                "normalization_valid": normalization.valid,
                "normalized_response": normalized_payload,
            }
        ],
        evidence_auditor_validation_results=evidence_auditor_validation_results,
        canonical_audit_findings=canonical_audit_findings,
        invocations=[invocation],
        results=[result],
        evaluation_report=report,
        artifacts_root=artifacts_root,
        replace_existing=replace_existing,
    )


def run_live_variant(
    *,
    variant: ExperimentVariant | str,
    config: QwenProviderConfig,
    allow_network: bool,
    case_path: Path | str = DEFAULT_CASE_PATH,
    artifacts_root: Path | str = LIVE_ARTIFACT_ROOT,
    experiment_id: str | None = None,
    replace_existing: bool = False,
    client: QwenModelClient | None = None,
) -> Path:
    from project_recovery_council.live_variant_runner import run_controlled_live_variant

    return run_controlled_live_variant(
        variant=variant,
        config=config,
        allow_network=allow_network,
        case_path=case_path,
        artifacts_root=artifacts_root,
        experiment_id=experiment_id,
        replace_existing=replace_existing,
        client=client,
    )


def write_live_artifacts(
    *,
    experiment_id: str,
    case_id: str,
    config: QwenProviderConfig,
    prompt_records: list[dict[str, Any]],
    selected_evidence_records: list[dict[str, Any]] | None = None,
    role_validation_results: list[RoleValidationResult] | None = None,
    schedule_semantic_validation_results: list[ScheduleSemanticValidationResult] | None = None,
    claim_normalization_results: list[ClaimNormalizationResult] | None = None,
    normalized_structured_responses: list[dict[str, Any]] | None = None,
    evidence_auditor_validation_results: list[EvidenceAuditorValidationResult] | None = None,
    canonical_audit_findings: list[CanonicalAuditFinding] | None = None,
    invocations: list[AgentInvocation],
    results: list[ModelResult],
    evaluation_report: EvaluationReport | None,
    artifacts_root: Path | str = LIVE_ARTIFACT_ROOT,
    replace_existing: bool = False,
) -> Path:
    root = Path(artifacts_root) / experiment_id
    if root.exists():
        if not replace_existing:
            raise FileExistsError(f"live experiment artifact path already exists: {root.as_posix()}")
        shutil.rmtree(root)
    root.mkdir(parents=True, exist_ok=False)

    reproducibility = _reproducibility(config, prompt_records, case_id)
    raw_provider_responses = [
        {
            "invocation_id": invocation.invocation_id,
            "raw_response_text": result.raw_response_text,
            "raw_provider_response": result.provider_metadata.get("raw_provider_response"),
            "provider_headers": result.provider_metadata.get("provider_headers"),
        }
        for invocation, result in zip(invocations, results)
    ]
    parsed = [
        {
            "invocation_id": invocation.invocation_id,
            "parsed_response": result.parsed_response,
            "finish_status": result.finish_status.value,
        }
        for invocation, result in zip(invocations, results)
    ]
    validation = [
        {
            "invocation_id": invocation.invocation_id,
            "schema_id": invocation.request.expected_response_schema,
            "schema_valid": not result.validation_errors and result.parsed_response is not None,
            "validation_errors": result.validation_errors,
            "failure": result.failure.model_dump(mode="json") if result.failure else None,
        }
        for invocation, result in zip(invocations, results)
    ]
    usage = [
        {
            "invocation_id": invocation.invocation_id,
            "input_tokens": result.input_token_count,
            "output_tokens": result.output_token_count,
            "total_tokens": result.total_token_count,
            "latency_seconds": result.latency_seconds,
            "provider_request_id": result.provider_metadata.get("provider_request_id"),
            "structured_output_mode": result.provider_metadata.get("actual_structured_output_mode"),
        }
        for invocation, result in zip(invocations, results)
    ]
    retry_history = [
        {
            "invocation_id": invocation.invocation_id,
            "retry_count": result.retry_count,
            "retry_history": result.provider_metadata.get("retry_history", []),
        }
        for invocation, result in zip(invocations, results)
    ]
    role_results = role_validation_results or []
    schedule_results = schedule_semantic_validation_results or []
    normalization_results = claim_normalization_results or []
    normalized_responses = normalized_structured_responses or []
    evidence_auditor_results = evidence_auditor_validation_results or []
    audit_findings = canonical_audit_findings or []
    experiment_config = ExperimentConfig(
        experiment_id=experiment_id,
        case_id=case_id,
        fixture_id="live-provider",
        variant=invocations[0].variant if invocations else ExperimentVariant.SINGLE_GENERALIST,
        invocation_purpose=invocations[0].invocation_purpose if invocations else None,
        execution_plan=build_experiment_plan(invocations[0].variant if invocations else ExperimentVariant.SINGLE_GENERALIST),
        live_provider_enabled=True,
        simulated_outputs=False,
    )
    files: list[tuple[str, str, Any]] = [
        ("sanitized-provider-config", "sanitized-provider-config.json", config.sanitized()),
        ("experiment-config", "experiment-config.json", experiment_config),
        ("rendered-prompt-hashes", "rendered-prompt-hashes.json", prompt_records),
        ("selected-evidence-records", "selected-evidence-records.json", selected_evidence_records or []),
        ("role-validation-results", "role-validation-results.json", role_results),
        ("claim-normalization-results", "claim-normalization-results.json", normalization_results),
        ("normalized-structured-responses", "normalized-structured-responses.json", normalized_responses),
        ("schedule-semantic-validation", "schedule-semantic-validation.json", schedule_results),
        (
            "evidence-auditor-validation-results",
            "evidence-auditor-validation-results.json",
            evidence_auditor_results,
        ),
        ("canonical-audit-findings", "canonical-audit-findings.json", audit_findings),
        ("invocation-records", "invocation-records.json", invocations),
        ("raw-provider-responses", "raw-provider-responses.json", raw_provider_responses),
        ("parsed-structured-responses", "parsed-structured-responses.json", parsed),
        ("validation-results", "validation-results.json", validation),
        ("token-usage", "token-usage.json", usage),
        ("retry-history", "retry-history.json", retry_history),
        ("role-compliance-metrics", "role-compliance-metrics.json", role_compliance_metrics(role_results)),
        (
            "claim-normalization-metrics",
            "claim-normalization-metrics.json",
            claim_normalization_metrics(normalization_results),
        ),
        ("schedule-semantic-metrics", "schedule-semantic-metrics.json", schedule_semantic_metrics(schedule_results)),
        ("reproducibility", "reproducibility.json", reproducibility),
    ]
    if evaluation_report is not None:
        files.append(("evaluation-results", "evaluation-results.json", evaluation_report))

    secrets = [config.read_api_key() or "dummy-secret-not-present"]
    for _, filename, payload in files:
        write_json(root / filename, redact_value(payload, secrets))

    generated_at = _now()
    entries = [
        ExperimentArtifactEntry(
            name=name,
            relative_path=filename,
            schema_id=_live_schema_id_for(filename),
            sha256=sha256_file(root / filename),
            generated_at=generated_at,
        )
        for name, filename, _ in files
    ]
    write_json(
        root / "artifact-manifest.json",
        ExperimentArtifactManifest(
            experiment_id=experiment_id,
            case_id=case_id,
            generated_at=generated_at,
            artifacts=entries,
        ),
    )
    inspection = validate_experiment_artifacts(root)
    if not inspection.passed:
        raise RuntimeError(f"live artifact validation failed: {inspection.errors}")
    return root


def _evaluation_for_result(
    result: ModelResult,
    *,
    bundle: CaseBundle,
    fixture_id: str,
) -> EvaluationReport | None:
    if result.parsed_response is None:
        return None
    if result.parsed_response.get("schema_version") != RECOVERY_ANALYSIS_RESPONSE_SCHEMA:
        return None
    return evaluate_model_result(
        result,
        variant=ExperimentVariant.SINGLE_GENERALIST,
        bundle=bundle,
        fixture_id=fixture_id,
        report_provenance="live_provider",
    )


def _assert_live_artifact_path_writable(
    artifacts_root: Path | str,
    experiment_id: str,
    *,
    replace_existing: bool,
) -> None:
    root = Path(artifacts_root) / experiment_id
    if root.exists() and not replace_existing:
        raise FileExistsError(f"live experiment artifact path already exists: {root.as_posix()}")


def _render_smoke_prompt(model_identifier: str) -> str:
    return json.dumps(
        {
            "instruction": "Return one small JSON object only.",
            "schema": {
                "schema_version": LIVE_SMOKE_RESPONSE_SCHEMA,
                "status": "ok",
                "model_identifier": model_identifier,
                "short_message": "string under 200 characters",
            },
            "no_private_reasoning": True,
        },
        indent=2,
        sort_keys=True,
    )


def _prompt_record(agent_role: str, prompt: str, schema_id: str) -> dict[str, Any]:
    return {
        "prompt_id": f"{agent_role}.{PROMPT_VERSION}",
        "prompt_version": PROMPT_VERSION,
        "prompt_sha256": stable_sha256_text(prompt),
        "schema_id": schema_id,
        "schema_sha256": stable_sha256_model_schema(SCHEMA_REGISTRY[schema_id]),
    }


def _reproducibility(
    config: QwenProviderConfig,
    prompt_records: list[dict[str, Any]],
    case_id: str,
) -> dict[str, Any]:
    return {
        "model_identifier": config.model_identifier,
        "endpoint_host": config.endpoint_host,
        "configuration_excluding_secrets": config.sanitized(),
        "prompt_records": prompt_records,
        "evidence_bundle_hash": _evidence_bundle_hash(DEFAULT_CASE_PATH),
        "case_id": case_id,
        "temperature": config.temperature,
        "seed": config.seed,
        "execution_timestamp": _now(),
        "package_version": _package_version(),
        "git_commit": _git_output(["git", "rev-parse", "HEAD"]),
        "git_dirty": _git_dirty(),
        "hosted_model_reproducibility_note": (
            "Hosted model outputs may be nondeterministic; this metadata supports auditability "
            "but does not claim perfect reproducibility."
        ),
    }


def _evidence_bundle_hash(path: Path | str) -> str:
    root = Path(path)
    digest = sha256()
    for file_path in sorted(root.iterdir()):
        if file_path.is_file():
            digest.update(file_path.name.encode("utf-8"))
            digest.update(file_path.read_bytes())
    return digest.hexdigest()


def _package_version() -> str:
    try:
        from importlib.metadata import version

        return version("project-recovery-council-qwen")
    except Exception:
        return "editable-or-uninstalled"


def _git_output(command: list[str]) -> str | None:
    try:
        result = subprocess.run(command, text=True, capture_output=True, check=False)
    except Exception:
        return None
    return result.stdout.strip() if result.returncode == 0 else None


def _git_dirty() -> bool | None:
    status = _git_output(["git", "status", "--short"])
    return None if status is None else bool(status)


def _live_schema_id_for(filename: str) -> str:
    if filename == "experiment-config.json":
        return "project-recovery-council.qwen.experiment-config.v1"
    if filename == "invocation-records.json":
        return "project-recovery-council.qwen.agent-invocations.v1"
    if filename == "evaluation-results.json":
        return "project-recovery-council.qwen.evaluation-report.v1"
    return {
        "sanitized-provider-config.json": "project-recovery-council.qwen.live-sanitized-provider-config.v1",
        "rendered-prompt-hashes.json": "project-recovery-council.qwen.live-rendered-prompt-hashes.v1",
        "selected-evidence-records.json": "project-recovery-council.qwen.live-selected-evidence-records.v1",
        "role-validation-results.json": "project-recovery-council.qwen.live-role-validation-results.v1",
        "claim-normalization-results.json": "project-recovery-council.qwen.live-claim-normalization-results.v1",
        "normalized-structured-responses.json": "project-recovery-council.qwen.live-normalized-structured-responses.v1",
        "schedule-semantic-validation.json": "project-recovery-council.qwen.live-schedule-semantic-validation.v1",
        "evidence-auditor-validation-results.json": (
            "project-recovery-council.qwen.live-evidence-auditor-validation-results.v1"
        ),
        "canonical-audit-findings.json": "project-recovery-council.qwen.live-canonical-audit-findings.v1",
        "schedule-semantic-metrics.json": "project-recovery-council.qwen.live-schedule-semantic-metrics.v1",
        "raw-provider-responses.json": "project-recovery-council.qwen.live-raw-provider-responses.v1",
        "parsed-structured-responses.json": "project-recovery-council.qwen.live-parsed-structured-responses.v1",
        "validation-results.json": "project-recovery-council.qwen.live-validation-results.v1",
        "token-usage.json": "project-recovery-council.qwen.live-token-usage.v1",
        "retry-history.json": "project-recovery-council.qwen.live-retry-history.v1",
        "role-compliance-metrics.json": "project-recovery-council.qwen.live-role-compliance-metrics.v1",
        "claim-normalization-metrics.json": "project-recovery-council.qwen.live-claim-normalization-metrics.v1",
        "reproducibility.json": "project-recovery-council.qwen.live-reproducibility.v1",
    }[filename]


def _timestamped_id(prefix: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{prefix}-{stamp}"


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
