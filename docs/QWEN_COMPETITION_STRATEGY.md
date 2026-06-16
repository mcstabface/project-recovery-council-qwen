# Qwen Competition Strategy

This repository tests a narrow competition claim: a dynamically routed modular
expert council may outperform a single general-purpose agent on a complex
enterprise recovery decision.

The deterministic Project Recovery Council implementation remains the oracle.
It supplies expected facts, regression coverage, and artifact discipline. It is
not an AI competitor.

## Competitors

- `single_generalist`: one Qwen-backed agent receives the complete evidence
  package and returns the final recommendation.
- `fixed_expert_chain`: all expert roles run in a fixed sequence with no
  dynamic routing.
- `dynamic_expert_council`: a Director selects relevant experts, specialists
  work independently, an Evidence Auditor checks claims, an Arbiter preserves or
  resolves disagreement, and the Recovery Planner recommends an option.

## Current Run Scope

This run establishes contracts, prompts, offline fixtures, evaluation models,
and CLI commands. It does not call live Qwen, require credentials, perform
network access in tests, or add Alibaba Cloud deployment code.

## Evidence Discipline

All AI variants must cite stable source record IDs from the synthetic evidence
bundle. Unsupported onsite assertions are prohibited until human confirmation
resolves the contradiction between progress, supplier, and logistics records.

## Result Claims

Offline fixtures are simulated outputs for test coverage. They must not be
presented as empirical Qwen performance results.
