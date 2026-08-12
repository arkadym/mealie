# Fork CI & test environment

Status: **plan — awaiting approval**
Scope: independent of `multi-provider-ai.md`; does not block it.

---

## 1. One local environment — `compose.local.yml`

A single full stack in the project directory: the real production image built from
`docker/Dockerfile`, plus postgres. No separate dev/test/staging split.

```
docker compose -f compose.local.yml up -d --build
docker compose -f compose.local.yml logs -f mealie      # AI errors land here at LOG_LEVEL=DEBUG
docker compose -f compose.local.yml down                # keeps data
docker compose -f compose.local.yml down -v             # wipes data
```

App on `http://localhost:9091`. State lives in named volumes (`mealie-data`, `mealie-postgres`),
never in the working tree.

**Why it can live in the project dir:** the file is untracked — `.gitignore:35` already matches
`*.local.*`, an upstream-sanctioned pattern for exactly this, so no `.git/info/exclude` entry is
needed and there is no merge-conflict surface. The `docker/` tree is left untouched.

**Build cost.** The Dockerfile is self-contained (the `packages` stage builds from source; CI's
`--build-context packages=dist` is only an override), so no `task py:package` is needed first. But a
Python change invalidates `COPY mealie ./mealie` and re-runs uv build → uv export →
`pip install --require-hashes`: minutes, not seconds. The frontend is a separate stage and stays
cached unless `frontend/` changes.

**Fast loop, same environment.** When iterating on backend code, leave postgres up and run the
backend natively — `task py:postgres` connects to `localhost:5432`, which this stack publishes. Same
database, same data, no image rebuild. Do not run `task dev:services` alongside it; it binds 5432 too.

## 2. Deployment

The VPS runs the published GHCR image. There is no intermediate test stack — `compose.local.yml`
*is* the pre-VPS verification environment, and it builds the same Dockerfile CI publishes.

## 3. CI — `.github/workflows/fork-publish.yml` *(new file)*

### Why a new workflow rather than editing upstream's

Upstream `publish.yml` cannot run on this fork:

- it pushes to DockerHub `hkotel/mealie` and requires `DOCKERHUB_USERNAME` / `DOCKERHUB_TOKEN`
- it builds via **Depot.dev** with upstream's hardcoded project id `srzjb6mhzm`

`build-package.yml` **is** fork-safe — only `GITHUB_TOKEN`, no external services — so it gets reused
as-is via `workflow_call`. Editing upstream workflow files is avoided entirely (fork discipline).

### Shape

| Aspect | Choice |
|---|---|
| Trigger | `push: tags: ['v*']` **plus** `workflow_dispatch` with a `tag` input |
| Platform | `linux/amd64` only — VPS is x86; no QEMU, no arm64 leg |
| Builder | `docker/setup-buildx-action` + `docker/build-push-action` (replaces Depot) |
| Registry | `ghcr.io/arkadym/mealie` only — no DockerHub |
| Auth | `GITHUB_TOKEN` with `packages: write` |
| Jobs | `build-package` (reused) → `publish` |

`publish` downloads the `backend-dist` artifact into `dist/`, then builds `./docker/Dockerfile` with
`context: .`, `build-contexts: packages=dist`, and `build-args: COMMIT=<sha>` — mirroring how
upstream's publish job consumes the same artifact.

`workflow_dispatch` builds publish only a `:sha-<short>` tag, so on-demand test builds never claim a
version tag or move `:latest`.

### Versioning

`build-package.yml` overwrites `mealie/__init__.py` with the `tag` input, so the tag drives the
in-app version. Fork tags follow `v<upstream-version>-fork.<n>` (e.g. `v3.22.0-fork.1`), with the
leading `v` stripped before it is passed through.

### Upstream workflows to disable on the fork

Once Actions is enabled, several upstream workflows auto-trigger and will fail (missing secrets,
missing Depot access, or simply irrelevant to a fork). Disable them via the **Actions UI per-workflow
toggle**, not by deleting files — deleting creates merge conflicts.

Review and disable at minimum: `nightly.yml` (fires on every push to `mealie-next`), `release.yml`,
`e2e.yml`, `docs.yml`, `locale-sync.yml`, `auto-merge-*.yml`, `stale.yml`, `scheduled-checks.yml`,
`release-drafter.yml`, `codeql.yml`.

Keep enabled: `test-backend.yml` / `test-frontend.yml` (useful), and the new `fork-publish.yml`.

### Gotcha

GHCR packages are **private by default**. After the first publish, either make the package public or
give the VPS a read-only PAT — otherwise `docker pull` on the VPS fails with a confusing auth error.

## 4. Tasks

- [ ] Write `.github/workflows/fork-publish.yml`
- [ ] Enable Actions on the fork; disable the upstream workflows listed above
- [ ] First tag + publish; verify the image runs locally
- [ ] Make the GHCR package public (or configure a pull PAT on the VPS)
- [ ] Create `~/services/mealie-test/docker-compose.yml` against the published tag
- [ ] Record the release procedure in `kb/ops/fork-workflow.md`

## 5. Open question

Cutover plan for the VPS: keep the current image until a fork tag has been smoke-tested in
`~/services/mealie-test`, then switch — with the previous tag retained for rollback. Confirm that's
the intended flow before the first tag is cut.
