import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).parents[1]
FIXTURE_PATH = ROOT / "sample-data" / "equipment-delay-case"


def cli_env() -> dict[str, str]:
    env = os.environ.copy()
    current = env.get("PYTHONPATH")
    src_path = str(ROOT / "src")
    env["PYTHONPATH"] = src_path if not current else os.pathsep.join([src_path, current])
    return env


def test_cli_success_exit_code(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "project_recovery_council",
            "run",
            "--case-path",
            str(FIXTURE_PATH),
            "--artifacts-root",
            str(tmp_path),
            "--run-id",
            "cli-success",
        ],
        cwd=ROOT,
        env=cli_env(),
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert "run completed" in result.stdout
    assert (tmp_path / "cli-success" / "run-summary.json").is_file()


def test_cli_failure_exit_code(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "project_recovery_council",
            "validate",
            "--case-path",
            str(tmp_path / "missing-fixture"),
        ],
        cwd=ROOT,
        env=cli_env(),
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 1
    assert "error:" in result.stderr

