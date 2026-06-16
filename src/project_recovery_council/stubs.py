"""Deterministic expert stubs for contract and orchestration tests."""

from __future__ import annotations

from project_recovery_council.contracts import (
    CaseStage,
    ExpertFinding,
    ExpertRequest,
    ExpertStatus,
)
from project_recovery_council.fixtures import CaseBundle
from project_recovery_council.interfaces import (
    CommercialExpert,
    Director,
    EvidenceAuditor,
    RecoveryPlanner,
    RiskExpert,
    ScheduleExpert,
)
from project_recovery_council.validation import (
    build_recovery_recommendation,
    calculate_gross_avoided_exposure_usd,
    calculate_milestone_delay_days,
    calculate_unmitigated_exposure_usd,
    completed_confidence,
    detect_onsite_contradictions,
)


class DeterministicScheduleExpert(ScheduleExpert):
    def evaluate(self, request: ExpertRequest, bundle: CaseBundle) -> ExpertFinding:
        schedule = bundle.evidence_by_id["SCH-DELIVERY-001"]
        delay_days = calculate_milestone_delay_days(schedule)
        evidence = [schedule.reference("/records/0")]
        return ExpertFinding(
            finding_id="FIND-SCHEDULE-001",
            request_id=request.request_id,
            expert_role="ScheduleExpert",
            status=ExpertStatus.COMPLETED,
            conclusion=f"Contractual milestone is forecast to slip {delay_days} days without intervention.",
            confidence=completed_confidence("Milestone dates and available float reconcile.", evidence),
            evidence=evidence,
            assumptions=["No further resequencing is applied in the unmitigated forecast."],
        )


class DeterministicCommercialExpert(CommercialExpert):
    def evaluate(self, request: ExpertRequest, bundle: CaseBundle) -> ExpertFinding:
        cost = bundle.evidence_by_id["COST-SUMMARY-001"]
        delay_days = int(cost.fields["unmitigated_delay_days"])
        exposure = calculate_unmitigated_exposure_usd(
            delay_days,
            int(cost.fields["delay_exposure_usd_per_day"]),
        )
        avoided = calculate_gross_avoided_exposure_usd(
            exposure,
            int(cost.fields["accelerated_logistics_cost_usd"]),
        )
        evidence = [cost.reference("/records/0")]
        return ExpertFinding(
            finding_id="FIND-COMMERCIAL-001",
            request_id=request.request_id,
            expert_role="CommercialExpert",
            status=ExpertStatus.COMPLETED,
            conclusion=f"Unmitigated exposure is {exposure} USD; gross avoided exposure is {avoided} USD.",
            confidence=completed_confidence("The calculation uses fixed fixture rates and costs.", evidence),
            evidence=evidence,
            assumptions=["Delay exposure is linear by calendar day."],
        )


class DeterministicRiskExpert(RiskExpert):
    def evaluate(self, request: ExpertRequest, bundle: CaseBundle) -> ExpertFinding:
        risk = bundle.evidence_by_id["RISK-001"]
        evidence = [risk.reference("row:2")]
        return ExpertFinding(
            finding_id="FIND-RISK-001",
            request_id=request.request_id,
            expert_role="RiskExpert",
            status=ExpertStatus.COMPLETED,
            conclusion="The primary residual risk is reliance on human confirmation of actual onsite status.",
            confidence=completed_confidence("Risk register row identifies the unresolved status conflict.", evidence),
            evidence=evidence,
            warnings=["Proceeding without human confirmation would authorize an unsupported onsite claim."],
        )


class DeterministicEvidenceAuditor(EvidenceAuditor):
    def audit(self, case, bundle: CaseBundle):
        return detect_onsite_contradictions(bundle)


class DeterministicRecoveryPlanner(RecoveryPlanner):
    def plan(self, case, bundle: CaseBundle):
        return build_recovery_recommendation(bundle)


class DeterministicDirector(Director):
    """Small orchestration stub that creates repeatable expert requests."""

    def __init__(
        self,
        schedule_expert: ScheduleExpert | None = None,
        commercial_expert: CommercialExpert | None = None,
        risk_expert: RiskExpert | None = None,
    ) -> None:
        self.schedule_expert = schedule_expert or DeterministicScheduleExpert()
        self.commercial_expert = commercial_expert or DeterministicCommercialExpert()
        self.risk_expert = risk_expert or DeterministicRiskExpert()

    def evaluate_case(self, bundle: CaseBundle) -> list[ExpertFinding]:
        case_id = bundle.case.case_id
        return [
            self.schedule_expert.evaluate(
                ExpertRequest(
                    request_id="REQ-SCHEDULE-001",
                    case_id=case_id,
                    expert_role="ScheduleExpert",
                    stage=CaseStage.EXPERT_ANALYSIS,
                    question="Calculate unmitigated milestone delay.",
                ),
                bundle,
            ),
            self.commercial_expert.evaluate(
                ExpertRequest(
                    request_id="REQ-COMMERCIAL-001",
                    case_id=case_id,
                    expert_role="CommercialExpert",
                    stage=CaseStage.EXPERT_ANALYSIS,
                    question="Compare mitigation cost with unmitigated exposure.",
                ),
                bundle,
            ),
            self.risk_expert.evaluate(
                ExpertRequest(
                    request_id="REQ-RISK-001",
                    case_id=case_id,
                    expert_role="RiskExpert",
                    stage=CaseStage.EXPERT_ANALYSIS,
                    question="Identify residual recommendation risks.",
                ),
                bundle,
            ),
        ]

