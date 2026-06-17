# Qwen Agent Society Results

## 1. Executive Summary

Project Recovery Council tests whether a dynamically routed modular expert
council can produce a higher-assurance enterprise decision than a single
general-purpose agent on a synthetic equipment-delay recovery case.

In one empirical run per variant using `qwen-plus`, the single generalist was
fastest and lowest-token. It was factually strong, but incomplete in evidence
provenance. The fixed expert chain showed that adding agents without governed
handoff can degrade results. The dynamic expert council produced the most
complete, cited, and governable decision, but paid a substantial token and
latency premium.

The value proposition is higher assurance for consequential decisions, not
universal efficiency.

## 2. Problem Statement

Enterprise recovery decisions often require schedule logic, commercial exposure
calculation, evidence contradiction handling, and human authorization gates. A
single model can often answer the visible question, but the organization also
needs traceable evidence, role boundaries, validation, and audit artifacts.

The synthetic case asks whether a delayed generator skid should use accelerated
logistics. The correct recommendation depends on:

- 21-day delivery movement
- 8 days of installation total float
- 13-day net milestone slip
- 15000 USD/day contractual exposure
- 195000 USD unmitigated exposure
- 48000 USD mitigation cost
- 147000 USD avoided exposure
- unresolved onsite-status contradiction
- human confirmation before authorization

## 3. Experiment Design

All three AI variants used the same synthetic case, same expected-result oracle,
same Qwen model, and same evaluation rules. These are single empirical runs and
do not establish statistical significance.

Selected empirical runs:

- Generalist: `live-variant-single_generalist-20260617T111645Z`
- Fixed chain: `live-variant-fixed_expert_chain-20260617T132617Z`
- Dynamic council: `live-variant-dynamic_expert_council-20260617T132007Z`

Source catalog:

- [empirical-result-catalog.json](empirical-result-catalog.json)

## 4. Architecture Variants

### Single Generalist

One `GeneralistAgent` received the complete evidence bundle and returned the
final analysis directly.

### Fixed Expert Chain

`ScheduleExpert`, `CommercialExpert`, `EvidenceAuditor`, `RiskExpert`, and
`RecoveryPlanner` ran in fixed order. The result shows that a sequential chain
without sufficiently robust synthesis behavior can lose useful specialist
findings.

### Dynamic Expert Council

`DirectorAgent` selected relevant specialists. Specialist outputs were checked
through deterministic claim normalization, role-scope validation, and semantic
validation where implemented. EvidenceAuditor reviewed claims and citations.
RecoveryPlanner consumed the validated-findings envelope and preserved the
human approval gate.

## 5. Results Table

| Variant | Facts | Citation Precision | Citation Recall | Human Gate | Recommendation | Invocations | Tokens | Latency |
|---|---:|---:|---:|---|---|---:|---:|---:|
| Generalist | 100% | 75% | 54.2% | Correct | Correct | 1 | 4298 | 15.0s |
| Fixed chain | 20% | 0% | 0% | Failed | Missing | 5 | 15090 | 37.0s |
| Dynamic council | 100% | 100% | 100% | Correct | Correct | 6 | 25785 | 66.5s |

Charts:

- [Required fact accuracy](charts/required_fact_accuracy.svg)
- [Citation recall](charts/citation_recall.svg)
- [Total tokens](charts/total_tokens.svg)
- [Latency](charts/latency.svg)

## 6. Quality-Versus-Cost Interpretation

The generalist delivered excellent factual performance with one invocation,
4298 tokens, and 15.0 seconds. Its main weakness was citation recall: it
provided only 54.2% of required source references.

The dynamic council matched the generalist on factual correctness and improved
citation precision and recall to 100%. It also produced a correct authorization
state: recommendation available, approval required, authorization blocked
pending human confirmation.

That governance came at a cost: 6 invocations, 25785 tokens, and 66.5 seconds.
The dynamic council should not be described as cheaper or faster than the
generalist. Its case is assurance, provenance, and controlled decision
governance for consequential work.

## 7. Fixed-Chain Failure Analysis

The fixed chain was not intentionally weakened. It used the same model and the
same expert prompt family as the dynamic council. It failed because useful
specialist work did not survive into a successful final synthesis.

Observed outcome:

- required fact accuracy: 20%
- monetary accuracy: 0%
- schedule accuracy: 0%
- citation precision and recall: 0%
- final recommendation missing

This is an important result: adding agents mechanically does not guarantee a
better enterprise decision. The handoff and validation architecture matters.

## 8. Dynamic-Council Governance Result

The dynamic council produced the strongest result:

- required fact accuracy: 100%
- monetary accuracy: 100%
- schedule accuracy: 100%
- citation precision and recall: 100%
- contradiction detection: correct
- human escalation: correct
- preferred recovery option: correct
- authorization gate correctness: 100%
- semantic validation compliance: 100%

Recorded role-scope compliance was 0.75. Post-run offline analysis found the
remaining failure was policy drift on two legitimate schedule identifiers:
`installation_activity_id` and `contractual_milestone_id`. The original
empirical artifact remains unchanged and still records 0.75.

See:

- [Remaining role-scope analysis](../docs/REMAINING_ROLE_SCOPE_ANALYSIS.md)

## 9. Limitations

- One empirical run per variant is not statistically significant.
- Hosted model outputs may vary across runs.
- Provider cost is unavailable because explicit pricing was not supplied.
- The dynamic council was slower and used more tokens than the generalist.
- The fixed-chain result is a single run and should not be generalized without
  repeated trials.
- No production deployment is claimed.

## 10. Reproducibility And Evidence References

The submission catalog records experiment IDs, model configuration, summary
metrics, and artifact manifest checksums. Raw provider responses are not copied
into `submission-artifacts/`.

Primary source artifact directories:

- `experiment-artifacts/live/live-variant-single_generalist-20260617T111645Z`
- `experiment-artifacts/live/live-variant-fixed_expert_chain-20260617T132617Z`
- `experiment-artifacts/live/live-variant-dynamic_expert_council-20260617T132007Z`

Manifest checksums:

- Generalist: `f6b9e9e79b694477b1b0972fcb7cb8bd43bbb935247088990beec998540590d2`
- Fixed chain: `55633c0ed915b28ff96f27b0fa120927df54a02fcbd5496115c099ed011a840c`
- Dynamic council: `8367e9998e903c884c3f4999daedaf1e6e0a8bec8cd5880637dcddc904ee4107`
