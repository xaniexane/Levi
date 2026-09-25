# Contributing

One rule above all: **keep each product's lane.** This repo holds the Python
core, the megazord scaffolding, two legacy runtime monoliths, a web app, and
VYVE. Don't mix concerns across them; if a change touches two products, say so
in the commit message.

## Branch and commit hygiene

- **Feature branches**, one feature per branch, opened from a current `main`.
- **Conventional commits**: `feat:`, `fix:`, `docs:`, `chore:`, `refactor:`,
  `test:`, `security:` + short imperative subject. Body explains *why*.
- **No squashed mega-commits.** Keep history bisectable: small commits, each
  building and passing on its own. This repo's history was squashed once
  (P3.8); that was the cost, not the model.
- PRs need **green CI** before merge (see below). No force-pushing shared
  branches.

## Tests

| Stack | Command |
|---|---|
| Python core | `cd core && python -m compileall levi && ruff check levi && mypy levi && python -m pytest ../tests` (tests/ to be added per P3.2) |
| Web | `cd web && npm run typecheck && npm run lint && npm test && npm run build` |
| VYVE backend | `cd apps/vyve-messenger/backend && python -m pytest tests/` |
| Android | `./gradlew :app:assembleDebug` |
| Secrets scan | gitleaks (CI) |

Lockfiles are committed: `web/package-lock.json`, backend via `pip-tools`/`uv
lock` (P3.8). Don't add unpinned deps.

## Docs

- Docs live in `docs/`; keep them **grounded in the code**. If a doc describes
  behavior, the code must do it. Fiction gets reverted.
- Product-level docs: megazord has its own README disclaimer; keep it honest.
- When you add a CLI subcommand, regenerate `docs/CLI.md` from
  `core/levi/cli/main.py` — never hand-write command descriptions.
- Changelog: add entries under `## Unreleased` in `CHANGELOG.md` with every
  behavior-changing PR.

## Security-sensitive changes

- Anything touching auth, tokens, keys, redirects, or the vault needs a second
  reviewer and an entry in `docs/SECURITY.md` if posture changes.
- Never commit secrets, keystores, or `.env` files (see `.gitignore`).
- Demo credentials (`VYVE_DEMO_MODE`) stay gated and off by default — do not
  add new demo backdoors.
