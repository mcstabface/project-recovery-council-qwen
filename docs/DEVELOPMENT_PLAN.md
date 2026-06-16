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

## Next Slice

Harden the workflow output contract:

- add JSON Schema exports for public contracts and run artifacts
- add a fixture replay acceptance document
- add a small sample artifact index for human review
- add explicit case-state mutation helpers if future workflows need persisted
  case snapshots

## Later Slices

- Add schema export for platform integration.
- Add richer case lifecycle state transitions.
- Add provider-backed expert implementations behind the same interfaces.
- Add UiPath Maestro orchestration only after the local contracts stabilize.

## Quality Gates

- Every fixture result must be reproducible from local source files.
- Every finding must cite evidence.
- Unsupported onsite claims must be rejected until human confirmation exists.
- Tests must run with `python -m pytest`.
