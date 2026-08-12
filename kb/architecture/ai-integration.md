# AI integration

[← KB index](../index.md)

Checked against `mealie-next` @ `b9b3ac9b`, 2026-08-12. Upstream user-facing docs:
`docs/docs/documentation/getting-started/installation/ai-providers.md`.

## Data model

AI providers are **data, not configuration** — per group, stored in the DB
(`mealie/db/models/group/ai_providers.py`), added upstream in migration `2187537c52b8` (2026-05-18).

`ai_providers` columns: `name`, `base_url`, `api_key`, `model`, `timeout`, plus two child KV tables
`ai_provider_headers` / `ai_provider_params`, surfaced as dicts on the schema
(`mealie/schema/group/ai_providers.py:52`).

`ai_provider_settings` is one row per group and assigns providers to three **roles**:

| Role | Column | Used for |
|---|---|---|
| default | `default_provider_id` | all text requests; also gates `ai_enabled` |
| image | `image_provider_id` | requests carrying image attachments |
| audio | `audio_provider_id` | transcription |

`ai_enabled` is a computed field: it is simply `default_provider_id is not None`
(`mealie/schema/group/ai_providers.py:119`).

**Non-obvious:** roles are independent provider rows, so one provider record can be assigned to
several roles, and the image/audio roles are *not* validated against what the model can actually do.
Assigning a text-only model to the image role fails at request time, not at save time.

## Request flow

`mealie/services/openai/openai.py` — `OpenAIService`:

1. `__init__` loads the group's settings and resolves the three provider rows (`openai.py:111-136`).
2. `_get_provider(attachments)` picks the role by inspecting attachment types (`openai.py:147`).
   Images and audio in one request is an explicit error.
3. `get_client(provider)` builds an `AsyncOpenAI` with `base_url`, `api_key`, `timeout`,
   `default_headers`, `default_query` (`openai.py:138`).
4. `_get_raw_response` sends the request (`openai.py:264`).
5. `get_response` reads the payload and validates it into the schema (`openai.py:283`).

Attachments are modelled as `OpenAIAttachment` subclasses that each build their own message dict:
`OpenAIImageExternal` (URL), `OpenAILocalImage` (minified to JPEG, base64 data URI),
`OpenAILocalAudio` (`input_audio`).

### Prompts

Plain text files under `mealie/services/openai/prompts/`, addressed with dot notation
(`recipes.build-recipe` → `prompts/recipes/build-recipe.txt`). Users can override individual prompts
by pointing `OPENAI_CUSTOM_PROMPT_DIR` at a directory with the same layout; resolution falls back to
the bundled prompt (`openai.py:170-230`). Both candidate paths are checked for directory traversal.

Data is appended to prompts via `OpenAIDataInjection`, which serialises Pydantic models/classes to
JSON or JSON Schema (`openai.py:35`).

### Response schemas

`mealie/schema/openai/` — all inherit `OpenAIBase`, which strips its own docstring from the generated
JSON schema and null bytes from responses (`mealie/schema/openai/_base.py`). Schemas in use:
`OpenAIRecipe`, `OpenAIRecipeIngredients`, `OpenAIOrganizers`, `OpenAICompiledSource`, `OpenAIText`.

### Call sites

`OpenAIService.get_response` is called from 8 places — ingredient parser, scraper fallback, the
import workflow steps/compilers, and the admin debug route. They all pass a `response_schema` and
never touch transport details, so transport changes do not ripple.

## Known provider incompatibilities

**The critical fact:** `openai.py:268` calls `client.chat.completions.parse(response_format=<model>)`.
With a Pydantic model this makes the SDK send
`response_format: {"type":"json_schema","json_schema":{...,"strict":true}}` — OpenAI Structured
Outputs, which in practice only OpenAI and Azure implement.

| Provider | Behaviour | Symptom |
|---|---|---|
| OpenAI / Azure | Native support | Works |
| DeepSeek (direct) | Only `{"type":"json_object"}`; requires the word "json" in the prompt; docs warn it can return empty content | HTTP 400 |
| Anthropic via `api.anthropic.com/v1/` | **`response_format` ignored entirely**; `strict` on tools ignored; audio input stripped | Prose returned → validation error |
| DeepSeek via LiteLLM | LiteLLM's `_add_response_format_to_tools()` converts the schema to a forced tool call | Model answers correctly, but Mealie throws |

**Second critical fact:** the payload is read from exactly one place, `openai.py:304`:

```python
response_text = response.choices[0].message.content
```

When a gateway or provider answers via a tool call, the JSON is in
`choices[0].message.tool_calls[0].function.arguments` and `content` is `None`. `None` becomes `""` in
`_preprocess_response`, and `model_validate_json("")` raises at `_base.py:32`. The answer was correct;
Mealie discarded it. This is a genuine upstream bug, independent of which provider is used.

Also: no `max_tokens` is ever sent, so providers with a low default output cap truncate mid-JSON on
the `compile-source` step (which transcribes an entire page).

DeepSeek reasoner models return `reasoning_content` alongside `content`; the answer stays in
`content`, so this needs no special handling — noted so it is not mistaken for a bug.

## Video imports (fork change)

Video URLs are handled by `TranscriptionCompiler`, which runs before the webpage compiler
(`CompileSourceStep.run` orders `requires_content = False` compilers first). yt-dlp decides what
counts as a video via its extractor list, so ordinary recipe sites are unaffected.

**Transcripts come from subtitles first, ASR second** — `resolve_transcription` prefers a known
transcript, then the subtitle track, and only then transcribes audio. This is the same mechanism
sites like NoteGPT use, and it needs no audio provider and costs nothing.

Upstream gated the entire compiler on `audio_provider_enabled`, so a video was never even
attempted without an audio provider — the workflow silently fell back to fetching the URL as a
webpage, which for YouTube means Google's cookie-consent page and no recipe. This fork removes
that gate and instead passes `download_audio=False` when no audio provider exists, so only
subtitles are fetched. If nothing usable comes back, `compile()` returns `None` and the webpage
path runs exactly as before.

Two related upstream limitations also fixed here:

- `SUBTITLE_LANGS` was a fixed list of five European languages, both for requesting tracks and
  for finding the downloaded file — so a Russian or Ukrainian video could never be transcribed.
  `download_video` now probes the video first and `select_subtitle_langs` ranks the available
  tracks: the video's own language, then the preferred list, then anything else. Only the best
  single track is downloaded.
- `parse_subtitle_content` kept VTT metadata (`Kind:`, `Language:`) and every repeated line of
  rolling captions. On a real short this tripled the transcript: 9467 → 3157 characters after
  collapsing adjacent duplicates.

**Environment note:** yt-dlp warns that no JS runtime (deno) and no impersonation backend
(`curl_cffi`) are installed in the Mealie image, and YouTube returned `429 Too Many Requests`
once during testing before succeeding on retry. Neither is a code defect, but both make YouTube
extraction less reliable than it could be.

## Pins

`openai==2.53.0` (`pyproject.toml:42`), checked 2026-08-12.

## Related

- [Decision 001 — Multi-provider AI support](../decisions/001-multi-provider-ai.md)
- Design doc: `tasks/multi-provider-ai.md`
