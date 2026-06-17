# Prompt Architecture

Versioned prompts live under `prompts/v1/`.

Prompt roles:

- `GeneralistAgent`
- `DirectorAgent`
- `ScheduleExpert`
- `CommercialExpert`
- `EvidenceAuditor`
- `RiskExpert`
- `RecoveryPlanner`
- `ArbiterAgent`

Each prompt defines:

- role and scope
- permitted evidence
- expected output schema
- evidence-citation requirements
- abstention behavior
- unsupported-claim prohibition
- concise rationale requirements
- no private chain-of-thought output
- failure behavior

The Director prompt requires concise routing rationale and selection of only
relevant experts. The Arbiter prompt requires preservation of unresolved
disagreement and evidence provenance.

EvidenceAuditor uses a dedicated response contract:
`project-recovery-council.qwen.evidence-auditor-response.v1`. Its prompt asks
for a nested audit matrix grouped by audited agent and claim key, with matching
nested citations and one of the permitted support statuses:
`supported`, `contradicted`, `unsupported`, or `insufficient_evidence`. The
prompt must not ask the auditor to flatten agent-prefixed audit results into
the generic specialist `claims` and `citations` map.

Prompt wording is not the access-control mechanism. Evidence is filtered before
rendering by `role_scope.py`. The rendered invocation packet includes case ID,
correlation ID, invocation purpose, agent role, selected evidence record IDs,
expected schema, and only the evidence records allowed for that role.

`ScheduleExpert` receives schedule records and minimal case identity only. It is
not given commercial, supplier, logistics, onsite progress, unrelated risk, or
recovery-option evidence.

Run prompt validation with:

```bash
PYTHONPATH=src python -m project_recovery_council validate-prompts
```
