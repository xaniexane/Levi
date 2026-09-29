"""Hicomb IDE: Plugin Studio — scaffold -> test -> publish.

Plugins are tricombs cells: a folder with ``tricombs.json`` (the manifest
contract from ``~/workspace/hicomb/src/tricombs/manifest.ts``) and the
entry file it names, speaking the waggle v1 protocol. The studio extends
the existing ``levi.hicomb.studio`` web-studio guards — it does not
duplicate them: those guard the shipped single-file studio HTML; this
module guards the plugin lifecycle.

LAWS (declared up front, machine-checked in tests/test_hicomb_plugin_studio.py):
  S1 SCAFFOLD-COMPLETE  scaffold writes every required file; a missing
      file fails the scaffold loudly, never half-scaffolds.
  S2 TEST-GATE           publish refuses when tests fail — fail-closed.
  S3 OFFLINE             scaffold/test/publish perform zero network
      fetches. The test gate scans the entry for undeclared network use
      (fetch/XHR/WebSocket/http URLs): undeclared -> fail; declared
      "net" -> warning receipt (an offline host may refuse the grant).
  S4 NO-SILENT           every scaffold/test/publish decision is receipted
      to an append-only log.

Stdlib only. The local publish store defaults to
``~/.levi/hicomb/plugin_store/``; tests stay hermetic.
"""

from __future__ import annotations

import json
import re
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

# ---- the tricombs manifest contract, mirrored from
#      ~/workspace/hicomb/src/tricombs/manifest.ts (never redefined here)
NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
VERSION_RE = re.compile(r"^\d+\.\d+\.\d+(-[0-9A-Za-z.-]+)?$")
KNOWN_CAPABILITIES = ("fs-read", "fs-write", "editor", "commands", "net")

PLUGIN_KINDS = ("formatter", "theme", "tool")

_DEFAULT_NEEDS = {
    "formatter": ["editor"],
    "theme": [],
    "tool": ["commands", "editor"],
}

# Undeclared network use: the offline gate (S3).
_NET_PATTERNS = (
    re.compile(r"\bfetch\s*\("),
    re.compile(r"\bXMLHttpRequest\b"),
    re.compile(r"\bWebSocket\s*\("),
    re.compile(r"https?://"),
)

DEFAULT_STORE = Path.home() / ".levi" / "hicomb" / "plugin_store"


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


# ------------------------------------------------------------------ receipts
@dataclass
class StudioReceipt:
    ts: str
    action: str  # scaffold | test | publish
    plugin: str
    ok: bool
    detail: str = ""

    def as_dict(self) -> Dict[str, Any]:
        return {
            "ts": self.ts, "action": self.action, "plugin": self.plugin,
            "ok": self.ok, "detail": self.detail,
        }


class StudioJournal:
    def __init__(self, store_dir: Optional[Path | str] = None):
        self.store_dir = Path(store_dir) if store_dir else DEFAULT_STORE
        self.store_dir.mkdir(parents=True, exist_ok=True)
        self.path = self.store_dir / "studio_receipts.jsonl"

    def log(self, action: str, plugin: str, ok: bool,
            detail: str = "") -> StudioReceipt:
        rec = StudioReceipt(ts=_now(), action=action, plugin=plugin,
                            ok=ok, detail=detail)
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec.as_dict(), ensure_ascii=False) + "\n")
        return rec


# ------------------------------------------------------------------ manifest
def validate_manifest(source: str, raw: Any) -> List[str]:
    """Mirror of parseManifest's checks. Returns problems (empty = valid)."""
    problems: List[str] = []
    at = lambda p: f"tricombs.json in '{source}': {p}"  # noqa: E731
    if not isinstance(raw, dict):
        return [at("must be a JSON object")]
    name = raw.get("name")
    if not isinstance(name, str) or not NAME_RE.match(name):
        problems.append(at(f'"name" must be lowercase letters/digits/dashes, '
                           f"got {name!r}"))
    version = raw.get("version")
    if not isinstance(version, str) or not VERSION_RE.match(version):
        problems.append(at(f'"version" must look like 1.2.3, got {version!r}'))
    if not isinstance(raw.get("title"), str) or not raw.get("title"):
        problems.append(at('"title" must be a non-empty string'))
    if not isinstance(raw.get("cell"), str) or not raw.get("cell"):
        problems.append(at('"cell" must name the entry file'))
    needs = raw.get("needs")
    if not isinstance(needs, list) or any(
            n not in KNOWN_CAPABILITIES for n in needs):
        problems.append(at(f'"needs" must be a list of {KNOWN_CAPABILITIES}, '
                           f"got {needs!r}"))
    return problems


# ------------------------------------------------------------------ scaffold
_CELL_SKELETON = """\
// {name} — Hicomb plugin cell (tricombs waggle v1).
// kind: {kind} | title: {title}
// The host loads this file into a sealed cell. Speak only the waggle
// envelopes below; capabilities are granted from tricombs.json "needs".
"use strict";

function send(msg) {{
  msg.v = 1;
  postMessage(msg);
}}

function onHostMessage(msg) {{
  if (!msg || msg.v !== 1) return; // drop non-waggle traffic
  switch (msg.kind) {{
    case "command-invoke":
      handleCommand(msg);
      break;
    case "shutdown":
      // release resources here
      break;
    default:
      break;
  }}
}}

{kind_body}

onmessage = (e) => onHostMessage(e.data);
send({{ kind: "ready" }});
"""

_KIND_BODIES = {
    "formatter": """\
// Formatter cell: refine raw text, return refined text.
// Register this language with Pollen via the host's formatter capability.
function format(language, text) {
  // Pollen's base pass: whitespace normalization. Add language-specific
  // rules after this block; keep the base pass first so every formatter
  // cell shares the same foundation.
  const lines = String(text).split("\n").map((l) => l.replace(/\s+$/u, ""));
  let out = lines.join("\n");
  if (out.length > 0 && !out.endsWith("\n")) out += "\n";
  return out;
}

function handleCommand(msg) {
  send({ kind: "command-result", id: msg.id, ok: true,
         result: "formatter cells run on save, not on command" });
}
""",
    "theme": """\
// Theme cell: answers the host's theme queries. No commands needed.
function handleCommand(msg) {
  send({ kind: "command-result", id: msg.id, ok: true,
         result: "theme cells serve tokens, not commands" });
}
""",
    "tool": """\
// Tool cell: registers palette commands on ready.
function handleCommand(msg) {
  const cmd = msg.commandId || "";
  send({ kind: "notify", text: "tool cell ran: " + cmd, level: "info" });
  send({ kind: "command-result", id: msg.id, ok: true, result: cmd });
}

send({ kind: "command-register",
       command: { id: "%s", title: "%s", category: "Plugin" } });
""",
}


def scaffold_plugin(
    name: str,
    kind: str,
    title: Optional[str] = None,
    needs: Optional[List[str]] = None,
    version: str = "0.1.0",
    author: str = "Chauncey Logan",
    plugins_root: Optional[Path | str] = None,
    store_dir: Optional[Path | str] = None,
) -> Dict[str, Any]:
    """Scaffold a plugin folder. S1: every required file, or loud failure."""
    journal = StudioJournal(store_dir)
    if not isinstance(name, str) or not NAME_RE.match(name):
        journal.log("scaffold", str(name), False, "bad plugin name")
        raise ValueError(f"bad plugin name: {name!r}")
    if kind not in PLUGIN_KINDS:
        journal.log("scaffold", name, False, f"bad kind {kind!r}")
        raise ValueError(f"kind must be one of {PLUGIN_KINDS} (got {kind!r})")
    if not isinstance(version, str) or not VERSION_RE.match(version):
        journal.log("scaffold", name, False, "bad version")
        raise ValueError(f"version must look like 1.2.3 (got {version!r})")
    needs = list(needs) if needs is not None else list(_DEFAULT_NEEDS[kind])
    if any(n not in KNOWN_CAPABILITIES for n in needs):
        journal.log("scaffold", name, False, "bad capability")
        raise ValueError(f"unknown capability in {needs!r}")

    root = Path(plugins_root) if plugins_root else Path.cwd() / "plugins"
    dest = root / name
    if dest.exists() and any(dest.iterdir()):
        # originals-first: an existing plugin is never overwritten.
        journal.log("scaffold", name, False, "original exists")
        raise FileExistsError(
            f"plugins/{name} already exists — originals are never overwritten")
    dest.mkdir(parents=True, exist_ok=True)

    manifest = {
        "name": name,
        "version": version,
        "title": title or name.replace("-", " ").title(),
        "cell": "cell.js",
        "needs": needs,
        "description": f"{kind} plugin scaffolded by Hicomb Plugin Studio.",
    }
    kind_body = _KIND_BODIES[kind]
    if kind == "tool":
        kind_body = kind_body % (f"{name}.run", manifest["title"])
    cell = _CELL_SKELETON.format(
        name=name, kind=kind, title=manifest["title"], kind_body=kind_body)
    readme = (
        f"# {manifest['title']}\n\n"
        f"Kind: {kind} · version {version} · by {author}\n\n"
        "A Hicomb tricombs plugin. Entry: `cell.js` (waggle v1). "
        "Capabilities requested: "
        + (", ".join(needs) if needs else "none")
        + ".\n"
    )
    (dest / "tricombs.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (dest / "cell.js").write_text(cell, encoding="utf-8")
    (dest / "README.md").write_text(readme, encoding="utf-8")

    # S1: verify every required file landed.
    missing = [f for f in ("tricombs.json", "cell.js", "README.md")
               if not (dest / f).is_file()]
    if missing:
        journal.log("scaffold", name, False, f"missing {missing}")
        raise IOError(f"scaffold incomplete, missing: {missing}")
    journal.log("scaffold", name, True,
                f"kind={kind} files=tricombs.json,cell.js,README.md")
    return {"ok": True, "path": str(dest), "manifest": manifest,
            "files": ["tricombs.json", "cell.js", "README.md"]}


# ------------------------------------------------------------------ test
@dataclass
class TestReport:
    ok: bool
    problems: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def as_dict(self) -> Dict[str, Any]:
        return {"ok": self.ok, "problems": self.problems,
                "warnings": self.warnings}


def test_plugin(path: Path | str,
                store_dir: Optional[Path | str] = None) -> TestReport:
    """Static test gate for a plugin folder (S3: zero network fetches)."""
    journal = StudioJournal(store_dir)
    root = Path(path)
    name = root.name
    problems: List[str] = []
    warnings: List[str] = []

    manifest_file = root / "tricombs.json"
    manifest: Dict[str, Any] = {}
    if not manifest_file.is_file():
        problems.append("missing tricombs.json")
    else:
        try:
            manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            problems.append(f"tricombs.json is not valid JSON: {exc}")
        else:
            problems.extend(validate_manifest(name, manifest))

    entry = root / str(manifest.get("cell", "cell.js"))
    if not entry.is_file():
        problems.append(f"entry file missing: {entry.name}")
    else:
        try:
            text = entry.read_text(encoding="utf-8")
        except OSError as exc:
            problems.append(f"cannot read entry file: {exc}")
            text = ""
        if text:
            needs = manifest.get("needs", []) \
                if isinstance(manifest.get("needs"), list) else []
            net_hits = []
            for i, line in enumerate(text.split("\n"), 1):
                for pat in _NET_PATTERNS:
                    if pat.search(line):
                        net_hits.append(f"L{i}: {line.strip()[:80]}")
                        break
            if net_hits:
                if "net" in needs:
                    warnings.append(
                        "entry uses network APIs with 'net' declared — "
                        "an offline host may refuse the grant: "
                        + "; ".join(net_hits[:3]))
                else:
                    problems.append(
                        "entry uses network APIs without the 'net' "
                        "capability: " + "; ".join(net_hits[:3]))

    ok = not problems
    journal.log("test", name, ok,
                f"{len(problems)} problem(s), {len(warnings)} warning(s)")
    return TestReport(ok=ok, problems=problems, warnings=warnings)


# ------------------------------------------------------------------ publish
def publish_plugin(
    path: Path | str,
    store_dir: Optional[Path | str] = None,
) -> Dict[str, Any]:
    """Publish a plugin to the local store. S2: the test gate is fail-closed;
    S3: the publish performs zero network fetches (local copy only)."""
    journal = StudioJournal(store_dir)
    report = test_plugin(path, store_dir)
    name = Path(path).name
    if not report.ok:
        journal.log("publish", name, False,
                    f"test gate refused: {report.problems[:2]}")
        return {"ok": False, "error": "test gate refused",
                "problems": report.problems,
                "detail": "fix the problems and re-test before publishing"}
    manifest = json.loads(
        (Path(path) / "tricombs.json").read_text(encoding="utf-8"))
    store = Path(store_dir) if store_dir else DEFAULT_STORE
    dest = store / manifest["name"] / manifest["version"]
    if dest.exists():
        journal.log("publish", name, False, "version already published")
        return {"ok": False, "error": "already published",
                "detail": f"{manifest['name']} {manifest['version']} is "
                          "already in the store — bump the version"}
    dest.mkdir(parents=True)
    for child in Path(path).iterdir():
        if child.is_file():
            shutil.copy2(child, dest / child.name)
    journal.log("publish", name, True,
                f"published {manifest['name']} {manifest['version']} "
                f"({len(report.warnings)} warning(s))")
    return {"ok": True, "dest": str(dest), "manifest": manifest,
            "warnings": report.warnings}


__all__ = [
    "KNOWN_CAPABILITIES",
    "PLUGIN_KINDS",
    "StudioJournal",
    "TestReport",
    "publish_plugin",
    "scaffold_plugin",
    "test_plugin",
    "validate_manifest",
]
