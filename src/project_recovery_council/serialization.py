"""JSON serialization and replay comparison helpers."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, is_dataclass
from enum import Enum
from hashlib import sha256
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
    encoded = json.dumps(to_jsonable(payload), indent=2, sort_keys=True) + "\n"
    tmp_path = path.with_name(f".{path.name}.tmp")
    tmp_path.write_text(encoded, encoding="utf-8")
    os.replace(tmp_path, path)


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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
    state = read_json(run_path / "workflow-state.json")
    return strip_volatile(
        {
            "terminal_status": state["current_workflow_stage"],
            "selected_experts": state["selected_experts"],
            "expert_findings": state["expert_findings"],
            "contradictions": state["contradictions"],
            "decision_requests": state["pending_human_requests"] + state["answered_human_requests"],
            "human_decisions": state["received_human_decisions"],
            "recovery_options": state["recovery_options"],
            "final_recommendation": state["final_recommendation"],
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
