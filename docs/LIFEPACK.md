# LEVI Life Pack

A life pack is a **versioned JSON bundle** that carries LEVI's portable state —
identity, settings, durable memory, and the skill manifest — between homes and
machines. It closes the organism-DNA gap of having no life-pack export/import:
an offline, user-controlled snapshot you can inspect before you ever apply it.

This is **not** the legacy `levi export` / `levi import` ZIP exporter
(`core/levi/identity/export_life.py`) — that stays untouched. Life packs are a
new, sectioned, diff-previewable format.

## Format (version 1)

```json
{
  "format": "levi-lifepack",
  "version": 1,
  "exported_at": "2026-09-15T20:42:00+00:00",
  "levi_version": "0.9.5",
  "sections": {
    "identity": { ... },              // UserProfile dict (profile.json)
    "settings": { "charter.json": { ... } },  // known root JSON config files
    "memory":   [ { ... }, ... ],      // durable MemoryEntry dicts
    "skills":   { "manifest": [ { "id", "name", "category", "version", "risk_level" }, ... ] }
  }
}
```

- `format` must be `"levi-lifepack"`, `version` must be `1`. Import refuses
  anything else with a plain-language `LifepackError`.
- Every file write during import is atomic (temp file + rename).

## What's included / excluded

| Section    | Included | Excluded (stays home) |
|------------|----------|------------------------|
| identity   | `profile.json` fields (name, goals, preferences, onboarding) | — |
| settings   | known root JSON config files: `settings.json`, `preferences.json`, `charter.json`, `control_daemon.json`, `monotropism.json`, `nervous_system.json`, `persona_bond.json`, `demand_pulse.json`, `brain_table.json`, `income_factory.json` (whichever exist) | everything else |
| memory     | **durable** entries: `semantic` (facts), `preference`, `procedural`, `relationship` | `working` (ephemeral), `episodic`, `project`-scoped, `device` state |
| skills     | **manifest only**: id, name, category, version, risk level | playbook bodies — they travel with the code, not the pack |

**Secrets never travel.** On import, any settings key that looks like a
token/password/API key (matching `token`, `secret`, `password`, `api_key`,
`client_secret`, `bearer`, `auth`, `credential`, `private_key`, … — separators
ignored, so `LEVIL_API_KEY` and `oauth-token` both match) is **skipped and
reported**, never written. Memory entries whose *content* looks secret-like
are skipped the same way. When in doubt, the filter errs on the side of
skipping. This is a last line of defense, not a guarantee — keep real
secrets in the vault, not in settings.

## Plan → Preview → Permission

Import follows the organism's binding law:

1. **Plan** — `preview_import(pack, home)` produces human-readable diff lines:
   `identity: name differs: 'Chauncey' → 'Someone Else'`,
   `memory: +3 new entries, 1 changed`,
   `settings: file 'charter.json' differs`,
   `skills: pack lists 853 skills; 853 registered here`.
   Preview is pure read-only; it touches nothing.
2. **Preview** — `levi lifepack import pack.json --preview` prints that diff
   and writes nothing.
3. **Permission** — real import needs explicit confirmation:
   `import_pack(pack, home, confirm=True)` raises unless `confirm=True`; the
   CLI without `--yes` prompts `Type IMPORT to confirm` on a TTY and refuses
   on a non-TTY.

## CLI usage

(`cli/main.py` wiring is done by the parent — see the snippet below.)

```bash
levi lifepack export ~/backup/lifepack-2026-09-15.json
levi lifepack import ~/backup/lifepack-2026-09-15.json --preview   # diff, no writes
levi lifepack import ~/backup/lifepack-2026-09-15.json --yes       # confirmed import
levi lifepack import ~/backup/lifepack-2026-09-15.json             # TTY prompt: type IMPORT
```

### Argparse wiring snippet for `core/levi/cli/main.py`

```python
from levi.lifepack import cmd_lifepack

lp = sub.add_parser(
    "lifepack", help="Life pack: versioned JSON export/import of LEVI state"
)
lp_sub = lp.add_subparsers(dest="lifepack_action")

lp_exp = lp_sub.add_parser("export", help="Write a life-pack JSON bundle")
lp_exp.add_argument("file", help="Output path for the .json bundle")

lp_imp = lp_sub.add_parser("import", help="Preview or apply a life-pack JSON bundle")
lp_imp.add_argument("file", help="Path to the .json bundle")
lp_imp.add_argument(
    "--preview", action="store_true", help="Show the diff and write nothing"
)
lp_imp.add_argument(
    "--yes",
    action="store_true",
    help="Confirm a real import without an interactive prompt",
)
```

and in the dispatch section:

```python
    elif args.command == "lifepack":
        return cmd_lifepack(args)
```

Note: this intentionally does **not** reuse the existing `export`/`import`
(ZIP) subcommands — those stay as-is.

## Honest limits

- **Last-writer-wins per section.** There is no merge UI and no conflict
  resolution beyond per-entry upsert (memory entries keep their ids; a
  changed entry overwrites the current one). If two homes diverge, the
  imported pack's content wins for that entry/section.
- **Skills are informational.** The pack records which skills existed at
  export time; import verifies the manifest against what's installed and
  writes nothing. Moving custom playbooks between machines is out of scope —
  skills ship with the code.
- **No secrets, by filter not by promise.** The filter is heuristic. Anything
  genuinely secret belongs in the vault (`levi vault`), not in settings or
  memory content.
- **Version 1 only.** Future versions must bump `version` and refuse
  gracefully (already the behavior for anything ≠ 1).
- Re-importing the same pack is a **no-op**: import is idempotent, and
  repeated imports write nothing.
