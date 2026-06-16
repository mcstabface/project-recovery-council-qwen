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
        try:
            _validate_payload(entry.schema_id, payload)
        except (ValidationError, ValueError) as exc:
            errors.append(f"schema validation failed for {entry.relative_path}: {exc}")
    return ArtifactInspectionResult(run_path=root.as_posix(), passed=not errors, errors=errors)


def _validate_payload(schema_id: str, payload: Any) -> None:
    if schema_id in LIST_ADAPTERS:
        LIST_ADAPTERS[schema_id].validate_python(payload)
        return
    if schema_id == "project-recovery-council.qwen.variant-results.v1":
        if not isinstance(payload, dict):
            raise ValueError("variant results must be a JSON object")
        return
    model = MODEL_ADAPTERS.get(schema_id)
    if model is None:
        raise ValueError(f"unknown schema id: {schema_id}")
    model.model_validate(payload)


def _schema_id_for(filename: str) -> str:
    return {
        "experiment-config.json": "project-recovery-council.qwen.experiment-config.v1",
        "invocation-records.json": "project-recovery-council.qwen.agent-invocations.v1",
        "variant-results.json": "project-recovery-council.qwen.variant-results.v1",
        "evaluation-results.json": "project-recovery-council.qwen.evaluation-report.v1",
        "comparison-report.json": "project-recovery-council.qwen.experiment-comparison.v1",
    }[filename]


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
