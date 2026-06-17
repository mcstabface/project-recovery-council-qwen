# Devpost Draft

## Project Title

Project Recovery Council: Qwen Agent Society Edition

## Tagline

A governed Qwen expert council for high-assurance project recovery decisions.

## Problem

Enterprise project recovery decisions are rarely just question answering. A
team needs to reconcile schedule impact, commercial exposure, conflicting
evidence, recovery options, and human approval gates. A single model can often
produce a plausible recommendation, but leaders still need evidence provenance,
role boundaries, validation, and audit artifacts before acting.

## Solution

Project Recovery Council models the decision as a governed agent society. It
compares:

- a single generalist Qwen agent
- a fixed sequential expert chain
- a dynamically routed expert council

The dynamic council uses a Director to select relevant experts, specialist
prompts with scoped evidence, deterministic claim normalization, role-scope and
semantic validation, an Evidence Auditor, a validated-findings envelope, and a
Recovery Planner that separates recommendation from authorization.

## Why An Agent Society

The case is consequential: a 21-day equipment delivery movement creates a
13-day projected milestone slip and 195000 USD unmitigated exposure. The
preferred recovery option is accelerated logistics, but authorization remains
blocked because onsite-status evidence is contradictory.

An agent society helps because each role can be bounded:

- ScheduleExpert handles schedule arithmetic.
- CommercialExpert handles exposure and mitigation calculations.
- RiskExpert handles human-gate and contradiction risk.
- EvidenceAuditor checks claims and citations.
- RecoveryPlanner synthesizes only validated findings.

The point is not that more agents are always better. The fixed-chain result
shows the opposite: adding agents without governed handoff can degrade the
final answer.

## How It Works

1. Load the synthetic equipment-delay case and deterministic expected results.
2. Run one selected live variant with explicit `--allow-network`.
3. Render versioned prompts with role-scoped evidence.
4. Parse structured Qwen responses through role-specific contracts.
5. Normalize explicit claim aliases to canonical keys.
6. Validate role scope and domain semantics.
7. Build a compact validated-findings envelope.
8. Preserve unresolved contradictions and human approval gates.
9. Evaluate the final structured result against the deterministic oracle.
10. Write checksummed artifacts for replay and inspection.

## Architecture

The dynamic council consists of:

- case evidence bundle
- DirectorAgent
- selected specialists
- EvidenceAuditor
- optional ArbiterAgent
- validated-findings envelope
- RecoveryPlanner
- human approval gate
- final recommendation and audit artifacts

The deterministic reference implementation remains the oracle and regression
baseline.

## Empirical Evaluation

All selected runs used `qwen-plus` with the same synthetic case and evaluation
rules. These are single empirical runs and are not statistically significant.

| Variant | Facts | Citation Precision | Citation Recall | Human Gate | Recommendation | Invocations | Tokens | Latency |
|---|---:|---:|---:|---|---|---:|---:|---:|
| Generalist | 100% | 75% | 54.2% | Correct | Correct | 1 | 4298 | 15.0s |
| Fixed chain | 20% | 0% | 0% | Failed | Missing | 5 | 15090 | 37.0s |
| Dynamic council | 100% | 100% | 100% | Correct | Correct | 6 | 25785 | 66.5s |

The generalist was fastest and lowest-token. The dynamic council produced the
most complete, cited, and governable result, but it was slower and more
expensive in tokens. It is not cheaper or faster than the generalist.

## Business Value

For high-consequence project recovery, the value is not universal efficiency.
The value is assurance:

- cited evidence for each material claim
- explicit contradiction handling
- human authorization gates
- deterministic validation against expected results
- replayable artifacts
- transparent failure modes

This is useful when a recommendation may affect schedule liability, mitigation
spend, supplier escalation, or executive approval.

## Technical Implementation

- Python package with frozen v1 domain contracts
- provider-neutral `ModelClient`
- opt-in Qwen live client
- versioned prompt catalog
- role-specific evidence-access policy
- claim-key normalization
- ScheduleExpert and CommercialExpert semantic validation
- dedicated EvidenceAuditor nested response contract
- controlled live variant runner
- artifact manifests and checksum validation
- offline comparison and diagnostic rebuild tooling

## Alibaba/Qwen Usage

The empirical comparison used Qwen through the live provider integration with
`qwen-plus`, DashScope API-key configuration via `DASHSCOPE_API_KEY`, and
prompted JSON structured output with local Pydantic validation. Live execution
is opt-in and never required for installation, imports, offline evaluation, or
normal tests.

## Challenges

- Ensuring live provider calls never run during normal tests.
- Keeping raw provider responses immutable while improving deterministic
  processing around them.
- Designing role boundaries that are strict without rejecting legitimate
  schedule identifiers.
- Preventing the planner from confusing "recommendation" with
  "authorization".
- Avoiding the assumption that more agents automatically improve results.

## Lessons Learned

- A strong generalist can be excellent on facts but weaker on provenance.
- A fixed chain can fail if the handoff is not governed.
- Dynamic routing needs validation, not just prompt instructions.
- Evidence auditing benefits from a dedicated nested contract rather than a
  generic specialist schema.
- Higher assurance currently carries a token and latency premium.

## Future Work

- Repeat live runs to measure variance.
- Optimize EvidenceAuditor and RecoveryPlanner token usage.
- Evaluate smaller Qwen models for routing or low-risk audit steps.
- Add prompt caching where available.
- Add official deployment proof after the core comparison is finalized.
- Expand beyond one synthetic case.

## Repository And Evidence

Primary submission artifacts:

- `submission-artifacts/empirical-result-catalog.json`
- `submission-artifacts/QWEN_AGENT_SOCIETY_RESULTS.md`
- `submission-artifacts/QWEN_AGENT_SOCIETY_RESULTS.html`
- `submission-artifacts/DEMO_STORYBOARD.md`
- `submission-artifacts/DEMO_NARRATION.md`
- `submission-artifacts/ARCHITECTURE_DIAGRAM_SPEC.md`
- `submission-artifacts/TOKEN_LATENCY_OPTIMIZATION_PLAN.md`

Source empirical runs remain under `experiment-artifacts/live/`. Raw provider
responses are not copied into submission artifacts.
