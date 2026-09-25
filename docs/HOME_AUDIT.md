# HOME AUDIT — AXIS 6 (One Home)

**Date:** 2026-09-15 · **Scope:** `core/levi/**` (131 `Path.home()`/`expanduser()` hits), `delivery/megazord`, `apps/`, `tools/`, `web/`
**Rule:** all LEVI runtime state lives under `~/.levi/` (honoring `LEVI_HOME`/`LEVI_*_DIR` env overrides). Hermetic tests use tmp HOME — correct.

## Method

Grep sweep for: hard-coded `/tmp/`, `/var/`, `/home/`, `/etc/`, `/opt/`, `~/Documents`, `~/Downloads`, `~/.config`, `~/.cache`; `Path.home()` / `expanduser()` / `getenv("HOME")` / `Path.cwd()` / `os.getcwd()`; `tempfile.*`; relative `write_text`/`open(..., "w")`; `.db`/`.sqlite` paths. Every hit was read in context to classify write vs read vs lookup.

## Findings

| # | Straggler | Location | Verdict |
|---|-----------|----------|---------|
| 1 | JWT keys written to `~/.vyve/keys` | `apps/vyve-messenger/backend/shared/jwt_keys.py:45` | **Flagged, not fixed** — vyve-messenger is an active separate crew's surface. Recommendation: consolidate to `~/.levi/vyve/keys` (or `~/.levi/apps/vyve-messenger/keys`) in a follow-up owned by that crew. |
| 2 | Ingest read-source falls back to `~/workspace/research_notes` | `core/levi/archive/__main__.py:27` (`_research_root`) | **Acceptable** — read-only input source, not state; CLI `--research-root` overrides. All archive *writes* go to `~/.levi/archive` (`archive/store.py`). |
| 3 | `home` parameter means different things per galaxy call site (`~/.levi` in CLI/`install`, raw `~` in `service._install_dir_for`/`galaxy_home`) | `core/levi/galaxy/{registry,service,trust,install,__main__}.py` | **Acceptable with advisory** — the production CLI always passes `~/.levi`, so real installs land at `~/.levi/galaxy/...`; tests pin `home/"galaxy"` consistently. The mixed docstrings are tech debt, not a stray write. Do not "fix" without the galaxy owner; it would break pinned tests. |
| 4 | Untracked training artifact in repo tree | `core/levi/brain/train/corpus_academy.jsonl` (untracked, another worker's runtime file) | **Instance, not code** — left alone (not my file). Code defaults are clean: brain train `out_dir` is an explicit CLI arg; brain state defaults to `~/.levi/brain` / `LEVI_BRAIN_DIR`. |
| 5 | Static-asset dir resolution touches CWD candidates | `core/levi/ops/serve_ui.py:16-17` | **Acceptable** — read-only discovery; the only `mkdir` runs on the resolved (existing or package-level) dir, never creates under CWD. |
| 6 | `tempfile` usages: model download staging, `levi-lab-*` workdir, oath/plan9/galaxy sandboxes, atomic-write sidecars | `agent/local_model.py:642`, `cli/main.py:2607`, `oath/trust.py:168,180`, `revival/plan9.py:157`, `galaxy/install.py:400`, `galaxy/registry.py:94`, `archive/store.py:35` | **Acceptable-ephemeral** — per policy, `/tmp` is fine for ephemeral caches/staging; all are cleaned up or atomic-write sidecars beside their final (in-`~/.levi`) targets. |
| 7 | `~/bin/rclone` lookup | `core/levi/backup/config.py:86` | **False positive** — read-only PATH-style lookup for the rclone binary, not state. Backup state is `~/.levi/backups`. |
| 8 | `{"PATH": "/usr/bin:/bin"}` in plan9 sandbox env | `core/levi/revival/plan9.py:95` | **False positive** — sandbox env var, not a filesystem write. |
| 9 | Cron example strings containing `cd ~/workspace/levi` | `core/levi/bot/{chat,services,automation}.py` | **False positive** — docstring/help text, no writes. Bot state is `~/.levi/bot`. |
| 10 | `torch/bundle.py` writes to caller-supplied path | `core/levi/torch/bundle.py:170` | **Acceptable** — explicit user-supplied export target, not ambient state. |

## Result

**True write stragglers in `core/levi` code: 0.** All 131 home-path hits resolve under `~/.levi/` (or an explicit caller path / env override). No code changes required. The one genuine stray (`~/.vyve/keys`) belongs to another crew and is flagged, not fixed.

## Established conventions (for future code)

- Canonical LEVI home: `LEVI_HOME` env → else `~/.levi`. Model implementation: `core/levi/daemon/supervisor.py::levi_home()`; same pattern in `methods/_persist.py::base_dir()`.
- Per-module overrides follow `LEVI_<MODULE>_DIR` (e.g. `LEVI_GROWTH_DIR`, `LEVI_CLOUD_DIR`, `LEVI_BRAIN_DIR`, `LEVI_AGENT_SESSIONS_DIR`) with `Path.home() / ".levi" / <module>` fallback.
- Private state dirs/files get `0o700`/`0o600` (`archive/store.py`, `cloud/apikeys.py`, `perpetual/*`).
- New modules: take an optional `home` param (the LEVI home), resolve via the env pattern above, and never write above `~/.levi` except to an explicit user-supplied export path.
