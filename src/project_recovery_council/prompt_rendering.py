"""Deterministic rendering for live Qwen agent prompts."""

from __future__ import annotations

import json
from hashlib import sha256
from typing import Any

from pydantic import BaseModel

from project_recovery_council.experiment_contracts import ExperimentVariant, SCHEMA_REGISTRY
from project_recovery_council.fixtures import CaseBundle
from project_recovery_council.prompt_catalog import PROMPT_VERSION, load_prompt_catalog
from project_recovery_council.serialization import to_jsonable


def render_agent_prompt(
    *,
    bundle: CaseBundle,
    agent_role: str,
    expected_response_schema: str,
    correlation_id: str,
    experiment_variant: ExperimentVariant | str,
    prompt_version: str = PROMPT_VERSION,
) -> str:
    catalog = load_prompt_catalog(prompt_version)
    if agent_role not in catalog:
        raise ValueError(f"unknown prompt agent role: {agent_role}")
    schema_model = SCHEMA_REGISTRY.get(expected_response_schema)
    schema_payload: dict[str, Any] = {}
    if schema_model is not None:
        schema_payload = schema_model.model_json_schema()
    payload = {
        "correlation_id": correlation_id,
        "case_id": bundle.case.case_id,
        "experiment_variant": ExperimentVariant(experiment_variant).value,
        "invocation_role": agent_role,
        "prompt_version": prompt_version,
        "expected_response_schema": expected_response_schema,
        "concise_output_requirements": [
            "Return one JSON object only.",
            "Do not include private chain-of-thought.",
            "Use concise conclusions, cited evidence, assumptions, warnings, confidence, and decision rationale.",
            "Cite stable source record IDs for material claims.",
        ],
        "evidence_records": [
            {
                "record_id": record.record_id,
                "source_file": record.source_file,
                "record_type": record.record_type,
                "title": record.title,
                "record_date": record.record_date.isoformat() if record.record_date else None,
                "summary": record.summary,
                "fields": record.fields,
            }
            for record in bundle.case.evidence_records
        ],
        "expected_output_json_schema": schema_payload,
    }
    return (
        f"{catalog[agent_role].content}\n\n"
        "## Live invocation packet\n"
        f"{json.dumps(to_jsonable(payload), indent=2, sort_keys=True)}\n"
    )


def stable_sha256_text(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def stable_sha256_model_schema(model: type[BaseModel]) -> str:
    encoded = json.dumps(model.model_json_schema(), sort_keys=True, separators=(",", ":"))
    return stable_sha256_text(encoded)
