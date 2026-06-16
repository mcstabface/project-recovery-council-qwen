import os
import subprocess
import sys
from pathlib import Path

from project_recovery_council.experiment_artifacts import validate_experiment_artifacts
from project_recovery_council.offline_experiments import (
    compare_offline_fixtures,
    write_offline_evaluation_artifacts,
)


ROOT = Path(__file__).parents[1]
FIXTURE_PATH = ROOT / "sample-data" / "equipment-delay-case"


def cli_env() -> dict[str, str]:
    env = os.environ.copy()
    current = env.get("PYTHONPATH")
    src_path = str(ROOT / "src")
    env["PYTHONPATH"] = src_path if not current else os.pathsep.join([src_path, current])
    return env


def test_experiment_artifact_validation_for_offline_evaluation(tmp_path: Path) -> None:
    run_path = write_offline_evaluation_artifacts(
        "strong_modular_council",
        case_path=FIXTURE_PATH,
        artifacts_root=tmp_path,
        experiment_id="artifact-contract-test",
    )
    result = validate_experiment_artifacts(run_path)

    assert result.passed is True
    assert (run_path / "experiment-config.json").is_file()
    assert (run_path / "invocation-records.json").is_file()
    assert (run_path / "variant-results.json").is_file()
    assert (run_path / "evaluation-results.json").is_file()
    assert (run_path / "comparison-report.json").is_file()
    assert (run_path / "artifact-manifest.json").is_file()


def test_offline_comparison_report_generation() -> None:
    comparison = compare_offline_fixtures(case_path=FIXTURE_PATH)

    assert len(comparison.rows) == 3
    assert {row.variant.value for row in comparison.rows} == {
        "dynamic_expert_council",
        "single_generalist",
        "fixed_expert_chain",
    }
    assert comparison.limitations


def test_new_cli_commands_validate_prompts_and_offline_artifacts(tmp_path: Path) -> None:
    validate_prompts = subprocess.run(
        [sys.executable, "-m", "project_recovery_council", "validate-prompts"],
        cwd=ROOT,
        env=cli_env(),
        text=True,
        capture_output=True,
        check=False,
    )

    assert validate_prompts.returncode == 0
    assert "prompt validation passed" in validate_prompts.stdout

    evaluate = subprocess.run(
        [
            sys.executable,
            "-m",
            "project_recovery_council",
            "evaluate-offline",
            "--fixture",
            "strong_modular_council",
            "--case-path",
            str(FIXTURE_PATH),
            "--artifacts-root",
            str(tmp_path),
            "--experiment-id",
            "cli-offline",
        ],
        cwd=ROOT,
        env=cli_env(),
        text=True,
        capture_output=True,
        check=False,
    )

    assert evaluate.returncode == 0
    assert "offline evaluation written" in evaluate.stdout

    inspect = subprocess.run(
        [
            sys.executable,
            "-m",
            "project_recovery_council",
            "inspect-experiment",
            str(tmp_path / "cli-offline"),
        ],
        cwd=ROOT,
        env=cli_env(),
        text=True,
        capture_output=True,
        check=False,
    )

    assert inspect.returncode == 0
    assert "experiment artifact inspection passed" in inspect.stdout
