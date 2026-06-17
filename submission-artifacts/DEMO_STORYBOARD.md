# Three-Minute Demo Storyboard

## 0:00-0:25 - Problem And Case Introduction

Screen:

- README title: Project Recovery Council - Qwen Agent Society Edition
- `sample-data/equipment-delay-case/expected-results.json`
- quick view of `sample-data/equipment-delay-case/schedule.json`

Narrative beat:

- A generator skid delivery moved 21 days later.
- Installation had 8 days float.
- The milestone slips 13 days without intervention.
- The case also has contradictory onsite-status evidence and requires human
  confirmation before authorization.

## 0:25-0:50 - Three Architecture Variants

Screen:

- `docs/EXPERIMENT_DESIGN.md`
- `submission-artifacts/ARCHITECTURE_DIAGRAM_SPEC.md`

Narrative beat:

- Compare one generalist, a fixed expert chain, and a dynamic expert council.
- Same case, same model, same oracle, same evaluation rules.

## 0:50-1:20 - Generalist Result

Screen:

- `submission-artifacts/QWEN_AGENT_SOCIETY_RESULTS.md`
- Results table row for Generalist
- `submission-artifacts/charts/citation_recall.svg`

Narrative beat:

- Generalist was fastest and lowest-token.
- It got the facts right.
- Citation recall was incomplete at 54.2%.

## 1:20-1:45 - Fixed-Chain Failure

Screen:

- Results table row for Fixed chain
- `experiment-artifacts/live/live-variant-fixed_expert_chain-20260617T132617Z/synthesis-metrics.json`

Narrative beat:

- Adding agents mechanically did not help.
- The fixed chain completed five invocations but failed final synthesis.
- This demonstrates that governed handoff matters.

## 1:45-2:30 - Dynamic Council Governance

Screen:

- `experiment-artifacts/live/live-variant-dynamic_expert_council-20260617T132007Z/routing-decisions.json`
- `role-validation-results.json`
- `evidence-auditor-validation-results.json`
- `validated-findings-envelope.json`
- `recommendation-authorization-state.json`

Narrative beat:

- Director selected relevant experts.
- Specialists used scoped evidence.
- EvidenceAuditor checked claims and citations.
- RecoveryPlanner recommended accelerated logistics.
- Authorization stayed blocked pending human confirmation.
- Post-run analysis identified the remaining role-scope issue as schedule
  identifier policy drift, not a substantive role violation.

## 2:30-2:50 - Comparison Table And Cost Tradeoff

Screen:

- `submission-artifacts/QWEN_AGENT_SOCIETY_RESULTS.html`
- Charts:
  - `charts/required_fact_accuracy.svg`
  - `charts/total_tokens.svg`
  - `charts/latency.svg`

Narrative beat:

- Dynamic council had the best quality and provenance.
- It was also the slowest and highest-token option.
- The claim is assurance for consequential decisions, not universal
  efficiency.

## 2:50-3:00 - Closing Value Proposition

Screen:

- `submission-artifacts/DEVPOST_DRAFT.md`
- `submission-artifacts/SUBMISSION_CHECKLIST.md`

Narrative beat:

- For high-stakes recovery decisions, the system provides cited facts,
  validation, human gates, and auditability.
- The deterministic oracle remains the regression baseline.
