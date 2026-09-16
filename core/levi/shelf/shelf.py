"""The Share Shelf: local-first curation desk.

One JSONL file per shelf: ``~/.levi/shelf/shelf.jsonl``. Items are
immutable dataclasses; the store is the only mutator. Ranking is
deterministic and honest: starred first, then newest, buried sunk to
the bottom. Bundles are self-describing zips (stdlib zipfile): a
human-readable ``shelf.md`` plus a machine ``shelf.json`` manifest.
"""

from __future__ import annotations

import json
import os
import re
import time
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

# -- errors ---------------------------------------------------------------


class ShelfError(Exception):
    """Deny-closed: anything malformed is refused, never half-written."""


# -- validation -----------------------------------------------------------

_URL_RE = re.compile(r"^https?://[^\s/$.?#].[^\s]*$", re.IGNORECASE)


def url_ok(url: str) -> bool:
    return isinstance(url, str) and bool(_URL_RE.match(url.strip()))


def _slug(text: str, max_len: int = 40) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return re.sub(r"-{2,}", "-", slug)[:max_len].strip("-") or "item"


# -- item -----------------------------------------------------------------


@dataclass(frozen=True)
class ShelfItem:
    id: str
    url: str
    title: str
    note: str = ""
    tags: Tuple[str, ...] = field(default_factory=tuple)
    starred: bool = False
    buried: bool = False
    added_at: float = field(default_factory=time.time)
    source: str = ""  # e.g. "hand-shelved", "bundle:friend.zip"

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "url": self.url,
            "title": self.title,
            "note": self.note,
            "tags": list(self.tags),
            "starred": self.starred,
            "buried": self.buried,
            "added_at": self.added_at,
            "source": self.source,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "ShelfItem":
        if not isinstance(data, dict):
            raise ShelfError("item must be a mapping")
        url = str(data.get("url", "")).strip()
        if not url_ok(url):
            raise ShelfError("bad item url: %r" % data.get("url"))
        title = str(data.get("title", "")).strip()
        if not title:
            raise ShelfError("item title is required")
        item_id = str(data.get("id", "")).strip()
        if not re.match(r"^[a-z0-9]+(?:-[a-z0-9]+)*$", item_id):
            raise ShelfError("bad item id: %r" % data.get("id"))
        tags = data.get("tags", []) or []
        if not isinstance(tags, list) or any(not isinstance(t, str) for t in tags):
            raise ShelfError("item tags must be a list of strings")
        return cls(
            id=item_id,
            url=url,
            title=title,
            note=str(data.get("note", "")),
            tags=tuple(str(t) for t in tags),
            starred=bool(data.get("starred", False)),
            buried=bool(data.get("buried", False)),
            added_at=float(data.get("added_at", time.time())),
            source=str(data.get("source", "")),
        )


def _new_id(url: str, title: str, added_at: float) -> str:
    base = _slug(title) or _slug(url)
    stamp = int(added_at)
    return "%s-%d" % (base[:32], stamp)


# -- store ----------------------------------------------------------------


def default_dir(home: Optional[Path] = None) -> Path:
    base = Path(home) if home else Path.home()
    return base / ".levi" / "shelf"


class ShelfStore:
    """Atomic JSONL shelf. Deny-closed on load: a corrupt line is refused
    loudly rather than skipped, so rot can never hide silently."""

    def __init__(self, home: Optional[Path] = None, shelf_dir: Optional[Path] = None):
        self.dir = shelf_dir or default_dir(home)
        self.path = self.dir / "shelf.jsonl"
        self._items: Dict[str, ShelfItem] = {}
        self.load()

    def load(self) -> None:
        self._items = {}
        if not self.path.is_file():
            return
        for lineno, line in enumerate(
            self.path.read_text(encoding="utf-8").splitlines(), 1
        ):
            line = line.strip()
            if not line:
                continue
            try:
                item = ShelfItem.from_dict(json.loads(line))
            except (
                ShelfError,
                json.JSONDecodeError,
                KeyError,
                TypeError,
                ValueError,
            ) as exc:
                raise ShelfError("shelf line %d refused: %s" % (lineno, exc)) from exc
            if item.id in self._items:
                raise ShelfError(
                    "shelf line %d refused: duplicate id %r" % (lineno, item.id)
                )
            self._items[item.id] = item

    def _save(self) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".jsonl.tmp")
        tmp.write_text(
            "\n".join(
                json.dumps(i.to_dict(), ensure_ascii=False)
                for i in self._items.values()
            )
            + ("\n" if self._items else ""),
            encoding="utf-8",
        )
        os.chmod(tmp, 0o600)
        os.replace(tmp, self.path)

    # -- mutation ---------------------------------------------------------

    def add(
        self,
        url: str,
        title: str,
        note: str = "",
        tags: Iterable[str] = (),
        source: str = "hand-shelved",
        added_at: Optional[float] = None,
    ) -> ShelfItem:
        if not url_ok(url):
            raise ShelfError("bad url: %r" % url)
        if not title or not title.strip():
            raise ShelfError("title is required")
        tag_list = [str(t).strip().lower() for t in (tags or []) if str(t).strip()]
        ts = added_at if added_at is not None else time.time()
        item = ShelfItem(
            id=_new_id(url, title.strip(), ts),
            url=url.strip(),
            title=title.strip(),
            note=note or "",
            tags=tuple(tag_list),
            added_at=ts,
            source=source,
        )
        self._items[item.id] = item
        self._save()
        return item

    def _get(self, item_id: str) -> ShelfItem:
        item = self._items.get(item_id)
        if item is None:
            raise ShelfError("no such shelf item: %r" % item_id)
        return item

    def _flip(self, item_id: str, **changes) -> ShelfItem:
        cur = self._get(item_id)
        data = cur.to_dict()
        data.update(changes)
        item = ShelfItem.from_dict(data)
        self._items[item_id] = item
        self._save()
        return item

    def star(self, item_id: str) -> ShelfItem:
        return self._flip(item_id, starred=True)

    def unstar(self, item_id: str) -> ShelfItem:
        return self._flip(item_id, starred=False)

    def bury(self, item_id: str) -> ShelfItem:
        """Digg's bury, revived: a reversible negative signal. The item is
        sunk, never deleted, and the bury is visible on the item itself."""
        return self._flip(item_id, buried=True)

    def unbury(self, item_id: str) -> ShelfItem:
        return self._flip(item_id, buried=False)

    def annotate(self, item_id: str, note: str) -> ShelfItem:
        return self._flip(item_id, note=note or "")

    def remove(self, item_id: str) -> None:
        self._get(item_id)
        del self._items[item_id]
        self._save()

    # -- reading ----------------------------------------------------------

    def get(self, item_id: str) -> ShelfItem:
        return self._get(item_id)

    def list(self, include_buried: bool = True) -> List[ShelfItem]:
        """Honest ranking: starred first, then newest, buried sunk to the
        bottom regardless of recency. No engagement signal anywhere."""
        items = list(self._items.values())
        if not include_buried:
            items = [i for i in items if not i.buried]

        def key(i: ShelfItem):
            return (i.buried, not i.starred, -i.added_at)

        return sorted(items, key=key)

    def search(self, query: str) -> List[ShelfItem]:
        q = (query or "").lower().strip()
        if not q:
            return []
        return [
            i
            for i in self._items.values()
            if q in i.title.lower()
            or q in i.note.lower()
            or q in i.url.lower()
            or any(q in t for t in i.tags)
        ]

    def stats(self) -> Dict[str, int]:
        n = len(self._items)
        return {
            "items": n,
            "starred": sum(1 for i in self._items.values() if i.starred),
            "buried": sum(1 for i in self._items.values() if i.buried),
        }

    # -- portability: share bundles ---------------------------------------

    def bundle(self, dest: Path) -> Path:
        """Export the shelf as a self-describing zip: shelf.md for humans,
        shelf.json for machines. The honest inversion of the sly trade:
        your curation leaves the platform; your data never leaves you."""
        dest = Path(dest)
        items = self.list(include_buried=True)
        lines = ["# Share Shelf — exported by LEVI", ""]
        lines.append(
            "%d item(s). Open this file, or import shelf.json "
            "into another shelf." % len(items)
        )
        lines.append("")
        for it in items:
            flags = []
            if it.starred:
                flags.append("STARRED")
            if it.buried:
                flags.append("BURIED")
            lines.append(
                "## %s%s" % (it.title, " [%s]" % ", ".join(flags) if flags else "")
            )
            lines.append("- url: %s" % it.url)
            if it.note:
                lines.append("- note: %s" % it.note)
            if it.tags:
                lines.append("- tags: %s" % ", ".join(it.tags))
            lines.append("")
        manifest = {
            "format": "levi-share-shelf/1",
            "exported_at": time.time(),
            "items": [i.to_dict() for i in items],
        }
        with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("shelf.md", "\n".join(lines).encode("utf-8"))
            zf.writestr(
                "shelf.json",
                json.dumps(manifest, indent=2, ensure_ascii=False).encode("utf-8"),
            )
        return dest

    def import_bundle(self, src: Path) -> Dict[str, int]:
        """Import a share bundle. Deny-closed: bad format or bad items are
        refused; items keep their provenance tag. Id collisions re-key."""
        src = Path(src)
        if not src.is_file():
            raise ShelfError("bundle not found: %s" % src)
        try:
            with zipfile.ZipFile(src) as zf:
                raw = zf.read("shelf.json")
        except (zipfile.BadZipFile, KeyError) as exc:
            raise ShelfError("not a share-shelf bundle: %s" % exc) from exc
        try:
            manifest = json.loads(raw.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise ShelfError("bundle manifest refused: %s" % exc) from exc
        if (
            not isinstance(manifest, dict)
            or manifest.get("format") != "levi-share-shelf/1"
        ):
            raise ShelfError("bundle manifest refused: unknown format")
        items = manifest.get("items", [])
        if not isinstance(items, list):
            raise ShelfError("bundle manifest refused: items must be a list")
        added = skipped = 0
        for entry in items:
            if not isinstance(entry, dict):
                raise ShelfError("bundle item refused: not a mapping")
            try:
                item = ShelfItem.from_dict(entry)
            except ShelfError as exc:
                raise ShelfError("bundle item refused: %s" % exc) from exc
            if item.id in self._items:
                # collision: re-key, never overwrite — loop until unique
                # (same-second re-keys could regenerate the same id)
                attempt = 0
                while True:
                    cand = _new_id(item.url, item.title, time.time())
                    if attempt:
                        cand = "%s-%d" % (cand, attempt)
                    try:
                        item = ShelfItem.from_dict({**entry, "id": cand})
                    except ShelfError as exc:
                        raise ShelfError("bundle item refused: %s" % exc) from exc
                    if cand not in self._items:
                        break
                    attempt += 1
            data = item.to_dict()
            data["source"] = "bundle:%s" % src.name
            item = ShelfItem.from_dict(data)
            self._items[item.id] = item
            added += 1
        self._save()
        return {"added": added, "skipped": skipped}
