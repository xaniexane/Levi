"""BeOS/BFS revival: reactive live queries over the memory store.

BeOS's filesystem let you register "live queries" that notified you the
moment matching files appeared. This module does the same for LEVI's memory
store: subscribe a query (keywords, tags, entry-type, min-importance) and
your callback fires whenever a matching entry arrives via ``notify``.

The two public pieces:

- ``LiveQuery``: the subscription registry. ``subscribe(query, callback)``
  returns an id; ``unsubscribe(id)`` removes it; ``notify(entry)`` fans a
  new entry out to every matching subscriber. Subscriptions persist as
  plain specs; callbacks re-register by name through ``register_handler``
  so live queries survive restarts.
- ``LiveStore``: a thin wrapper around LEVI's real ``MemoryStore`` (lazy
  import; the memory module is never modified). ``store_entry(...)`` both
  persists the entry and notifies subscribers.

Entries may be ``MemoryEntry`` objects (from ``levi.memory``) or plain
dicts — ``notify`` normalizes them before matching.

Defensive notes:

- A misbehaving subscriber callback can never break ``notify``: each
  callback runs in its own guard, failures are recorded and reported.
- Duplicate subscription ids are impossible; unknown unsubscribe ids
  raise ``ValueError`` loudly instead of being silently ignored.
"""

from __future__ import annotations

import itertools
import json
import traceback
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional


# --------------------------------------------------------------------------
# Query spec
# --------------------------------------------------------------------------


@dataclass
class QuerySpec:
    """A live query: entry matches when ALL non-None fields match.

    - ``keywords``: at least one keyword appears in the content (case-insensitive)
    - ``tags``: at least one tag is present on the entry
    - ``entry_type``: memory_type equals this (e.g. "fact", "journal")
    - ``min_importance``: entry importance >= this
    """

    keywords: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    entry_type: Optional[str] = None
    min_importance: Optional[float] = None

    def __post_init__(self) -> None:
        if self.keywords is not None and (
            not isinstance(self.keywords, list)
            or not all(isinstance(k, str) for k in self.keywords)
        ):
            raise ValueError("bfs: keywords must be a list of strings")
        if self.tags is not None and (
            not isinstance(self.tags, list)
            or not all(isinstance(t, str) for t in self.tags)
        ):
            raise ValueError("bfs: tags must be a list of strings")
        if self.min_importance is not None:
            try:
                self.min_importance = float(self.min_importance)
            except (TypeError, ValueError):
                raise ValueError("bfs: min_importance must be a number")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "keywords": self.keywords,
            "tags": self.tags,
            "entry_type": self.entry_type,
            "min_importance": self.min_importance,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "QuerySpec":
        if not isinstance(data, dict):
            raise ValueError("bfs: query spec must be a dict")
        return cls(
            keywords=data.get("keywords"),
            tags=data.get("tags"),
            entry_type=data.get("entry_type"),
            min_importance=data.get("min_importance"),
        )


def entry_as_dict(entry: Any) -> Dict[str, Any]:
    """Normalize a MemoryEntry (or dict) into a plain dict for matching."""
    if isinstance(entry, dict):
        return entry
    to_dict = getattr(entry, "to_dict", None)
    if callable(to_dict):
        try:
            result = to_dict()
            if isinstance(result, dict):
                return result
        except Exception:
            pass
    out: Dict[str, Any] = {}
    for key in (
        "id",
        "content",
        "tags",
        "source",
        "importance",
        "memory_type",
        "metadata",
    ):
        if hasattr(entry, key):
            out[key] = getattr(entry, key)
    # memory_type may be an Enum; normalize to its value.
    mt = out.get("memory_type")
    out["memory_type"] = getattr(mt, "value", mt)
    return out


def query_matches(spec: QuerySpec, entry: Any) -> bool:
    """True when the entry satisfies every non-None field of the spec."""
    e = entry_as_dict(entry) if not isinstance(entry, dict) else entry
    content = str(e.get("content") or "")
    tags = e.get("tags") or []
    tags = [str(t) for t in tags] if isinstance(tags, list) else [str(tags)]
    mt = e.get("memory_type")
    mt = getattr(mt, "value", mt)
    try:
        importance = float(e.get("importance", 0.0))
    except (TypeError, ValueError):
        importance = 0.0

    if spec.keywords:
        low = content.lower()
        if not any(k.lower() in low for k in spec.keywords):
            return False
    if spec.tags:
        have = {t.lower() for t in tags}
        if not any(t.lower() in have for t in spec.tags):
            return False
    if spec.entry_type is not None and str(mt) != str(spec.entry_type):
        return False
    if spec.min_importance is not None and importance < spec.min_importance:
        return False
    return True


# --------------------------------------------------------------------------
# Live query registry
# --------------------------------------------------------------------------

_HANDLER_REGISTRY: Dict[str, Callable[[Dict[str, Any]], None]] = {}


def register_handler(name: str, fn: Callable[[Dict[str, Any]], None]) -> None:
    """Register a named callback so durable subscriptions can re-arm after load."""
    if not isinstance(name, str) or not name.strip():
        raise ValueError("bfs: handler name must be a non-empty string")
    if not callable(fn):
        raise TypeError("bfs: handler must be callable")
    _HANDLER_REGISTRY[name] = fn


def get_handler(name: str) -> Optional[Callable[[Dict[str, Any]], None]]:
    return _HANDLER_REGISTRY.get(name)


@dataclass
class Subscription:
    sub_id: str
    spec: QuerySpec
    callback: Callable[[Dict[str, Any]], None]
    handler_name: Optional[str] = None
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class LiveQuery:
    """Subscription registry for reactive memory queries."""

    def __init__(self) -> None:
        self._subs: Dict[str, Subscription] = {}
        self._counter = itertools.count(1)
        self._errors: List[Dict[str, Any]] = []  # subscriber callback failures

    def subscribe(
        self,
        query: QuerySpec,
        callback: Callable[[Dict[str, Any]], None],
        handler_name: Optional[str] = None,
    ) -> str:
        """Register a live query; returns a subscription id."""
        if not isinstance(query, QuerySpec):
            raise TypeError("bfs: query must be a QuerySpec")
        if not callable(callback):
            raise TypeError("bfs: callback must be callable")
        sub_id = "liveq-%d" % next(self._counter)
        self._subs[sub_id] = Subscription(
            sub_id=sub_id, spec=query, callback=callback, handler_name=handler_name
        )
        return sub_id

    def unsubscribe(self, sub_id: str) -> Subscription:
        """Remove a subscription; raises ValueError for unknown ids."""
        try:
            return self._subs.pop(sub_id)
        except KeyError:
            raise ValueError("bfs: no subscription %r" % sub_id)

    def subscriptions(self) -> List[Subscription]:
        return list(self._subs.values())

    def notify(self, entry: Any) -> List[str]:
        """Fan a new entry out to every matching subscriber.

        Returns the ids of the subscribers that were called. A callback
        that raises is recorded in ``errors()`` and never breaks delivery
        to the remaining subscribers.
        """
        called: List[str] = []
        for sub in list(self._subs.values()):
            try:
                if query_matches(sub.spec, entry):
                    try:
                        sub.callback(entry)
                    except Exception as exc:
                        self._errors.append(
                            {
                                "ts": datetime.now(timezone.utc).isoformat(),
                                "sub_id": sub.sub_id,
                                "error": "%s: %s" % (type(exc).__name__, exc),
                                "trace": traceback.format_exc(limit=5),
                            }
                        )
                    called.append(sub.sub_id)
            except Exception:
                # A pathological spec/entry pair must not stop the fan-out.
                continue
        return called

    def errors(self) -> List[Dict[str, Any]]:
        return list(self._errors)

    # -- durability ---------------------------------------------------------
    def save(self, path: Path) -> Path:
        """Persist subscription specs; callbacks re-arm via handler names."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": 1,
            "subscriptions": [
                {
                    "sub_id": s.sub_id,
                    "handler_name": s.handler_name,
                    "created_at": s.created_at,
                    "spec": s.spec.to_dict(),
                }
                for s in self._subs.values()
            ],
        }
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        tmp.replace(path)
        return path

    def load(self, path: Path) -> List[str]:
        """Re-arm durable subscriptions whose handlers are registered.

        Returns the re-armed subscription ids. Specs whose handler name
        is not registered are skipped (reported via ``load_warnings``).
        """
        path = Path(path)
        if not path.exists():
            return []
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("bfs: subscription file is not an object")
        self._warnings: List[str] = []
        rearmed: List[str] = []
        for item in raw.get("subscriptions", []):
            handler_name = item.get("handler_name")
            fn = _HANDLER_REGISTRY.get(handler_name) if handler_name else None
            if fn is None:
                self._warnings.append(
                    "bfs: subscription %r skipped; handler %r not registered"
                    % (item.get("sub_id"), handler_name)
                )
                continue
            spec = QuerySpec.from_dict(item.get("spec", {}))
            sub_id = "liveq-%d" % next(self._counter)
            self._subs[sub_id] = Subscription(
                sub_id=sub_id,
                spec=spec,
                callback=fn,
                handler_name=handler_name,
                created_at=item.get("created_at")
                or datetime.now(timezone.utc).isoformat(),
            )
            rearmed.append(sub_id)
        return rearmed

    def load_warnings(self) -> List[str]:
        return list(getattr(self, "_warnings", []))


# --------------------------------------------------------------------------
# LiveStore: MemoryStore wrapper with notifications
# --------------------------------------------------------------------------


class LiveStore:
    """Wraps a MemoryStore (or any object with ``add``) with live queries.

    ``store_entry`` persists through the inner store, then notifies every
    ``LiveQuery`` subscriber. Read-only wrapping: the memory module is
    never modified, only called.
    """

    def __init__(self, store: Any, queries: Optional[LiveQuery] = None):
        if store is None or not callable(getattr(store, "add", None)):
            raise TypeError("bfs: store must expose an add(...) method")
        self.store = store
        self.queries = queries if queries is not None else LiveQuery()

    @classmethod
    def from_default(
        cls, data_dir: Optional[Path] = None, queries: Optional[LiveQuery] = None
    ) -> "LiveStore":
        """Build a LiveStore around LEVI's real MemoryStore (lazy import)."""
        try:
            from levi.memory.store import MemoryStore  # lazy; honest degradation
        except ImportError as exc:
            raise RuntimeError(
                "bfs: levi.memory.store is unavailable (%s); "
                "pass an explicit store instead" % exc
            )
        store = MemoryStore(data_dir=data_dir) if data_dir else MemoryStore()
        return cls(store, queries=queries)

    def store_entry(self, memory_type: Any, content: str, **kwargs: Any) -> Any:
        """Persist via the inner store, then notify live subscribers.

        Returns the entry the inner store produced. If notification
        fails for a subscriber, the failure is recorded on the
        ``LiveQuery`` (see ``errors()``) and the persisted entry is
        still returned — persistence wins.
        """
        entry = self.store.add(memory_type, content, **kwargs)
        self.queries.notify(entry)
        return entry

    # Convenience passthroughs (read-only surface of the inner store).
    def get(self, entry_id: str) -> Any:
        return self.store.get(entry_id)

    def list(self, *args: Any, **kwargs: Any) -> Any:
        return self.store.list(*args, **kwargs)


__all__ = [
    "QuerySpec",
    "Subscription",
    "LiveQuery",
    "LiveStore",
    "register_handler",
    "get_handler",
    "query_matches",
    "entry_as_dict",
]
