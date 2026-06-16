# Schema Versioning Policy

## V1 Freeze

The committed files under `schemas/v1/` are frozen public contract artifacts.
They are checked by `project-recovery-council check-schema-drift`.

The drift check exports the current Pydantic schemas into a temporary directory
and compares them byte-for-byte with the committed v1 schemas. Missing,
unexpected, or changed files fail the check.

## Intentional Changes

Do not silently modify v1 schemas.

For an intentional contract change:

- If the change is a reviewed correction that remains compatible with existing
  v1 artifacts, update the schema file, tests, ADRs, and compatibility notes in
  the same change.
- If the change is not clearly compatible, create a future versioned directory
  such as `schemas/v2/`.
- Document migration or non-migration behavior before adopting the new version.
- Update replay acceptance and artifact inspection documentation when behavior
  changes.

## Local Commands

Regenerate schemas intentionally:

```bash
project-recovery-council export-schemas
```

Check for drift:

```bash
project-recovery-council check-schema-drift
```

The check command never overwrites committed schemas.

