# Fork workflow

[← KB index](../index.md)

## Remotes

| Remote | URL | Purpose |
|---|---|---|
| `origin` | `git@github-arkadym:arkadym/mealie.git` | the fork — push here |
| `upstream` | `https://github.com/mealie-recipes/mealie` | read-only source, merge from here |

`origin` uses SSH via the `github-arkadym` host alias in `~/.ssh/config` (key
`id_ed25519.github-arkadym`). HTTPS pushes fail here — the libsecret credential helper is configured
but holds no GitHub credential, and there is no TTY to prompt on.

Upstream develops on `mealie-next`; releases are cut from it.

## Branches

| Branch | Role |
|---|---|
| `mealie-next` | **Pristine mirror of upstream.** Never commit here — it only ever fast-forwards. |
| `mealie-fork` | **Integration branch.** All fork work lands here; this is what gets tagged and built. |
| `feature/<slug>` | Feature work, branched from `mealie-fork`, merged back into it. |

`mealie-fork` is the fork's default branch on GitHub.

Keeping `mealie-next` untouched is what makes the rest cheap: `git diff mealie-next..mealie-fork` is
*exactly* the fork delta at any moment, which is how you review what you carry and how you extract a
clean branch for an upstream PR.

## What the fork tracks

**Intent: the latest stable upstream release**, not the `mealie-next` development branch. Releases
are tagged `vX.Y.Z`.

**Current exception (2026-08-13):** the fork sits on `upstream/mealie-next`, because `v3.22.0` does
not contain `mealie/services/recipe/import_workflow/` (the Import-with-AI page) or
`mealie/services/openai/transcription.py` (video transcripts). Both land in v3.23.0, and the fork's
AI work depends on them. **Switch the mirror to the release tag once v3.23.0 ships**, then sync from
tags rather than from `mealie-next`.

Before changing the base, always check the target actually contains the features the fork builds on:

```
git cat-file -e v3.23.0:mealie/services/openai/transcription.py && echo present
```

## Syncing

```
git fetch upstream --tags
git log --oneline mealie-next..upstream/mealie-next    # what's new

git checkout mealie-next
git merge --ff-only upstream/mealie-next               # mirror can only fast-forward

git checkout mealie-fork
git merge mealie-next                                  # bring upstream into the fork
```

Merging is a **manual, user-initiated** step. Per `CLAUDE.md`, the agent never runs `git merge`
automatically — it fetches, reports divergence, and waits.

If `--ff-only` fails on `mealie-next`, something was committed to the mirror by mistake; move that
commit to `mealie-fork` and reset the mirror rather than merging.

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
edited) which reuses `build-package.yml` and pushes `linux/amd64` to `ghcr.io/arkadym/mealie`.

### Releasing

Tag names state which upstream code is actually inside the image:

| Fork base | Tag form | Example |
|---|---|---|
| a stable upstream release | `v<release>-fork.<n>` | `v3.23.0-fork.1` |
| upstream's dev branch | `v<next-release>-dev.fork.<n>` | `v3.23.0-dev.fork.1` |

The `-dev` form matters while the fork sits on `mealie-next`: the tree is dozens of commits past the
last release, so a tag naming that release would misrepresent the image — and it would mislead
precisely when deciding months later whether to roll the VPS forward.

Tag on `mealie-fork`:

```
git tag -a v3.23.0-dev.fork.1 -m "..."
git push origin v3.23.0-dev.fork.1
```

A `v*` tag publishes `ghcr.io/arkadym/mealie:<version>` **and** moves `:latest`. A manual
`workflow_dispatch` publishes only `sha-<short>`, so an ad-hoc build never moves the tag the VPS
follows.

`build-package.yml` stamps the tag into `mealie/__init__.py`, so the version shown in the app is the
fork tag.

### Workflows to keep disabled

Upstream workflows auto-trigger on a fork and fail (missing secrets, missing Depot access, or simply
irrelevant): `nightly.yml`, `docs.yml`, `locale-sync.yml`, `codeql.yml`, `scheduled-checks.yml`,
`stale.yml`, `release-drafter.yml`, `release.yml`, `auto-merge-*.yml`, `pull-request*.yml`.

Disable them with the **per-workflow toggle in the Actions UI**, never by deleting the files —
deleting creates a conflict on every upstream merge. `fork-publish.yml` must stay **enabled**, and
Actions must be enabled for the repository, or tags will publish nothing.

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
