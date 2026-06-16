# Build Checkpoint: Final Local Hardening

**Date:** 2026-06-16  
**Repository:** `project-recovery-council`  
**Status:** Complete for final local hardening pass

## Created Or Updated

- Added GitHub Actions CI for install, tests, schema export, schema drift,
  fixture validation, deterministic demo execution, and artifact inspection.
- Added byte-level schema drift checks for frozen `schemas/v1/` contracts.
- Added run directory overwrite protection with explicit `--replace-existing`
  override for local deterministic regeneration.
- Added deterministic complete `demo` command and cross-platform
  `scripts/run_demo.py` helper.
- Generated canonical completed evidence run under
  `session-artifacts/canonical-demo/`.
- Added `recovery-options.json` to the formal run artifact contract.
- Added schema versioning policy and ADR-0004.
- Updated architecture, run artifact, development plan, README, and UiPath
  mapping documentation.

## Verification Commands

```bash
PYTHONPATH=src python -m project_recovery_council check-schema-drift
```

Result: `schema drift check passed`

```bash
PYTHONPATH=src python -m project_recovery_council validate
```

Result: `validation passed`

```bash
PYTHONPATH=src python -m project_recovery_council demo --artifacts-root session-artifacts --run-id canonical-demo --replace-existing
```

Result: completed canonical demo run with 13 projected delay days, USD 195000
unmitigated exposure, USD 48000 mitigation cost, USD 147000 gross avoided
exposure, resolved contradiction, answered human decision, approved final
recommendation, and passed artifact inspection.

```bash
PYTHONPATH=src python -m project_recovery_council inspect session-artifacts/canonical-demo
```

Result: `artifact inspection passed`

```bash
python scripts/run_demo.py --artifacts-root /tmp/project-recovery-council-demo --run-id script-demo --replace-existing
```

Result: completed and inspected a temporary deterministic demo run.

```bash
PYTHONPATH=src python -m project_recovery_council demo --artifacts-root /tmp/project-recovery-council-demo-cli --run-id cli-demo --replace-existing
```

Result: completed and inspected a temporary deterministic CLI demo run.

```bash
python -m pytest
```

Result: `43 passed in 4.10s`

## Remaining Limitations

- No UiPath SDK or Maestro tenant behavior has been exercised.
- No external expert adapter transport is implemented; the placeholder remains
  safely disabled.
- No schema migration tooling exists beyond the documented policy.
- The canonical case is a single synthetic equipment-delay scenario.

## Recommended Next Step

Use the canonical completed run and frozen v1 schemas to perform a UiPath Labs
integration spike that validates case state, human task, retry, audit history,
and artifact attachment assumptions against the actual platform.
