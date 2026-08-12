# Multi-Provider AI Support

Status: **design — awaiting approval**
Branch: `feature/multi-provider-ai`
Base: `mealie-next` @ `b9b3ac9b`

---

## 1. Problem

Mealie already models AI providers as data (`ai_providers` table, per-group, with
`base_url` / `api_key` / `model` / `timeout` / headers / params, assigned to three roles:
default, image, audio). The provider *record* is not the problem.

The problem is a single line — `mealie/services/openai/openai.py:268`:

```python
return await client.chat.completions.parse(..., response_format=response_schema)
```

Passing a Pydantic model to `.parse()` makes the OpenAI SDK emit
`response_format: {"type": "json_schema", "json_schema": {..., "strict": true}}`.
In practice only OpenAI and Azure implement that. Everything else fails in one of
three ways:

| Provider | Behaviour | Result |
|---|---|---|
| DeepSeek (direct) | Supports only `response_format: {"type":"json_object"}` | 400 on the request |
| Anthropic (OpenAI-compat endpoint) | **Ignores `response_format` entirely**, and ignores `strict` on tools | Prose returned, `model_validate_json` throws |
| DeepSeek via LiteLLM | LiteLLM's `_add_response_format_to_tools()` fallback converts the schema into a forced tool call | **Model answers correctly**, but the JSON lands in `message.tool_calls[0].function.arguments` while `message.content` is `None` |

That last row is the observed failure in practice. Mealie reads exactly one place —
`openai.py:304`:

```python
response_text = response.choices[0].message.content
```

`None` → `_preprocess_response` returns `""` → `model_validate_json("")` raises at
`mealie/schema/openai/_base.py:32`. The provider did its job; Mealie discarded the answer.

### Secondary gaps

1. **No `max_tokens` is ever sent.** The `compile-source` step transcribes an entire web
   page; providers with a low default output cap truncate mid-JSON.
2. **No tolerant parsing.** `_base.py` does a bare `model_validate_json`. Providers without
   strict schemas routinely wrap output in ```` ```json ```` fences or prepend a sentence.
3. **Modality is implicit.** Any provider can be assigned to the image or audio role, but
   DeepSeek has neither vision nor audio, and the Anthropic compat layer silently strips
   audio. Misassignment fails at request time with an opaque error.

---

## 2. Goals / Non-goals

**Goals**

- Any OpenAI-compatible endpoint works as a first-class provider — no proxy, no gateway,
  no per-vendor `if` statements scattered through the service.
- Structured output is a declared, per-provider **capability**, not an assumption.
- Modality support is declared and validated up front rather than discovered at runtime.
- The change is shaped as an additive, upstreamable PR to `mealie-next`.

**Non-goals**

- Native (non-OpenAI-compatible) SDKs. Anthropic's own SDK would buy guaranteed structured
  outputs and prompt caching; it is deliberately deferred (see the escape hatch in §3).
  Revisit only if compat-mode quality proves insufficient.
- Changing prompts' content strategy, per-provider prompt variants, or model routing.
- Anything about the mobile app. AI import stays server-side; an offline client queues jobs.

---

## 3. Decisions taken

| # | Decision | Rationale |
|---|---|---|
| D1 | **No adapter layer** — mode branching inside the existing `OpenAIService`, plus one extraction module | One transport; the variation is parametric, not behavioural. Follows current architecture. *(revised — an earlier draft proposed an adapter ABC)* |
| D2 | Fork-first, but additive and rename-free where that costs nothing | Upstream merges happen regularly; cheap merges by default, correctness wins when they conflict |
| D3 | Providers declare vision/audio capability and the UI validates role assignment | Prevents the silent-failure class that cost hours of debugging |

Recorded as [`kb/decisions/001-multi-provider-ai.md`](../kb/decisions/001-multi-provider-ai.md).

### Why D1 was reversed

The first draft of this doc introduced an `AIProviderAdapter` ABC, a registry, and per-provider
modules. Applying "follow current architecture unless it conflicts with proper design", it
does not conflict here — the simpler shape *is* the better design:

- There is exactly **one transport**: the `openai` SDK against an OpenAI-compatible HTTP API.
  Every provider in scope (OpenAI, DeepSeek, Anthropic-compat, Ollama, vLLM, OpenRouter,
  LiteLLM) speaks it.
- What varies is **parameters**, not behaviour: how the request expresses the schema, where
  the payload lands in the response, an optional token cap, and two declarative capability
  flags. None of that is polymorphism.
- An ABC with a single implementation is speculative generality — indirection paid now to
  serve a second implementation that §2 explicitly defers.

**Escape hatch:** if the `anthropic` SDK is ever added natively (guaranteed structured
outputs, prompt caching), extracting the seam is a mechanical refactor of one class — done
with knowledge of what the second implementation actually needs, rather than guessed at now.

**D2 consequence:** the response-extraction fix (§4.3) is a real upstream bug, small and
self-contained. Worth offering upstream on its own even though the rest of this is fork-local.

---

## 4. Backend design

### 4.1 Where the changes go

`OpenAIService` keeps its name, location, and public surface (`get_response`,
`transcribe_audio`, `get_prompt`, `_get_provider`). Two changes inside it:

- `_get_raw_response` (`openai.py:264`) branches on `provider.structured_output_mode` to build
  the request. It returns the raw response rather than assuming a shape.
- `get_response` (`openai.py:283`) delegates payload location to the extraction helper instead
  of reading `message.content` directly.

One new module, `mealie/services/openai/response_extraction.py` — pure functions, no state, no
client, trivially unit-testable:

```python
def extract_payload(message) -> str | None: ...   # content -> tool_calls -> function_call
def strip_code_fences(text: str) -> str: ...
def extract_json_span(text: str) -> str | None: ...
```

That is the whole structural change. No new package, no ABC, no registry — the mode enum on
the provider row carries the variation, which is what it is for.

### 4.2 Structured output modes

New per-provider enum `structured_output_mode`:

| Mode | Request | Read from | Use for |
|---|---|---|---|
| `json_schema` *(default)* | `.parse(response_format=Model)` — unchanged | `message.content` | OpenAI, Azure |
| `tool_call` | `tools=[{function: {name: "format_response", parameters: <schema>}}]`, `tool_choice` forced to it | `message.tool_calls[0].function.arguments` | **DeepSeek, Claude compat, most others** |
| `json_object` | `response_format={"type":"json_object"}` + schema injected into the system prompt | `message.content` | providers with JSON mode but no tools |
| `text` | plain completion + schema injected into the prompt | `message.content`, JSON extracted from prose | last resort, small local models |

`tool_call` is the recommended mode for non-OpenAI providers, and this is empirically
grounded: it is exactly the path LiteLLM fell back to, and DeepSeek produced correct output
over it. DeepSeek's own docs warn that `json_object` mode occasionally returns empty
content; Anthropic's compat layer ignores `response_format` but supports `tools` fully. One
mechanism covers both.

`json_object` mode must inject the literal word "json" into the system prompt — DeepSeek
rejects the request otherwise.

### 4.3 Response extraction

`response_extraction.py` — ordered, provider-agnostic, applied in every mode:

1. `message.content` if non-empty
2. else `message.tool_calls[0].function.arguments`
3. else `message.function_call.arguments` (legacy shape)
4. strip ```` ```json ```` / ```` ``` ```` fences
5. if still not parseable, extract the first balanced `{...}` / `[...]` span
6. existing null-byte scrub from `_base.py`

Steps 1–3 are correctness, not leniency: once `response_format` is in play the payload
legitimately lives in different places, and step 2 is what unblocks the LiteLLM path today.

DeepSeek reasoner models also return `reasoning_content` alongside `content`; the answer
stays in `content`, so no special handling — noted so it isn't mistaken for a bug later.

### 4.4 Schema injection

For `json_object` and `text` modes the schema must reach the model through the prompt.
A helper renders `response_schema.model_json_schema()` into an appended block, reusing the
existing `OpenAIDataInjection` mechanism so prompt files stay untouched.

**Risk:** nested Pydantic models (e.g. `OpenAIRecipe` → `OpenAIRecipeIngredient`) produce
`$defs`/`$ref`. Some providers handle `$ref` poorly in tool parameters. Mitigation: inline/
dereference the schema before sending. Needs an explicit test (§8).

### 4.5 max_tokens

New nullable `max_tokens` column. When null, nothing is sent (today's behaviour, no
regression). When set, sent as `max_tokens`.

**Open question:** OpenAI's newer reasoning models reject `max_tokens` and require
`max_completion_tokens`. Proposal: send `max_tokens` only when the column is set, and
document "leave empty for OpenAI reasoning models". Cleaner alternative — a general
request-body KV escape hatch alongside the existing header/query KVs — is rejected as
over-engineering for one field.

### 4.6 Error mapping

`openai.RateLimitError` → `exceptions.RateLimitError` is preserved. Adapters additionally
map an empty-payload result to a distinct, actionable exception rather than letting a bare
`ValidationError` surface as `"OpenAI Request Failed. ValidationError: ..."` — that message
is precisely what made the original diagnosis hard.

---

## 5. Data model & migration

Additive columns on `ai_providers`:

| Column | Type | Default | Notes |
|---|---|---|---|
| `structured_output_mode` | String | `'json_schema'` | non-null; enum validated at the schema layer |
| `max_tokens` | Integer | `NULL` | nullable |
| `supports_images` | Boolean | `true` | permissive default preserves existing behaviour on upgrade |
| `supports_audio` | Boolean | `true` | same |

Capability defaults are deliberately permissive: an upgrade must not silently disable a
working image or audio provider. Validation therefore only constrains providers the user
edits or creates after the upgrade.

Migration generated with `task py:migrate -- "add ai provider capabilities"`.
Current head: `2187537c52b8` (add_table_for_ai_providers).

Schema changes in `mealie/schema/group/ai_providers.py`: fields on `AIProviderCreate`
(inherited by Save/Update/Out), plus a `model_validator` on `AIProviderSettingsUpdate`
rejecting assignment of a non-capable provider to the image or audio role.

---

## 6. API

No new endpoints. The added fields flow through the existing
`controller_group_ai_providers.py` and `admin_management_ai_providers.py` CRUD.

`admin_debug.py` gains role-awareness: testing a provider assigned to the image role sends
an image, audio role attempts a transcription — so the test button exercises what the
provider is actually used for.

---

## 7. Frontend

`GroupAIProviderDialog.vue`:

- **Structured output mode** — `v-select`, four options, default `json_schema`, with hint text
- **Max tokens** — optional `v-number-input`, empty = unset
- **Supports images / Supports audio** — two switches
- **Provider preset** — optional `v-select` (OpenAI / DeepSeek / Anthropic / Ollama / Custom)
  that pre-fills `base_url`, mode and capability flags. Frontend-only sugar, no backend
  coupling, so it cannot rot into a compatibility matrix.

`GroupAIProviderSettingsEditor.vue`: the image and audio role selectors list only providers
declaring that capability, with an inline explanation when a provider is filtered out.

Types in `frontend/app/lib/api/types/group.ts` are generated — regenerate with
`task dev:generate`. New i18n keys go in `frontend/app/lang/messages/en-US.json` only;
Crowdin handles the rest.

---

## 8. Testing

- **Unit — extraction:** payload in `content`; in `tool_calls[0].function.arguments` with
  `content: None`; fenced; prose-wrapped; empty. This is the regression test for the actual bug.
- **Unit — modes:** each of the four modes builds the expected request kwargs (mocked client).
- **Unit — schema injection:** nested schema renders without unresolved `$ref` (§4.4 risk).
- **Unit — validation:** assigning a non-image provider to the image role is rejected.
- **Existing:** `tests/unit_tests/services_tests/test_openai_service.py`,
  `test_openai_parser.py`, `tests/unit_tests/schema_tests/test_ai_providers.py`,
  `tests/integration_tests/user_group_tests/test_group_ai_providers.py`,
  `tests/integration_tests/admin_tests/test_admin_ai_providers.py` — all must pass unchanged
  (default mode is today's behaviour).
- **Manual:** DeepSeek direct with `tool_call`; Claude compat with `tool_call`; OpenAI
  unchanged with `json_schema`.

---

## 9. Documentation

`docs/docs/documentation/getting-started/installation/ai-providers.md` — new section on
choosing a structured output mode, a short table of known-good settings per provider, and a
note that image/audio roles require a capable provider. This is the only upstream-owned docs
file this work touches; the design doc lives in `tasks/` and the durable notes in `kb/`, so the
published mkdocs tree stays clean.

The README also gains an "About this fork" section listing this feature, following the pattern
used in [arkadym/docmost](https://github.com/arkadym/docmost).

---

## 10. Phasing

| Phase | Content | Independently shippable |
|---|---|---|
| 1 | Response extraction (§4.1, §4.3). No migration, no UI, no schema change. | **Yes** — fixes the LiteLLM/DeepSeek path immediately and stands alone as an upstream bug-fix PR |
| 2 | `structured_output_mode` + `max_tokens`, migration, dialog fields (§4.2, §4.5, §5) | Yes — removes the proxy from the stack |
| 3 | Capability flags, role validation, presets, role-aware debug (§4.x, §6, §7) | Yes |
| 4 | Docs + full test pass (§8, §9) | — |

Phase 1 first is worth it on its own merits: it is the smallest change that proves DeepSeek's
actual parse quality on Mealie's recipe schemas, which is the one thing this design cannot
answer on paper and which determines whether phases 2–3 are worth your time.

---

## 11. Affected files

**Backend**

- `mealie/services/openai/openai.py` — mode branching in `_get_raw_response`, extraction in
  `get_response`; public API unchanged
- `mealie/services/openai/response_extraction.py` — new, pure functions
- `mealie/schema/openai/_base.py` — parsing hardening
- `mealie/schema/group/ai_providers.py` — new fields + role validation
- `mealie/db/models/group/ai_providers.py` — new columns
- `mealie/alembic/versions/<new>.py` — new migration
- `mealie/routes/admin/admin_debug.py` — role-aware test

**Frontend**

- `frontend/app/components/Domain/Group/GroupAIProviderDialog.vue`
- `frontend/app/components/Domain/Group/GroupAIProviderSettingsEditor.vue`
- `frontend/app/lib/api/types/group.ts` *(generated)*
- `frontend/app/lang/messages/en-US.json`

**Docs/tests** — as listed in §8 and §9.

---

## 12. Risks

| Risk | Mitigation |
|---|---|
| DeepSeek parse quality on the large `build-recipe` / `compile-source` schemas is unknown | Phase 1 answers this before phases 2–3 are built |
| `$ref` in nested tool-parameter schemas | Dereference before sending; explicit test |
| Upstream may refactor `ai_providers` concurrently | Additive-only columns, no renames; rebase cost stays low |
| Capability defaults could mislead | Permissive `true` defaults on migration; validation applies to edits only |

## 13. Open questions

1. `max_tokens` vs `max_completion_tokens` for OpenAI reasoning models (§4.5) — proposal is
   to document rather than auto-detect. Agree?
2. Should the `text` mode ship at all in phase 2, or wait until a user actually needs it?
   It is ~15 lines but adds a footgun.
3. `origin` currently points at `mealie-recipes/mealie`. Fork remote name preference before
   any push — `fork`, or re-point `origin` and add `upstream`?
