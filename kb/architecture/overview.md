# Repo overview

[← KB index](../index.md)

Checked against `mealie-next` @ `b9b3ac9b`, 2026-08-12.

## Stack

| Part | Technology | Location |
|---|---|---|
| Backend | FastAPI, SQLAlchemy, Alembic, Pydantic v2 | `mealie/` |
| Frontend | Nuxt 4.4, Vue 3.5, Vuetify 4.1 | `frontend/` |
| Python | 3.12 (`requires-python = ">=3.12,<3.13"`), deps via `uv` | `pyproject.toml`, `uv.lock` |
| Frontend deps | `yarn` | `frontend/package.json` |
| Command runner | `task` | `Taskfile.yml` |

App version at time of writing: `3.22.0` (`pyproject.toml:3`).

## Backend layout

```
mealie/
  routes/     FastAPI controllers (class-based, @controller decorator)
  schema/     Pydantic models (API contracts) — MealieModel base
  services/   business logic
  repos/      repository layer over SQLAlchemy
  db/models/  SQLAlchemy ORM models
  alembic/    migrations
  core/       settings, exceptions, logging
```

Conventions worth knowing:

- Schemas inherit `MealieModel`, which handles camelCase aliasing for the frontend.
- ORM models use `@auto_init()` on `__init__` to map kwargs to columns.
- Output schemas expose `loader_options()` returning SQLAlchemy loader options; the repo layer applies
  them, so eager-loading is declared on the schema, not at the query site.
- Controllers derive from `BaseAdminController` / `BaseUserController` etc. and get `self.repos`.

## Frontend layout

Nuxt 4 `app/` directory layout:

```
frontend/app/
  components/Domain/<Area>/   feature components
  pages/                      routes
  composables/                use-*.ts
  lib/api/                    typed API client
  lib/api/types/              GENERATED from backend schemas — do not hand-edit
  lang/messages/              i18n; en-US.json is the source of truth
```

`frontend/app/lang/messages/en-US.json` is the only locale file to edit by hand. All others are
managed by Crowdin (`crowdin.yml`) and arrive via `chore(l10n)` commits.

## Common commands

| Task | Command |
|---|---|
| Regenerate frontend API types from backend schemas | `task dev:generate` |
| New Alembic migration | `task py:migrate -- "description"` |
| Local services (postgres, mailpit) | `task dev:services` (uses `docker/docker-compose.dev.yml`) |

`task dev:generate` runs `dev/code-generation/main.py` and then `task py:format`. Any backend schema
change that the frontend consumes requires running it; `frontend/app/lib/api/types/*.ts` is generated
output.

## Migrations

Migrations live in `mealie/alembic/versions/`, named `<date>_<rev>_<slug>.py`. Head as of this note:
`2187537c52b8` (`add_table_for_ai_providers`, 2026-05-18).

Because this is a fork that merges from upstream, migration heads are a conflict hotspot: upstream
adding a migration while we hold a fork-local one produces two heads. See
[fork workflow](../ops/fork-workflow.md).

## Related

- [AI integration](ai-integration.md)
