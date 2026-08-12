# Deviations log

[← KB index](../index.md)

Running record of places where **implementation diverged from design, docs, or an agreed plan** — and
why. The point is that "does the app still follow the design?" can be answered later without
re-deriving history, and that a deliberate deviation is never mistaken for a defect.

Log an entry when any of these happen:

- UI is changed without the design being updated (or vice versa)
- a design doc in `tasks/` is not followed, in whole or in part
- an upstream merge overwrites or reshapes fork-local behaviour
- a planned step is skipped, deferred, or descoped
- upstream docs (`docs/`) become inaccurate for this fork

## Format

```
### YYYY-MM-DD — short title
- **Area:** backend / frontend / docs / ops
- **Planned:** what the design or doc said
- **Actual:** what was implemented
- **Reason:** why
- **Follow-up:** what still needs reconciling, or "none"
```

---

## Entries

### 2026-08-12 — Design doc location differs from CLAUDE.md
- **Area:** docs
- **Planned:** `CLAUDE.md` originally required feature design docs at `docs/<feature-slug>.md`.
- **Actual:** design docs live in `tasks/<feature-slug>.md`.
- **Reason:** `docs/` in this repo is the published mkdocs source tree owned by upstream; putting
  fork-local design docs there pollutes the documentation site and creates merge conflicts.
  `CLAUDE.md` has been updated to match.
- **Follow-up:** none.

### 2026-08-12 — Video transcription fixes folded into the multi-provider branch
- **Area:** backend
- **Planned:** `tasks/multi-provider-ai.md` covers structured output only. The transcription gate is
  a separate bug, found while diagnosing a failed YouTube import.
- **Actual:** fixed on the same branch at the user's instruction — the `audio_provider_enabled`
  gate, subtitle language selection, and VTT parsing. The VTT parser fix (header stripping and
  rolling-caption dedupe) was added on the agent's initiative after the transcript came back 3×
  larger than necessary; flagged to the user rather than done silently.
- **Reason:** the gate made video import fail for any user without an audio provider, and the
  language list made it fail for all Russian/Ukrainian content regardless.
- **Follow-up:** the design doc does not describe this work; `kb/architecture/ai-integration.md`
  is the reference. If this is split out for upstream, it is independent of the multi-provider
  commits.

### 2026-08-12 — Test suite never executed; verification done in-container
- **Area:** backend / process
- **Planned:** run `task py:test` and `task py:lint` before reporting work complete.
- **Actual:** no `uv` and no venv on the machine, and system Python is 3.14 against the project's
  `>=3.12,<3.13`. Verification instead ran targeted assertions inside the running container
  (23 extraction + 16 structured-output + 16 transcription + 11 gate checks, all passing) plus one
  real end-to-end subtitle fetch.
- **Reason:** toolchain missing; the container has a correct 3.12 environment with all deps.
- **Follow-up:** install uv, then run the real suite and ruff. In-container checks are not a
  substitute — they do not exercise fixtures, integration tests, or lint.

### 2026-08-12 — Adapter layer designed, then reversed before implementation
- **Area:** backend
- **Planned:** first draft of `tasks/multi-provider-ai.md` introduced an `AIProviderAdapter` ABC,
  registry, and per-provider modules.
- **Actual:** reversed to mode-branching inside the existing `OpenAIService`, plus one extraction
  module. Nothing was implemented under the old design.
- **Reason:** one transport, and the variation is parametric rather than behavioural — an ABC with a
  single implementation is speculative generality. See
  [decision 001](../decisions/001-multi-provider-ai.md).
- **Follow-up:** revisit only if a native non-OpenAI-compatible SDK is added.
