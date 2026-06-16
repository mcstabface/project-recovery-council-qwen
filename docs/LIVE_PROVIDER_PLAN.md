# Live Provider Plan

Live Qwen provider access is implemented as an opt-in path only. The default
client remains offline or disabled. Normal tests, imports, installation, and
offline commands require no credentials and make no network calls.

The live path uses Alibaba Cloud Model Studio's OpenAI-compatible chat
interface, which documents `/chat/completions`, bearer authentication from
`DASHSCOPE_API_KEY`, `messages`, `temperature`, optional `seed`, response IDs,
and token usage fields:

- https://www.alibabacloud.com/help/en/model-studio/compatibility-of-openai-with-dashscope

## Implemented

- credential configuration through environment or secret manager controls
- model selection and version pinning
- structured-output mechanism compatible with the response schemas, with local
  Pydantic validation
- retry policy and retry budget
- timeout handling
- rate-limit handling and backoff
- token accounting from provider-reported usage fields
- estimated provider cost only from explicitly supplied pricing data
- secrets handling and redaction in logs and artifacts
- experiment reproducibility, including prompt version, model identifier,
  generation parameters, fixture or provider metadata, and evidence bundle hash

## Deferred

- Alibaba Cloud deployment proof
- provider-specific cost estimation
- live matrix execution
- default model selection

`DisabledQwenModelClient` remains available as the safe non-networking
placeholder. `QwenModelClient` is used only by live commands after
`--allow-network` and credential checks.

Live provider tests are opt-in and separate from the default offline test
suite. Use `PRC_QWEN_RUN_LIVE_TESTS=1` only when intentionally exercising a
real provider.
