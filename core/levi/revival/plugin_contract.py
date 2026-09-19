"""plugin_contract — an open plugin contract as the capability engine.

Studied from: desktop-casualties-20260916/report.md (2. Winamp: open
plugin architecture — visualizations, equalizers, new formats).

The load-bearing idea: the host defines a small, stable contract
(kinds of slots, lifecycle hooks, an API version) and the community
supplies everything else. Capability arrives from the edges; the
core stays tiny because the contract does the extending.

LEVI's take: ``PluginHost`` manages ``Plugin`` descriptors in typed
slots (``source``, ``filter``, ``renderer``). Registration validates
the API version; lifecycle runs ``on_load``/``on_unload`` hooks in
dependency order; ``dispatch`` fans a payload through every filter
in a slot. Plugins are plain Python objects the caller constructs —
this module defines the contract, not a loader. This is an original,
from-scratch implementation for LEVI.

Honest limits: plugin code runs in-process with full trust — there
is no sandbox and no signature check. API mismatch raises instead
of degrading silently.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

ORIGIN = "levi-revival/plugin-contract"

CONTRACT_API = "levi-plugin/1"  # what this host accepts

VALID_KINDS = ("source", "filter", "renderer")

Hook = Callable[["Plugin", "PluginHost"], None]


@dataclass
class Plugin:
    """One plugin, as seen by the contract."""

    name: str
    kind: str  # one of VALID_KINDS
    api: str = CONTRACT_API
    version: str = "0.1.0"
    requires: List[str] = field(default_factory=list)  # other plugin names
    on_load: Optional[Hook] = None
    on_unload: Optional[Hook] = None
    handle: Optional[Callable[[Any], Any]] = None  # the plugin's work


class ContractError(Exception):
    """A plugin broke the contract."""


class PluginHost:
    """Hosts plugins behind a stable, versioned contract."""

    def __init__(self) -> None:
        self._plugins: Dict[str, Plugin] = {}
        self._load_order: List[str] = []

    # -- registration -------------------------------------------------
    def register(self, plugin: Plugin) -> None:
        if plugin.api != CONTRACT_API:
            raise ContractError(
                f"{plugin.name}: api {plugin.api!r} not accepted "
                f"(host wants {CONTRACT_API!r})"
            )
        if plugin.kind not in VALID_KINDS:
            raise ContractError(f"{plugin.name}: unknown kind {plugin.kind!r}")
        if not plugin.name.strip():
            raise ContractError("plugin name must be non-empty")
        if plugin.name in self._plugins:
            raise ContractError(f"plugin {plugin.name!r} already registered")
        for dep in plugin.requires:
            if dep == plugin.name:
                raise ContractError(f"{plugin.name}: cannot require itself")
        self._plugins[plugin.name] = plugin

    def unregister(self, name: str) -> Plugin:
        plugin = self._plugins.get(name)
        if plugin is None:
            raise KeyError(f"no plugin {name!r}")
        dependents = [p.name for p in self._plugins.values() if name in p.requires]
        if dependents:
            raise ContractError(
                f"cannot unload {name!r}: still required by {dependents}"
            )
        del self._plugins[name]
        if plugin.on_unload is not None:
            plugin.on_unload(plugin, self)
        if name in self._load_order:
            self._load_order.remove(name)
        return plugin

    # -- lifecycle ----------------------------------------------------
    def load_all(self) -> List[str]:
        """Run on_load hooks in dependency order; returns load order."""
        order = self._topo_order()
        for name in order:
            if name not in self._load_order:
                plugin = self._plugins[name]
                if plugin.on_load is not None:
                    plugin.on_load(plugin, self)
                self._load_order.append(name)
        return list(self._load_order)

    def _topo_order(self) -> List[str]:
        order: List[str] = []
        visiting: List[str] = []

        def visit(name: str) -> None:
            if name in order:
                return
            if name in visiting:
                raise ContractError(f"circular dependency at {name!r}")
            if name not in self._plugins:
                raise ContractError(f"missing dependency {name!r}")
            visiting.append(name)
            for dep in self._plugins[name].requires:
                visit(dep)
            visiting.pop()
            order.append(name)

        for name in sorted(self._plugins):
            visit(name)
        return order

    # -- capability fan-out -------------------------------------------
    def dispatch(self, kind: str, payload: Any) -> List[Any]:
        """Pass a payload through every loaded plugin of a kind, in order."""
        if kind not in VALID_KINDS:
            raise ContractError(f"unknown kind {kind!r}")
        results: List[Any] = []
        for name in self._load_order:
            plugin = self._plugins[name]
            if plugin.kind == kind and plugin.handle is not None:
                results.append(plugin.handle(payload))
        return results

    def inventory(self) -> List[Dict[str, object]]:
        return [
            {
                "name": p.name,
                "kind": p.kind,
                "version": p.version,
                "requires": list(p.requires),
                "loaded": p.name in self._load_order,
            }
            for p in (self._plugins[n] for n in sorted(self._plugins))
        ]


def demo() -> Dict[str, object]:
    """Register a source + two filters, load, and dispatch a payload."""
    host = PluginHost()
    calls: List[str] = []
    host.register(
        Plugin(
            name="upper",
            kind="filter",
            handle=lambda s: str(s).upper(),
            on_load=lambda p, h: calls.append(f"load:{p.name}"),
        )
    )
    host.register(
        Plugin(
            name="bang",
            kind="filter",
            requires=["upper"],
            handle=lambda s: f"{s}!",
        )
    )
    order = host.load_all()
    return {
        "load_order": order,
        "load_calls": calls,
        "dispatch": host.dispatch("filter", "hello"),
        "inventory": host.inventory(),
    }
