"""archive-showcase: archive search -> assemble a collection -> galaxy publish.

Searches the live archive store (:py:func:`levi.archive.search.search`),
assembles the hits into a named collection manifest, and publishes the
collection to the galaxy registry (:py:class:`levi.galaxy.registry.GalaxyRegistry`).

Zero hits, or an invalid filter (e.g. a bad ``kind``), fails honestly with
a reason — a showcase is never published over an empty shelf.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from levi.archive.search import search as archive_search
from levi.archive.store import ArchiveStore
from levi.galaxy.registry import GalaxyRegistry

from ._common import (
    emit,
    finish_step,
    new_step,
    resolve_home,
    workflow_env,
    workflow_result,
)

NAME = "archive-showcase"
SUMMARY = (
    "Search the archive, assemble matching records into a named collection, "
    "and publish the collection to the galaxy registry."
)
STEP_NAMES = ["archive_search", "assemble_collection", "galaxy_publish"]


def run(
    home=None,
    query: str = "",
    kind: Optional[str] = None,
    rating: Optional[str] = None,
    status: Optional[str] = None,
    era: Optional[str] = None,
    title: Optional[str] = None,
    limit: int = 20,
    author: str = "levi-workflows",
    **kwargs,
) -> Dict[str, Any]:
    levi_home = resolve_home(home)
    emit("workflow.start", {"workflow": NAME, "home": str(levi_home), "query": query})
    steps: list = []
    artifacts: Dict[str, Any] = {}

    # -- step 1: archive search --------------------------------------------
    step = new_step("archive_search")
    try:
        with workflow_env(levi_home):
            store = ArchiveStore(home=levi_home.parent)
            hits = archive_search(
                store,
                query=query,
                kind=kind,
                rating=rating,
                status=status,
                era=era,
                limit=limit,
            )
        if not hits:
            raise ValueError("no archive records match query %r" % query)
        hit_ids = [h.record.id for h in hits]
        hit_titles = [h.record.title for h in hits]
        finish_step(
            step,
            True,
            {
                "query": query,
                "hits": len(hits),
                "record_ids": hit_ids,
                "scores": [h.score for h in hits],
            },
        )
        artifacts["record_ids"] = hit_ids
        artifacts["record_titles"] = hit_titles
    except Exception as exc:
        finish_step(step, False, reason="%s: %s" % (type(exc).__name__, exc))
        steps.append(step)
        emit("workflow.done", {"workflow": NAME, "ok": False})
        return workflow_result(NAME, steps, artifacts)
    steps.append(step)

    # -- step 2: assemble the collection manifest --------------------------
    step = new_step("assemble_collection")
    try:
        digest = hashlib.sha256(
            json.dumps(sorted(hit_ids), sort_keys=True).encode("utf-8")
        ).hexdigest()
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        pkg_id = "levi/workflows/showcase-%s" % stamp
        collection = {
            "id": pkg_id,
            "title": title or ("Showcase: %s" % (query or "archive picks")),
            "query": query,
            "filters": {"kind": kind, "rating": rating, "status": status, "era": era},
            "records": hit_ids,
            "record_count": len(hit_ids),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "records_sha256": digest,
        }
        finish_step(step, True, {"collection_id": pkg_id, "record_count": len(hit_ids)})
        artifacts["collection"] = collection
    except Exception as exc:
        finish_step(step, False, reason="%s: %s" % (type(exc).__name__, exc))
        steps.append(step)
        emit("workflow.done", {"workflow": NAME, "ok": False})
        return workflow_result(NAME, steps, artifacts)
    steps.append(step)

    # -- step 3: publish to the galaxy registry ----------------------------
    step = new_step("galaxy_publish")
    try:
        record = {
            "id": collection["id"],
            "version": "1.0.0",
            "kind": "archive-collection",
            "author": author,
            "source": "workflow:%s" % NAME,
            "description": collection["title"],
            "capabilities": ["archive", "search"],
            "root_sha256": digest,
            "installed_at": datetime.now(timezone.utc).isoformat(),
            "granted": {"network": False, "fs": [], "subprocess": False},
        }
        registry = GalaxyRegistry(levi_home)
        registry.add(record)
        finish_step(step, True, {"package_id": pkg_id, "root_sha256": digest})
        artifacts["package_id"] = pkg_id
        artifacts["registry_record"] = registry.get(pkg_id)
    except Exception as exc:
        finish_step(step, False, reason="%s: %s" % (type(exc).__name__, exc))
        steps.append(step)
        emit("workflow.done", {"workflow": NAME, "ok": False})
        return workflow_result(NAME, steps, artifacts)
    steps.append(step)

    emit("workflow.done", {"workflow": NAME, "ok": True, "records": len(hit_ids)})
    return workflow_result(NAME, steps, artifacts)
