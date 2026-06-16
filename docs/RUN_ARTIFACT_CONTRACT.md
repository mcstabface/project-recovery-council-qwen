# Run Artifact Contract

## Scope

This document describes the v1 local run artifact contract for Project Recovery
Council. It is platform-neutral and does not depend on UiPath, LLM providers,
databases, or external connectors.

## Required Files

Each run directory must contain:

- `workflow-state.json`
- `artifact-manifest.json`
- `run-summary.json`
- `audit-events.json`
- `expert-findings.json`
- `contradictions.json`
- `human-decisions.json`
- `human-decision-requests.json`
- `draft-recommendation.json`
- `final-recommendation.json`
- `replay-input.json`

Draft and final recommendation payloads may be `null` for paused runs, but the
files must exist and be listed in the manifest.

## Manifest

`artifact-manifest.json` uses contract version
`project-recovery-council.run-artifacts.v1`.

Each entry includes:

- relative path
- media type
- schema identifier
- SHA-256 checksum
- generation timestamp
- required flag

The manifest does not include its own checksum.

## Inspection Rules

`python -m project_recovery_council inspect <run-path>` validates:

- required files exist
- JSON files parse
- payloads validate against Pydantic contracts
- checksums match
- audit sequence numbers are ordered and gap-free
- referenced evidence records exist
- pending human gates agree with workflow state
- completed runs include final approval and final recommendation
- incomplete runs do not claim completion

Inspection returns a nonzero exit code on failure.

