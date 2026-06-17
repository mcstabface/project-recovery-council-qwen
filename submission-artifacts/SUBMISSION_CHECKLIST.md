# Submission Checklist

## Repository

- [ ] Public repository link is available.
- [ ] MIT license is visible.
- [ ] README identifies the Qwen Agent Society edition.
- [ ] Frozen `schemas/v1/` are unchanged from the intended baseline.
- [ ] No commits include live secrets.

## Alibaba And Qwen Usage Evidence

- [ ] Live empirical runs identify `qwen-plus`.
- [ ] Live provider configuration is sanitized.
- [ ] API key is referenced only by environment variable name.
- [ ] No API key or authorization header appears in source, docs, tests, or
  submission artifacts.

## Deployment Proof

- [ ] Deployment proof is either attached or explicitly listed as future work.
- [ ] No unimplemented Alibaba Cloud deployment code is presented as complete.

## Architecture Diagram

- [ ] Diagram rendered from
  `submission-artifacts/ARCHITECTURE_DIAGRAM_SPEC.md`.
- [ ] Diagram shows Director, selected experts, EvidenceAuditor, optional
  Arbiter, validated-findings envelope, RecoveryPlanner, human gate, and audit
  artifacts.

## Demo Video

- [ ] Demo follows `submission-artifacts/DEMO_STORYBOARD.md`.
- [ ] Narration follows `submission-artifacts/DEMO_NARRATION.md`.
- [ ] Video states single-run limitation.
- [ ] Video states dynamic council is higher assurance but more expensive and
  slower than the generalist.

## Devpost Fields

- [ ] Title and tagline copied from `submission-artifacts/DEVPOST_DRAFT.md`.
- [ ] Problem, solution, architecture, evaluation, challenges, and future work
  are filled.
- [ ] No statistical significance claim.
- [ ] No production-readiness claim.
- [ ] No lower-cost-than-generalist claim for dynamic council.

## Empirical Results

- [ ] Use `submission-artifacts/empirical-result-catalog.json`.
- [ ] Results table matches source artifacts.
- [ ] Generalist run: `live-variant-single_generalist-20260617T111645Z`.
- [ ] Fixed-chain run: `live-variant-fixed_expert_chain-20260617T132617Z`.
- [ ] Dynamic-council run:
  `live-variant-dynamic_expert_council-20260617T132007Z`.
- [ ] Failed and diagnostic runs are excluded from normal comparison.

## Limitations

- [ ] One empirical run per variant is disclosed.
- [ ] Hosted-model variability is disclosed.
- [ ] Provider cost is unavailable without explicit pricing.
- [ ] Dynamic token and latency premium is disclosed.
- [ ] Recorded dynamic role-scope compliance remains 0.75 in the empirical
  artifact.

## Secret Scan

- [ ] Search for `DASHSCOPE_API_KEY` and ensure only environment variable names
  are present.
- [ ] Search for known dummy secret values in generated artifacts.
- [ ] Confirm `submission-artifacts/` does not contain raw provider responses.

## Live Artifact Handling

- [ ] Do not stage `experiment-artifacts/live/` unless intentionally adding a
  sanitized example.
- [ ] Do not modify prior empirical live artifacts.
- [ ] Preserve failed empirical runs as failed.

## Reproducibility

- [ ] Artifact manifest checksums are recorded in the empirical catalog.
- [ ] `python -m pytest` passes.
- [ ] `PYTHONPATH=src python -m project_recovery_council check-schema-drift`
  passes.
- [ ] `PYTHONPATH=src python -m project_recovery_council validate-prompts`
  passes.
- [ ] `git diff --check` passes.

## Final Link Verification

- [ ] `submission-artifacts/QWEN_AGENT_SOCIETY_RESULTS.md`
  links resolve locally.
- [ ] `submission-artifacts/QWEN_AGENT_SOCIETY_RESULTS.html`
  chart image links resolve locally.
- [ ] Chart SVG files exist under `submission-artifacts/charts/`.
