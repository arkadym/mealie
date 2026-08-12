# Lessons

Patterns extracted from user corrections. Reviewed at session start. Each entry states the trigger,
the rule, and why — so the rule survives without the original conversation.

---

## L1 — Don't diagnose an integration failure from the provider's side alone

**Trigger:** "provider X doesn't work with this app."

**Rule:** before concluding the provider or its API is at fault, verify where the client reads the
response from. Check the full response object, not just the field the code happens to read.

**Why:** DeepSeek was assumed to be failing on JSON handling. It was answering correctly; Mealie reads
only `choices[0].message.content` and the payload was in `tool_calls[0].function.arguments`. Hours
were spent tuning gateway settings for what was a client-side bug.

---

## L2 — Fork-local files never go in upstream-owned files

**Trigger:** needing to ignore, configure, or exclude something in a fork.

**Rule:** use `.git/info/exclude` for private files, not `.gitignore`. More generally: before editing
any upstream-owned file for a fork-local need, ask whether a fork-local mechanism exists instead.

**Why:** every edit to an upstream-owned file is a permanent merge-conflict site, paid on every sync.

---

## L3 — Surface conflicts between instructions instead of silently picking one

**Trigger:** two instructions (or an instruction and a prior decision) point in different directions.

**Rule:** state the conflict explicitly, recommend one side with reasoning, and wait. Do not quietly
resolve it and proceed.

**Why:** confirmed as valued by the user this session. Examples: "upstreamable shape" vs. a new
top-level package; "follow current architecture / small changes" vs. the previously chosen adapter
seam; global `CLAUDE.md` requiring `docs/<slug>.md` vs. `docs/` being upstream's published tree.

---

## L4 — Don't carry stale context from another project into this one

**Trigger:** instructions referencing infrastructure, files, or services.

**Rule:** verify referenced paths exist in *this* repo before acting on them. Flag the ones that
don't.

**Why:** this project's `CLAUDE.md` was copied from another project and referenced "Vantage",
`kb/ops/deployment.md`, and `docker-compose.prod.yml` — none of which exist here. Acting on them
would have produced confident nonsense about a production deployment that doesn't exist.

---

## L5 — Verify provider/API facts against current docs, never from memory

**Trigger:** any claim about a model's capabilities, pricing, limits, or API surface.

**Rule:** fetch the current documentation. State the date checked.

**Why:** model line-ups and API capabilities move fast — DeepSeek's current models turned out to be
`deepseek-v4-flash`/`v4-pro`, and Anthropic's OpenAI-compat layer ignores `response_format` outright,
which is the kind of detail that silently invalidates a design.
