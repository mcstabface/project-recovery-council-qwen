import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).parents[1]


def cli_env_without_credentials() -> dict[str, str]:
    env = os.environ.copy()
    current = env.get("PYTHONPATH")
    src_path = str(ROOT / "src")
    env["PYTHONPATH"] = src_path if not current else os.pathsep.join([src_path, current])
    env.pop("DASHSCOPE_API_KEY", None)
    return env


def test_live_smoke_requires_allow_network_before_credentials() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "project_recovery_council",
            "live-smoke",
            "--model",
            "explicit-test-model",
        ],
        cwd=ROOT,
        env=cli_env_without_credentials(),
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 1
    assert "requires --allow-network" in result.stderr
    assert "explicit-test-model" in result.stdout
    assert "Provider charges may apply" in result.stdout


def test_live_smoke_missing_credentials_fails_before_request() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "project_recovery_council",
            "live-smoke",
            "--model",
            "explicit-test-model",
            "--allow-network",
        ],
        cwd=ROOT,
        env=cli_env_without_credentials(),
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 1
    assert "missing required credential environment variable: DASHSCOPE_API_KEY" in result.stderr
    assert "dummy-secret" not in result.stdout
    assert "dummy-secret" not in result.stderr
