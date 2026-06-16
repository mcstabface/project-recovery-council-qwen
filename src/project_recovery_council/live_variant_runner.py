"""Controlled opt-in live execution for Qwen competition variants."""

from __future__ import annotations

import json
import shutil
import subprocess
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from time import monotonic
from typing import Any, Callable

from pydantic import Field, ValidationError

from project_recovery_council.claim_normalization import (
    ClaimNormalizationResult,
    claim_normalization_metrics,
    normalize_claim_keys,
    normalize_response_payload,
)
from project_recovery_council.contracts import ContractModel
from project_recovery_council.evaluation import evaluate_model_result
from project_recovery_council.experiment_artifacts import (
    ExperimentArtifactEntry,
    ExperimentArtifactManifest,
    validate_experiment_artifacts,
)
from project_recovery_council.experiment_contracts import (
    ARBITER_RESPONSE_SCHEMA,
    DIRECTOR_ROUTING_RESPONSE_SCHEMA,
    RECOVERY_ANALYSIS_RESPONSE_SCHEMA,
    SCHEMA_REGISTRY,
    SPECIALIST_FINDING_RESPONSE_SCHEMA,
    AgentInvocation,
    AgentRole,
    DirectorRoutingResponse,
    EvaluationReport,
    ExperimentConfig,
    ExperimentVariant,
    MetricResult,
)
from project_recovery_council.experiments import build_experiment_plan
from project_recovery_council.fixtures import CaseBundle, load_equipment_delay_case
from project_recovery_council.model_client import FinishStatus, ModelClient, ModelRequest, ModelResult
from project_recovery_council.prompt_catalog import PROMPT_VERSION, load_prompt_catalog
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
    select_evidence_for_role,
    validate_role_scope,
)
from project_recovery_council.schedule_semantics import (
    ScheduleSemanticValidationResult,
    schedule_semantic_metrics,
    validate_schedule_semantics,
)
from project_recovery_council.serialization import read_json, sha256_file, to_jsonable, write_json
from project_recovery_council.workflow import DEFAULT_CASE_PATH


LIVE_VARIANT_ARTIFACT_ROOT = Path("experiment-artifacts") / "live"
LIVE_COMPARISON_ARTIFACT_ROOT = Path("experiment-artifacts") / "live-comparisons"

SPECIALIST_ROLES = {
    AgentRole.SCHEDULE_EXPERT.value,
    AgentRole.COMMERCIAL_EXPERT.value,
    AgentRole.EVIDENCE_AUDITOR.value,
    AgentRole.RISK_EXPERT.value,
}

DYNAMIC_DIRECTOR_SELECTABLE_ROLES = {
    AgentRole.SCHEDULE_EXPERT.value,
    AgentRole.COMMERCIAL_EXPERT.value,
    AgentRole.RISK_EXPERT.value,
}

FINAL_RESPONSE_ROLES = {
    AgentRole.GENERALIST.value,
    AgentRole.RECOVERY_PLANNER.value,
}


class LiveRunControls(ContractModel):
    max_invocation_count: int = Field(default=8, ge=1)
    max_total_input_tokens: int | None = Field(default=100000, ge=0)
    max_total_output_tokens: int | None = Field(default=50000, ge=0)
    max_elapsed_seconds: float | None = Field(default=300.0, ge=0.0)
    max_retries_per_invocation: int = Field(default=2, ge=0)
    stop_after_invocation: int | None = Field(default=None, ge=1)


class DomainSemanticValidationResult(ContractModel):
    invocation_id: str = Field(min_length=1)
    role: str = Field(min_length=1)
    validator: str = Field(min_length=1)
    implemented: bool
    valid: bool | None = None
    checked_fields: list[str] = Field(default_factory=list)
    semantic_violations: list[str] = Field(default_factory=list)
    concise_findings: list[str] = Field(default_factory=list)


class LiveVariantSummary(ContractModel):
    experiment_id: str = Field(min_length=1)
    case_id: str = Field(min_length=1)
    variant: ExperimentVariant
    status: str = Field(pattern="^(completed|incomplete|failed)$")
    completed: bool
    stopped_by_limit: str | None = None
    failure_reason: str | None = None
    total_invocation_count: int = Field(ge=0)
    final_invocation_id: str | None = None
    final_response_available: bool = False
    evaluation_available: bool = False
    role_scope_compliance_rate: float | None = None
    semantic_validation_compliance_rate: float | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    latency_seconds: float | None = None
    retry_count: int = Field(default=0, ge=0)


class LiveComparisonVariantRow(ContractModel):
    variant: ExperimentVariant
    experiment_id: str = Field(min_length=1)
    path: str = Field(min_length=1)
    completed: bool
    stopped_by_limit: str | None = None
    total_invocation_count: int = Field(ge=0)
    required_fact_accuracy: float | None = None
    schedule_correctness: float | None = None
    commercial_correctness: float | None = None
    citation_precision: float | None = None
    citation_recall: float | None = None
    contradiction_detection: float | None = None
    unsupported_claim_count: float | None = None
    correct_human_escalation: float | None = None
    preferred_recovery_option: float | None = None
    schema_valid_response_rate: float | None = None
    role_scope_compliance: float | None = None
    semantic_validation_compliance: float | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    latency_seconds: float | None = None
    retry_count: int = Field(default=0, ge=0)


class LiveComparisonReport(ContractModel):
    schema_version: str = "project-recovery-council.qwen.live-comparison-report.v1"
    comparison_id: str = Field(min_length=1)
    case_id: str = Field(min_length=1)
    model_configuration: dict[str, Any] = Field(default_factory=dict)
    rows: list[LiveComparisonVariantRow]
    limitations: list[str] = Field(default_factory=list)


class LiveVariantRun:
    def __init__(
        self,
        *,
        experiment_id: str,
        variant: ExperimentVariant,
        bundle: CaseBundle,
        config: QwenProviderConfig,
        controls: LiveRunControls,
        client: ModelClient,
        time_func: Callable[[], float],
    ) -> None:
        self.experiment_id = experiment_id
        self.variant = variant
        self.bundle = bundle
        self.config = config
        self.controls = controls
        self.client = client
        self.time_func = time_func
        self.started = time_func()

        self.plan = build_experiment_plan(variant, model_identifier=config.model_identifier)
        self.invocations: list[AgentInvocation] = []
        self.results: list[ModelResult] = []
        self.prompt_records: list[dict[str, Any]] = []
        self.selected_evidence_records: list[dict[str, Any]] = []
        self.role_results: list[RoleValidationResult] = []
        self.normalization_results: list[ClaimNormalizationResult] = []
        self.normalized_responses: list[dict[str, Any]] = []
        self.schedule_results: list[ScheduleSemanticValidationResult] = []
        self.domain_results: list[DomainSemanticValidationResult] = []
        self.routing_decisions: list[dict[str, Any]] = []
        self.disagreements: list[dict[str, Any]] = []
        self.final_result: ModelResult | None = None
        self.final_invocation_id: str | None = None
        self.evaluation_report: EvaluationReport | None = None
        self.stopped_by_limit: str | None = None
        self.failure_reason: str | None = None

    @property
    def completed(self) -> bool:
        return self.evaluation_report is not None and self.stopped_by_limit is None and self.failure_reason is None

    def run(self) -> None:
        if self.variant == ExperimentVariant.SINGLE_GENERALIST:
            self._run_single_generalist()
        elif self.variant == ExperimentVariant.FIXED_EXPERT_CHAIN:
            self._run_fixed_chain()
        elif self.variant == ExperimentVariant.DYNAMIC_EXPERT_COUNCIL:
            self._run_dynamic_council()
        else:
            self.failure_reason = f"unsupported live AI variant: {self.variant.value}"

    def _run_single_generalist(self) -> None:
        result = self._invoke(
            role=AgentRole.GENERALIST.value,
            schema_id=RECOVERY_ANALYSIS_RESPONSE_SCHEMA,
            step_id="generalist_final_analysis",
            prompt=self._render_standard_prompt(AgentRole.GENERALIST.value, RECOVERY_ANALYSIS_RESPONSE_SCHEMA),
            selected_record_ids=selected_evidence_record_ids(self.bundle, AgentRole.GENERALIST.value),
        )
        if result is not None:
            self._set_final_result(result, self.invocations[-1].invocation_id)

    def _run_fixed_chain(self) -> None:
        specialist_context: list[dict[str, Any]] = []
        for role in [
            AgentRole.SCHEDULE_EXPERT.value,
            AgentRole.COMMERCIAL_EXPERT.value,
            AgentRole.EVIDENCE_AUDITOR.value,
            AgentRole.RISK_EXPERT.value,
        ]:
            result = self._invoke_specialist(role=role, step_id=f"fixed_{role}")
            if result is None:
                return
            specialist_context.append(self._context_for_last_invocation())
            if self._should_stop_after_last_invocation():
                return
        prompt = self._render_synthesis_prompt(
            role=AgentRole.RECOVERY_PLANNER.value,
            schema_id=RECOVERY_ANALYSIS_RESPONSE_SCHEMA,
            specialist_context=specialist_context,
            routing_context=[],
            arbitration_context=[],
        )
        result = self._invoke(
            role=AgentRole.RECOVERY_PLANNER.value,
            schema_id=RECOVERY_ANALYSIS_RESPONSE_SCHEMA,
            step_id="fixed_recovery_synthesis",
            prompt=prompt,
            selected_record_ids=[],
        )
        if result is not None:
            self._set_final_result(result, self.invocations[-1].invocation_id)

    def _run_dynamic_council(self) -> None:
        director_result = self._invoke(
            role=AgentRole.DIRECTOR.value,
            schema_id=DIRECTOR_ROUTING_RESPONSE_SCHEMA,
            step_id="director_routing",
            prompt=self._render_director_prompt(),
            selected_record_ids=selected_evidence_record_ids(self.bundle, AgentRole.DIRECTOR.value),
        )
        if director_result is None:
            return
        selected_roles = self._director_selected_roles(director_result)
        if selected_roles is None:
            return
        specialist_context: list[dict[str, Any]] = []
        for role in selected_roles:
            result = self._invoke_specialist(role=role, step_id=f"dynamic_{role}")
            if result is None:
                return
            specialist_context.append(self._context_for_last_invocation())
            if self._should_stop_after_last_invocation():
                return
        audit_result = self._invoke_specialist(
            role=AgentRole.EVIDENCE_AUDITOR.value,
            step_id="dynamic_evidence_audit",
            specialist_context=specialist_context,
        )
        if audit_result is None:
            return
        specialist_context.append(self._context_for_last_invocation())
        if self._should_stop_after_last_invocation():
            return
        arbitration_context = self._validation_issues()
        arbiter_prompt = self._render_synthesis_prompt(
            role=AgentRole.ARBITER.value,
            schema_id=ARBITER_RESPONSE_SCHEMA,
            specialist_context=specialist_context,
            routing_context=self.routing_decisions,
            arbitration_context=arbitration_context,
        )
        arbiter_result = self._invoke(
            role=AgentRole.ARBITER.value,
            schema_id=ARBITER_RESPONSE_SCHEMA,
            step_id="dynamic_arbitration",
            prompt=arbiter_prompt,
            selected_record_ids=[],
        )
        if arbiter_result is None:
            return
        if arbiter_result.parsed_response:
            self.disagreements.extend(arbiter_result.parsed_response.get("unresolved_disagreements", []))
        if self._should_stop_after_last_invocation():
            return
        final_prompt = self._render_synthesis_prompt(
            role=AgentRole.RECOVERY_PLANNER.value,
            schema_id=RECOVERY_ANALYSIS_RESPONSE_SCHEMA,
            specialist_context=specialist_context,
            routing_context=self.routing_decisions,
            arbitration_context=[arbiter_result.parsed_response],
        )
        final_result = self._invoke(
            role=AgentRole.RECOVERY_PLANNER.value,
            schema_id=RECOVERY_ANALYSIS_RESPONSE_SCHEMA,
            step_id="dynamic_recovery_recommendation",
            prompt=final_prompt,
            selected_record_ids=[],
        )
        if final_result is not None:
            self._set_final_result(final_result, self.invocations[-1].invocation_id)

    def _invoke_specialist(
        self,
        *,
        role: str,
        step_id: str,
        specialist_context: list[dict[str, Any]] | None = None,
    ) -> ModelResult | None:
        prompt = (
            self._render_contextual_specialist_prompt(role, specialist_context)
            if specialist_context
            else self._render_standard_prompt(role, SPECIALIST_FINDING_RESPONSE_SCHEMA)
        )
        selected_record_ids = selected_evidence_record_ids(self.bundle, role)
        result = self._invoke(
            role=role,
            schema_id=SPECIALIST_FINDING_RESPONSE_SCHEMA,
            step_id=step_id,
            prompt=prompt,
            selected_record_ids=selected_record_ids,
        )
        if result is None:
            return None
        self._validate_specialist(role=role, result=result, selected_record_ids=selected_record_ids)
        return result

    def _invoke(
        self,
        *,
        role: str,
        schema_id: str,
        step_id: str,
        prompt: str,
        selected_record_ids: list[str],
    ) -> ModelResult | None:
        if not self._can_start_invocation():
            return None
        sequence = len(self.invocations) + 1
        invocation_id = f"INV-{self.experiment_id}-{sequence:02d}-{_slug(role)}"
        request = ModelRequest(
            model_identifier=self.config.model_identifier,
            system_instructions="You are a Project Recovery Council live experiment agent. Return one JSON object only.",
            user_payload=prompt,
            expected_response_schema=schema_id,
            generation_parameters={"temperature": self.config.temperature, "seed": self.config.seed},
            correlation_id=f"{self.experiment_id}-{sequence:02d}",
            metadata={
                "command": "live-variant",
                "variant": self.variant.value,
                "agent_role": role,
                "step_id": step_id,
                "prompt_version": PROMPT_VERSION,
                "invocation_purpose": self.variant.value,
                "selected_evidence_record_ids": selected_record_ids,
            },
        )
        result = self.client.generate(request)
        invocation = AgentInvocation(
            invocation_id=invocation_id,
            variant=self.variant,
            invocation_purpose=self.variant.value,
            agent_role=role,
            prompt_id=f"{role}.{PROMPT_VERSION}",
            request=request,
            result=result,
        )
        self.invocations.append(invocation)
        self.results.append(result)
        self.prompt_records.append(
            {
                "invocation_id": invocation_id,
                "prompt_id": f"{role}.{PROMPT_VERSION}",
                "prompt_version": PROMPT_VERSION,
                "prompt_sha256": stable_sha256_text(prompt),
                "schema_id": schema_id,
                "schema_sha256": stable_sha256_model_schema(SCHEMA_REGISTRY[schema_id]),
            }
        )
        self.selected_evidence_records.append(
            {"invocation_id": invocation_id, "agent_role": role, "record_ids": selected_record_ids}
        )
        self._record_post_invocation_limits(result)
        if result.retry_count > self.controls.max_retries_per_invocation:
            self.stopped_by_limit = "max_retries_per_invocation"
        if result.finish_status not in {FinishStatus.COMPLETED}:
            self.failure_reason = f"failed invocation {invocation_id}: {result.finish_status.value}"
        return result

    def _validate_specialist(self, *, role: str, result: ModelResult, selected_record_ids: list[str]) -> None:
        invocation_id = self.invocations[-1].invocation_id
        normalization = normalize_claim_keys(
            invocation_id=invocation_id,
            role=role,
            response_payload=result.parsed_response,
        )
        normalized_payload = normalize_response_payload(result.parsed_response, normalization)
        role_result = validate_role_scope(
            role=role,
            invocation_id=invocation_id,
            response_payload=normalized_payload,
            selected_record_ids=selected_record_ids,
            bundle=self.bundle,
        )
        self.normalization_results.append(normalization)
        self.normalized_responses.append(
            {
                "invocation_id": invocation_id,
                "normalization_valid": normalization.valid,
                "normalized_response": normalized_payload,
            }
        )
        self.role_results.append(role_result)
        if role == AgentRole.SCHEDULE_EXPERT.value:
            schedule_result = validate_schedule_semantics(
                invocation_id=invocation_id,
                response_payload=normalized_payload,
                bundle=self.bundle,
            )
            self.schedule_results.append(schedule_result)
            self.domain_results.append(
                DomainSemanticValidationResult(
                    invocation_id=invocation_id,
                    role=role,
                    validator="ScheduleExpertSemanticValidator.v1",
                    implemented=True,
                    valid=schedule_result.valid,
                    checked_fields=schedule_result.checked_fields,
                    semantic_violations=schedule_result.semantic_violations,
                    concise_findings=schedule_result.concise_findings,
                )
            )
        else:
            self.domain_results.append(
                DomainSemanticValidationResult(
                    invocation_id=invocation_id,
                    role=role,
                    validator="not_implemented",
                    implemented=False,
                    valid=None,
                    concise_findings=["no specialized semantic validator implemented for this role"],
                )
            )

    def _set_final_result(self, result: ModelResult, invocation_id: str) -> None:
        self.final_result = result
        self.final_invocation_id = invocation_id
        if result.parsed_response and result.parsed_response.get("schema_version") == RECOVERY_ANALYSIS_RESPONSE_SCHEMA:
            self.evaluation_report = evaluate_model_result(
                result,
                variant=self.variant,
                bundle=self.bundle,
                fixture_id=self.experiment_id,
                invocation_results=self.results,
            )
        else:
            self.failure_reason = self.failure_reason or "final response unavailable or not evaluable"

    def _director_selected_roles(self, result: ModelResult) -> list[str] | None:
        if result.finish_status != FinishStatus.COMPLETED or result.parsed_response is None:
            self.failure_reason = "invalid Director routing response"
            return None
        try:
            routing = DirectorRoutingResponse.model_validate(result.parsed_response)
        except ValidationError as exc:
            self.failure_reason = f"invalid Director routing response: {exc.errors()}"
            return None
        selected = list(dict.fromkeys(routing.selected_experts))
        unknown = [role for role in selected if role not in DYNAMIC_DIRECTOR_SELECTABLE_ROLES and role != AgentRole.EVIDENCE_AUDITOR.value]
        if unknown:
            self.failure_reason = f"Director selected unknown or unsupported roles: {unknown}"
            return None
        selected = [role for role in selected if role in DYNAMIC_DIRECTOR_SELECTABLE_ROLES]
        if not selected:
            self.failure_reason = "Director selected no executable specialists"
            return None
        self.routing_decisions.append(
            {
                "invocation_id": self.invocations[-1].invocation_id,
                "selected_agent_roles": selected,
                "skipped_agent_roles": routing.skipped_experts,
                "routing_rationale": routing.routing_rationale,
                "evidence_record_ids": sorted({record_id for ids in routing.citations.values() for record_id in ids}),
            }
        )
        return selected

    def _can_start_invocation(self) -> bool:
        if self.failure_reason or self.stopped_by_limit:
            return False
        if len(self.invocations) >= self.controls.max_invocation_count:
            self.stopped_by_limit = "max_invocation_count"
            return False
        if self.controls.max_elapsed_seconds is not None and self.time_func() - self.started > self.controls.max_elapsed_seconds:
            self.stopped_by_limit = "max_elapsed_seconds"
            return False
        return True

    def _record_post_invocation_limits(self, result: ModelResult) -> None:
        if self.controls.stop_after_invocation is not None and len(self.invocations) >= self.controls.stop_after_invocation:
            self.stopped_by_limit = "stop_after_invocation"
        input_tokens, output_tokens, _total_tokens = _token_totals(self.results)
        if (
            self.controls.max_total_input_tokens is not None
            and input_tokens is not None
            and input_tokens > self.controls.max_total_input_tokens
        ):
            self.stopped_by_limit = "max_total_input_tokens"
        if (
            self.controls.max_total_output_tokens is not None
            and output_tokens is not None
            and output_tokens > self.controls.max_total_output_tokens
        ):
            self.stopped_by_limit = "max_total_output_tokens"
        if self.controls.max_elapsed_seconds is not None and self.time_func() - self.started > self.controls.max_elapsed_seconds:
            self.stopped_by_limit = "max_elapsed_seconds"

    def _should_stop_after_last_invocation(self) -> bool:
        return bool(self.stopped_by_limit or self.failure_reason)

    def _render_standard_prompt(self, role: str, schema_id: str) -> str:
        return render_agent_prompt(
            bundle=self.bundle,
            agent_role=role,
            expected_response_schema=schema_id,
            correlation_id=self.experiment_id,
            experiment_variant=self.variant,
            invocation_purpose=self.variant.value,
            scoped_evidence=True,
        )

    def _render_director_prompt(self) -> str:
        catalog = load_prompt_catalog(PROMPT_VERSION)
        schema_model = SCHEMA_REGISTRY[DIRECTOR_ROUTING_RESPONSE_SCHEMA]
        records = select_evidence_for_role(self.bundle, AgentRole.DIRECTOR.value)
        payload = {
            "correlation_id": self.experiment_id,
            "case_id": self.bundle.case.case_id,
            "experiment_variant": self.variant.value,
            "invocation_purpose": self.variant.value,
            "invocation_role": AgentRole.DIRECTOR.value,
            "prompt_version": PROMPT_VERSION,
            "selected_evidence_record_ids": [record.record_id for record in records],
            "routing_constraint": "Select only relevant executable specialists; do not default to every expert.",
            "executable_specialist_roles": sorted(DYNAMIC_DIRECTOR_SELECTABLE_ROLES),
            "expected_response_schema": DIRECTOR_ROUTING_RESPONSE_SCHEMA,
            "evidence_metadata": [
                {
                    "record_id": record.record_id,
                    "record_type": record.record_type,
                    "title": record.title,
                    "summary": record.summary,
                }
                for record in records
            ],
            "expected_output_json_schema": schema_model.model_json_schema(),
        }
        return (
            f"{catalog[AgentRole.DIRECTOR.value].content}\n\n"
            "## Live routing packet\n"
            f"{json.dumps(to_jsonable(payload), indent=2, sort_keys=True)}\n"
        )

    def _render_contextual_specialist_prompt(
        self,
        role: str,
        specialist_context: list[dict[str, Any]] | None,
    ) -> str:
        base = self._render_standard_prompt(role, SPECIALIST_FINDING_RESPONSE_SCHEMA)
        return (
            f"{base}\n"
            "## Prior validated specialist findings\n"
            f"{json.dumps(to_jsonable(specialist_context or []), indent=2, sort_keys=True)}\n"
        )

    def _render_synthesis_prompt(
        self,
        *,
        role: str,
        schema_id: str,
        specialist_context: list[dict[str, Any]],
        routing_context: list[dict[str, Any]],
        arbitration_context: list[Any],
    ) -> str:
        catalog = load_prompt_catalog(PROMPT_VERSION)
        schema_model = SCHEMA_REGISTRY[schema_id]
        payload = {
            "correlation_id": self.experiment_id,
            "case_id": self.bundle.case.case_id,
            "experiment_variant": self.variant.value,
            "invocation_purpose": self.variant.value,
            "invocation_role": role,
            "prompt_version": PROMPT_VERSION,
            "selected_evidence_record_ids": [],
            "expected_response_schema": schema_id,
            "evidence_policy": "Use validated specialist findings and validation records; complete raw evidence is intentionally omitted.",
            "routing_decisions": routing_context,
            "validated_specialist_findings": specialist_context,
            "arbitration_context": arbitration_context,
            "expected_output_json_schema": schema_model.model_json_schema(),
        }
        return (
            f"{catalog[role].content}\n\n"
            "## Live synthesis packet\n"
            f"{json.dumps(to_jsonable(payload), indent=2, sort_keys=True)}\n"
        )

    def _context_for_last_invocation(self) -> dict[str, Any]:
        invocation = self.invocations[-1]
        return {
            "invocation_id": invocation.invocation_id,
            "agent_role": invocation.agent_role,
            "schema_valid": not invocation.result.validation_errors and invocation.result.parsed_response is not None,
            "parsed_response": invocation.result.parsed_response,
            "normalization": _last_for_invocation(self.normalization_results, invocation.invocation_id),
            "role_validation": _last_for_invocation(self.role_results, invocation.invocation_id),
            "domain_semantic_validation": _last_for_invocation(self.domain_results, invocation.invocation_id),
        }

    def _validation_issues(self) -> list[dict[str, Any]]:
        issues = []
        for role_result in self.role_results:
            if not role_result.valid:
                issues.append({"kind": "role_scope", "result": role_result.model_dump(mode="json")})
        for domain_result in self.domain_results:
            if domain_result.valid is False:
                issues.append({"kind": "domain_semantic", "result": domain_result.model_dump(mode="json")})
        return issues

    def summary(self) -> LiveVariantSummary:
        input_tokens, output_tokens, total_tokens = _token_totals(self.results)
        role_metrics = role_compliance_metrics(self.role_results)
        schedule_metrics = schedule_semantic_metrics(self.schedule_results)
        status = "completed" if self.completed else "incomplete"
        if self.failure_reason and not self.stopped_by_limit:
            status = "failed"
        return LiveVariantSummary(
            experiment_id=self.experiment_id,
            case_id=self.bundle.case.case_id,
            variant=self.variant,
            status=status,
            completed=self.completed,
            stopped_by_limit=self.stopped_by_limit,
            failure_reason=self.failure_reason,
            total_invocation_count=len(self.invocations),
            final_invocation_id=self.final_invocation_id,
            final_response_available=self.final_result is not None and self.final_result.parsed_response is not None,
            evaluation_available=self.evaluation_report is not None,
            role_scope_compliance_rate=role_metrics["scope_compliance_rate"],
            semantic_validation_compliance_rate=schedule_metrics["schedule_semantic_compliance_rate"],
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            latency_seconds=_sum_optional_float([result.latency_seconds for result in self.results]),
            retry_count=sum(result.retry_count for result in self.results),
        )


def run_controlled_live_variant(
    *,
    variant: ExperimentVariant | str,
    config: QwenProviderConfig,
    allow_network: bool,
    controls: LiveRunControls | None = None,
    case_path: Path | str = DEFAULT_CASE_PATH,
    artifacts_root: Path | str = LIVE_VARIANT_ARTIFACT_ROOT,
    experiment_id: str | None = None,
    replace_existing: bool = False,
    client: ModelClient | None = None,
    time_func: Callable[[], float] = monotonic,
) -> Path:
    selected_variant = ExperimentVariant(variant)
    if selected_variant == ExperimentVariant.DETERMINISTIC_ORACLE:
        raise ValueError("live-variant does not execute the deterministic oracle")
    if not allow_network:
        raise ValueError("live execution requires --allow-network")
    if config.read_api_key() is None:
        raise ValueError(f"missing required credential environment variable: {config.api_key_env_var}")
    selected_id = experiment_id or _timestamped_id(f"live-variant-{selected_variant.value}")
    root = Path(artifacts_root) / selected_id
    if root.exists() and not replace_existing:
        raise FileExistsError(f"live experiment artifact path already exists: {root.as_posix()}")
    bundle = load_equipment_delay_case(case_path)
    selected_client = client or QwenModelClient(config, schema_registry=SCHEMA_REGISTRY)
    run = LiveVariantRun(
        experiment_id=selected_id,
        variant=selected_variant,
        bundle=bundle,
        config=config,
        controls=controls or LiveRunControls(),
        client=selected_client,
        time_func=time_func,
    )
    run.run()
    return write_live_variant_artifacts(
        run,
        artifacts_root=artifacts_root,
        replace_existing=replace_existing,
    )


def write_live_variant_artifacts(
    run: LiveVariantRun,
    *,
    artifacts_root: Path | str,
    replace_existing: bool = False,
) -> Path:
    root = Path(artifacts_root) / run.experiment_id
    if root.exists():
        if not replace_existing:
            raise FileExistsError(f"live experiment artifact path already exists: {root.as_posix()}")
        shutil.rmtree(root)
    root.mkdir(parents=True, exist_ok=False)

    summary = run.summary()
    evaluation_payload = {
        "available": run.evaluation_report is not None,
        "report": run.evaluation_report.model_dump(mode="json") if run.evaluation_report else None,
    }
    experiment_config = ExperimentConfig(
        experiment_id=run.experiment_id,
        case_id=run.bundle.case.case_id,
        fixture_id="live-provider",
        variant=run.variant,
        invocation_purpose=run.variant.value,
        execution_plan=run.plan,
        live_provider_enabled=True,
        simulated_outputs=False,
    )
    files: list[tuple[str, str, Any, bool]] = [
        ("sanitized-provider-config", "sanitized-provider-config.json", run.config.sanitized(), True),
        ("experiment-config", "experiment-config.json", experiment_config, True),
        ("execution-plan", "execution-plan.json", run.plan, True),
        ("rendered-prompt-hashes", "rendered-prompt-hashes.json", run.prompt_records, True),
        ("selected-evidence-records", "selected-evidence-records.json", run.selected_evidence_records, True),
        ("claim-normalization-results", "claim-normalization-results.json", run.normalization_results, bool(run.normalization_results)),
        ("normalized-structured-responses", "normalized-structured-responses.json", run.normalized_responses, bool(run.normalized_responses)),
        ("role-validation-results", "role-validation-results.json", run.role_results, bool(run.role_results)),
        ("schedule-semantic-validation", "schedule-semantic-validation.json", run.schedule_results, bool(run.schedule_results)),
        ("domain-semantic-validation-results", "domain-semantic-validation-results.json", run.domain_results, bool(run.domain_results)),
        ("invocation-records", "invocation-records.json", run.invocations, True),
        ("raw-provider-responses", "raw-provider-responses.json", _raw_provider_responses(run.invocations), True),
        ("parsed-structured-responses", "parsed-structured-responses.json", _parsed_responses(run.invocations), True),
        ("validation-results", "validation-results.json", _validation_results(run.invocations), True),
        ("token-usage", "token-usage.json", _token_usage(run.invocations), True),
        ("retry-history", "retry-history.json", _retry_history(run.invocations), True),
        ("routing-decisions", "routing-decisions.json", run.routing_decisions, run.variant == ExperimentVariant.DYNAMIC_EXPERT_COUNCIL),
        ("disagreement-records", "disagreement-records.json", run.disagreements, False),
        ("final-variant-result", "final-variant-result.json", summary, True),
        ("evaluation-results", "evaluation-results.json", evaluation_payload, True),
        ("role-compliance-metrics", "role-compliance-metrics.json", role_compliance_metrics(run.role_results), bool(run.role_results)),
        (
            "claim-normalization-metrics",
            "claim-normalization-metrics.json",
            claim_normalization_metrics(run.normalization_results),
            bool(run.normalization_results),
        ),
        ("schedule-semantic-metrics", "schedule-semantic-metrics.json", schedule_semantic_metrics(run.schedule_results), bool(run.schedule_results)),
        ("reproducibility", "reproducibility.json", _reproducibility(run), True),
    ]

    secrets = [run.config.read_api_key() or "dummy-secret-not-present"]
    for _, filename, payload, _required in files:
        write_json(root / filename, redact_value(payload, secrets))

    generated_at = _now()
    entries = [
        ExperimentArtifactEntry(
            name=name,
            relative_path=filename,
            schema_id=_live_variant_schema_id_for(filename),
            sha256=sha256_file(root / filename),
            generated_at=generated_at,
            required=required,
        )
        for name, filename, _payload, required in files
    ]
    write_json(
        root / "artifact-manifest.json",
        ExperimentArtifactManifest(
            experiment_id=run.experiment_id,
            case_id=run.bundle.case.case_id,
            generated_at=generated_at,
            artifacts=entries,
        ),
    )
    inspection = validate_experiment_artifacts(root)
    if not inspection.passed:
        raise RuntimeError(f"live variant artifact validation failed: {inspection.errors}")
    return root


def compare_live_variant_runs(
    *,
    generalist_path: Path | str,
    fixed_chain_path: Path | str,
    dynamic_council_path: Path | str,
    output_root: Path | str = LIVE_COMPARISON_ARTIFACT_ROOT,
    comparison_id: str | None = None,
    allow_incomplete: bool = False,
) -> Path:
    paths = {
        ExperimentVariant.SINGLE_GENERALIST: Path(generalist_path),
        ExperimentVariant.FIXED_EXPERT_CHAIN: Path(fixed_chain_path),
        ExperimentVariant.DYNAMIC_EXPERT_COUNCIL: Path(dynamic_council_path),
    }
    rows = []
    case_id = None
    model_config: dict[str, Any] = {}
    for variant, path in paths.items():
        inspection = validate_experiment_artifacts(path)
        if not inspection.passed and not allow_incomplete:
            raise ValueError(f"invalid live run artifacts for {variant.value}: {inspection.errors}")
        summary = LiveVariantSummary.model_validate(read_json(path / "final-variant-result.json"))
        if not summary.completed and not allow_incomplete:
            raise ValueError(f"incomplete live run for {variant.value}: {path.as_posix()}")
        config = read_json(path / "sanitized-provider-config.json")
        if not model_config:
            model_config = {
                "model_identifier": config.get("model_identifier"),
                "base_url": config.get("base_url"),
                "provider_region_label": config.get("provider_region_label"),
                "temperature": config.get("temperature"),
                "seed": config.get("seed"),
            }
        case_id = case_id or summary.case_id
        rows.append(_comparison_row(variant, path, summary))
    report = LiveComparisonReport(
        comparison_id=comparison_id or _timestamped_id("live-comparison"),
        case_id=case_id or "unknown",
        model_configuration=model_config,
        rows=rows,
        limitations=[
            "One live run per variant is not statistically significant.",
            "The deterministic oracle remains the expected-result source and is not an AI competitor.",
            "Provider pricing is omitted unless supplied explicitly elsewhere.",
        ],
    )
    root = Path(output_root) / report.comparison_id
    root.mkdir(parents=True, exist_ok=False)
    write_json(root / "live-comparison-report.json", report)
    (root / "live-comparison-report.md").write_text(_comparison_markdown(report), encoding="utf-8")
    generated_at = _now()
    write_json(
        root / "artifact-manifest.json",
        ExperimentArtifactManifest(
            experiment_id=report.comparison_id,
            case_id=report.case_id,
            generated_at=generated_at,
            artifacts=[
                ExperimentArtifactEntry(
                    name="live-comparison-report",
                    relative_path="live-comparison-report.json",
                    schema_id="project-recovery-council.qwen.live-comparison-report.v1",
                    sha256=sha256_file(root / "live-comparison-report.json"),
                    generated_at=generated_at,
                )
            ],
        ),
    )
    return root


def live_variant_completed(path: Path | str) -> bool:
    summary = LiveVariantSummary.model_validate(read_json(Path(path) / "final-variant-result.json"))
    return summary.completed


def _comparison_row(variant: ExperimentVariant, path: Path, summary: LiveVariantSummary) -> LiveComparisonVariantRow:
    evaluation = read_json(path / "evaluation-results.json")
    metrics = {}
    report = evaluation.get("report") if isinstance(evaluation, dict) else None
    if isinstance(report, dict):
        metrics = {item["metric_id"]: item.get("score") for item in report.get("metric_results", [])}
    role_metrics = read_json(path / "role-compliance-metrics.json")
    schedule_metrics = read_json(path / "schedule-semantic-metrics.json")
    return LiveComparisonVariantRow(
        variant=variant,
        experiment_id=summary.experiment_id,
        path=path.as_posix(),
        completed=summary.completed,
        stopped_by_limit=summary.stopped_by_limit,
        total_invocation_count=summary.total_invocation_count,
        required_fact_accuracy=metrics.get("required_fact_accuracy"),
        schedule_correctness=metrics.get("schedule_impact_accuracy"),
        commercial_correctness=metrics.get("monetary_calculation_accuracy"),
        citation_precision=metrics.get("evidence_citation_precision"),
        citation_recall=metrics.get("evidence_citation_recall"),
        contradiction_detection=metrics.get("contradiction_detection"),
        unsupported_claim_count=metrics.get("unsupported_claim_count"),
        correct_human_escalation=metrics.get("correct_human_escalation"),
        preferred_recovery_option=metrics.get("preferred_recovery_option"),
        schema_valid_response_rate=metrics.get("schema_valid_response_rate"),
        role_scope_compliance=role_metrics.get("scope_compliance_rate") if isinstance(role_metrics, dict) else None,
        semantic_validation_compliance=schedule_metrics.get("schedule_semantic_compliance_rate")
        if isinstance(schedule_metrics, dict)
        else None,
        input_tokens=summary.input_tokens,
        output_tokens=summary.output_tokens,
        total_tokens=summary.total_tokens,
        latency_seconds=summary.latency_seconds,
        retry_count=summary.retry_count,
    )


def _comparison_markdown(report: LiveComparisonReport) -> str:
    lines = [
        f"# Live Comparison: {report.comparison_id}",
        "",
        "One run per variant is not statistically significant.",
        "",
        "| Variant | Complete | Invocations | Required facts | Schedule | Commercial | Cit. precision | Cit. recall | Unsupported | Human escalation | Preferred option | Tokens | Latency | Retries |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in report.rows:
        lines.append(
            "| "
            f"{row.variant.value} | {row.completed} | {row.total_invocation_count} | "
            f"{_fmt(row.required_fact_accuracy)} | {_fmt(row.schedule_correctness)} | "
            f"{_fmt(row.commercial_correctness)} | {_fmt(row.citation_precision)} | "
            f"{_fmt(row.citation_recall)} | {_fmt(row.unsupported_claim_count)} | "
            f"{_fmt(row.correct_human_escalation)} | {_fmt(row.preferred_recovery_option)} | "
            f"{row.total_tokens if row.total_tokens is not None else ''} | "
            f"{_fmt(row.latency_seconds)} | {row.retry_count} |"
        )
    return "\n".join(lines) + "\n"


def _fmt(value: float | None) -> str:
    return "" if value is None else f"{value:.3g}"


def _token_totals(results: list[ModelResult]) -> tuple[int | None, int | None, int | None]:
    return (
        _sum_optional([result.input_token_count for result in results]),
        _sum_optional([result.output_token_count for result in results]),
        _sum_optional([result.total_token_count for result in results]),
    )


def _sum_optional(values: list[int | None]) -> int | None:
    known = [value for value in values if value is not None]
    return sum(known) if known else None


def _sum_optional_float(values: list[float | None]) -> float | None:
    known = [value for value in values if value is not None]
    return sum(known) if known else None


def _last_for_invocation(items: list[Any], invocation_id: str) -> dict[str, Any] | None:
    for item in reversed(items):
        if getattr(item, "invocation_id", None) == invocation_id:
            return item.model_dump(mode="json")
    return None


def _raw_provider_responses(invocations: list[AgentInvocation]) -> list[dict[str, Any]]:
    return [
        {
            "invocation_id": invocation.invocation_id,
            "raw_response_text": invocation.result.raw_response_text,
            "raw_provider_response": invocation.result.provider_metadata.get("raw_provider_response"),
            "provider_headers": invocation.result.provider_metadata.get("provider_headers"),
        }
        for invocation in invocations
    ]


def _parsed_responses(invocations: list[AgentInvocation]) -> list[dict[str, Any]]:
    return [
        {
            "invocation_id": invocation.invocation_id,
            "parsed_response": invocation.result.parsed_response,
            "finish_status": invocation.result.finish_status.value,
        }
        for invocation in invocations
    ]


def _validation_results(invocations: list[AgentInvocation]) -> list[dict[str, Any]]:
    return [
        {
            "invocation_id": invocation.invocation_id,
            "schema_id": invocation.request.expected_response_schema,
            "schema_valid": not invocation.result.validation_errors and invocation.result.parsed_response is not None,
            "validation_errors": invocation.result.validation_errors,
            "failure": invocation.result.failure.model_dump(mode="json") if invocation.result.failure else None,
        }
        for invocation in invocations
    ]


def _token_usage(invocations: list[AgentInvocation]) -> list[dict[str, Any]]:
    return [
        {
            "invocation_id": invocation.invocation_id,
            "input_tokens": invocation.result.input_token_count,
            "output_tokens": invocation.result.output_token_count,
            "total_tokens": invocation.result.total_token_count,
            "latency_seconds": invocation.result.latency_seconds,
            "provider_request_id": invocation.result.provider_metadata.get("provider_request_id"),
            "structured_output_mode": invocation.result.provider_metadata.get("actual_structured_output_mode"),
        }
        for invocation in invocations
    ]


def _retry_history(invocations: list[AgentInvocation]) -> list[dict[str, Any]]:
    return [
        {
            "invocation_id": invocation.invocation_id,
            "retry_count": invocation.result.retry_count,
            "retry_history": invocation.result.provider_metadata.get("retry_history", []),
        }
        for invocation in invocations
    ]


def _reproducibility(run: LiveVariantRun) -> dict[str, Any]:
    return {
        "model_identifier": run.config.model_identifier,
        "endpoint_host": run.config.endpoint_host,
        "configuration_excluding_secrets": run.config.sanitized(),
        "prompt_records": run.prompt_records,
        "evidence_bundle_hash": _evidence_bundle_hash(DEFAULT_CASE_PATH),
        "case_id": run.bundle.case.case_id,
        "variant": run.variant.value,
        "temperature": run.config.temperature,
        "seed": run.config.seed,
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


def _live_variant_schema_id_for(filename: str) -> str:
    if filename == "experiment-config.json":
        return "project-recovery-council.qwen.experiment-config.v1"
    if filename == "invocation-records.json":
        return "project-recovery-council.qwen.agent-invocations.v1"
    return {
        "sanitized-provider-config.json": "project-recovery-council.qwen.live-sanitized-provider-config.v1",
        "execution-plan.json": "project-recovery-council.qwen.live-execution-plan.v1",
        "rendered-prompt-hashes.json": "project-recovery-council.qwen.live-rendered-prompt-hashes.v1",
        "selected-evidence-records.json": "project-recovery-council.qwen.live-selected-evidence-records.v1",
        "role-validation-results.json": "project-recovery-council.qwen.live-role-validation-results.v1",
        "claim-normalization-results.json": "project-recovery-council.qwen.live-claim-normalization-results.v1",
        "normalized-structured-responses.json": "project-recovery-council.qwen.live-normalized-structured-responses.v1",
        "schedule-semantic-validation.json": "project-recovery-council.qwen.live-schedule-semantic-validation.v1",
        "domain-semantic-validation-results.json": "project-recovery-council.qwen.live-domain-semantic-validation-results.v1",
        "schedule-semantic-metrics.json": "project-recovery-council.qwen.live-schedule-semantic-metrics.v1",
        "raw-provider-responses.json": "project-recovery-council.qwen.live-raw-provider-responses.v1",
        "parsed-structured-responses.json": "project-recovery-council.qwen.live-parsed-structured-responses.v1",
        "validation-results.json": "project-recovery-council.qwen.live-validation-results.v1",
        "token-usage.json": "project-recovery-council.qwen.live-token-usage.v1",
        "retry-history.json": "project-recovery-council.qwen.live-retry-history.v1",
        "routing-decisions.json": "project-recovery-council.qwen.live-routing-decisions.v1",
        "disagreement-records.json": "project-recovery-council.qwen.live-disagreement-records.v1",
        "final-variant-result.json": "project-recovery-council.qwen.live-final-variant-result.v1",
        "evaluation-results.json": "project-recovery-council.qwen.live-evaluation-results.v1",
        "role-compliance-metrics.json": "project-recovery-council.qwen.live-role-compliance-metrics.v1",
        "claim-normalization-metrics.json": "project-recovery-council.qwen.live-claim-normalization-metrics.v1",
        "reproducibility.json": "project-recovery-council.qwen.live-reproducibility.v1",
    }[filename]


def _slug(value: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "-" for ch in value).strip("-")


def _timestamped_id(prefix: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{prefix}-{stamp}"


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
