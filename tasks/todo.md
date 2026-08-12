# TODO

Active work. Design: `multi-provider-ai.md` · Decision: `../kb/decisions/001-multi-provider-ai.md`
Branch: `feature/multi-provider-ai`

---

## Session scaffolding

- [x] Repoint `origin` to `arkadym/mealie`, keep upstream as `upstream`
- [x] Update `CLAUDE.md` for this repo; remove stale Vantage/ops references
- [x] Exclude `CLAUDE.md` via `.git/info/exclude` (not `.gitignore` — upstream-owned)
- [x] Create `kb/` tree (index, architecture, ops, decisions, process)
- [x] Create `tasks/todo.md` and `tasks/lessons.md`
- [x] Revise design doc after D1 reversal (no adapter layer)

## Phase 1 — response extraction *(no migration, no UI)*

- [x] `mealie/services/openai/response_extraction.py`: `extract_payload`, `normalize_payload`, `strip_code_fences`, `extract_json_span`
- [x] `get_response` uses it instead of reading `message.content` directly
- [x] Normalization lives in the service, not `_base.py` — schema→service import would be circular; see design doc §4.3
- [x] `OpenAIEmptyResponseError` — the old generic wrapper hid the real cause
- [x] Unit tests written: payload in `content` / in `tool_calls[0].function.arguments` with `content=None` / fenced / prose-wrapped / empty
- [ ] **Run the test suite** — blocked: no `uv`, no venv, system Python is 3.14 vs the project's `>=3.12,<3.13`
- [ ] `task py:lint` / `task py:format`
- [ ] **Verify against the real DeepSeek + LiteLLM setup** — this is the acceptance test for the phase
- [ ] Judge DeepSeek's parse quality on `build-recipe` and `compile-source` before committing to phases 2–3

## Phase 2 — structured output modes

- [x] `structured_output_mode` + `max_tokens` columns (hand-written migration `8f2c41d0b7ae` — `task py:migrate` needs uv)
- [x] Schema fields + `AIStructuredOutputMode` enum in `mealie/schema/group/ai_providers.py`
- [x] Mode branching in `_get_raw_response`: `json_schema` | `tool_call` | `json_object` | `text`
- [x] Schema injection for `json_object` / `text` (incl. literal "json" for DeepSeek)
- [x] Dereference `$defs`/`$ref` before sending nested schemas — verified against `OpenAIRecipe`
- [ ] Dialog fields + `task dev:generate` for TS types — blocked on toolchain
- [ ] Resolve open question 1: `max_tokens` vs `max_completion_tokens`
- [ ] **Acceptance: real DeepSeek import succeeds with `tool_call`** (set the mode via SQL until the UI exists)

## Phase 3 — capabilities

- [ ] `supports_images` / `supports_audio` columns, permissive `true` defaults
- [ ] Role-assignment validation in `AIProviderSettingsUpdate`
- [ ] Filter role selectors in `GroupAIProviderSettingsEditor.vue`, explain filtered-out providers
- [ ] Role-aware provider test in `admin_debug.py`
- [ ] Optional: provider presets in the dialog (frontend-only)

## Phase 4 — docs & tests

- [ ] Update `docs/docs/documentation/getting-started/installation/ai-providers.md`
- [ ] README "About this fork" section
- [ ] Full backend test pass; confirm existing AI tests pass unchanged
- [ ] Update `kb/architecture/ai-integration.md` to describe the shipped behaviour

---

## Video transcription *(folded into this branch — see `kb/architecture/ai-integration.md`)*

- [x] `TranscriptionCompiler.can_compile()` no longer requires an audio provider — subtitles need none
- [x] `download_video(..., download_audio=False)` fetches subtitles only, no wasted audio download
- [x] `resolve_transcription` returns `""` (not an error) when there is nothing to transcribe, so the workflow falls back to the webpage path
- [x] Subtitle language chosen from the video itself, preferring its own language over the hardcoded list
- [x] Only the single best track is downloaded, not every translation
- [x] `parse_subtitle_content` strips VTT headers and collapses rolling-caption repeats (3× fewer tokens)
- [x] Verified end-to-end on a real Russian YouTube short: picked `ru`, 3157 chars, no audio, no AI cost
- [ ] Consider `curl_cffi` / a JS runtime in the image — yt-dlp warns both are missing, and YouTube returned 429 once

## Fork CI & test env *(separate track — see `fork-ci-and-test-env.md`)*

- [ ] `.github/workflows/fork-publish.yml` — amd64, GHCR only, git tags + `workflow_dispatch`
- [ ] Enable Actions on the fork; disable upstream auto-triggering workflows via the Actions UI
- [ ] First tag, publish, verify image runs; make the GHCR package public (or PAT on the VPS)
- [x] `compose.local.yml` — single full local stack (untracked via `.gitignore:35` `*.local.*`)
- [ ] Record the release procedure in `kb/ops/fork-workflow.md`

## Open questions

1. `max_tokens` vs `max_completion_tokens` for OpenAI reasoning models — propose documenting rather than auto-detecting
2. Ship `text` mode in phase 2, or defer until something needs it?
3. Offer the phase-1 extraction fix upstream as a standalone PR?
4. VPS cutover flow: smoke-test a fork tag in `~/services/mealie-test`, then switch, keeping the previous tag for rollback?

## Review

*(filled in as phases complete)*
