"""Command-line entry point for Project Recovery Council."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from project_recovery_council.runner import (
    approve_workflow,
    demo_equipment_delay_case,
    inspect_run,
    replay_run,
    resume_workflow,
    run_equipment_delay_case,
    start_equipment_delay_case,
    submit_decision,
    validate_case_fixture,
    workflow_status,
)
from project_recovery_council.schemas import check_schema_drift, export_schemas
from project_recovery_council.experiment_artifacts import validate_experiment_artifacts
from project_recovery_council.experiment_contracts import ExperimentVariant
from project_recovery_council.live_experiments import (
    LIVE_ARTIFACT_ROOT,
    run_live_agent,
    run_live_smoke,
)
from project_recovery_council.live_variant_runner import (
    LiveRunControls,
    compare_live_variant_runs,
    live_variant_completed,
    run_controlled_live_variant,
)
from project_recovery_council.offline_experiments import (
    DEFAULT_COMPARISON_FIXTURES,
    compare_offline_fixtures,
    write_offline_evaluation_artifacts,
)
from project_recovery_council.prompt_catalog import validate_prompt_catalog
from project_recovery_council.qwen_config import StructuredOutputMode, qwen_config_from_env
from project_recovery_council.workflow import DEFAULT_ARTIFACTS_ROOT, DEFAULT_CASE_PATH


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="prc-qwen")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="run the default equipment-delay workflow")
    run_parser.add_argument("--case-path", type=Path, default=DEFAULT_CASE_PATH)
    run_parser.add_argument("--artifacts-root", type=Path, default=DEFAULT_ARTIFACTS_ROOT)
    run_parser.add_argument("--run-id", default=None)
    run_parser.add_argument("--inject-commercial-failure", action="store_true")
    run_parser.add_argument("--replace-existing", action="store_true")

    start_parser = subparsers.add_parser("start", help="start and pause at the first human gate")
    start_parser.add_argument("--case-path", type=Path, default=DEFAULT_CASE_PATH)
    start_parser.add_argument("--artifacts-root", type=Path, default=DEFAULT_ARTIFACTS_ROOT)
    start_parser.add_argument("--run-id", default="equipment-delay-paused")
    start_parser.add_argument("--inject-commercial-failure", action="store_true")
    start_parser.add_argument("--replace-existing", action="store_true")

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

    subparsers.add_parser("check-schema-drift", help="compare generated schemas with committed v1 schemas")

    demo_parser = subparsers.add_parser("demo", help="run complete deterministic demo lifecycle")
    demo_parser.add_argument("--case-path", type=Path, default=DEFAULT_CASE_PATH)
    demo_parser.add_argument("--artifacts-root", type=Path, default=DEFAULT_ARTIFACTS_ROOT)
    demo_parser.add_argument("--run-id", default="deterministic-demo")
    demo_parser.add_argument("--inject-commercial-failure", action="store_true")
    demo_parser.add_argument("--replace-existing", action="store_true")

    validate_parser = subparsers.add_parser("validate", help="validate the fixture bundle")
    validate_parser.add_argument("--case-path", type=Path, default=DEFAULT_CASE_PATH)

    replay_parser = subparsers.add_parser("replay", help="replay a prior run from replay input")
    replay_parser.add_argument("path", type=Path)
    replay_parser.add_argument("--artifacts-root", type=Path, default=None)
    replay_parser.add_argument("--run-id", default=None)
    replay_parser.add_argument("--replace-existing", action="store_true")

    evaluate_parser = subparsers.add_parser("evaluate-offline", help="evaluate a simulated offline response fixture")
    evaluate_parser.add_argument("--fixture", default="strong_modular_council")
    evaluate_parser.add_argument("--case-path", type=Path, default=DEFAULT_CASE_PATH)
    evaluate_parser.add_argument("--artifacts-root", type=Path, default=Path("experiment-artifacts"))
    evaluate_parser.add_argument("--experiment-id", default=None)

    compare_parser = subparsers.add_parser("compare-offline", help="compare simulated offline response fixtures")
    compare_parser.add_argument("--case-path", type=Path, default=DEFAULT_CASE_PATH)
    compare_parser.add_argument("--fixtures", nargs="*", default=DEFAULT_COMPARISON_FIXTURES)

    subparsers.add_parser("validate-prompts", help="validate the versioned competition prompt catalog")

    inspect_experiment_parser = subparsers.add_parser("inspect-experiment", help="validate experiment artifact contract")
    inspect_experiment_parser.add_argument("path", type=Path)

    live_smoke_parser = subparsers.add_parser("live-smoke", help="run one opt-in live Qwen smoke request")
    _add_live_provider_args(live_smoke_parser)

    live_agent_parser = subparsers.add_parser("live-agent", help="run one named live Qwen agent")
    live_agent_parser.add_argument("--agent", required=True)
    live_agent_parser.add_argument("--case-path", type=Path, default=DEFAULT_CASE_PATH)
    _add_live_provider_args(live_agent_parser)

    live_variant_parser = subparsers.add_parser("live-variant", help="run one live Qwen experiment variant")
    live_variant_parser.add_argument(
        "--variant",
        required=True,
        choices=[
            ExperimentVariant.SINGLE_GENERALIST.value,
            ExperimentVariant.FIXED_EXPERT_CHAIN.value,
            ExperimentVariant.DYNAMIC_EXPERT_COUNCIL.value,
        ],
    )
    live_variant_parser.add_argument("--case-path", type=Path, default=DEFAULT_CASE_PATH)
    _add_live_provider_args(live_variant_parser)
    _add_live_control_args(live_variant_parser)

    compare_live_parser = subparsers.add_parser("compare-live", help="compare three completed live variant runs")
    compare_live_parser.add_argument("--generalist", required=True, type=Path)
    compare_live_parser.add_argument("--fixed-chain", required=True, type=Path)
    compare_live_parser.add_argument("--dynamic-council", required=True, type=Path)
    compare_live_parser.add_argument("--output-root", type=Path, default=Path("experiment-artifacts") / "live-comparisons")
    compare_live_parser.add_argument("--comparison-id", default=None)
    compare_live_parser.add_argument("--allow-incomplete", action="store_true")

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
                replace_existing=args.replace_existing,
            )
            print(f"run completed: {result.run_path}")
            return 0

        if args.command == "start":
            result = start_equipment_delay_case(
                case_path=args.case_path,
                artifacts_root=args.artifacts_root,
                run_id=args.run_id,
                inject_commercial_failure=args.inject_commercial_failure,
                replace_existing=args.replace_existing,
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

        if args.command == "check-schema-drift":
            result = check_schema_drift()
            if result.passed:
                print("schema drift check passed")
                return 0
            print("schema drift check failed:")
            for message in result.messages:
                print(f"- {message}")
            return 1

        if args.command == "demo":
            summary = demo_equipment_delay_case(
                case_path=args.case_path,
                artifacts_root=args.artifacts_root,
                run_id=args.run_id,
                inject_commercial_failure=args.inject_commercial_failure,
                replace_existing=args.replace_existing,
            )
            print("demo completed")
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

        if args.command == "replay":
            result = replay_run(
                args.path,
                artifacts_root=args.artifacts_root,
                run_id=args.run_id,
                replace_existing=args.replace_existing,
            )
            equivalent = result.replay_comparison["equivalent"] if result.replay_comparison else False
            print(f"replay completed: {result.run_path}")
            print(f"logically equivalent: {str(equivalent).lower()}")
            return 0 if equivalent else 1

        if args.command == "evaluate-offline":
            run_path = write_offline_evaluation_artifacts(
                args.fixture,
                case_path=args.case_path,
                artifacts_root=args.artifacts_root,
                experiment_id=args.experiment_id,
            )
            print(f"offline evaluation written: {run_path}")
            return 0

        if args.command == "compare-offline":
            comparison = compare_offline_fixtures(args.fixtures, case_path=args.case_path)
            print(f"offline comparison: {comparison.comparison_id}")
            for row in comparison.rows:
                fact_score = row.metric_scores.get("required_fact_accuracy")
                schema = "valid" if row.schema_valid else "invalid"
                print(
                    f"{row.variant.value}:{row.fixture_id} "
                    f"required_fact_accuracy={fact_score} schema={schema} "
                    f"unsupported_claims={row.unsupported_claim_count}"
                )
            return 0

        if args.command == "validate-prompts":
            issues = validate_prompt_catalog()
            if issues:
                print("prompt validation failed:")
                for issue in issues:
                    print(f"- {issue}")
                return 1
            print("prompt validation passed")
            return 0

        if args.command == "inspect-experiment":
            result = validate_experiment_artifacts(args.path)
            if result.passed:
                print("experiment artifact inspection passed")
                return 0
            print("experiment artifact inspection failed:")
            for error in result.errors:
                print(f"- {error}")
            return 1

        if args.command == "live-smoke":
            config = _live_config_from_args(args)
            _print_live_notice(config)
            run_path = run_live_smoke(
                config=config,
                allow_network=args.allow_network,
                artifacts_root=args.artifacts_root,
                experiment_id=args.experiment_id,
                replace_existing=args.replace_existing,
            )
            print(f"live smoke artifacts written: {run_path}")
            return 0

        if args.command == "live-agent":
            config = _live_config_from_args(args)
            _print_live_notice(config)
            run_path = run_live_agent(
                agent_role=args.agent,
                config=config,
                allow_network=args.allow_network,
                case_path=args.case_path,
                artifacts_root=args.artifacts_root,
                experiment_id=args.experiment_id,
                replace_existing=args.replace_existing,
            )
            print(f"live agent artifacts written: {run_path}")
            return 0

        if args.command == "live-variant":
            config = _live_config_from_args(args)
            _print_live_notice(config)
            controls = LiveRunControls(
                max_invocation_count=args.max_invocation_count,
                max_total_input_tokens=args.max_total_input_tokens,
                max_total_output_tokens=args.max_total_output_tokens,
                max_elapsed_seconds=args.max_elapsed_seconds,
                max_retries_per_invocation=args.max_retries_per_invocation,
                stop_after_invocation=args.stop_after_invocation,
            )
            run_path = run_controlled_live_variant(
                variant=args.variant,
                config=config,
                allow_network=args.allow_network,
                controls=controls,
                case_path=args.case_path,
                artifacts_root=args.artifacts_root,
                experiment_id=args.experiment_id,
                replace_existing=args.replace_existing,
            )
            print(f"live variant artifacts written: {run_path}")
            return 0 if live_variant_completed(run_path) else 1

        if args.command == "compare-live":
            run_path = compare_live_variant_runs(
                generalist_path=args.generalist,
                fixed_chain_path=args.fixed_chain,
                dynamic_council_path=args.dynamic_council,
                output_root=args.output_root,
                comparison_id=args.comparison_id,
                allow_incomplete=args.allow_incomplete,
            )
            print(f"live comparison artifacts written: {run_path}")
            return 0

    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    parser.error(f"unsupported command: {args.command}")
    return 2


def _add_live_provider_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--allow-network", action="store_true", help="required acknowledgement for live provider calls")
    parser.add_argument("--model", required=True, help="Qwen model identifier for this live run")
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--api-key-env-var", default=None)
    parser.add_argument("--timeout-seconds", type=float, default=None)
    parser.add_argument("--max-retries", type=int, default=None)
    parser.add_argument("--retry-initial-seconds", type=float, default=None)
    parser.add_argument("--retry-multiplier", type=float, default=None)
    parser.add_argument("--retry-max-seconds", type=float, default=None)
    parser.add_argument("--temperature", type=float, default=None)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument(
        "--structured-output-mode",
        choices=[mode.value for mode in StructuredOutputMode],
        default=None,
    )
    parser.add_argument("--provider-region-label", default=None)
    parser.add_argument("--artifacts-root", type=Path, default=LIVE_ARTIFACT_ROOT)
    parser.add_argument("--experiment-id", default=None)
    parser.add_argument("--replace-existing", action="store_true")


def _add_live_control_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--max-invocation-count", type=int, default=8)
    parser.add_argument("--max-total-input-tokens", type=int, default=100000)
    parser.add_argument("--max-total-output-tokens", type=int, default=50000)
    parser.add_argument("--max-elapsed-seconds", type=float, default=300.0)
    parser.add_argument("--max-retries-per-invocation", type=int, default=2)
    parser.add_argument("--stop-after-invocation", type=int, default=None)


def _live_config_from_args(args: argparse.Namespace):
    return qwen_config_from_env(
        model_identifier=args.model,
        api_key_env_var=args.api_key_env_var,
        base_url=args.base_url,
        request_timeout_seconds=args.timeout_seconds,
        maximum_retries=args.max_retries,
        retry_initial_seconds=args.retry_initial_seconds,
        retry_multiplier=args.retry_multiplier,
        retry_max_seconds=args.retry_max_seconds,
        temperature=args.temperature,
        seed=args.seed,
        structured_output_mode=args.structured_output_mode,
        provider_region_label=args.provider_region_label,
    )


def _print_live_notice(config) -> None:
    print("Live Qwen execution requested.")
    print(f"model: {config.model_identifier}")
    print(f"endpoint: {config.base_url}")
    print(f"region_label: {config.provider_region_label}")
    print("Provider charges may apply. API keys and authorization headers will not be printed.")


if __name__ == "__main__":
    raise SystemExit(main())
