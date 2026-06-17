# ADR-0015: Shared Dynamic Validation And Arbitration Policy

## Status

Accepted

## Context

A live `dynamic_expert_council` run completed all provider invocations but
failed final artifact validation. The Director selected relevant specialists
and the specialists returned useful content, but deterministic role validation
rejected the specialist outputs, no eligible findings reached synthesis,
ArbiterAgent abstained, RecoveryPlanner abstained, and the derived
authorization state was rejected.

This was an orchestration and deterministic-processing defect, not a reason to
weaken artifact validation or relabel the failed empirical run as successful.

## Decision

Fixed-chain and dynamic-council runs now share the same specialist processing
path:

- schema validation
- explicit claim-key normalization
- role-scope validation
- domain semantic validation where implemented
- validated-findings envelope construction
- recommendation/authorization state derivation

`CommercialExpert` receives deterministic commercial-semantic validation. The
validator preserves valid commercial findings, rejects incorrect arithmetic, and
does not silently overwrite conflicting gross and net avoided-exposure fields.

Dynamic governance is constrained:

- EvidenceAuditor receives compact normalized claims, citations, validation
  status, cited evidence, and contradiction candidates.
- ArbiterAgent runs only for substantive disagreements among eligible validated
  findings.
- ArbiterAgent is skipped for support-only audit findings, rejected validation
  outputs, and unresolved human gates without specialist disagreement.
- Skipped arbitration is recorded without a provider invocation.

A no-network `rebuild-derived-artifacts` command can reprocess previously paid
live responses into a new diagnostic directory. It preserves source artifacts,
records source hashes, and marks the output as non-empirical.

## Consequences

Dynamic-council runs should now retain valid specialist findings through the
same deterministic processing as the fixed chain. Commercial arithmetic defects
are visible without losing valid net avoided-exposure evidence. Arbiter calls
are reserved for real disagreements, reducing governance overhead and avoiding
unnecessary paid invocations.

Failed empirical runs remain failed. Diagnostic rebuilds are useful for
validating deterministic hardening but are not substitutes for a new empirical
live run.

## Non-Goals

- No live provider calls during this change.
- No changes to frozen v1 schemas or the deterministic oracle.
- No fuzzy or LLM-based normalization.
- No artifact-validation weakening.
- No automatic live matrix execution.
