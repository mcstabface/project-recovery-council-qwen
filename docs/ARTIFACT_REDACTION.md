# Artifact Redaction

Live artifacts may preserve operational metadata needed for auditability:

- model identifier
- endpoint host and region label
- provider request ID when returned
- timing
- usage metadata
- retry count and retry history
- structured-output mode requested and used

Live artifacts must not preserve:

- API key values
- authorization headers
- credential-like environment values
- provider request payload fields designated secret

The central redactor is `project_recovery_council.redaction.redact_value`.
It redacts API keys, authorization headers, access tokens, secrets,
credentials, passwords, bearer values, and known secret strings. Non-secret
status fields such as `api_key_env_var` and `api_key_present` may be preserved.

Generated live artifacts are scanned in tests using a dummy secret value. The
test fails if that dummy value appears in any generated live artifact JSON file.
