"""JSON serialization and replay comparison helpers."""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel


VOLATILE_KEYS = {"event_id", "occurred_at", "decided_at", "run_id", "run_path", "artifact_path"}


def to_jsonable(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, Path):
        return value.as_posix()
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value) and not isinstance(value, type):
        return to_jsonable(asdict(value))
    if isinstance(value, dict):
        return {str(key): to_jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [to_jsonable(item) for item in value]
    if isinstance(value, tuple):
        return [to_jsonable(item) for item in value]
    return value


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(to_jsonable(payload), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def strip_volatile(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: strip_volatile(item)
            for key, item in value.items()
            if key not in VOLATILE_KEYS
        }
    if isinstance(value, list):
        return [strip_volatile(item) for item in value]
    return value


def logical_signature_from_run(run_path: Path) -> dict[str, Any]:
    summary = read_json(run_path / "run-summary.json")
    return strip_volatile(
        {
            "state": summary["state"],
            "selected_experts": summary["selected_experts"],
            "inject_commercial_failure": summary["inject_commercial_failure"],
            "audit_events": read_json(run_path / "audit-events.json"),
            "expert_findings": read_json(run_path / "expert-findings.json"),
            "contradictions": read_json(run_path / "contradictions.json"),
            "human_decisions": read_json(run_path / "human-decisions.json"),
            "final_recommendation": read_json(run_path / "final-recommendation.json"),
        }
    )


def compare_run_artifacts(original_run_path: Path, replay_run_path: Path) -> dict[str, Any]:
    original = logical_signature_from_run(original_run_path)
    replay = logical_signature_from_run(replay_run_path)
    equivalent = original == replay
    return {
        "equivalent": equivalent,
        "ignored_fields": sorted(VOLATILE_KEYS),
        "differences": [] if equivalent else ["logical signatures differ"],
    }

