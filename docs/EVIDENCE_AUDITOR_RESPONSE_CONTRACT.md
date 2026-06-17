# EvidenceAuditor Response Contract

EvidenceAuditor uses an experiment-layer response contract distinct from the
generic specialist finding response:

```text
project-recovery-council.qwen.evidence-auditor-response.v1
```

This contract lives in the Qwen experiment layer. It does not modify frozen
domain schemas under `schemas/v1/`.

## Shape

The response may use `assessments_by_agent` directly or the observed provider
shape with matching nested `claims` and `citations` fields.

```json
{
  "schema_version": "project-recovery-council.qwen.evidence-auditor-response.v1",
  "agent_role": "EvidenceAuditor",
  "status": "completed",
  "claims": {
    "ScheduleExpert": {
      "forecast_milestone_slip_days": {
        "support_status": "supported",
        "observed_value": 13
      }
    }
  },
  "citations": {
    "ScheduleExpert": {
      "forecast_milestone_slip_days": ["SCH-DELIVERY-001"]
    }
  },
  "unsupported_claims": [],
  "warnings": [],
  "abstention_reason": null
}
```

Every nested claim assessment must have a matching nested citation entry. The
citation list may be empty for an explicitly unsupported claim, but the key must
still be present.

## Claim Assessment

Each claim assessment contains:

- `support_status`: one of `supported`, `contradicted`, `unsupported`, or
  `insufficient_evidence`
- `citations`: stable evidence record IDs, supplied directly or through the
  matching nested citation map
- optional `rationale`
- optional `observed_value`
- optional `expected_value`
- optional `validation_reference`

Audited agent names must be known experiment roles. Citation record IDs must
exist in the synthetic evidence bundle.

## Canonical Audit Findings

Validated EvidenceAuditor output is converted deterministically into canonical
audit findings. Each finding preserves:

- source EvidenceAuditor invocation ID
- audited agent
- audited claim key
- canonical claim key after explicit alias normalization
- support status
- citations
- rationale
- observed and expected values
- relationship to the original specialist finding when available

`supported` findings may reinforce the corresponding validated specialist
finding. `contradicted`, `unsupported`, and `insufficient_evidence` findings
remain visible but are excluded from positive synthesis and can make the
audited specialist claim disputed or ineligible.

The original provider response is preserved unchanged in
`parsed-structured-responses.json`. Flattened canonical audit findings are
written separately through normalization and audit artifacts.

## Validation Rules

The contract validator rejects:

- unknown audited agent names
- support statuses outside the enum
- nested claim keys without matching citation keys
- nested citation keys without matching claim keys
- citations that reference unknown evidence record IDs
- attempts to promote contradicted or unsupported assessments into eligible
  positive synthesis findings

This keeps audit structure strict without forcing legitimate per-agent audit
matrices into the generic flat specialist contract.
