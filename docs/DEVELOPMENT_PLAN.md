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

## Next Slice

Build a deterministic Director workflow runner that:

- loads a case bundle
- creates specialist requests
- executes deterministic experts
- stores findings and contradictions
- emits a draft recommendation artifact
- writes an audit event stream

## Later Slices

- Add schema export for platform integration.
- Add fixture replay CLI.
- Add richer case lifecycle state transitions.
- Add provider-backed expert implementations behind the same interfaces.
- Add UiPath Maestro orchestration only after the local contracts stabilize.

## Quality Gates

- Every fixture result must be reproducible from local source files.
- Every finding must cite evidence.
- Unsupported onsite claims must be rejected until human confirmation exists.
- Tests must run with `python -m pytest`.

