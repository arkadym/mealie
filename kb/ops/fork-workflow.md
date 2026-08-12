# Fork workflow

[← KB index](../index.md)

## Remotes

| Remote | URL | Purpose |
|---|---|---|
| `origin` | `https://github.com/arkadym/mealie` | the fork — push here |
| `upstream` | `https://github.com/mealie-recipes/mealie` | read-only source, merge from here |

Default branch is **`mealie-next`**, not `main`. Upstream develops on `mealie-next`; releases are cut
from it.

## Syncing

```
git fetch upstream
git log --oneline HEAD..upstream/mealie-next   # what's new
```

Merging is a **manual, user-initiated** step. Per `CLAUDE.md`, the agent never runs `git merge`
automatically — it fetches, reports divergence, and waits.

### Conflict hotspots

| Area | Why | Mitigation |
|---|---|---|
| `mealie/alembic/versions/` | Two heads when both sides add a migration | Rebase the fork-local migration onto the new upstream head; never edit an already-applied revision |
| `frontend/app/lib/api/types/*.ts` | Generated output; both sides regenerate | Resolve by rerunning `task dev:generate`, never by hand-merging |
| `frontend/app/lang/messages/*.json` | Crowdin rewrites all locales | Only ever hand-edit `en-US.json`; take upstream's version for the rest |
| `.gitignore` | Upstream-owned | Never edit it for fork-local needs — use `.git/info/exclude` |

## Fork-local files

Kept out of the repo entirely via `.git/info/exclude` (local, never committed, never conflicts):

- `CLAUDE.md` — private agent instructions

Committed to the fork but not intended for upstream:

- `kb/` — this knowledge base
- `tasks/` — design docs, todo, lessons

## Design principle

Keep merges cheap **by default**: additive changes, no renaming or moving upstream files, new code in
new files where natural. But this is a preference, not a hard rule — if correct design for a feature
requires restructuring upstream code, do it and record the reason in [decisions](../decisions/index.md).
Never contort a design just to dodge a future conflict.

## CI and images

Upstream's `publish.yml` cannot run on this fork: it pushes to DockerHub (`hkotel/mealie`, needs
secrets we don't have) and builds via Depot.dev with upstream's hardcoded project id `srzjb6mhzm`.
`build-package.yml` **is** reusable as-is — it needs only `GITHUB_TOKEN`.

The fork therefore adds `.github/workflows/fork-publish.yml` (new file; upstream workflows are never
edited) which reuses `build-package.yml` and pushes `linux/amd64` to `ghcr.io/arkadym/mealie` on git
tags plus manual dispatch. Upstream workflows that auto-trigger — `nightly.yml` fires on every push
to `mealie-next` — are disabled through the Actions UI per-workflow toggle rather than deleted.

Plan and details: `tasks/fork-ci-and-test-env.md`.

## Environments

Two environments only — deliberately. An intermediate "test" stack was considered and rejected as
unnecessary: `compose.local.yml` builds the same Dockerfile that CI publishes, so it already is the
pre-VPS verification environment.

| Environment | Where | Purpose |
|---|---|---|
| Local | project dir, `compose.local.yml` | full stack (production image + postgres) on `localhost:9091`; also the pre-release verification env |
| Production | VPS | runs the published GHCR image — never targeted by the local stack |

`compose.local.yml` is untracked because `.gitignore:35` already matches `*.local.*` — upstream's own
pattern for local-only files. Use that pattern for any future fork-local file in the working tree; it
needs no `.git/info/exclude` entry and creates no conflict surface. State is in named docker volumes,
so nothing lands in the working tree.

For a fast backend edit loop without rebuilding the image, leave the stack up and run
`task py:postgres` — it connects to the same published `localhost:5432`. Don't run
`task dev:services` at the same time; it binds 5432 too.

## Documenting fork features

Every fork-local feature gets:

1. an entry in the README "About this fork" section (following the pattern used in
   [arkadym/docmost](https://github.com/arkadym/docmost)),
2. a KB page, and
3. a decision record if it involved a non-obvious architectural choice.
