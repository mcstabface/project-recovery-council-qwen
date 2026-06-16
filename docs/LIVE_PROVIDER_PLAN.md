# Live Provider Plan

Live Qwen provider access is intentionally not implemented in this run.

Future implementation must address:

- credential configuration through environment or secret manager controls
- model selection and version pinning
- structured-output mechanism compatible with the response schemas
- retry policy and retry budget
- timeout handling
- rate-limit handling and backoff
- token accounting from provider-reported usage fields
- estimated provider cost only from explicitly supplied pricing data
- Alibaba Cloud deployment proof
- secrets handling and redaction in logs and artifacts
- experiment reproducibility, including prompt version, model identifier,
  generation parameters, fixture or provider metadata, and evidence bundle hash

`DisabledQwenModelClient` is the current Qwen adapter placeholder. It returns a
typed configuration failure and records `network_attempted=false`.

Live provider tests must be opt-in and separate from the default offline test
suite.
