# UniForge — The Code Surgeon

UniForge is the code surgeon division: **forensics, cyber security,
emergency error response, and code refinement**. Doctrine:
*"Open it up, find the cause, heal it stronger."*

UniForge has two halves:

1. **The build forge** (existing): one build plan across heterogeneous
   targets, run through Plan → Preview → Permission → Execute → Verify →
   Receipt. `levi uniforge plan|build`.
2. **The code-surgeon instruments** (this doc): diagnose → fix → verify on
   live code. `levi uniforge surgeon|operate`.

## Instruments

`core/levi/uniforge/surgeon.py` — stdlib only.

- **`quick_cleanup(text)`** — the plugin's quick-cleanup rules, ported
  faithfully: strip trailing whitespace (per line), tabs → 4 spaces,
  collapse 4+ blank lines to 3, `<name> == None` → `<name> is None`,
  `<name> != None` → `<name> is not None`, preserve trailing-newline
  state. Returns `(new_text, fix_counts)`.
- **`stamp_header(text, author)`** — the plugin's closed-source header
  stamp: replaces any existing copyright/SPDX/proprietary header with
  `CLOSED SOURCE – All Rights Reserved`.
- **`diagnose(path)`** — forensic pass: syntax check (`.py` files) plus
  everything `quick_cleanup` would fix. Returns findings.
- **`surgeon_file(path, apply=False)`** — quick cleanup on one file.
  Dry-run by default; `--apply` writes.
- **`operate(path, apply=False)`** — full surgery: diagnose → fix →
  verify. Verify re-runs diagnose after the fix; `verified` is True only
  when zero findings remain. A syntax error the surgeon cannot repair
  leaves `verified: False` and `decision: executed-with-findings` — the
  wound is reported, never hidden.

## CLI

```bash
levi uniforge surgeon <file>            # preview quick-cleanup fixes
levi uniforge surgeon <file> --apply    # apply them
levi uniforge operate <file>            # diagnose only
levi uniforge operate <file> --apply   # diagnose -> fix -> verify
```

Both accept `--receipt FILE` to write the receipt as JSON.

## The field instrument (Acode plugin, untouched)

The **Omega Triple Threat Elite** Acode plugin (`~/workspace/user/files/`
— `main.js`, `plugin.json`, `readme.md`) is UniForge's hand on Chauncey's
phone: Surgeon quick cleanups (Ctrl/Cmd-Shift-E), format (Shift-F),
closed-source header (Shift-L), watchdog guidance (Shift-W, info-only —
it cannot monitor inside Acode and says so). The plugin is **not**
rewritten or absorbed; it stays as-is as the field instrument. The deep
power the plugin defers to Termux (`omega_code_surgeon_elite.py`,
`omega_converter.py`, `omega_elite_guard.sh`) is not present in this
repo — `operate` is the in-repo deep instrument.

## ⚠ Known contradiction — Chauncey decides

`plugin.json` declares the plugin's license as **MIT**, but the
Converter stamps files with **"CLOSED SOURCE – All Rights Reserved"**
headers. Those contradict: an MIT-licensed tool that marks output
closed-source. The port preserves the behavior exactly as Chauncey
wrote it — nothing here resolves the contradiction. His call which
one wins.

## Honest limits

- Quick cleanup is cosmetic + style-level: whitespace, tabs, blank
  lines, `None` comparisons. It does not refactor, optimize, or fix
  logic bugs.
- `diagnose` finds syntax wounds and cleanup opportunities; it does not
  prove the code correct.
- `operate` cannot repair what it cannot understand — syntax errors
  stay reported, never silently dropped.
- The regex port follows JavaScript semantics; on non-ASCII identifiers
  Python's unicode `\w` may differ slightly from JS's ASCII `\w`.
  Parity tests cover the ASCII behavior Chauncey's plugin targets.
- The watchdog half lives in the Acode plugin as guidance only; there
  is no in-repo continuous-monitoring daemon.
