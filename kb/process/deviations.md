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
