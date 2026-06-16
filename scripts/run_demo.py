"""Run the deterministic Project Recovery Council demo.

This script is cross-platform and does not rely on shell-specific syntax.
It works with an installed package and also from a source checkout.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _ensure_source_tree_import() -> None:
    root = Path(__file__).resolve().parents[1]
    src = root / "src"
    if src.is_dir() and str(src) not in sys.path:
        sys.path.insert(0, str(src))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the deterministic equipment-delay demo.")
    parser.add_argument("--artifacts-root", type=Path, default=Path("session-artifacts") / "runs")
    parser.add_argument("--run-id", default="script-demo")
    parser.add_argument("--replace-existing", action="store_true")
    parser.add_argument("--inject-commercial-failure", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    _ensure_source_tree_import()
    from project_recovery_council.runner import demo_equipment_delay_case

    args = build_parser().parse_args(argv)
    try:
        summary = demo_equipment_delay_case(
            artifacts_root=args.artifacts_root,
            run_id=args.run_id,
            replace_existing=args.replace_existing,
            inject_commercial_failure=args.inject_commercial_failure,
        )
    except Exception as exc:
        print(f"demo failed: {exc}", file=sys.stderr)
        return 1

    print(f"run_path: {summary['run_path']}")
    print(f"projected_delay_days: {summary['projected_delay_days']}")
    print(f"unmitigated_exposure_usd: {summary['unmitigated_exposure_usd']}")
    print(f"mitigation_cost_usd: {summary['mitigation_cost_usd']}")
    print(f"gross_avoided_exposure_usd: {summary['gross_avoided_exposure_usd']}")
    print(f"contradiction_status: {summary['contradiction_status']}")
    print(f"human_decision_status: {summary['human_decision_status']}")
    print(f"final_approval_status: {summary['final_approval_status']}")
    print(f"artifact_inspection: {'passed' if summary['inspection_passed'] else 'failed'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

