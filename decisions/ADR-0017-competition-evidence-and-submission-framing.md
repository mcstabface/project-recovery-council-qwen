# ADR-0017: Competition Evidence And Submission Framing

## Status

Accepted

## Context

The repository now contains a completed three-way empirical comparison for the
Qwen Agent Society submission:

- `single_generalist`
- `fixed_expert_chain`
- `dynamic_expert_council`

The dynamic council produced the strongest quality and governance result, with
complete required facts, complete citation precision and recall, correct human
gate handling, correct recommendation, and correct authorization-state
preservation. It also used substantially more tokens and latency than the
generalist.

The fixed chain completed provider calls but failed final synthesis quality,
demonstrating that adding agents without governed handoff can degrade results.

The dynamic run recorded role-scope compliance of 0.75. Post-run analysis found
the remaining failure was policy drift around legitimate schedule identifier
keys, not a substantive role violation. Prior empirical artifacts must remain
unchanged.

## Decision

Submission materials will frame the result as:

- The generalist was fastest and lowest-token.
- The generalist was factually strong but incomplete in evidence provenance.
- The fixed chain showed that adding agents without governed handoff can
  degrade results.
- The dynamic council produced the most complete, cited, and governable
  decision.
- The dynamic council paid a substantial token and latency premium.
- The value proposition is higher assurance for consequential decisions, not
  universal efficiency.

The submission will not claim:

- statistical significance
- production readiness
- lower cost than the generalist
- lower latency than the generalist
- perfect empirical role compliance for the dynamic run

The stable submission package is written under `submission-artifacts/`, and raw
provider responses are not copied there.

## Consequences

The evidence package is judge-facing and transparent about tradeoffs. It
preserves empirical provenance, records source artifact paths and checksums,
and separates post-run deterministic analysis from the original live result.

Future optimization work should focus on reducing EvidenceAuditor and
RecoveryPlanner token usage without weakening citation recall, contradiction
handling, or authorization-gate correctness.

## Non-Goals

- No live provider calls during submission packaging.
- No modification of prior empirical artifacts.
- No changes to frozen `schemas/v1`.
- No claim that the dynamic council is universally computationally efficient.
- No relabeling of failed or diagnostic runs as successful empirical results.
