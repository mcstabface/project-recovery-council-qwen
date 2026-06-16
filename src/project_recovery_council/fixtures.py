"""Fixture loading for the synthetic equipment-delay case."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from project_recovery_council.contracts import (
    AuditEvent,
    CaseStage,
    CaseStatus,
    EvidenceRecord,
    RecoveryCase,
)


@dataclass(frozen=True)
class CaseBundle:
    """Loaded case data and source records used by deterministic validators."""

    base_path: Path
    case: RecoveryCase
    expected_results: dict[str, Any]
    source_payloads: dict[str, Any]

    @property
    def evidence_by_id(self) -> dict[str, EvidenceRecord]:
        return {record.record_id: record for record in self.case.evidence_records}


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object in {path}")
    return payload


def load_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def load_risk_register(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def load_equipment_delay_case(base_path: Path | str) -> CaseBundle:
    """Load the synthetic evidence pack and construct a RecoveryCase."""

    root = Path(base_path)
    source_payloads: dict[str, Any] = {
        "case.json": load_json(root / "case.json"),
        "schedule.json": load_json(root / "schedule.json"),
        "progress-report.md": load_text(root / "progress-report.md"),
        "supplier-correspondence.md": load_text(root / "supplier-correspondence.md"),
        "logistics-status.json": load_json(root / "logistics-status.json"),
        "cost-summary.json": load_json(root / "cost-summary.json"),
        "contract-excerpt.md": load_text(root / "contract-excerpt.md"),
        "risk-register.csv": load_risk_register(root / "risk-register.csv"),
    }
    expected_results = load_json(root / "expected-results.json")
    case_payload = source_payloads["case.json"]
    evidence_records = _collect_evidence_records(source_payloads)
    case = RecoveryCase(
        case_id=case_payload["case_id"],
        title=case_payload["title"],
        status=CaseStatus(case_payload["status"]),
        stage=CaseStage(case_payload["stage"]),
        opened_on=case_payload["opened_on"],
        summary=case_payload["summary"],
        evidence_records=evidence_records,
        audit_history=[
            AuditEvent(
                event_id="AUDIT-001",
                case_id=case_payload["case_id"],
                occurred_at=case_payload["opened_at"],
                actor="fixture-loader",
                action="case_loaded",
                summary="Synthetic equipment-delay case loaded from local fixture files.",
                metadata={"fixture_path": root.as_posix()},
            )
        ],
    )
    return CaseBundle(
        base_path=root,
        case=case,
        expected_results=expected_results,
        source_payloads=source_payloads,
    )


def _collect_evidence_records(source_payloads: dict[str, Any]) -> list[EvidenceRecord]:
    records: list[EvidenceRecord] = []

    case_payload = source_payloads["case.json"]
    records.append(
        EvidenceRecord(
            record_id=case_payload["record_id"],
            source_file="case.json",
            record_type="case_intake",
            title=case_payload["title"],
            record_date=case_payload["opened_on"],
            summary=case_payload["summary"],
            fields={
                "contractual_milestone_id": case_payload["contractual_milestone_id"],
                "equipment_id": case_payload["equipment_id"],
            },
        )
    )

    for record in source_payloads["schedule.json"]["records"]:
        records.append(
            EvidenceRecord(
                record_id=record["record_id"],
                source_file="schedule.json",
                record_type="schedule_record",
                title=record["title"],
                record_date=record["data_date"],
                summary=record["summary"],
                fields=record,
            )
        )

    records.append(
        EvidenceRecord(
            record_id="PRG-ONSITE-001",
            source_file="progress-report.md",
            record_type="progress_report",
            title="Progress report equipment status assertion",
            record_date="2026-06-28",
            summary="Progress report asserts the generator skid is onsite and released to installation.",
            fields={"equipment_onsite_claim": True, "source_section": "Equipment Status"},
        )
    )

    records.append(
        EvidenceRecord(
            record_id="SUP-NOT-ARRIVED-001",
            source_file="supplier-correspondence.md",
            record_type="supplier_correspondence",
            title="Supplier correspondence arrival status",
            record_date="2026-06-29",
            summary="Supplier confirms the generator skid has not arrived and remains with carrier.",
            fields={"equipment_arrived": False, "forecast_delivery_date": "2026-07-22"},
        )
    )

    for record in source_payloads["logistics-status.json"]["records"]:
        records.append(
            EvidenceRecord(
                record_id=record["record_id"],
                source_file="logistics-status.json",
                record_type="logistics_status",
                title=record["title"],
                record_date=record["status_date"],
                summary=record["summary"],
                fields=record,
            )
        )

    for record in source_payloads["cost-summary.json"]["records"]:
        records.append(
            EvidenceRecord(
                record_id=record["record_id"],
                source_file="cost-summary.json",
                record_type="cost_summary",
                title=record["title"],
                record_date=record["pricing_date"],
                summary=record["summary"],
                fields=record,
            )
        )

    records.append(
        EvidenceRecord(
            record_id="CTR-DELAY-001",
            source_file="contract-excerpt.md",
            record_type="contract_excerpt",
            title="Contractual delay exposure excerpt",
            record_date="2026-01-15",
            summary="Contract excerpt states delay exposure is 15000 USD per calendar day.",
            fields={"delay_exposure_usd_per_day": 15000},
        )
    )

    for row in source_payloads["risk-register.csv"]:
        records.append(
            EvidenceRecord(
                record_id=row["record_id"],
                source_file="risk-register.csv",
                record_type="risk_register",
                title=row["title"],
                record_date=row["status_date"],
                summary=row["summary"],
                fields=row,
            )
        )

    return records

