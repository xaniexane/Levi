---
skill_id: web_ops_env_config
name: Environment Configuration
description: Manage config across environments: env vars, secrets separation, validation at startup, and twelve-factor habits.
risk: info
permissions: []
requires_confirmation: false
tags: [ops, deployment]
version: 1.0.0
---
# Environment Configuration
## Purpose
Make the same artifact run in dev, staging, and prod with behavior driven by environment, not by code edits.
## Key ideas
- Configuration lives in the environment, not in code: env vars or mounted config, never hard-coded.
- Secrets are configuration with extra handling: injected from a vault or secret store, never in repos or images.
- Validate all required config at startup and fail fast with a message naming the missing variable.
- Keep a documented schema of every variable: name, purpose, default, and which environments override it.
- Build one artifact and promote it through environments; rebuilding per environment invites drift.

## In practice
Fail at boot, loudly, when required config is missing; a service that starts half-configured fails in confusing ways at 3am. Separate secrets from plain config in both storage and handling: secrets come from the vault at deploy time, plain config from env files, and neither lives in the container image or git history. Provide a .env.example documenting every variable so new developers and new environments start complete. When a value differs per environment, the difference lives in the environment's config, and the code reads the same variable everywhere; grep the codebase for literals that should have been variables.

```bash
# .env.example -- the documented schema, committed to the repo
DATABASE_URL=postgres://localhost:5432/orders_dev
PORT=8000
LOG_LEVEL=info
# Secrets are NOT here; they come from the vault at deploy time:
# STRIPE_SECRET_KEY=<injected>
# DB_PASSWORD=<injected>

# fail fast at startup
: "${DATABASE_URL:?DATABASE_URL must be set}"
: "${PORT:=8000}"
```

## Common mistakes
- Committing secrets to git or baking them into container images.
- Starting with missing config and failing obscurely on first use instead of at boot.
- Rebuilding artifacts per environment, letting prod and staging silently diverge.

## Checklist
- Does the service fail fast naming any missing required variable?
- Are secrets injected from a store, absent from repos and images?
- Is one artifact promoted unchanged through all environments?

---
*Original work authored for LEVI. All explanations written fresh; no content copied from external sources.*
