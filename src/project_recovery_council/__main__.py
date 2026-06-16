"""Command-line entry point for Project Recovery Council."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from project_recovery_council.runner import (
    approve_workflow,
    inspect_run,
    replay_run,
    resume_workflow,
    run_equipment_delay_case,
    start_equipment_delay_case,
    submit_decision,
    validate_case_fixture,
    workflow_status,
)
from project_recovery_council.schemas import export_schemas
from project_recovery_council.workflow import DEFAULT_ARTIFACTS_ROOT, DEFAULT_CASE_PATH


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="project_recovery_council")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="run the default equipment-delay workflow")
    run_parser.add_argument("--case-path", type=Path, default=DEFAULT_CASE_PATH)
    run_parser.add_argument("--artifacts-root", type=Path, default=DEFAULT_ARTIFACTS_ROOT)
    run_parser.add_argument("--run-id", default=None)
    run_parser.add_argument("--inject-commercial-failure", action="store_true")

    start_parser = subparsers.add_parser("start", help="start and pause at the first human gate")
    start_parser.add_argument("--case-path", type=Path, default=DEFAULT_CASE_PATH)
    start_parser.add_argument("--artifacts-root", type=Path, default=DEFAULT_ARTIFACTS_ROOT)
    start_parser.add_argument("--run-id", default="equipment-delay-paused")
    start_parser.add_argument("--inject-commercial-failure", action="store_true")

    status_parser = subparsers.add_parser("status", help="show persisted workflow status")
    status_parser.add_argument("run_path", type=Path)

    decide_parser = subparsers.add_parser("decide", help="record a human decision for a paused run")
    decide_parser.add_argument("run_path", type=Path)
    decide_parser.add_argument("--request-id", required=True)
    decide_parser.add_argument("--decision", required=True, choices=["equipment_not_onsite"])
    decide_parser.add_argument("--actor", required=True)

    resume_parser = subparsers.add_parser("resume", help="resume after a recorded human decision")
    resume_parser.add_argument("run_path", type=Path)

    approve_parser = subparsers.add_parser("approve", help="record final approval and complete the run")
    approve_parser.add_argument("run_path", type=Path)
    approve_parser.add_argument("--actor", required=True)

    inspect_parser = subparsers.add_parser("inspect", help="validate run artifact contract")
    inspect_parser.add_argument("run_path", type=Path)

    schemas_parser = subparsers.add_parser("export-schemas", help="export v1 JSON Schemas")
    schemas_parser.add_argument("--output-dir", type=Path, default=Path("schemas") / "v1")

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

        if args.command == "start":
            result = start_equipment_delay_case(
                case_path=args.case_path,
                artifacts_root=args.artifacts_root,
                run_id=args.run_id,
                inject_commercial_failure=args.inject_commercial_failure,
            )
            print(f"run started: {result.run_path}")
            print(f"stage: {result.context.state.value}")
            return 0

        if args.command == "status":
            status = workflow_status(args.run_path)
            print(f"run_id: {status['run_id']}")
            print(f"stage: {status['stage']}")
            for request in status["pending_requests"]:
                print(f"pending: {request['decision_request_id']} - {request['question']}")
            print(f"approval_state: {status['approval_state']}")
            return 0

        if args.command == "decide":
            result = submit_decision(
                args.run_path,
                request_id=args.request_id,
                decision=args.decision,
                actor=args.actor,
            )
            print(f"decision recorded: {args.request_id}")
            print(f"stage: {result.context.state.value}")
            return 0

        if args.command == "resume":
            result = resume_workflow(args.run_path)
            print(f"run resumed: {result.run_path}")
            print(f"stage: {result.context.state.value}")
            return 0

        if args.command == "approve":
            result = approve_workflow(args.run_path, actor=args.actor)
            print(f"approval recorded: {args.actor}")
            print(f"stage: {result.context.state.value}")
            return 0

        if args.command == "inspect":
            result = inspect_run(args.run_path)
            if result.passed:
                print("artifact inspection passed")
                return 0
            print("artifact inspection failed:")
            for error in result.errors:
                print(f"- {error}")
            return 1

        if args.command == "export-schemas":
            catalog = export_schemas(args.output_dir)
            print(f"schemas exported: {args.output_dir}")
            print(f"schema count: {len(catalog)}")
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
