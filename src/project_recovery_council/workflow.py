"""Deterministic local workflow runner for Project Recovery Council."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from project_recovery_council.audit import AuditRecorder, DeterministicClock
from project_recovery_council.contracts import (
    CaseStage,
    ConfidenceAssessment,
    Contradiction,
    ExpertFinding,
    ExpertRequest,
    ExpertStatus,
    FinalRecommendation,
    HumanDecision,
    HumanDecisionRequest,
)
from project_recovery_council.director import RuleBasedDirector
from project_recovery_council.fixtures import CaseBundle, load_equipment_delay_case
from project_recovery_council.serialization import write_json
from project_recovery_council.state import (
    ExpertSelection,
    WorkflowConfig,
    WorkflowContext,
    WorkflowStage,
    WorkflowTransitionError,
    validate_transition,
)
from project_recovery_council.stubs import (
    DeterministicCommercialExpert,
    DeterministicEvidenceAuditor,
    DeterministicRecoveryPlanner,
    DeterministicRiskExpert,
    DeterministicScheduleExpert,
)
from project_recovery_council.validation import (
    assert_expected_results,
    build_actual_expected_results,
    evaluate_human_gate_required,
    validate_date_and_duration_consistency,
    validate_evidence_references,
)


DEFAULT_CASE_PATH = Path("sample-data/equipment-delay-case")
DEFAULT_ARTIFACTS_ROOT = Path("session-artifacts/runs")


class WorkflowExecutionError(RuntimeError):
    """Raised when deterministic workflow execution cannot continue."""


@dataclass(frozen=True)
class WorkflowRunResult:
    """Completed or paused workflow result."""

    context: WorkflowContext
    run_path: Path | None = None
    replay_comparison: dict[str, Any] | None = None


def default_workflow_config(
    *,
    case_path: Path | str = DEFAULT_CASE_PATH,
    artifacts_root: Path | str = DEFAULT_ARTIFACTS_ROOT,
    run_id: str = "equipment-delay-standard",
    inject_commercial_failure: bool = False,
    auto_human_decision: bool = True,
) -> WorkflowConfig:
    return WorkflowConfig(
        case_path=Path(case_path),
        artifacts_root=Path(artifacts_root),
        run_id=run_id,
        inject_commercial_failure=inject_commercial_failure,
        auto_human_decision=auto_human_decision,
    )


def validate_fixture_bundle(case_path: Path | str) -> list[str]:
    """Validate fixture consistency without running the workflow."""

    bundle = load_equipment_delay_case(case_path)
    issues = validate_date_and_duration_consistency(bundle)
    references = [record.reference("record") for record in bundle.case.evidence_records]
    issues.extend(validate_evidence_references(bundle, references))
    try:
        assert_expected_results(case_path)
    except AssertionError as exc:
        issues.append(str(exc))
    return issues


class LocalWorkflowRunner:
    """End-to-end deterministic local workflow execution engine."""

    def __init__(
        self,
        config: WorkflowConfig,
        *,
        director: RuleBasedDirector | None = None,
        clock: DeterministicClock | None = None,
    ) -> None:
        self.config = config
        self.director = director or RuleBasedDirector()
        self.clock = clock or DeterministicClock()
        self.context: WorkflowContext | None = None
        self.schedule_expert = DeterministicScheduleExpert()
        self.commercial_expert = DeterministicCommercialExpert(
            fail_first_attempt=config.inject_commercial_failure
        )
        self.risk_expert = DeterministicRiskExpert()
        self.evidence_auditor = DeterministicEvidenceAuditor()
        self.recovery_planner = DeterministicRecoveryPlanner()

    def run(self, *, write_artifacts: bool = True) -> WorkflowRunResult:
        context = self.run_until_human_gate()
        if context.state == WorkflowStage.AWAITING_HUMAN_DECISION:
            if not self.config.auto_human_decision:
                return WorkflowRunResult(context=context)
            self.resume_with_human_decision()
        if self.context is None:
            raise WorkflowExecutionError("workflow context was not initialized")
        result = WorkflowRunResult(context=self.context)
        if write_artifacts:
            run_path = self.write_artifacts(self.context)
            result = WorkflowRunResult(context=self.context, run_path=run_path)
        return result

    def run_until_human_gate(self) -> WorkflowContext:
        if self.context is not None:
            raise WorkflowExecutionError("workflow has already started")
        self.context = self._initialize_context()
        try:
            self._validate_fixture(self.context)
            self._triage(self.context)
            self._run_expert_analysis(self.context)
            self._review_contradictions(self.context)
        except Exception:
            self._mark_failed()
            raise
        return self.context

    def resume_with_human_decision(self, decision: HumanDecision | None = None) -> WorkflowContext:
        context = self._require_context()
        if context.state != WorkflowStage.AWAITING_HUMAN_DECISION:
            raise WorkflowTransitionError(
                f"cannot resume from state {context.state.value}; expected awaiting_human_decision"
            )
        decision = decision or self._simulated_not_onsite_decision(context)
        context.human_decisions.append(decision)
        self._answer_latest_human_request(context)
        context.audit.record(
            "human_decision_received",
            "simulated-human",
            "Human decision confirms the generator skid is not onsite.",
            evidence=decision.evidence,
            metadata={"decision_id": decision.decision_id, "outcome": decision.outcome},
        )
        self._transition(context, WorkflowStage.RECOVERY_PLANNING)
        self._plan_recovery(context)
        return context

    def write_artifacts(self, context: WorkflowContext) -> Path:
        run_path = context.config.artifacts_root / context.config.run_id
        replay_input = self._replay_input(context)
        summary = {
            "run_id": context.config.run_id,
            "case_id": context.bundle.case.case_id,
            "state": context.state.value,
            "inject_commercial_failure": context.config.inject_commercial_failure,
            "selected_experts": context.selections,
            "expert_request_count": len(context.expert_requests),
            "expert_finding_count": len(context.expert_findings),
            "contradiction_count": len(context.contradictions),
            "human_decision_count": len(context.human_decisions),
            "audit_event_count": len(context.audit_events),
            "run_path": run_path,
        }
        write_json(run_path / "run-summary.json", summary)
        write_json(run_path / "audit-events.json", context.audit_events)
        write_json(run_path / "expert-findings.json", context.expert_findings)
        write_json(run_path / "contradictions.json", context.contradictions)
        write_json(run_path / "human-decisions.json", context.human_decisions)
        write_json(run_path / "human-decision-requests.json", context.human_decision_requests)
        write_json(run_path / "draft-recommendation.json", context.draft_recommendation)
        write_json(run_path / "final-recommendation.json", context.final_recommendation)
        write_json(run_path / "replay-input.json", replay_input)
        return run_path

    def _initialize_context(self) -> WorkflowContext:
        bundle = load_equipment_delay_case(self.config.case_path)
        audit = AuditRecorder(bundle.case.case_id, self.clock)
        context = WorkflowContext(config=self.config, bundle=bundle, audit=audit)
        case_record = bundle.evidence_by_id["CASE-INTAKE-001"]
        audit.record(
            "case_created",
            "workflow",
            "Recovery case created from synthetic fixture bundle.",
            evidence=[case_record.reference("record")],
            metadata={"title": bundle.case.title},
        )
        return context

    def _validate_fixture(self, context: WorkflowContext) -> None:
        self._transition(context, WorkflowStage.VALIDATING)
        context.audit.record(
            "fixture_validation_started",
            "workflow",
            "Fixture validation started.",
            metadata={"case_path": context.config.case_path.as_posix()},
        )
        issues = validate_fixture_bundle(context.config.case_path)
        context.validation_issues.extend(issues)
        if issues:
            context.audit.record(
                "fixture_validation_failed",
                "workflow",
                "Fixture validation failed.",
                metadata={"issues": issues},
            )
            raise WorkflowExecutionError(f"fixture validation failed: {issues}")
        context.audit.record(
            "fixture_validation_completed",
            "workflow",
            "Fixture validation completed successfully.",
            metadata={"evidence_record_count": len(context.bundle.case.evidence_records)},
        )

    def _triage(self, context: WorkflowContext) -> None:
        self._transition(context, WorkflowStage.TRIAGING)
        selections = self.director.select_experts(context.bundle)
        context.selections.extend(selections)
        for selection in selections:
            context.audit.record(
                "expert_selected",
                "Director",
                f"{selection.expert_role} selected.",
                metadata={
                    "expert_role": selection.expert_role,
                    "phase": selection.phase,
                    "rationale": selection.rationale,
                },
            )

    def _run_expert_analysis(self, context: WorkflowContext) -> None:
        self._transition(context, WorkflowStage.EXPERT_ANALYSIS)
        for selection in context.selections:
            if selection.phase != "expert_analysis":
                continue
            self._execute_finding_expert(context, selection)

    def _execute_finding_expert(self, context: WorkflowContext, selection: ExpertSelection) -> None:
        attempt = 1
        max_attempts = 2
        while True:
            request = self._expert_request(context, selection, attempt, max_attempts)
            context.expert_requests.append(request)
            context.audit.record(
                "expert_request_created",
                "Director",
                f"Request created for {selection.expert_role}.",
                metadata={
                    "request_id": request.request_id,
                    "expert_role": selection.expert_role,
                    "attempt": attempt,
                },
            )
            context.audit.record(
                "expert_execution_started",
                selection.expert_role,
                f"{selection.expert_role} execution started.",
                metadata={"request_id": request.request_id, "attempt": attempt},
            )
            finding = self._evaluate_expert(selection.expert_role, request, context.bundle)
            context.expert_findings.append(finding)
            if finding.status == ExpertStatus.FAILED:
                context.audit.record(
                    "expert_execution_failed",
                    selection.expert_role,
                    f"{selection.expert_role} execution failed.",
                    metadata={
                        "request_id": request.request_id,
                        "finding_id": finding.finding_id,
                        "failure_reason": finding.failure_reason,
                        "attempt": attempt,
                    },
                )
                if self.director.authorize_retry(request, finding):
                    context.audit.record(
                        "retry_authorized",
                        "Director",
                        f"Retry authorized for {selection.expert_role}.",
                        metadata={
                            "request_id": request.request_id,
                            "next_attempt": attempt + 1,
                            "max_attempts": max_attempts,
                        },
                    )
                    attempt += 1
                    continue
                raise WorkflowExecutionError(f"{selection.expert_role} failed without available retry")
            context.audit.record(
                "expert_execution_completed",
                selection.expert_role,
                f"{selection.expert_role} execution completed.",
                evidence=finding.evidence,
                metadata={
                    "request_id": request.request_id,
                    "finding_id": finding.finding_id,
                    "status": finding.status.value,
                    "attempt": attempt,
                },
            )
            return

    def _evaluate_expert(
        self,
        expert_role: str,
        request: ExpertRequest,
        bundle: CaseBundle,
    ) -> ExpertFinding:
        if expert_role == "ScheduleExpert":
            return self.schedule_expert.evaluate(request, bundle)
        if expert_role == "CommercialExpert":
            return self.commercial_expert.evaluate(request, bundle)
        if expert_role == "RiskExpert":
            return self.risk_expert.evaluate(request, bundle)
        raise WorkflowExecutionError(f"unsupported finding expert role: {expert_role}")

    def _review_contradictions(self, context: WorkflowContext) -> None:
        self._transition(context, WorkflowStage.CONTRADICTION_REVIEW)
        selection = self._selection_for(context, "EvidenceAuditor")
        if selection is None:
            self._transition(context, WorkflowStage.RECOVERY_PLANNING)
            return
        request = self._expert_request(context, selection, 1, 1)
        context.expert_requests.append(request)
        context.audit.record(
            "expert_request_created",
            "Director",
            "Request created for EvidenceAuditor.",
            metadata={"request_id": request.request_id, "expert_role": "EvidenceAuditor", "attempt": 1},
        )
        context.audit.record(
            "expert_execution_started",
            "EvidenceAuditor",
            "EvidenceAuditor execution started.",
            metadata={"request_id": request.request_id, "attempt": 1},
        )
        contradictions = self.evidence_auditor.audit(context.bundle.case, context.bundle)
        context.contradictions.extend(contradictions)
        context.audit.record(
            "expert_execution_completed",
            "EvidenceAuditor",
            "EvidenceAuditor execution completed.",
            metadata={"request_id": request.request_id, "contradiction_count": len(contradictions)},
        )
        for contradiction in contradictions:
            context.audit.record(
                "contradiction_detected",
                "EvidenceAuditor",
                contradiction.summary,
                evidence=contradiction.conflicting_evidence,
                metadata={"contradiction_id": contradiction.contradiction_id, "issue": contradiction.issue},
            )
        if evaluate_human_gate_required(contradictions):
            decision_request = self._human_decision_request(context, contradictions)
            context.human_decision_requests.append(decision_request)
            context.audit.record(
                "human_decision_requested",
                "EvidenceAuditor",
                "Human confirmation requested for contradicted onsite status.",
                evidence=decision_request.evidence,
                metadata={"decision_request_id": decision_request.decision_request_id},
            )
            self._transition(context, WorkflowStage.AWAITING_HUMAN_DECISION)
            return
        self._transition(context, WorkflowStage.RECOVERY_PLANNING)

    def _plan_recovery(self, context: WorkflowContext) -> None:
        selection = self._selection_for(context, "RecoveryPlanner")
        if selection is None:
            raise WorkflowExecutionError("RecoveryPlanner was not selected")
        request = self._expert_request(context, selection, 1, 1)
        context.expert_requests.append(request)
        context.audit.record(
            "expert_request_created",
            "Director",
            "Request created for RecoveryPlanner.",
            metadata={"request_id": request.request_id, "expert_role": "RecoveryPlanner", "attempt": 1},
        )
        context.audit.record(
            "expert_execution_started",
            "RecoveryPlanner",
            "RecoveryPlanner execution started.",
            metadata={"request_id": request.request_id, "attempt": 1},
        )
        base_recommendation = self.recovery_planner.plan(context.bundle.case, context.bundle)
        draft = self._post_human_draft_recommendation(context, base_recommendation)
        context.draft_recommendation = draft
        option = draft.options_considered[0]
        context.audit.record(
            "recovery_option_created",
            "RecoveryPlanner",
            "Accelerated logistics recovery option created.",
            evidence=option.evidence,
            metadata={"option_id": option.option_id, "cost_usd": option.cost_usd},
        )
        context.audit.record(
            "draft_recommendation_created",
            "RecoveryPlanner",
            "Draft recovery recommendation created after human confirmation.",
            evidence=draft.evidence,
            metadata={"recommendation_id": draft.recommendation_id, "approval_status": draft.approval_status},
        )
        context.audit.record(
            "expert_execution_completed",
            "RecoveryPlanner",
            "RecoveryPlanner execution completed.",
            metadata={"request_id": request.request_id, "recommendation_id": draft.recommendation_id},
        )
        self._transition(context, WorkflowStage.AWAITING_FINAL_APPROVAL)
        approval = self._simulated_final_approval(context)
        context.human_decisions.append(approval)
        context.audit.record(
            "final_approval_recorded",
            "simulated-approver",
            "Final approval recorded for accelerated logistics recommendation.",
            metadata={"decision_id": approval.decision_id, "outcome": approval.outcome},
        )
        final = draft.model_copy(
            update={
                "status": "authorized",
                "approval_status": "approved",
                "summary": (
                    "Accelerated logistics is authorized for the 13-day projected milestone "
                    "delay without intervention: the 48000 USD mitigation is lower than the "
                    "195000 USD unmitigated exposure, and the equipment is confirmed not onsite "
                    "by simulated human decision."
                ),
                "warnings": [
                    "Authorization assumes accelerated logistics can still recover the 13-day projected milestone slip.",
                    "Execution remains subject to implementing the approved logistics option before secondary effects emerge.",
                ],
            }
        )
        context.final_recommendation = final
        context.audit.record(
            "final_recommendation_created",
            "RecoveryPlanner",
            "Final recovery recommendation created.",
            evidence=final.evidence,
            metadata={
                "recommendation_id": final.recommendation_id,
                "approval_status": final.approval_status,
                "preferred_option_id": final.preferred_option_id,
            },
        )
        self._transition(context, WorkflowStage.COMPLETED)
        context.audit.record(
            "case_completed",
            "workflow",
            "Case workflow completed with final recommendation.",
            metadata={"final_recommendation_id": final.recommendation_id},
        )

    def _post_human_draft_recommendation(
        self,
        context: WorkflowContext,
        base_recommendation: FinalRecommendation,
    ) -> FinalRecommendation:
        actual = build_actual_expected_results(context.bundle)
        resolved_contradictions = [self._resolved_contradiction(item) for item in context.contradictions]
        answered_request = context.human_decision_requests[-1]
        confidence = ConfidenceAssessment(
            level="high",
            score=0.96,
            rationale=(
                "Schedule, commercial, logistics, contract, and human-confirmation records "
                "support the recommendation."
            ),
            evidence=base_recommendation.evidence,
        )
        return base_recommendation.model_copy(
            update={
                "status": "draft",
                "human_decision_required": False,
                "human_decision_request": answered_request,
                "contradictions": resolved_contradictions,
                "confidence": confidence,
                "approval_status": "pending",
                "summary": (
                    "Draft recommendation: use accelerated logistics. The projected milestone "
                    f"delay without intervention is {actual['calculated_milestone_delay_days']} days; "
                    f"unmitigated exposure is {actual['unmitigated_exposure_usd']} USD; "
                    f"mitigation cost is {actual['mitigation_cost_usd']} USD; gross avoided exposure "
                    f"before secondary effects is {actual['gross_avoided_exposure_before_secondary_effects_usd']} USD. "
                    "Equipment is confirmed not onsite by simulated human decision."
                ),
                "warnings": [
                    "Draft recommendation remains subject to final authorization.",
                    "Assumes accelerated logistics remains available at the cited price.",
                ],
            }
        )

    def _resolved_contradiction(self, contradiction: Contradiction) -> Contradiction:
        return contradiction.model_copy(
            update={
                "status": "resolved",
                "requires_human_confirmation": False,
                "summary": (
                    contradiction.summary
                    + " Human decision confirms the equipment is not onsite."
                ),
            }
        )

    def _human_decision_request(
        self,
        context: WorkflowContext,
        contradictions: list[Contradiction],
    ) -> HumanDecisionRequest:
        evidence = []
        for contradiction in contradictions:
            evidence.extend(contradiction.conflicting_evidence)
        return HumanDecisionRequest(
            decision_request_id="HDR-ONSITE-001",
            case_id=context.bundle.case.case_id,
            reason="Onsite status is contradicted by cited source records.",
            question="Confirm whether the generator skid has physically arrived onsite.",
            contradictions=contradictions,
            evidence=evidence,
            requested_by="EvidenceAuditor",
        )

    def _simulated_not_onsite_decision(self, context: WorkflowContext) -> HumanDecision:
        request = context.human_decision_requests[-1]
        evidence = request.evidence
        return HumanDecision(
            decision_id="HD-ONSITE-001",
            decision_request_id=request.decision_request_id,
            outcome="confirmed",
            rationale="Simulated human decision confirms the generator skid is not onsite.",
            decided_by="simulated-human",
            decided_at=context.audit.model_timestamp(),
            evidence=evidence,
        )

    def _simulated_final_approval(self, context: WorkflowContext) -> HumanDecision:
        return HumanDecision(
            decision_id="HD-FINAL-APPROVAL-001",
            decision_request_id="HDR-FINAL-APPROVAL-001",
            outcome="approved",
            rationale="Simulated final approver authorizes the accelerated logistics recommendation.",
            decided_by="simulated-approver",
            decided_at=context.audit.model_timestamp(),
            evidence=context.draft_recommendation.evidence if context.draft_recommendation else [],
        )

    def _answer_latest_human_request(self, context: WorkflowContext) -> None:
        request = context.human_decision_requests[-1]
        context.human_decision_requests[-1] = request.model_copy(update={"status": "answered"})

    def _expert_request(
        self,
        context: WorkflowContext,
        selection: ExpertSelection,
        attempt: int,
        max_attempts: int,
    ) -> ExpertRequest:
        token = {
            "ScheduleExpert": "SCHEDULE",
            "CommercialExpert": "COMMERCIAL",
            "EvidenceAuditor": "EVIDENCE",
            "RiskExpert": "RISK",
            "RecoveryPlanner": "RECOVERY",
        }[selection.expert_role]
        question = {
            "ScheduleExpert": "Calculate unmitigated milestone delay.",
            "CommercialExpert": "Compare mitigation cost with unmitigated exposure.",
            "EvidenceAuditor": "Detect contradictory onsite-status evidence.",
            "RiskExpert": "Identify residual recovery recommendation risks.",
            "RecoveryPlanner": "Create recovery recommendation options.",
        }[selection.expert_role]
        return ExpertRequest(
            request_id=f"REQ-{token}-{attempt:03d}",
            case_id=context.bundle.case.case_id,
            expert_role=selection.expert_role,
            stage={
                "expert_analysis": CaseStage.EXPERT_ANALYSIS,
                "contradiction_review": CaseStage.EVIDENCE_REVIEW,
                "recovery_planning": CaseStage.RECOVERY_PLANNING,
            }[selection.phase],
            question=question,
            attempt=attempt,
            max_attempts=max_attempts,
        )

    def _selection_for(self, context: WorkflowContext, role: str) -> ExpertSelection | None:
        for selection in context.selections:
            if selection.expert_role == role:
                return selection
        return None

    def _transition(self, context: WorkflowContext, target: WorkflowStage) -> None:
        previous = context.state
        validate_transition(previous, target)
        context.state = target
        context.audit.record(
            "workflow_stage_changed",
            "workflow",
            f"Workflow stage changed from {previous.value} to {target.value}.",
            metadata={"from": previous.value, "to": target.value},
        )

    def _mark_failed(self) -> None:
        if self.context is None or self.context.state == WorkflowStage.FAILED:
            return
        try:
            self._transition(self.context, WorkflowStage.FAILED)
        except WorkflowTransitionError:
            self.context.state = WorkflowStage.FAILED

    def _require_context(self) -> WorkflowContext:
        if self.context is None:
            raise WorkflowExecutionError("workflow has not started")
        return self.context

    def _replay_input(self, context: WorkflowContext) -> dict[str, Any]:
        return {
            "schema_version": "project-recovery-council.replay-input.v1",
            "run_id": context.config.run_id,
            "case_path": context.config.case_path.as_posix(),
            "inject_commercial_failure": context.config.inject_commercial_failure,
            "auto_human_decision": context.config.auto_human_decision,
            "simulated_human_decision": {
                "onsite_status": "not_onsite",
                "decision_id": "HD-ONSITE-001",
            },
        }
