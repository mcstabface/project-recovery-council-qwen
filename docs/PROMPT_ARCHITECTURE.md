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

Run prompt validation with:

```bash
PYTHONPATH=src python -m project_recovery_council validate-prompts
```
