"""Export versioned JSON Schemas for public integration contracts."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from pydantic import TypeAdapter

from project_recovery_council.artifacts import ReplayInput, RunArtifactManifest, RunSummary
from project_recovery_council.contracts import (
    AuditEvent,
    Contradiction,
    EvidenceRecord,
    EvidenceReference,
    ExpertFinding,
    ExpertRequest,
    FinalRecommendation,
    HumanDecision,
    HumanDecisionRequest,
    RecoveryCase,
    RecoveryOption,
)
from project_recovery_council.serialization import write_json
from project_recovery_council.state import PersistedWorkflowState


SCHEMA_VERSION = "v1"
SCHEMA_ROOT = Path("schemas") / SCHEMA_VERSION


SCHEMA_EXPORTS: list[dict[str, Any]] = [
    {"id": "project-recovery-council.recovery-case.v1", "title": "RecoveryCase", "model": RecoveryCase, "file": "recovery-case.schema.json", "producer": "case intake", "consumer": "workflow runner and external case systems"},
    {"id": "project-recovery-council.evidence-record.v1", "title": "EvidenceRecord", "model": EvidenceRecord, "file": "evidence-record.schema.json", "producer": "fixture loader or evidence adapters", "consumer": "experts and evidence auditors"},
    {"id": "project-recovery-council.evidence-reference.v1", "title": "EvidenceReference", "model": EvidenceReference, "file": "evidence-reference.schema.json", "producer": "experts and validators", "consumer": "auditors, recommendations, and artifact inspectors"},
    {"id": "project-recovery-council.expert-request.v1", "title": "ExpertRequest", "model": ExpertRequest, "file": "expert-request.schema.json", "producer": "Director", "consumer": "expert adapters"},
    {"id": "project-recovery-council.expert-finding.v1", "title": "ExpertFinding", "model": ExpertFinding, "file": "expert-finding.schema.json", "producer": "expert adapters", "consumer": "workflow runner and artifact inspectors"},
    {"id": "project-recovery-council.contradiction.v1", "title": "Contradiction", "model": Contradiction, "file": "contradiction.schema.json", "producer": "EvidenceAuditor", "consumer": "human gate and recommendation workflow"},
    {"id": "project-recovery-council.human-decision-request.v1", "title": "HumanDecisionRequest", "model": HumanDecisionRequest, "file": "human-decision-request.schema.json", "producer": "workflow runner", "consumer": "human task systems"},
    {"id": "project-recovery-council.human-decision.v1", "title": "HumanDecision", "model": HumanDecision, "file": "human-decision.schema.json", "producer": "human task systems or demo CLI", "consumer": "workflow runner"},
    {"id": "project-recovery-council.recovery-option.v1", "title": "RecoveryOption", "model": RecoveryOption, "file": "recovery-option.schema.json", "producer": "RecoveryPlanner", "consumer": "approval workflow"},
    {"id": "project-recovery-council.final-recommendation.v1", "title": "FinalRecommendation", "model": FinalRecommendation, "file": "final-recommendation.schema.json", "producer": "RecoveryPlanner", "consumer": "case governance and approval systems"},
    {"id": "project-recovery-council.audit-event.v1", "title": "AuditEvent", "model": AuditEvent, "file": "audit-event.schema.json", "producer": "workflow runner", "consumer": "artifact inspectors and case history systems"},
    {"id": "project-recovery-council.persisted-workflow-state.v1", "title": "PersistedWorkflowState", "model": PersistedWorkflowState, "file": "persisted-workflow-state.schema.json", "producer": "workflow runner", "consumer": "resume workflow and artifact inspectors"},
    {"id": "project-recovery-council.run-summary.v1", "title": "RunSummary", "model": RunSummary, "file": "run-summary.schema.json", "producer": "workflow runner", "consumer": "operators and artifact inspectors"},
    {"id": "project-recovery-council.replay-input.v1", "title": "ReplayInput", "model": ReplayInput, "file": "replay-input.schema.json", "producer": "workflow runner", "consumer": "replay runner"},
    {"id": "project-recovery-council.run-artifact-manifest.v1", "title": "RunArtifactManifest", "model": RunArtifactManifest, "file": "run-artifact-manifest.schema.json", "producer": "workflow runner", "consumer": "artifact inspectors"},
]


@dataclass(frozen=True)
class SchemaDriftResult:
    """Byte-level schema drift comparison result."""

    passed: bool
    changed_files: list[str]
    missing_files: list[str]
    unexpected_files: list[str]

    @property
    def messages(self) -> list[str]:
        messages: list[str] = []
        messages.extend(f"changed: {path}" for path in self.changed_files)
        messages.extend(f"missing: {path}" for path in self.missing_files)
        messages.extend(f"unexpected: {path}" for path in self.unexpected_files)
        return messages


def export_schemas(output_dir: Path | str = SCHEMA_ROOT) -> list[dict[str, Any]]:
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    catalog: list[dict[str, Any]] = []
    for item in SCHEMA_EXPORTS:
        schema = TypeAdapter(item["model"]).json_schema()
        schema["$id"] = item["id"]
        schema["title"] = item["title"]
        schema["x-schema-version"] = SCHEMA_VERSION
        path = root / item["file"]
        write_json(path, schema)
        catalog.append(
            {
                "schema_id": item["id"],
                "title": item["title"],
                "version": SCHEMA_VERSION,
                "file_path": (SCHEMA_ROOT / item["file"]).as_posix(),
                "intended_producer": item["producer"],
                "intended_consumer": item["consumer"],
                "compatibility_notes": "Initial v1 contract. No forward/backward compatibility beyond exact v1 schema is guaranteed.",
            }
        )
    write_json(root / "schema-catalog.json", {"schema_version": SCHEMA_VERSION, "schemas": catalog})
    return catalog


def check_schema_drift(committed_dir: Path | str = SCHEMA_ROOT) -> SchemaDriftResult:
    """Export schemas to a temporary directory and compare against committed v1 files."""

    committed = Path(committed_dir)
    with TemporaryDirectory() as tmp:
        exported = Path(tmp) / SCHEMA_VERSION
        export_schemas(exported)
        return compare_schema_directories(committed, exported)


def compare_schema_directories(committed_dir: Path | str, exported_dir: Path | str) -> SchemaDriftResult:
    committed = Path(committed_dir)
    exported = Path(exported_dir)
    committed_files = _relative_files(committed)
    exported_files = _relative_files(exported)
    missing = sorted(str(path) for path in exported_files - committed_files)
    unexpected = sorted(str(path) for path in committed_files - exported_files)
    changed: list[str] = []
    for relative in sorted(committed_files & exported_files):
        if (committed / relative).read_bytes() != (exported / relative).read_bytes():
            changed.append(str(relative))
    return SchemaDriftResult(
        passed=not changed and not missing and not unexpected,
        changed_files=changed,
        missing_files=missing,
        unexpected_files=unexpected,
    )


def _relative_files(root: Path) -> set[Path]:
    if not root.exists():
        return set()
    return {
        path.relative_to(root)
        for path in root.rglob("*")
        if path.is_file()
    }


def main() -> int:
    export_schemas()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
