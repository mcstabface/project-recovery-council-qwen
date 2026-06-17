import json
import re
import socket
from pathlib import Path
from typing import Any


ROOT = Path(__file__).parents[1]
SUBMISSION = ROOT / "submission-artifacts"
CATALOG_PATH = SUBMISSION / "empirical-result-catalog.json"


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def metric(report: dict[str, Any], metric_id: str) -> float | None:
    for item in report["metric_results"]:
        if item["metric_id"] == metric_id:
            return item["score"]
    raise AssertionError(f"metric not found: {metric_id}")


def test_selected_empirical_run_ids_exist_in_catalog() -> None:
    catalog = read_json(CATALOG_PATH)
    ids = {run["experiment_id"] for run in catalog["runs"]}

    assert "live-variant-single_generalist-20260617T111645Z" in ids
    assert "live-variant-fixed_expert_chain-20260617T132617Z" in ids
    assert "live-variant-dynamic_expert_council-20260617T132007Z" in ids
    assert catalog["raw_provider_responses_copied"] is False


def test_reported_numbers_match_source_artifacts() -> None:
    catalog = read_json(CATALOG_PATH)
    for run in catalog["runs"]:
        artifact_path = ROOT / run["artifact_path"]
        final = read_json(artifact_path / "final-variant-result.json")
        evaluation = read_json(artifact_path / "evaluation-results.json")["report"]

        assert artifact_path.exists()
        assert run["invocation_count"] == final["total_invocation_count"]
        assert run["total_tokens"] == final["total_tokens"]
        assert run["latency_seconds"] == final["latency_seconds"]
        assert run["factual_metrics"]["required_fact_accuracy"] == metric(evaluation, "required_fact_accuracy")
        assert run["factual_metrics"]["monetary_calculation_accuracy"] == metric(
            evaluation, "monetary_calculation_accuracy"
        )
        assert run["factual_metrics"]["schedule_impact_accuracy"] == metric(evaluation, "schedule_impact_accuracy")
        assert run["citation_metrics"]["evidence_citation_precision"] == metric(
            evaluation, "evidence_citation_precision"
        )
        assert run["citation_metrics"]["evidence_citation_recall"] == metric(evaluation, "evidence_citation_recall")


def test_dynamic_result_is_not_labeled_cheaper_or_faster() -> None:
    report = (SUBMISSION / "QWEN_AGENT_SOCIETY_RESULTS.md").read_text(encoding="utf-8").lower()
    narrative = (SUBMISSION / "DEVPOST_DRAFT.md").read_text(encoding="utf-8").lower()

    assert "dynamic council should not be described as cheaper or faster" in report
    assert "it is not cheaper or faster" in narrative
    assert "dynamic council is fastest" not in report
    assert "dynamic council is cheapest" not in report
    assert "dynamic council is fastest" not in narrative
    assert "dynamic council is cheapest" not in narrative


def test_single_run_limitation_is_present() -> None:
    files = [
        SUBMISSION / "empirical-result-catalog.json",
        SUBMISSION / "QWEN_AGENT_SOCIETY_RESULTS.md",
        SUBMISSION / "DEVPOST_DRAFT.md",
        SUBMISSION / "DEMO_NARRATION.md",
    ]
    for path in files:
        text = path.read_text(encoding="utf-8").lower()
        assert "single" in text
        assert "statistical" in text


def test_diagnostic_runs_are_excluded() -> None:
    catalog = read_json(CATALOG_PATH)
    excluded = catalog["excluded_runs"]

    assert any(item.get("experiment_id") == "live-variant-dynamic_expert_council-20260617T120357Z" for item in excluded)
    assert any(item.get("path_prefix") == "experiment-artifacts/live-diagnostics/" for item in excluded)
    assert all("live-diagnostics" not in run["artifact_path"] for run in catalog["runs"])


def test_raw_provider_responses_are_not_copied_into_submission_artifacts() -> None:
    forbidden_filenames = {"raw-provider-responses.json"}
    forbidden_json_keys = {"raw_response_text", "provider_request_id", "authorization", "api_key"}

    for path in SUBMISSION.rglob("*"):
        if path.is_dir():
            continue
        assert path.name not in forbidden_filenames
        if path.suffix != ".json":
            continue
        payload = read_json(path)
        serialized = json.dumps(payload)
        assert "chat.completion" not in serialized
        assert not forbidden_json_keys.intersection(_json_keys(payload))


def test_role_scope_analysis_matches_actual_offending_invocation() -> None:
    dynamic_path = ROOT / "experiment-artifacts/live/live-variant-dynamic_expert_council-20260617T132007Z"
    role_results = read_json(dynamic_path / "role-validation-results.json")
    invalid = [item for item in role_results if item["valid"] is False]
    analysis = (ROOT / "docs/REMAINING_ROLE_SCOPE_ANALYSIS.md").read_text(encoding="utf-8")

    assert len(invalid) == 1
    result = invalid[0]
    assert result["invocation_id"] == "INV-live-variant-dynamic_expert_council-20260617T132007Z-04-scheduleexpert"
    assert result["role"] == "ScheduleExpert"
    assert "installation_activity_id: claim key outside role policy" in result["prohibited_claims"]
    assert "contractual_milestone_id: claim key outside role policy" in result["prohibited_claims"]
    assert result["invocation_id"] in analysis
    assert "policy false positive" in analysis


def test_generated_report_links_reference_valid_relative_paths() -> None:
    markdown = SUBMISSION / "QWEN_AGENT_SOCIETY_RESULTS.md"
    html = SUBMISSION / "QWEN_AGENT_SOCIETY_RESULTS.html"
    markdown_text = markdown.read_text(encoding="utf-8")
    html_text = html.read_text(encoding="utf-8")
    links = re.findall(r"\[[^\]]+\]\(([^)]+)\)", markdown_text)
    links.extend(re.findall(r'(?:href|src)="([^"]+)"', html_text))

    for link in links:
        if "://" in link or link.startswith("#"):
            continue
        target = (SUBMISSION / link).resolve()
        assert target.exists(), link


def test_charts_are_generated() -> None:
    expected = {
        "required_fact_accuracy.svg",
        "citation_recall.svg",
        "total_tokens.svg",
        "latency.svg",
    }
    charts = SUBMISSION / "charts"
    assert expected == {path.name for path in charts.glob("*.svg")}
    for path in charts.glob("*.svg"):
        text = path.read_text(encoding="utf-8")
        assert "<svg" in text
        assert "<title" in text
        assert "<desc" in text


def test_submission_artifacts_do_not_require_network(monkeypatch) -> None:
    def fail_network(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("network should not be used by submission artifact tests")

    monkeypatch.setattr(socket, "create_connection", fail_network)
    assert read_json(CATALOG_PATH)["case_id"] == "PRC-EQ-DELAY-001"
    assert (SUBMISSION / "QWEN_AGENT_SOCIETY_RESULTS.md").exists()


def _json_keys(value: Any) -> set[str]:
    if isinstance(value, dict):
        keys = set(value)
        for item in value.values():
            keys.update(_json_keys(item))
        return keys
    if isinstance(value, list):
        keys: set[str] = set()
        for item in value:
            keys.update(_json_keys(item))
        return keys
    return set()
