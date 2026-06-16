"""Convenience entry points for local runs, validation, and replay."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from project_recovery_council.serialization import (
    compare_run_artifacts,
    read_json,
    write_json,
)
from project_recovery_council.workflow import (
    DEFAULT_ARTIFACTS_ROOT,
    DEFAULT_CASE_PATH,
    LocalWorkflowRunner,
    WorkflowRunResult,
    default_workflow_config,
    validate_fixture_bundle,
)


def run_equipment_delay_case(
    *,
    case_path: Path | str = DEFAULT_CASE_PATH,
    artifacts_root: Path | str = DEFAULT_ARTIFACTS_ROOT,
    run_id: str = "equipment-delay-standard",
    inject_commercial_failure: bool = False,
) -> WorkflowRunResult:
    config = default_workflow_config(
        case_path=case_path,
        artifacts_root=artifacts_root,
        run_id=run_id,
        inject_commercial_failure=inject_commercial_failure,
        auto_human_decision=True,
    )
    return LocalWorkflowRunner(config).run(write_artifacts=True)


def validate_case_fixture(case_path: Path | str = DEFAULT_CASE_PATH) -> list[str]:
    return validate_fixture_bundle(case_path)


def replay_run(
    path: Path | str,
    *,
    artifacts_root: Path | str | None = None,
    run_id: str | None = None,
) -> WorkflowRunResult:
    replay_path = Path(path)
    replay_input_path = replay_path / "replay-input.json" if replay_path.is_dir() else replay_path
    replay_input: dict[str, Any] = read_json(replay_input_path)
    original_run_path = replay_input_path.parent
    replay_run_id = run_id or f"{replay_input['run_id']}-replay"
    output_root = Path(artifacts_root) if artifacts_root is not None else original_run_path.parent
    result = run_equipment_delay_case(
        case_path=Path(replay_input["case_path"]),
        artifacts_root=output_root,
        run_id=replay_run_id,
        inject_commercial_failure=bool(replay_input["inject_commercial_failure"]),
    )
    if result.run_path is None:
        return result
    comparison = compare_run_artifacts(original_run_path, result.run_path)
    write_json(result.run_path / "replay-comparison.json", comparison)
    return WorkflowRunResult(
        context=result.context,
        run_path=result.run_path,
        replay_comparison=comparison,
    )

