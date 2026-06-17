# Build Checkpoint: Submission Package

Date: 2026-06-17

Git base: `72a2a43e974058ed64f29f00573587e244b17392`

## Scope

This checkpoint finalizes judge-facing competition evidence for the completed
three-way empirical Qwen comparison without making live network calls or
modifying prior empirical artifacts.

## Changes

- Analyzed the remaining dynamic-council role-scope failure from
  `live-variant-dynamic_expert_council-20260617T132007Z`.
- Classified the failure as policy false positive on schedule identifier keys:
  `installation_activity_id` and `contractual_milestone_id`.
- Added the minimum explicit ScheduleExpert correction:
  `contractual_milestone_id` normalizes to `milestone_id`, and
  `installation_activity_id` is allowed as a schedule identifier.
- Added a sanitized offline regression fixture for the captured ScheduleExpert
  response shape.
- Created `submission-artifacts/empirical-result-catalog.json`.
- Created judge-facing Markdown and HTML reports.
- Added report-ready SVG charts for fact accuracy, citation recall, total
  tokens, and latency.
- Drafted Devpost narrative, demo storyboard, demo narration, architecture
  diagram spec, token/latency optimization plan, and submission checklist.
- Added ADR-0017 and submission artifact regression tests.

## Verification

- `python -m pytest tests/test_role_scope_policy.py tests/test_claim_normalization.py tests/test_submission_artifacts.py`
  - `37 passed in 0.26s`
- `python -m pytest`
  - `174 passed, 1 skipped in 8.38s`
- `PYTHONPATH=src python -m project_recovery_council check-schema-drift`
  - `schema drift check passed`
- `PYTHONPATH=src python -m project_recovery_council validate-prompts`
  - `prompt validation passed`
- `git diff --check`
  - passed with no output

## Live Network

No live network request was made during this checkpoint.

## Preservation

Prior empirical live artifacts were not modified. Frozen `schemas/v1` contracts
and the deterministic oracle were not modified. The selected dynamic empirical
artifact still records role-scope compliance of 0.75.

## Submission Framing

The submission materials explicitly state that the results are single empirical
runs and are not statistically significant. They do not claim that the dynamic
council is cheaper, faster, production-ready, or perfectly role-compliant in
the original empirical artifact.
