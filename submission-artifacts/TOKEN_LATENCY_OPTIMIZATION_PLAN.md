# Token And Latency Optimization Plan

## Baseline From Dynamic Empirical Run

Run:

```text
live-variant-dynamic_expert_council-20260617T132007Z
```

Measured high-cost invocations:

| Agent | Input Tokens | Output Tokens | Total Tokens | Latency |
|---|---:|---:|---:|---:|
| EvidenceAuditor | 5997 | 1250 | 7247 | 24.12s |
| RecoveryPlanner | 9650 | 609 | 10259 | 12.82s |

The dynamic council produced the strongest quality and governance result, but
these two invocations dominate its token budget.

## Low-Risk Optimizations

### Tighter Evidence Selection

EvidenceAuditor currently received 8 selected evidence records and 16275
serialized payload bytes. Reduce this by selecting only records cited by
normalized specialist claims plus known contradiction candidates. Measure:

- selected evidence-record count
- serialized payload bytes
- input tokens
- citation recall

### Compact Canonical Claim Envelopes

Replace verbose specialist claim text with:

- canonical claim key
- normalized value
- citation IDs
- validation status
- short warning code

Keep full provider text in artifacts, but pass compact envelopes to governance
agents. Measure planner and auditor input tokens.

### Remove Repeated Schema Text

Prompts already avoid repeated full schemas in compact governance payloads, but
planner synthesis still includes substantial schema instructions. Replace full
schema blocks with schema ID plus concise required-output checklist where the
provider path supports it. Measure schema-valid response rate.

### Deterministic Arithmetic Outside The Model

Schedule and commercial arithmetic are deterministic. Pass computed validation
summaries rather than asking Auditor or Planner to re-derive:

- delivery movement
- float absorption
- milestone slip
- exposure arithmetic
- avoided exposure

Measure factual accuracy and token reduction.

### Citation Bundles By Reference

Instead of repeating evidence snippets, pass citation bundles keyed by record
ID:

```json
{
  "SCH-DELIVERY-001": "schedule arithmetic source",
  "COST-SUMMARY-001": "cost source"
}
```

Planner can cite IDs without receiving repeated excerpts. Measure citation
precision and recall.

## Architecture Changes

### Conditional EvidenceAuditor Invocation

Skip EvidenceAuditor when all specialist outputs are schema-valid,
role-valid, semantically valid, and cite only required source records. Replace
with deterministic citation verification. Invoke Auditor only for:

- unsupported or unknown claim keys
- citation gaps
- contradiction candidates
- semantic failures
- disagreement domains

This could remove a 7247-token invocation in low-risk cases, but needs new
empirical testing.

### Smaller Model For Routing Or Audit

Evaluate a smaller Qwen model for:

- Director routing
- EvidenceAuditor support-status classification
- low-risk citation audit

Do not switch without measuring schema validity, citation recall, and
contradiction handling.

### Two-Stage Planner

Split planner into:

1. deterministic recommendation-state builder
2. short Qwen narrative formatter

The model would format an already computed recommendation instead of carrying
the full synthesis burden. Measure recommendation correctness and output
latency.

## Items Requiring New Empirical Testing

- Any prompt-caching feature available at the selected endpoint.
- Smaller model substitution.
- Conditional Auditor skipping.
- Reduced planner prompt with schema checklist only.
- Reference-only citation bundles.
- Two-stage planner.

## Success Criteria

Optimization is acceptable only if the dynamic council preserves:

- required-fact accuracy at 1.0
- monetary accuracy at 1.0
- schedule accuracy at 1.0
- citation precision and recall near 1.0
- correct contradiction detection
- correct human escalation
- correct preferred option
- authorization gate correctness at 1.0

The goal is to lower the assurance premium, not to claim the dynamic council is
universally cheaper or faster than the generalist.
