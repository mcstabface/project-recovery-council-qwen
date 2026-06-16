# Development Plan

## Foundation Slice

Completed in this run:

- project metadata and MIT license
- deterministic contract models
- local evidence fixtures
- expected-results fixture
- validation utilities
- expert ABCs and deterministic stubs
- automated tests
- build checkpoint and run manifest
- deterministic local workflow runner
- CLI commands for validate, run, failure-injection run, and replay
- replayable run artifacts
- deterministic commercial-expert failure injection and retry tests
- persistent pause/resume across process invocations
- versioned JSON Schema exports and schema catalog
- expert adapter boundary
- run artifact manifest and inspect command
- replay acceptance profile
- UiPath Maestro mapping document
- package installability with a console entry point
- GitHub Actions CI for tests, schema drift, fixture validation, demo execution,
  and artifact inspection
- frozen v1 schema drift control
- run directory overwrite protection
- deterministic complete demo command and cross-platform demo script
- canonical completed demo evidence run

## Next Slice

Prepare the UiPath integration spike:

- confirm Maestro case-state, Action Center, retry, artifact attachment, and
  audit-history semantics against a real UiPath Labs tenant
- map the v1 JSON Schemas into the exact payload constraints required by
  Maestro workflows and agent tasks
- decide how canonical local evidence will be attached to or referenced by a
  governed Maestro case
- define the first external expert adapter implementation behind the existing
  platform-neutral adapter boundary

## Later Slices

- Add provider-backed expert implementations behind the same interfaces.
- Add UiPath Maestro orchestration only after the local contracts stabilize.
- Add richer multi-case lifecycle behavior after the first platform integration
  spike validates the current state model.

## Quality Gates

- Every fixture result must be reproducible from local source files.
- Every finding must cite evidence.
- Unsupported onsite claims must be rejected until human confirmation exists.
- Tests must run with `python -m pytest`.
