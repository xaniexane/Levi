"""Release-bundle assembler — the customer cut, hash-manifested.

Builds the standalone customer tarball: the ``demand`` engine + the
``demandpulse`` product layer, rewritten into the customer-neutral
``demandpulse/`` namespace (zero ``levi`` references), plus the customer
README, the HQ Decision 3 terms, the HQ Decision 5 product sheet, and a
POSIX setup script.

LAWS (invariants — the tests prove each one):
  * Exclusion law: watch.py, threat_feed.py, threat_signals.py (the
    internal tracker / threat-intel feed) and cybrus_alliance.py (the
    internal Cybrus guard pairing) NEVER appear in the payload. The
    bundled demandpulse/__init__.py is rewritten to drop them from its
    imports and __all__ so the bundle imports clean.
  * Namespace law: every payload path ``core/levi/X`` ships as
    ``demandpulse/X``; every ``levi`` token in .py sources becomes
    ``demandpulse`` (imports, home dirs, env vars, prose); no bundled
    file contains a ``levi``/``LEVI`` word afterward.
  * Docs law: README.md + TERMS.md (HQ3 verbatim) + PRODUCT_SHEET.md
    (HQ5 verbatim) ship inside the tarball; setup.sh passes ``bash -n``.
  * Manifest law: the sidecar manifest hashes every tarball member;
    verify_bundle() re-checks all of them against a fresh plan.
  * Gate law: assembly is pure local file work. This module never runs
    the setup script, never installs, never delivers, never lists, never
    wires payments. Those stop at Chauncey's explicit per-action word.

Stdlib only.
"""

from __future__ import annotations

import hashlib
import io
import json
import re
import tarfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from levi.demandpulse.payments import TERMS_HQ3
from levi.demandpulse.product import PRODUCT_NAME, PRODUCT_SHEET_HQ5, PRODUCT_VERSION

# Payload roots, relative to the repo root (~/workspace/levi).
PAYLOAD_MODULES = ("core/levi/demand", "core/levi/demandpulse")

# Internal material — never in the customer cut.
EXCLUDE_FILES = frozenset(
    {
        "watch.py",  # his internal "tracker of everything"
        "threat_feed.py",  # Cybrus threat-intel feed (guard business)
        "threat_signals.py",  # Cybrus threat-intel signals (guard business)
        "cybrus_alliance.py",  # internal Cybrus guard pairing
    }
)
EXCLUDE_NAMES = frozenset({"__pycache__", ".pytest_cache", ".hypothesis"})
# Module basenames dropped from the bundled demandpulse/__init__.py.
EXCLUDED_MODNAMES = frozenset(
    {Path(n).stem for n in EXCLUDE_FILES} | {"threat_feed"}
)

BUNDLE_STEM = f"demandpulse-{PRODUCT_VERSION}"


def repo_root(start: Optional[Path] = None) -> Path:
    """Find the repo root by walking up to the dir containing core/levi."""
    here = Path(start or __file__).resolve()
    for parent in (here, *here.parents):
        if (parent / "core" / "levi").is_dir():
            return parent
    raise RuntimeError("could not locate repo root (core/levi) from " + str(here))


# ---------------------------------------------------------------------------
# Namespace neutralization
# ---------------------------------------------------------------------------

_BUNDLE_INIT = "demandpulse/demandpulse/__init__.py"


def _drop_excluded_from_init(text: str) -> str:
    """Remove excluded modules from the bundled package __init__."""
    names = "|".join(sorted(EXCLUDED_MODNAMES))
    import_pat = re.compile(r"\s*(?:" + names + r")\s+as\s+\w+,\s*$")
    all_pat = re.compile(r"\s*\"(?:" + names + r")\",\s*$")
    out: List[str] = []
    for line in text.splitlines():
        if import_pat.match(line):
            continue
        if all_pat.match(line):
            continue
        out.append(line)
    return "\n".join(out) + "\n"


def neutralize_source(text: str, bundle_rel: str) -> str:
    """Rewrite one .py source into the customer-neutral namespace.

    Rules (order matters):
      1. ``core/levi/`` -> ``demandpulse/`` (repo-path references)
      2. ``LEVI_HOME`` -> ``DEMANDPULSE_HOME`` (env var)
      3. ``levi_home`` -> ``demandpulse_home`` (internal helper; renamed
         whole-word so every definition, call site, and export stays in sync)
      4. ``LEVI`` -> ``DEMANDPULSE`` (whole word, prose)
      5. ``levi`` -> ``demandpulse`` (whole word: imports, paths, prose)
    """
    text = text.replace("core/levi/", "demandpulse/")
    text = text.replace("LEVI_HOME", "DEMANDPULSE_HOME")
    text = re.sub(r"\blevi_home\b", "demandpulse_home", text)
    text = re.sub(r"\bLEVI\b", "DEMANDPULSE", text)
    text = re.sub(r"\blevi\b", "demandpulse", text)
    if bundle_rel == _BUNDLE_INIT:
        text = _drop_excluded_from_init(text)
    return text


def _bundle_rel(src_rel: str) -> str:
    """Map a repo-relative payload path to its tarball path.

    ``core/levi/demand/pulse.py`` -> ``demandpulse/demand/pulse.py``.
    """
    if not src_rel.startswith("core/levi/"):
        raise ValueError(f"payload path outside core/levi: {src_rel}")
    return "demandpulse/" + src_rel[len("core/levi/") :]


def _iter_payload_files(root: Path) -> List[Tuple[Path, str]]:
    """(source path, tarball-relative path) for every payload file."""
    found: List[Tuple[Path, str]] = []
    for module in PAYLOAD_MODULES:
        base = root / module
        if not base.is_dir():
            raise FileNotFoundError(f"payload module missing: {base}")
        for path in sorted(base.rglob("*")):
            if path.is_dir() or path.name in EXCLUDE_NAMES:
                continue
            if path.name in EXCLUDE_FILES:
                continue
            if any(part in EXCLUDE_NAMES for part in path.parts):
                continue
            src_rel = path.relative_to(root).as_posix()
            found.append((path, _bundle_rel(src_rel)))
    found.sort(key=lambda item: item[1])
    return found


def _final_bytes(src: Path, bundle_rel: str) -> bytes:
    """File content as it ships: .py sources neutralized, rest raw."""
    data = src.read_bytes()
    if src.suffix == ".py":
        data = neutralize_source(data.decode("utf-8"), bundle_rel).encode("utf-8")
    return data


# ---------------------------------------------------------------------------
# Customer docs + setup script (generated text, reviewed not executed)
# ---------------------------------------------------------------------------

def customer_readme() -> str:
    return f"""# {PRODUCT_NAME} — $6/month

Demand sensing that runs on your machine — no cloud, no meter, no tiers.

## What this is

The standalone customer cut: the DemandPulse sensing engine plus its
command surface. You type keywords in; it watches public sources, clusters
what it finds, scores it on five factors with a written basis for every
score, and delivers threshold alerts, morning briefings, breakout watches,
and reminders to your console and a file outbox you own.

Read PRODUCT_SHEET.md for exactly what the $6 buys (and its honest limits),
and TERMS.md for the billing terms.

## Requirements

- Python 3.11+ (no other dependencies — the core is stdlib-only)
- A POSIX shell for setup.sh (Linux, macOS, Termux)

## Install

REVIEW FIRST: setup.sh is generated text. Read it before running anything.

```bash
bash setup.sh {BUNDLE_STEM}.tar.gz
```

This installs into `~/.demandpulse` and puts a `demandpulse` launcher on
your PATH (`~/.local/bin`). It never touches the network.

## Activate your license

After your $6 payment is confirmed you receive a license key by email:

```bash
demandpulse activate --email you@example.com --key DP-XXXX-XXXX-XXXX
```

## Use it

```bash
demandpulse status                              # smoke check
demandpulse quickstart --keywords "sourdough,fermentation"
demandpulse digest                              # latest briefing
demandpulse digest --out                        # ...to your file outbox
demandpulse sheet                               # the product sheet again
```

Your data lives under `~/.demandpulse` (override with `DEMANDPULSE_HOME`).
Your settings and history are kept even if your month lapses.

## Terms

TERMS.md — $6/month, no auto-renewal, stop = don't pay, 7-day grace,
7-day full refund no questions. Plain speech on purpose: if anything is
unclear, ask before you pay.

## Honesty

Scores are hypotheses — advisory, never a claim about real demand.
Anything the engine can't prove gets quarantined, never published.
Sources are polite public reads, not a realtime firehose.
"""


def write_setup_script() -> str:
    """Generate the POSIX setup script text. Review-only: never executed
    by this build. Must pass ``bash -n``."""
    return f"""#!/usr/bin/env bash
# {PRODUCT_NAME} v{PRODUCT_VERSION} setup — REVIEW ONLY, OWNER GATE.
#
# This script is generated, not executed, by the build. Running it installs
# the customer product and is NOT authorized: installation, listing,
# delivery, and release all stop at Chauncey's explicit per-action word.
#
# Usage (after owner approval):  bash setup.sh <{BUNDLE_STEM}.tar.gz>
set -euo pipefail

TARBALL="${{1:-}}"
if [ -z "$TARBALL" ] || [ ! -f "$TARBALL" ]; then
  echo "usage: bash setup.sh <{BUNDLE_STEM}.tar.gz>" >&2
  exit 1
fi

DP_HOME="${{DEMANDPULSE_HOME:-$HOME/.demandpulse}}"
APP_DIR="$DP_HOME/app"

echo "==> installing {PRODUCT_NAME} v{PRODUCT_VERSION} into $DP_HOME"
mkdir -p "$APP_DIR"
tar -xzf "$TARBALL" -C "$APP_DIR"

echo "==> installing 'demandpulse' wrapper into ~/.local/bin"
mkdir -p "$HOME/.local/bin"
cat > "$HOME/.local/bin/demandpulse" <<'WRAP'
#!/usr/bin/env bash
# {PRODUCT_NAME} launcher. Core is stdlib-only: no venv, no pip needed.
APP_DIR="${{DEMANDPULSE_HOME:-$HOME/.demandpulse}}/app"
export PYTHONPATH="$APP_DIR${{PYTHONPATH:+:$PYTHONPATH}}"
export DEMANDPULSE_HOME="${{DEMANDPULSE_HOME:-$HOME/.demandpulse}}"
exec python3 -m demandpulse.demandpulse "$@"
WRAP
chmod +x "$HOME/.local/bin/demandpulse"

echo "==> smoke test (status only — no scans, no network)"
"$HOME/.local/bin/demandpulse" status

echo "done. Next: demandpulse quickstart --keywords 'a,b,c'"
"""


def extra_files() -> List[Tuple[str, bytes]]:
    """Docs + setup script shipped at the tarball root."""
    return [
        ("README.md", customer_readme().encode("utf-8")),
        ("TERMS.md", (TERMS_HQ3 + "\n").encode("utf-8")),
        ("PRODUCT_SHEET.md", (PRODUCT_SHEET_HQ5 + "\n").encode("utf-8")),
        ("setup.sh", write_setup_script().encode("utf-8")),
    ]


# ---------------------------------------------------------------------------
# Plan / write / verify
# ---------------------------------------------------------------------------

def plan_bundle(root: Optional[Path] = None) -> List[Dict[str, Any]]:
    """List every tarball member with size + sha256 of its FINAL bytes.

    Deterministic order. Payload entries use neutralized content hashes —
    what ships, not what the repo holds.
    """
    root = Path(root) if root else repo_root()
    entries: List[Dict[str, Any]] = []
    for src, bundle_rel in _iter_payload_files(root):
        data = _final_bytes(src, bundle_rel)
        entries.append(
            {
                "rel": f"{BUNDLE_STEM}/{bundle_rel}",
                "size": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
            }
        )
    for name, data in extra_files():
        entries.append(
            {
                "rel": f"{BUNDLE_STEM}/{name}",
                "size": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
            }
        )
    entries.sort(key=lambda e: e["rel"])
    return entries


def write_bundle(root: Optional[Path] = None, dest_dir: Optional[Path] = None) -> Path:
    """Assemble the tarball into ``dest_dir`` (caller's choice; tests use
    tmp dirs). Returns the tarball path. Does not install or deliver it."""
    root = Path(root) if root else repo_root()
    dest = Path(dest_dir) if dest_dir else Path.cwd()
    dest.mkdir(parents=True, exist_ok=True)
    tarball = dest / f"{BUNDLE_STEM}.tar.gz"

    payload = {bundle_rel: _final_bytes(src, bundle_rel)
               for src, bundle_rel in _iter_payload_files(root)}
    extras = dict(extra_files())

    def member_bytes(rel: str) -> bytes:
        prefix = BUNDLE_STEM + "/"
        assert rel.startswith(prefix), rel
        inner = rel[len(prefix):]
        if inner in payload:
            return payload[inner]
        return extras[inner]

    with tarfile.open(tarball, "w:gz") as tf:
        for entry in plan_bundle(root):
            data = member_bytes(entry["rel"])
            assert len(data) == entry["size"], entry["rel"]
            info = tarfile.TarInfo(name=entry["rel"])
            info.size = len(data)
            info.mtime = 0  # deterministic tarball
            if entry["rel"].endswith("setup.sh"):
                info.mode = 0o755
            tf.addfile(info, io.BytesIO(data))

    manifest = dest / f"{BUNDLE_STEM}.manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "product": PRODUCT_NAME,
                "version": PRODUCT_VERSION,
                "files": plan_bundle(root),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return tarball


def verify_bundle(tarball: Path, root: Optional[Path] = None) -> Dict[str, Any]:
    """Re-open a tarball and verify every member hash against a fresh plan.
    Returns {ok, files, mismatches}. Pure check — changes nothing."""
    tarball = Path(tarball)
    result: Dict[str, Any] = {"ok": False, "files": 0, "mismatches": []}
    if not tarball.is_file():
        result["mismatches"].append("tarball not found")
        return result
    try:
        with tarfile.open(tarball, "r:gz") as tf:
            seen = {}
            for member in tf.getmembers():
                if not member.isfile():
                    continue
                fh = tf.extractfile(member)
                if fh is None:
                    continue
                seen[member.name] = hashlib.sha256(fh.read()).hexdigest()
            result["files"] = len(seen)
            for entry in plan_bundle(root):
                got = seen.get(entry["rel"])
                if got != entry["sha256"]:
                    result["mismatches"].append(entry["rel"])
            planned = {e["rel"] for e in plan_bundle(root)}
            for name in seen:
                if name not in planned:
                    result["mismatches"].append(f"unexpected member: {name}")
    except (tarfile.TarError, OSError) as exc:
        result["mismatches"].append(f"unreadable tarball: {exc}")
        return result
    result["ok"] = not result["mismatches"]
    return result
