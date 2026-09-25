# Migrations: no tree while sign-in is off

**Decision (2026-09-15).** Corrected the test's expectation instead of
generating migration files. This workspace ships with sign-in **off**
(`.grok/app-env.json`: `VITE_AUTH_ENABLED=false`), so there is no
`web/migrations/` directory at all — and there should not be one.

**Why not generate `migrations/auth/0001_auth.sql`?**

- Both appliers already treat a missing directory as "nothing to do":
  `scripts/migrate.mjs` logs `no migrations/ directory` and exits;
  `src/lib/db.ts` globs `/migrations/*.sql`, which matches nothing.
- `AGENTS.md` §0.5: auth-off apps ship no migrations.
- Any `0001_auth.sql` written today would be fiction. The schema must be
  generated from the app's real Better Auth config (`src/lib/auth/server.ts`,
  with its bearer/genericOAuth plugins and gate-session tables) **at the time
  sign-in turns on**; a hand-written or config-duplicated approximation risks
  being applied verbatim to a real database later via the auth-on copy flow
  (`migrations/auth/0001_auth.sql` → `migrations/0001_auth.sql`).
- The web app does use Better Auth code (pre-wired template in
  `src/lib/auth/*`, `better-auth` in dependencies), but with sign-in off none
  of it runs against a database.

**What changed.** `scripts/migration-plan.test.mjs`, test "the auth schema
ships outside the globbed directory": when `web/migrations/` does not exist,
the test documents the auth-off shipped state and returns; when the tree
exists (sign-in on), the original assertions run unchanged — the tripwire
keeps its value. The sibling byte-identical-copy test already skipped the
same way.

**When sign-in turns on**, generate `migrations/auth/0001_auth.sql` from the
real config at that time, copy it up to `migrations/0001_auth.sql` per the
`scripts/migration-plan.mjs` design, and this test's assertions reactivate
automatically.

**Reversibility.** Fully reversible: creating the tree re-arms the original
assertions with no further edits.
