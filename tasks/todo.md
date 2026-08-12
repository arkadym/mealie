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

- [ ] `mealie/services/openai/response_extraction.py`: `extract_payload`, `strip_code_fences`, `extract_json_span`
- [ ] `get_response` uses it instead of reading `message.content` directly
- [ ] Harden `_base.py` parsing (fences, prose-wrapped JSON, existing null-byte scrub)
- [ ] Distinct exception for empty payload — current message hid the real cause
- [ ] Unit tests: payload in `content` / in `tool_calls[0].function.arguments` with `content=None` / fenced / prose-wrapped / empty
- [ ] **Verify against the real DeepSeek + LiteLLM setup** — this is the acceptance test for the phase
- [ ] Judge DeepSeek's parse quality on `build-recipe` and `compile-source` before committing to phases 2–3

## Phase 2 — structured output modes

- [ ] `structured_output_mode` + `max_tokens` columns; migration via `task py:migrate`
- [ ] Schema fields + enum validation in `mealie/schema/group/ai_providers.py`
- [ ] Mode branching in `_get_raw_response`: `json_schema` | `tool_call` | `json_object` | `text`
- [ ] Schema injection for `json_object` / `text` (incl. literal "json" for DeepSeek)
- [ ] Dereference `$defs`/`$ref` before sending nested schemas — verify with `OpenAIRecipe`
- [ ] Dialog fields + `task dev:generate` for TS types
- [ ] Resolve open question 1: `max_tokens` vs `max_completion_tokens`

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
