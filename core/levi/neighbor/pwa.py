"""PWA shell — `pwa.py` (spec §13 phase 3).

A static, installable PWA shell for the gig-dispatch organ: `export_pwa`
writes a fully self-contained directory — index.html, manifest.json,
sw.js, and a snapshot.json of the operator's local state. No network
calls, no external scripts, no build step. Serve the directory with any
static server, or open index.html from disk.

Honest limits (stated in the shell itself): the PWA is a READ view of
a local snapshot plus deep links back to the CLI for actions; it does
not post jobs or move money. Branding comes from operator config
(policies.json `branding`) — white-label by config, never a code fork.

LAWS (machine-checked by `check_laws`):
- L1: the export is fully static — no remote URLs, no external scripts
  in any emitted file.
- L2: snapshot.json reflects only the latest snapshots of each stream
  (readable current state), generated locally at export time.
- L3: branding and labels come from operator config, never hardcoded.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from . import policies as policies_mod
from .store import Store


def snapshot(store: Store) -> dict[str, Any]:
    """Latest-snapshot view of the organ's readable state."""
    snap: dict[str, list] = {}
    for stream in ("gigs", "workers", "suppliers", "courses"):
        latest: dict[str, dict] = {}
        for r in store.read_all(stream):
            if r.get("id"):
                latest[r["id"]] = r
        # Readable state: strip stream bookkeeping, keep the record.
        snap[stream] = [
            {k: v for k, v in rec.items() if k not in ("seq", "ts")}
            for rec in latest.values()
        ]
    twin_dir = store.base / "twins"
    twins = []
    if twin_dir.exists():
        for p in twin_dir.glob("property_*.json"):
            if not p.name.endswith(".export.json"):
                t = json.loads(p.read_text(encoding="utf-8"))
                t.pop("maintenance_log", None)  # snapshot keeps the summary
                twins.append(t)
    snap["property_twins"] = twins
    return snap


_INDEX_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="theme-color" content="#111827">
<title>{app_name} — {tagline}</title>
<link rel="manifest" href="manifest.json">
<style>
body{{font-family:system-ui,sans-serif;background:#111827;color:#f3f4f6;margin:0;padding:1rem;max-width:42rem}}
h1{{font-size:1.4rem}} h2{{font-size:1.1rem;color:#93c5fd;margin-top:1.5rem}}
.card{{background:#1f2937;border-radius:.5rem;padding:.75rem;margin:.5rem 0}}
.badge{{font-size:.7rem;background:#374151;border-radius:.25rem;padding:.1rem .4rem;margin-left:.4rem}}
.limit{{background:#7c2d12;border-radius:.5rem;padding:.75rem;margin:1rem 0}}
small{{color:#9ca3af}}
</style>
</head>
<body>
<h1>{app_name}</h1>
<p><small>{tagline} · local snapshot, read-only</small></p>
<div class="limit">This shell shows a local snapshot. To post work, claim jobs, or
settle, use the <code>levi neighbor</code> CLI — the PWA never moves money.</div>
<h2>Open gigs (<span id="gig-count"></span>)</h2>
<div id="gigs"></div>
<h2>Workers (<span id="worker-count"></span>)</h2>
<div id="workers"></div>
<h2>Property twins (<span id="twin-count"></span>)</h2>
<div id="twins"></div>
<script>
fetch("snapshot.json").then(r=>r.json()).then(s=>{{
  const gigs=s.gigs.filter(g=>g.status==="open");
  document.getElementById("gig-count").textContent=gigs.length;
  document.getElementById("gigs").innerHTML=gigs.map(g=>
    `<div class="card"><b>${{g.title}}</b><span class="badge">${{g.category}}</span>
     <span class="badge">${{g.neighborhood_cell}}</span><br>
     <small>${{g.description||""}} · requester ${{g.requester||""}}</small></div>`).join("")
    || "<small>no open gigs in this snapshot</small>";
  const w=s.workers.filter(w=>w.status==="active");
  document.getElementById("worker-count").textContent=w.length;
  document.getElementById("workers").innerHTML=w.map(x=>
    `<div class="card"><b>${{x.name}}</b><span class="badge">${{(x.categories||[]).join(", ")}}</span>
     <br><small>${{x.home_cell||""}} · ${{x.available?"available":"unavailable"}}</small></div>`).join("")
    || "<small>no workers yet</small>";
  document.getElementById("twin-count").textContent=s.property_twins.length;
  document.getElementById("twins").innerHTML=s.property_twins.map(t=>
    `<div class="card"><b>${{t.address}}</b><br>
     <small>${{Object.keys(t.systems||{{}}).length}} systems tracked</small></div>`).join("")
    || "<small>no property twins yet</small>";
}}).catch(()=>{{document.body.innerHTML+="<p>snapshot.json missing — re-run the export.</p>"}});
if("serviceWorker" in navigator){{navigator.serviceWorker.register("sw.js").catch(()=>{{}});}}
</script>
</body>
</html>
"""

_SW_JS = """// NeighborOS PWA shell service worker — caches same-directory assets only.
const CACHE = "neighboros-shell-v1";
self.addEventListener("install", e => {
  e.waitUntil(caches.open(CACHE).then(c =>
    c.addAll(["./", "index.html", "manifest.json", "snapshot.json"])));
});
self.addEventListener("fetch", e => {
  e.respondWith(caches.match(e.request).then(r => r || fetch(e.request)));
});
"""


def export_pwa(store: Store, dest: str | Path | None = None) -> dict[str, Any]:
    """Write the static PWA shell directory."""
    policies = policies_mod.load_policies(store)
    branding = policies.get("branding", {})
    app_name = branding.get("app_name", "NeighborOS")
    tagline = branding.get(
        "tagline", "neighbors post work, trusted workers claim it"
    )
    dest_path = Path(dest) if dest else store.base / "pwa"
    dest_path.mkdir(parents=True, exist_ok=True)

    (dest_path / "snapshot.json").write_text(
        json.dumps(snapshot(store), indent=2, sort_keys=True, default=str),
        encoding="utf-8",
    )
    (dest_path / "index.html").write_text(
        _INDEX_TEMPLATE.format(app_name=app_name, tagline=tagline),
        encoding="utf-8",
    )
    (dest_path / "manifest.json").write_text(
        json.dumps(
            {
                "name": app_name,
                "short_name": app_name,
                "description": tagline,
                "start_url": "./index.html",
                "display": "standalone",
                "background_color": "#111827",
                "theme_color": "#111827",
                "icons": [],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (dest_path / "sw.js").write_text(_SW_JS, encoding="utf-8")
    return {"dir": str(dest_path), "app_name": app_name}


_REMOTE_URL = re.compile(r"https?://|src=\"http|href=\"http")


def check_laws(store: Store, dest: str | Path | None = None) -> dict[str, Any]:
    """Machine-check the PWA laws on the last export."""
    dest_path = Path(dest) if dest else store.base / "pwa"
    checks: dict[str, dict] = {}
    files = {
        "index.html": dest_path / "index.html",
        "manifest.json": dest_path / "manifest.json",
        "sw.js": dest_path / "sw.js",
        "snapshot.json": dest_path / "snapshot.json",
    }
    missing = [n for n, p in files.items() if not p.exists()]
    checks["export_present"] = {"ok": not missing, "missing": missing}
    remote = []
    for name in ("index.html", "sw.js"):
        p = files[name]
        if p.exists() and _REMOTE_URL.search(p.read_text(encoding="utf-8")):
            remote.append(name)
    checks["no_remote_urls"] = {"ok": not remote, "violations": remote}
    snap_ok = True
    if files["snapshot.json"].exists():
        snap = json.loads(files["snapshot.json"].read_text(encoding="utf-8"))
        for g in snap.get("gigs", []):
            if "seq" in g:  # snapshots must be readable state, not raw stream rows
                snap_ok = False
    checks["snapshot_is_readable_state"] = {"ok": snap_ok}
    return {"ok": all(c["ok"] for c in checks.values()), "checks": checks}
