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
- `recovery-options.json`
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

## Run Directory Safety

New run creation fails when the target run directory already exists. The only
supported override is an explicit `--replace-existing` option, intended for
local deterministic regeneration and automated tests. Normal competition and
review runs should use a fresh run ID so prior evidence is not overwritten.

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

## Canonical Evidence

The committed canonical completed run is:

```text
session-artifacts/canonical-demo/
```

It contains a completed workflow state, audit history, expert findings,
contradictions, human decisions, recovery options, draft and final
recommendations, replay input, run summary, and artifact manifest. Ad hoc
runtime output under `session-artifacts/runs/` should generally remain local
unless a specific review artifact is intentionally promoted.
