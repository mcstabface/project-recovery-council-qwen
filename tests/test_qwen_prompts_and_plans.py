from project_recovery_council.experiment_contracts import (
    ARBITER_RESPONSE_SCHEMA,
    DIRECTOR_ROUTING_RESPONSE_SCHEMA,
    RECOVERY_ANALYSIS_RESPONSE_SCHEMA,
    SPECIALIST_FINDING_RESPONSE_SCHEMA,
    AgentRole,
    ExperimentVariant,
)
from project_recovery_council.experiments import all_experiment_plans, build_experiment_plan
from project_recovery_council.prompt_catalog import PROMPT_FILES, PROMPT_VERSION, load_prompt_catalog, validate_prompt_catalog


def test_prompt_catalog_is_complete_versioned_and_schema_associated() -> None:
    issues = validate_prompt_catalog()
    catalog = load_prompt_catalog()

    assert issues == []
    assert set(catalog) == set(PROMPT_FILES)
    assert all(prompt.version == PROMPT_VERSION for prompt in catalog.values())
    assert catalog[AgentRole.GENERALIST.value].expected_response_schema == RECOVERY_ANALYSIS_RESPONSE_SCHEMA
    assert catalog[AgentRole.DIRECTOR.value].expected_response_schema == DIRECTOR_ROUTING_RESPONSE_SCHEMA
    assert catalog[AgentRole.SCHEDULE_EXPERT.value].expected_response_schema == SPECIALIST_FINDING_RESPONSE_SCHEMA
    assert catalog[AgentRole.ARBITER.value].expected_response_schema == ARBITER_RESPONSE_SCHEMA


def test_all_four_experiment_plans_are_explicit() -> None:
    plans = all_experiment_plans()

    assert set(plans) == set(ExperimentVariant)
    assert plans[ExperimentVariant.DETERMINISTIC_ORACLE].ai_competitor is False
    assert plans[ExperimentVariant.SINGLE_GENERALIST].steps[0].agent_role == AgentRole.GENERALIST.value
    assert [step.agent_role for step in plans[ExperimentVariant.FIXED_EXPERT_CHAIN].steps] == [
        AgentRole.SCHEDULE_EXPERT.value,
        AgentRole.COMMERCIAL_EXPERT.value,
        AgentRole.EVIDENCE_AUDITOR.value,
        AgentRole.RISK_EXPERT.value,
        AgentRole.RECOVERY_PLANNER.value,
        AgentRole.ARBITER.value,
    ]
    dynamic = build_experiment_plan(ExperimentVariant.DYNAMIC_EXPERT_COUNCIL)
    assert dynamic.steps[0].agent_role == AgentRole.DIRECTOR.value
    assert dynamic.steps[0].dynamic is True
    assert dynamic.steps[-1].agent_role == AgentRole.RECOVERY_PLANNER.value
