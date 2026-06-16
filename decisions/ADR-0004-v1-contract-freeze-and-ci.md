# ADR-0004: V1 Contract Freeze and CI

**Status:** Accepted  
**Date:** 2026-06-16  
**Decision Owner:** Project Recovery Council maintainers

---

## Context

Project Recovery Council now has versioned public schemas, persistent workflow
state, run artifact manifests, and deterministic demo artifacts. Before UiPath
integration work, the local reference needs CI, schema drift protection,
installable CLI verification, run overwrite protection, and a canonical evidence
run.

---

## Decision

Freeze `schemas/v1/` as public v1 contract artifacts and add deterministic
schema drift checks. Add GitHub Actions CI that installs the package, runs tests,
exports schemas, checks drift, validates fixtures, runs the demo workflow, and
inspects resulting artifacts.

Run creation now fails when the requested run directory already exists unless
`--replace-existing` is explicitly supplied. Add a `demo` command and
cross-platform Python demo script for deterministic end-to-end evidence
generation.

---

## Consequences

Accidental public contract drift and evidence overwrite are now caught locally
and in CI. The package can be installed with `python -m pip install -e ".[dev]"`
and used through the `project-recovery-council` console command.

Intentional schema changes now require explicit review. Incompatible changes
must use a future versioned schema directory instead of silently modifying v1.

---

## Alternatives Considered

- Continue treating generated schemas as disposable outputs. Rejected because
  external integration needs frozen contracts.
- Allow demo commands to overwrite artifacts by default. Rejected because
  evidence runs should not be erased accidentally.
- Add release or deployment automation to CI. Rejected because this pass is only
  local hardening before integration.

---

## Invariants Touched

- Versioned public contracts
- Deterministic demo evidence
- Artifact integrity
- Local-only orchestration
- Integration independence

---

## Follow-up Work

- Add a schema migration template before any v2 schema is proposed.
- Review UiPath mapping assumptions with actual UiPath Labs access.
- Add a human-readable artifact index for canonical evidence review.

