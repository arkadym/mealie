# 001 — Multi-provider AI support

[← Decisions](index.md) · Design doc: `tasks/multi-provider-ai.md` · Status: **accepted (design)**, not implemented

## Context

Mealie's AI stack already models providers as data with three roles, but hardcodes one
structured-output mechanism — OpenAI Structured Outputs via
`client.chat.completions.parse(response_format=<pydantic model>)`. Only OpenAI and Azure implement
it. DeepSeek and Claude both fail, for different reasons. See
[AI integration](../architecture/ai-integration.md) for the mechanics.

Goal: make any OpenAI-compatible endpoint a first-class provider, without a gateway in front.

## Decisions

### D1 — How structured output is expressed: **a declared per-provider capability, four modes**

New column `structured_output_mode` on `ai_providers`:
`json_schema` (default, today's behaviour) | `tool_call` | `json_object` | `text`.

`tool_call` is the recommended mode for non-OpenAI providers. This is empirically grounded, not a
guess: LiteLLM's fallback for providers lacking `json_schema` support converts the schema into a
forced tool call, and DeepSeek produced correct output over exactly that path. DeepSeek's own docs
warn `json_object` mode can return empty content; Anthropic's compat layer ignores `response_format`
entirely but supports `tools` fully. One mechanism covers both providers.

### D2 — No adapter/strategy layer (**revised** — an earlier draft proposed one)

The first draft introduced an `AIProviderAdapter` ABC plus a registry and per-provider modules. That
was reversed.

**Reasoning:** there is exactly one transport — the `openai` SDK against an OpenAI-compatible HTTP
API. What varies between providers is *parameters* (how the request expresses the schema, where the
payload lands, an optional token cap), not *behaviour*. An abstract base class with a single
implementation is speculative generality; it adds indirection now to serve a second implementation
that has been explicitly deferred.

So: branch on the mode inside `OpenAIService._get_raw_response`, and put payload extraction in one
small pure-function module. This follows the existing service architecture rather than introducing a
new pattern into it.

**Revisit when:** a native, non-OpenAI-compatible SDK is actually added (the realistic candidate is
the `anthropic` SDK, for guaranteed structured outputs and prompt caching). Extracting the seam at
that point is a mechanical refactor of one class — and it will be informed by what the second
implementation genuinely needs, instead of guessed at in advance.

### D3 — Modality is declared and validated

New `supports_images` / `supports_audio` flags; the settings UI will not let a text-only provider be
assigned to the image or audio role. Migration defaults are permissive (`true`) so an upgrade cannot
silently disable a working provider.

Rationale: the failure this prevents — a provider silently unable to do the job it was assigned —
is precisely the class of bug that cost hours of debugging to diagnose.

### D4 — Fork-first, but merge-cheap

Not shaped as an upstream PR (see [fork workflow](../ops/fork-workflow.md)). Still additive and
rename-free wherever that does not compromise the design, because upstream merges happen regularly.

**Exception worth noting:** the response-extraction fix (reading the payload from wherever the
provider actually put it) is a genuine upstream bug and is small and self-contained. It is worth
offering upstream separately even though the rest of this work is not.

## Consequences

- Existing providers keep working unchanged: `json_schema` is the default and the current code path.
- A future native SDK requires a refactor first. Accepted deliberately.
- Prompt files gain no per-provider variants; schema injection for `json_object`/`text` modes reuses
  the existing `OpenAIDataInjection` mechanism.
