# CreatorLab API — labeled design reference

> **Reference only — no code was ported.** During the Omega source-sync,
> the source repo contained an orval-generated TypeScript client
> (`api.ts` / `api.schemas.ts`, ~3,100 lines) for a "CreatorLab" backend
> API. The backend does not exist in the source repo, so the client is
> dead code without it and was **not ported** (`format: design-reference`
> in `sync/sources.yaml`). This document records only the *API surface
> shape* as a labeled reference for LEVI's own builder/engine design
> work. All descriptions below are paraphrased; no generated code was
> copied. See `docs/SOURCE_SYNC_PROTOCOL.md`.

## Resource groups (all under `/api/`)

| Group | Operations observed |
|---|---|
| `projects` | list, create, get, update, delete |
| `integrations` | list, create, get, update, delete |
| `automations` | list, create, get, update, delete, toggle (enable/disable) |
| `chat/sessions` | list, create, get, delete (chat sessions) |
| `plans` | list, create, get, update, delete |
| `engine/workflows` | list, create, get, update, delete, run |
| `dashboard` | stats, activity |
| `healthz` | health check |

## AI / builder endpoints

| Endpoint | Apparent purpose |
|---|---|
| `POST /api/builder/generate` | Generate a project from a prompt/spec |
| `POST /api/builder/scaffold` | Scaffold a project from a structured input |
| `GET /api/builder/templates` | List builder templates |
| `POST /api/ai/assist` | AI assistance on a task |
| `POST /api/ai/generate-steps` | Generate plan steps via AI |

## Scaffold input shape (paraphrased)

The scaffold endpoint takes a small model: a project **name**, a
**type** drawn from `{web, mobile, api, automation}`, a **tech stack**
string, and a free-text **description**. This is a reasonable minimal
shape for any future LEVI scaffold surface and is noted here only as a
design data point.

## Integration providers named (references, not sources)

The client names these third-party providers as integration targets:
GitHub, Supabase, n8n, Replit, OpenAI, Vercel, Netlify. Per the
identity rule, these are **references** — pointers for comparison —
never sources LEVI draws on and never LEVI branding. They appear here
only as a labeled reference list.

## Takeaways for LEVI's own builder/engine

- A workflow engine wants the same verbs the reference shows:
  CRUD on workflows plus an explicit **run** operation, separate from
  updates.
- Automations benefit from a distinct **toggle** (enable/disable)
  rather than overloading update.
- A scaffold surface can stay minimal: name + type + tech stack +
  description is enough to start.
- Dashboard **stats** + **activity** as first-class read endpoints
  keeps the control plane honest about what ran.
