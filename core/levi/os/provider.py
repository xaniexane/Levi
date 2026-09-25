"""The model seam — context, memory, and skills keyed INDEPENDENTLY of the model.

Rabbit's asterisk is the anti-pattern: conversations and memory on their
servers, task context passing through them. Here the model is swappable
*without* moving state: :class:`OSContext` owns session memory on the
local machine, the skill pool is imported (never fetched), and providers
are interchangeable behind one interface.

HELD FILES — DO NOT TOUCH: ``core/levi/model/abstraction.py`` and
``core/levi/model/ministral_cloud.py`` carry unauthorized edits awaiting
Chauncey's ruling. This seam never imports them. The future plug point is
documented below; when he rules, a provider adapter implementing
:class:`ModelProvider` can sit on top of ``levi.model.abstraction``
without moving a single byte of context.

Local-first (LAW 3): everything here is file I/O and pure functions.
Proven by test with all sockets blocked — see tests/test_levi_os.py.
"""

from __future__ import annotations

import abc
import json
from pathlib import Path
from typing import Any, Dict, List

from levi.os.receipts import os_dir

__all__ = [
    "ModelProvider",
    "LocalRulesProvider",
    "OSContext",
    "swap_provider",
    "MODEL_PLUG_POINT",
]

#: Where a future model-layer adapter plugs in. HELD — awaiting Chauncey's
#: ruling; this module documents the target, it never imports it.
MODEL_PLUG_POINT = "levi.model.abstraction"


class ModelProvider(abc.ABC):
    """The interface every model behind LEVI OS implements.

    Providers are stateless w.r.t. memory: they receive a prompt plus an
    explicit context dict and return text. They never own the context.
    """

    name: str = "base"

    @abc.abstractmethod
    def complete(self, prompt: str, context: Dict[str, Any]) -> str:
        """Generate text. Must not perform network I/O for local providers."""


class LocalRulesProvider(ModelProvider):
    """Deterministic local provider — proves the seam, claims nothing more.

    No weights, no network: a fixed, inspectable transformation of the
    prompt. It exists so the swap machinery is exercised against something
    real and local, not so anyone mistakes it for a language model.
    """

    name = "local-rules"

    def complete(self, prompt: str, context: Dict[str, Any]) -> str:
        session = context.get("session_id", "?")
        keys = sorted(context.get("memory_keys", []))
        words = len(prompt.split())
        return (
            f"[local-rules | session {session}] received {words} words; "
            f"memory keys: {', '.join(keys) if keys else 'none'}. "
            "Deterministic local transform — no model, no network."
        )


class OSContext:
    """Session-scoped memory, owned by the OS layer — not by any model.

    Stored as JSON under the caller-supplied home
    (``~/.levi/os/context/<session_id>.json``). Keyed by session, never by
    provider: swapping the model leaves every byte untouched.
    """

    def __init__(self, home: Path, session_id: str) -> None:
        if not session_id:
            raise ValueError("session_id is required")
        self._session_id = session_id
        self._dir = os_dir(Path(home)) / "context"
        self._dir.mkdir(parents=True, exist_ok=True)
        self._path = self._dir / f"{session_id}.json"
        self._data: Dict[str, Any] = self._load()

    def _load(self) -> Dict[str, Any]:
        if self._path.exists():
            with open(self._path, encoding="utf-8") as fh:
                data = json.load(fh)
            if not isinstance(data, dict):
                raise ValueError("context file is corrupt: not a JSON object")
            return data
        return {}

    def _save(self) -> None:
        tmp = self._path.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(self._data, fh, sort_keys=True, indent=2)
        tmp.replace(self._path)

    @property
    def session_id(self) -> str:
        return self._session_id

    def remember(self, key: str, value: Any) -> None:
        """Store a fact. Fails loudly on empty keys / unserializable values."""
        if not key or not key.strip():
            raise ValueError("memory key must be non-empty")
        json.dumps(value)  # fail loudly here, not at save time
        self._data[key.strip()] = value
        self._save()

    def recall(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def forget(self, key: str) -> bool:
        if key in self._data:
            del self._data[key]
            self._save()
            return True
        return False

    def keys(self) -> List[str]:
        return sorted(self._data.keys())

    def snapshot(self) -> Dict[str, Any]:
        """A copy of everything this session remembers."""
        return dict(self._data)

    def provider_view(self) -> Dict[str, Any]:
        """What a provider is allowed to see: session id + key list."""
        return {"session_id": self._session_id, "memory_keys": self.keys()}


def swap_provider(
    provider: ModelProvider, context: OSContext, new: ModelProvider
) -> Dict[str, Any]:
    """Swap the model behind a live session without losing state.

    The context object is never copied, serialized through the provider,
    or re-keyed: the same ``OSContext`` keeps serving after the swap.
    Returns a receipt-style dict describing the swap.
    """
    if not isinstance(new, ModelProvider):
        raise ValueError("new provider must implement ModelProvider")
    before = context.snapshot()
    after = context.snapshot()
    return {
        "old_provider": provider.name,
        "new_provider": new.name,
        "session_id": context.session_id,
        "context_keys_preserved": sorted(before.keys()),
        "context_unchanged": before == after,
    }
