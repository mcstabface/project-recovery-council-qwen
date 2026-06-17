"""Versioned prompt catalog for competition agents."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field

from project_recovery_council.contracts import ContractModel
from project_recovery_council.experiment_contracts import (
    ARBITER_RESPONSE_SCHEMA,
    DIRECTOR_ROUTING_RESPONSE_SCHEMA,
    EVIDENCE_AUDITOR_RESPONSE_SCHEMA,
    RECOVERY_ANALYSIS_RESPONSE_SCHEMA,
    SPECIALIST_FINDING_RESPONSE_SCHEMA,
    AgentRole,
)


PROMPT_VERSION = "v1"


class PromptSpec(ContractModel):
    prompt_id: str = Field(min_length=1)
    version: str = Field(min_length=1)
    agent_role: str = Field(min_length=1)
    path: str = Field(min_length=1)
    expected_response_schema: str = Field(min_length=1)
    content: str = Field(min_length=1)


PROMPT_FILES: dict[str, tuple[str, str]] = {
    AgentRole.GENERALIST.value: ("generalist_agent.md", RECOVERY_ANALYSIS_RESPONSE_SCHEMA),
    AgentRole.DIRECTOR.value: ("director_agent.md", DIRECTOR_ROUTING_RESPONSE_SCHEMA),
    AgentRole.SCHEDULE_EXPERT.value: ("schedule_expert.md", SPECIALIST_FINDING_RESPONSE_SCHEMA),
    AgentRole.COMMERCIAL_EXPERT.value: ("commercial_expert.md", SPECIALIST_FINDING_RESPONSE_SCHEMA),
    AgentRole.EVIDENCE_AUDITOR.value: ("evidence_auditor.md", EVIDENCE_AUDITOR_RESPONSE_SCHEMA),
    AgentRole.RISK_EXPERT.value: ("risk_expert.md", SPECIALIST_FINDING_RESPONSE_SCHEMA),
    AgentRole.RECOVERY_PLANNER.value: ("recovery_planner.md", RECOVERY_ANALYSIS_RESPONSE_SCHEMA),
    AgentRole.ARBITER.value: ("arbiter_agent.md", ARBITER_RESPONSE_SCHEMA),
}


REQUIRED_PROMPT_PHRASES = [
    "Role and scope",
    "Permitted evidence",
    "Expected output schema",
    "Evidence-citation requirements",
    "Abstention behavior",
    "Unsupported-claim prohibition",
    "Concise rationale requirements",
    "No private chain-of-thought output",
    "Failure behavior",
]


def prompt_root(version: str = PROMPT_VERSION) -> Path:
    return Path(__file__).parents[2] / "prompts" / version


def load_prompt_catalog(version: str = PROMPT_VERSION) -> dict[str, PromptSpec]:
    root = prompt_root(version)
    catalog: dict[str, PromptSpec] = {}
    for role, (filename, schema_id) in PROMPT_FILES.items():
        path = root / filename
        content = path.read_text(encoding="utf-8")
        catalog[role] = PromptSpec(
            prompt_id=f"{role}.{version}",
            version=version,
            agent_role=role,
            path=path.as_posix(),
            expected_response_schema=schema_id,
            content=content,
        )
    return catalog


def validate_prompt_catalog(version: str = PROMPT_VERSION) -> list[str]:
    issues: list[str] = []
    root = prompt_root(version)
    if not root.is_dir():
        return [f"missing prompt directory: {root.as_posix()}"]
    for role, (filename, schema_id) in PROMPT_FILES.items():
        path = root / filename
        if not path.is_file():
            issues.append(f"missing prompt for {role}: {path.as_posix()}")
            continue
        content = path.read_text(encoding="utf-8")
        for phrase in REQUIRED_PROMPT_PHRASES:
            if phrase not in content:
                issues.append(f"{filename} missing required section: {phrase}")
        if schema_id not in content:
            issues.append(f"{filename} does not name expected schema {schema_id}")
    return issues
