"""Rule-based local Director for deterministic expert selection."""

from __future__ import annotations

from project_recovery_council.contracts import ExpertFinding, ExpertRequest, ExpertStatus
from project_recovery_council.fixtures import CaseBundle
from project_recovery_council.state import ExpertSelection
from project_recovery_council.validation import calculate_delivery_shift_days


class RuleBasedDirector:
    """Selects experts from source facts with concise routing rationale."""

    def select_experts(self, bundle: CaseBundle) -> list[ExpertSelection]:
        selections: list[ExpertSelection] = []
        schedule = bundle.evidence_by_id["SCH-DELIVERY-001"]
        cost = bundle.evidence_by_id["COST-SUMMARY-001"]
        progress = bundle.evidence_by_id["PRG-ONSITE-001"]
        logistics = bundle.evidence_by_id["LOG-STATUS-001"]

        if calculate_delivery_shift_days(schedule) > 0:
            selections.append(
                ExpertSelection(
                    expert_role="ScheduleExpert",
                    phase="expert_analysis",
                    rationale="Delivery forecast moved later than baseline and milestone impact must be calculated.",
                )
            )

        if int(cost.fields["unmitigated_exposure_usd"]) > 0:
            selections.append(
                ExpertSelection(
                    expert_role="CommercialExpert",
                    phase="expert_analysis",
                    rationale="Cost summary contains delay exposure and mitigation economics.",
                )
            )

        if progress.fields["equipment_onsite_claim"] is True and logistics.fields["actual_arrival_date"] is None:
            selections.append(
                ExpertSelection(
                    expert_role="EvidenceAuditor",
                    phase="contradiction_review",
                    rationale="Onsite progress assertion conflicts with logistics arrival data.",
                )
            )

        if "RISK-001" in bundle.evidence_by_id:
            selections.append(
                ExpertSelection(
                    expert_role="RiskExpert",
                    phase="expert_analysis",
                    rationale="Risk register contains an unresolved status-conflict risk.",
                )
            )

        if cost.fields["accelerated_logistics_option_id"] == "REC-ACCEL-LOGISTICS":
            selections.append(
                ExpertSelection(
                    expert_role="RecoveryPlanner",
                    phase="recovery_planning",
                    rationale="Approved accelerated logistics option is available subject to project approval.",
                )
            )

        return selections

    def authorize_retry(self, request: ExpertRequest, finding: ExpertFinding) -> bool:
        return finding.status == ExpertStatus.FAILED and request.attempt < request.max_attempts

