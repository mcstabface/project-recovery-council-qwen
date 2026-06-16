"""Command-line entry point for Project Recovery Council."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from project_recovery_council.runner import (
    replay_run,
    run_equipment_delay_case,
    validate_case_fixture,
)
from project_recovery_council.workflow import DEFAULT_ARTIFACTS_ROOT, DEFAULT_CASE_PATH


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="project_recovery_council")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="run the default equipment-delay workflow")
    run_parser.add_argument("--case-path", type=Path, default=DEFAULT_CASE_PATH)
    run_parser.add_argument("--artifacts-root", type=Path, default=DEFAULT_ARTIFACTS_ROOT)
    run_parser.add_argument("--run-id", default=None)
    run_parser.add_argument("--inject-commercial-failure", action="store_true")

    validate_parser = subparsers.add_parser("validate", help="validate the fixture bundle")
    validate_parser.add_argument("--case-path", type=Path, default=DEFAULT_CASE_PATH)

    replay_parser = subparsers.add_parser("replay", help="replay a prior run from replay input")
    replay_parser.add_argument("path", type=Path)
    replay_parser.add_argument("--artifacts-root", type=Path, default=None)
    replay_parser.add_argument("--run-id", default=None)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "validate":
            issues = validate_case_fixture(args.case_path)
            if issues:
                print("validation failed:")
                for issue in issues:
                    print(f"- {issue}")
                return 1
            print("validation passed")
            return 0

        if args.command == "run":
            default_id = (
                "equipment-delay-commercial-failure"
                if args.inject_commercial_failure
                else "equipment-delay-standard"
            )
            result = run_equipment_delay_case(
                case_path=args.case_path,
                artifacts_root=args.artifacts_root,
                run_id=args.run_id or default_id,
                inject_commercial_failure=args.inject_commercial_failure,
            )
            print(f"run completed: {result.run_path}")
            return 0

        if args.command == "replay":
            result = replay_run(
                args.path,
                artifacts_root=args.artifacts_root,
                run_id=args.run_id,
            )
            equivalent = result.replay_comparison["equivalent"] if result.replay_comparison else False
            print(f"replay completed: {result.run_path}")
            print(f"logically equivalent: {str(equivalent).lower()}")
            return 0 if equivalent else 1

    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    parser.error(f"unsupported command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

