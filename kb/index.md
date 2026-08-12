# Knowledge Base — Mealie (arkadym fork)

Root index. Every KB page is reachable from here. Add new pages to the tree below.

## Tree

- **Architecture**
  - [Repo overview](architecture/overview.md) — layout, stack, command runner, codegen, migrations
  - [AI integration](architecture/ai-integration.md) — providers, roles, request/response flow, known provider incompatibilities
- **Operations**
  - [Fork workflow](ops/fork-workflow.md) — remotes, branch strategy (`mealie-next` mirror / `mealie-fork` integration), syncing, releases, CI
- **Decisions**
  - [Index](decisions/index.md)
    - [001 — Multi-provider AI support](decisions/001-multi-provider-ai.md)
- **Process**
  - [Deviations log](process/deviations.md) — where implementation diverged from design/docs, and why

## Rules for this KB

- KB is a source of truth. If it conflicts with `docs/` (the upstream mkdocs tree) or a design doc in
  `tasks/`, raise the conflict rather than silently overwriting — annotate the conflicting entry and
  leave it flagged until resolved.
- Update the KB whenever non-obvious logic, an undocumented convention, or a surprising upstream
  behaviour is discovered. Facts here should be verifiable against the code, with `file:line` refs.
- `docs/` belongs to upstream and is the *published* documentation. This KB is fork-local and private
  to the development process. Do not duplicate upstream docs here — link to them.

## Conventions

- Every claim that can rot cites `path/to/file.py:LINE`.
- Versions and pins are recorded with the date they were checked.
