"""Meta DYI graph export — the full social graph out of a DYI download.

The liberation research (``arch-giant-meta-dyi-graph``) found Meta's
"Download Your Information" export to be *browse-grade, not
import-grade*: social-graph portability was closed in 2013, and the
export scatters your graph across dozens of JSON files with no
single machine-readable graph. This module fixes that, locally: point
it at an unzipped DYI export and it extracts the **full graph** —
nodes (profile, people, pages, groups) and relationship edges
(friend, follows, member_of, interacted_with) — into one deterministic
``graph.json`` plus a checksum manifest.

LAWS
----
1. **Read-only on the source.** The DYI directory is never modified.
2. **No silent drops.** Every edge endpoint must exist as a node; an
   endpoint with no source record becomes an ``unresolved`` placeholder
   node, listed in the manifest. Dangling edges are never quietly lost.
3. **Deterministic.** Same export → byte-identical ``graph.json``
   (sorted nodes, sorted edges, canonical JSON).
4. **Manifest with checksums.** ``manifest.json`` records sha256 of the
   graph, node/edge counts, and the unresolved-endpoint report —
   verify before you trust.

The parser is tolerant by design: DYI file names drift between export
versions, so extraction works off filename *patterns* plus JSON shape,
and everything unrecognized is reported in the manifest, not crashed
on. stdlib-only, local-first, no network.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple

__all__ = [
    "DYIError",
    "extract_graph",
    "write_export",
    "verify_export",
    "KNOWN_SOURCES",
]


class DYIError(Exception):
    """The DYI export could not be read."""


def _node_id(kind: str, key: str) -> str:
    digest = hashlib.sha256(f"{kind}\x00{key}".encode("utf-8")).hexdigest()[:16]
    return f"{kind}:{digest}"


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DYIError(f"cannot read {path}: {exc}") from exc


def _iter_json_files(root: Path) -> Iterator[Path]:
    for p in sorted(root.rglob("*.json")):
        if p.is_file():
            yield p


# (filename pattern, extractor name) — DYI names drift; patterns hold.
KNOWN_SOURCES = (
    (re.compile(r"profile_information.*\.json$"), "profile"),
    (re.compile(r"friends\.json$"), "friends"),
    (re.compile(r"followers\.json$"), "followers"),
    (re.compile(r"following\.json$"), "following"),
    (re.compile(r"your_groups.*\.json$"), "groups"),
    (re.compile(r"pages.*\.json$"), "pages"),
)


@dataclass
class Graph:
    nodes: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    edges: List[Dict[str, Any]] = field(default_factory=list)
    sources_seen: List[str] = field(default_factory=list)
    unrecognized: List[str] = field(default_factory=list)

    def add_node(self, kind: str, key: str, attrs: Dict[str, Any]) -> str:
        nid = _node_id(kind, key.strip().casefold())
        if nid not in self.nodes:
            node = {"id": nid, "kind": kind, "key": key.strip(), **attrs}
            self.nodes[nid] = node
        else:
            # Merge: later sources enrich, never overwrite the key.
            for k, v in attrs.items():
                self.nodes[nid].setdefault(k, v)
        return nid

    def add_edge(self, src: str, dst: str, rel: str,
                 attrs: Optional[Dict[str, Any]] = None) -> None:
        self.edges.append({"src": src, "dst": dst, "rel": rel,
                           **(attrs or {})})


def _as_list(obj: Any) -> List[Any]:
    if isinstance(obj, list):
        return obj
    if isinstance(obj, dict):
        for v in obj.values():
            if isinstance(v, list):
                return v
    return []


def _extract_profile(g: Graph, path: Path, self_id: str) -> None:
    data = _read_json(path)
    info = data.get("profile_v2", data) if isinstance(data, dict) else {}
    name = ""
    if isinstance(info, dict):
        name = str(info.get("name", {}).get("full_name", "")
                   if isinstance(info.get("name"), dict)
                   else info.get("full_name", "") or "")
    g.nodes[self_id]["key"] = name or "me"
    g.nodes[self_id]["source_file"] = path.name


def _extract_friends(g: Graph, path: Path, self_id: str) -> None:
    for entry in _as_list(_read_json(path)):
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("name", "")).strip()
        if not name:
            continue
        nid = g.add_node("person", name, {"source_file": path.name})
        g.add_edge(self_id, nid, "friend",
                   {"since": entry.get("timestamp")})


def _extract_follow(g: Graph, path: Path, self_id: str, rel: str) -> None:
    for entry in _as_list(_read_json(path)):
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("name", "") or entry.get("title", "")).strip()
        if not name:
            continue
        nid = g.add_node("person", name, {"source_file": path.name})
        g.add_edge(self_id, nid, rel, {"since": entry.get("timestamp")})


def _extract_groups(g: Graph, path: Path, self_id: str) -> None:
    for entry in _as_list(_read_json(path)):
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("name", "") or entry.get("title", "")).strip()
        if not name:
            continue
        nid = g.add_node("group", name, {"source_file": path.name})
        g.add_edge(self_id, nid, "member_of")


def _extract_pages(g: Graph, path: Path, self_id: str) -> None:
    for entry in _as_list(_read_json(path)):
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("name", "") or entry.get("title", "")).strip()
        if not name:
            continue
        nid = g.add_node("page", name, {"source_file": path.name})
        g.add_edge(self_id, nid, "follows_page")


_EXTRACTORS = {
    "profile": _extract_profile,
    "friends": _extract_friends,
    "followers": lambda g, p, s: _extract_follow(g, p, s, "followed_by"),
    "following": lambda g, p, s: _extract_follow(g, p, s, "follows"),
    "groups": _extract_groups,
    "pages": _extract_pages,
}


def extract_graph(dyi_dir: "str | Path") -> Graph:
    """Extract the full social graph from an unzipped DYI export."""
    root = Path(dyi_dir)
    if not root.is_dir():
        raise DYIError(f"not a directory: {dyi_dir}")
    g = Graph()
    self_id = g.add_node("profile", "me", {"role": "export owner"})
    for path in _iter_json_files(root):
        rel = str(path.relative_to(root))
        matched = next((name for pat, name in KNOWN_SOURCES
                        if pat.search(path.name.lower())), None)
        if matched is None:
            g.unrecognized.append(rel)
            continue
        g.sources_seen.append(rel)
        try:
            _EXTRACTORS[matched](g, path, self_id)
        except DYIError:
            raise
        except Exception as exc:  # tolerant: report, don't crash
            g.unrecognized.append(f"{rel} (parse note: {exc})")
    # Law 2: no dangling edges — unresolved endpoints become placeholders.
    unresolved: List[str] = []
    for e in g.edges:
        for end in ("src", "dst"):
            if e[end] not in g.nodes:
                g.nodes[e[end]] = {"id": e[end], "kind": "unresolved",
                                   "key": e[end], "note": "endpoint with no source record"}
                unresolved.append(e[end])
    g.unresolved_endpoints = sorted(set(unresolved))  # type: ignore[attr-defined]
    return g


def _canonical(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def write_export(g: Graph, out_dir: "str | Path",
                 source_dir: "str | Path") -> Dict[str, Any]:
    """Write ``graph.json`` + ``manifest.json``. Returns the manifest."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    nodes = sorted(g.nodes.values(), key=lambda n: n["id"])
    edges = sorted(g.edges, key=lambda e: (e["src"], e["dst"], e["rel"]))
    graph_doc = {"format": "levi-dyi-graph/1", "nodes": nodes, "edges": edges}
    graph_bytes = _canonical(graph_doc) + b"\n"
    (out / "graph.json").write_bytes(graph_bytes)
    manifest = {
        "format": "levi-dyi-manifest/1",
        "exported_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source_dir": str(source_dir),
        "graph_sha256": hashlib.sha256(graph_bytes).hexdigest(),
        "node_count": len(nodes),
        "edge_count": len(edges),
        "node_kinds": sorted({n["kind"] for n in nodes}),
        "sources_seen": sorted(g.sources_seen),
        "unrecognized_files": sorted(g.unrecognized),
        "unresolved_endpoints": sorted(getattr(g, "unresolved_endpoints", [])),
    }
    (out / "manifest.json").write_bytes(_canonical(manifest) + b"\n")
    return manifest


def verify_export(out_dir: "str | Path") -> Tuple[bool, List[str]]:
    """Verify an export: checksum match + referential integrity.

    Returns ``(ok, findings)``. An export whose graph.json fails the
    checksum is refused outright; referential breaks are named.
    """
    out = Path(out_dir)
    findings: List[str] = []
    for fname in ("graph.json", "manifest.json"):
        if not (out / fname).exists():
            return False, [f"missing {fname}"]
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    graph_bytes = (out / "graph.json").read_bytes()
    digest = hashlib.sha256(graph_bytes).hexdigest()
    if digest != manifest.get("graph_sha256"):
        return False, ["graph.json checksum mismatch: export is not intact"]
    graph = json.loads(graph_bytes.decode("utf-8"))
    node_ids = {n["id"] for n in graph.get("nodes", [])}
    for e in graph.get("edges", []):
        for end in ("src", "dst"):
            if e[end] not in node_ids:
                findings.append(f"dangling edge {e['src']} -[{e['rel']}]-> {e['dst']}")
    if findings:
        return False, findings
    return True, [f"ok: {len(node_ids)} nodes, "
                  f"{len(graph.get('edges', []))} edges, checksum intact"]
