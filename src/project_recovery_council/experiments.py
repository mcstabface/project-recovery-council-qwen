"""Experiment variant definitions for the Qwen competition adaptation."""

from __future__ import annotations

from project_recovery_council.experiment_contracts import (
    ARBITER_RESPONSE_SCHEMA,
    DIRECTOR_ROUTING_RESPONSE_SCHEMA,
    RECOVERY_ANALYSIS_RESPONSE_SCHEMA,
    SPECIALIST_FINDING_RESPONSE_SCHEMA,
    AgentRole,
    ExecutionPlan,
    ExperimentStep,
    ExperimentVariant,
)


DEFAULT_QWEN_MODEL_IDENTIFIER = "qwen-disabled-offline-placeholder"


def build_experiment_plan(
    variant: ExperimentVariant | str,
    *,
    model_identifier: str = DEFAULT_QWEN_MODEL_IDENTIFIER,
) -> ExecutionPlan:
    selected = ExperimentVariant(variant)
    if selected == ExperimentVariant.DETERMINISTIC_ORACLE:
        return ExecutionPlan(
            plan_id="deterministic_oracle.v1",
            variant=selected,
            ai_competitor=False,
            description=(
                "Uses the deterministic reference implementation and expected-results fixture "
                "as the oracle. This is not counted as an AI competitor."
            ),
            steps=[
                ExperimentStep(
                    sequence=0,
                    step_id="oracle_expected_results",
                    agent_role=AgentRole.DETERMINISTIC_ORACLE.value,
                    prompt_id="deterministic-reference-oracle.v1",
                    expected_response_schema=RECOVERY_ANALYSIS_RESPONSE_SCHEMA,
                    model_identifier="deterministic-reference",
                    description="Read deterministic expected results and canonical evidence.",
                    required=True,
                )
            ],
        )

    if selected == ExperimentVariant.SINGLE_GENERALIST:
        return ExecutionPlan(
            plan_id="single_generalist.v1",
            variant=selected,
            ai_competitor=True,
            description=(
                "One generalist receives the complete evidence package and returns final "
                "analysis and recommendation directly."
            ),
            steps=[
                ExperimentStep(
                    sequence=1,
                    step_id="generalist_final_analysis",
                    agent_role=AgentRole.GENERALIST.value,
                    prompt_id="GeneralistAgent.v1",
                    expected_response_schema=RECOVERY_ANALYSIS_RESPONSE_SCHEMA,
                    model_identifier=model_identifier,
                    description="Generalist analyzes all evidence and recommends recovery.",
                    required=True,
                )
            ],
        )

    if selected == ExperimentVariant.FIXED_EXPERT_CHAIN:
        roles = [
            AgentRole.SCHEDULE_EXPERT,
            AgentRole.COMMERCIAL_EXPERT,
            AgentRole.EVIDENCE_AUDITOR,
            AgentRole.RISK_EXPERT,
            AgentRole.RECOVERY_PLANNER,
            AgentRole.ARBITER,
        ]
        steps = []
        previous_step = ""
        for index, role in enumerate(roles, start=1):
            schema = ARBITER_RESPONSE_SCHEMA if role == AgentRole.ARBITER else SPECIALIST_FINDING_RESPONSE_SCHEMA
            if role == AgentRole.RECOVERY_PLANNER:
                schema = RECOVERY_ANALYSIS_RESPONSE_SCHEMA
            step_id = f"fixed_{role.value}"
            steps.append(
                ExperimentStep(
                    sequence=index,
                    step_id=step_id,
                    agent_role=role.value,
                    prompt_id=f"{role.value}.v1",
                    expected_response_schema=schema,
                    model_identifier=model_identifier,
                    description="Fixed-sequence expert step with no dynamic routing.",
                    depends_on=[previous_step] if previous_step else [],
                    required=True,
                )
            )
            previous_step = step_id
        return ExecutionPlan(
            plan_id="fixed_expert_chain.v1",
            variant=selected,
            ai_competitor=True,
            description=(
                "All specialists run in a fixed sequence with no dynamic routing; "
                "the final synthesis combines findings."
            ),
            steps=steps,
        )

    if selected == ExperimentVariant.DYNAMIC_EXPERT_COUNCIL:
        return ExecutionPlan(
            plan_id="dynamic_expert_council.v1",
            variant=selected,
            ai_competitor=True,
            description=(
                "Director selects relevant experts; specialists return independent findings; "
                "Evidence Auditor checks claims; Arbiter resolves or escalates disagreement; "
                "Recovery Planner produces the recommendation."
            ),
            steps=[
                ExperimentStep(
                    sequence=1,
                    step_id="director_routing",
                    agent_role=AgentRole.DIRECTOR.value,
                    prompt_id="DirectorAgent.v1",
                    expected_response_schema=DIRECTOR_ROUTING_RESPONSE_SCHEMA,
                    model_identifier=model_identifier,
                    description="Select only evidence-relevant specialists.",
                    dynamic=True,
                    required=True,
                ),
                ExperimentStep(
                    sequence=2,
                    step_id="selected_specialists",
                    agent_role="DirectorSelectedExperts",
                    prompt_id="SelectedSpecialists.v1",
                    expected_response_schema=SPECIALIST_FINDING_RESPONSE_SCHEMA,
                    model_identifier=model_identifier,
                    description="Run specialists selected by the Director independently.",
                    depends_on=["director_routing"],
                    dynamic=True,
                    required=True,
                ),
                ExperimentStep(
                    sequence=3,
                    step_id="evidence_audit",
                    agent_role=AgentRole.EVIDENCE_AUDITOR.value,
                    prompt_id="EvidenceAuditor.v1",
                    expected_response_schema=SPECIALIST_FINDING_RESPONSE_SCHEMA,
                    model_identifier=model_identifier,
                    description="Check cited claims and unsupported assertions.",
                    depends_on=["selected_specialists"],
                    required=True,
                ),
                ExperimentStep(
                    sequence=4,
                    step_id="arbitration",
                    agent_role=AgentRole.ARBITER.value,
                    prompt_id="ArbiterAgent.v1",
                    expected_response_schema=ARBITER_RESPONSE_SCHEMA,
                    model_identifier=model_identifier,
                    description="Resolve or preserve specialist disagreement.",
                    depends_on=["selected_specialists", "evidence_audit"],
                    required=True,
                ),
                ExperimentStep(
                    sequence=5,
                    step_id="recovery_recommendation",
                    agent_role=AgentRole.RECOVERY_PLANNER.value,
                    prompt_id="RecoveryPlanner.v1",
                    expected_response_schema=RECOVERY_ANALYSIS_RESPONSE_SCHEMA,
                    model_identifier=model_identifier,
                    description="Produce final recommendation subject to gates.",
                    depends_on=["arbitration"],
                    required=True,
                ),
            ],
        )

    raise ValueError(f"unsupported experiment variant: {variant}")


def all_experiment_plans() -> dict[ExperimentVariant, ExecutionPlan]:
    return {variant: build_experiment_plan(variant) for variant in ExperimentVariant}
