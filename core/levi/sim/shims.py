"""Network shim for the bounty-hunt simulation.

Only the seven low-level network functions of the bounty pipeline are
redirected at a :class:`~levi.sim.world.SimWorld`:

* ``levi.bounty.enum``: ``_fetch_text`` (crt.sh), ``_resolve`` (DNS)
* ``levi.bounty.probe``: ``_tcp_open``, ``_http_get``, ``_tls_cert``
* ``levi.bounty.content``: ``wayback_urls``, ``_fetch_text`` (JS fetches)

The public stage functions (``enumerate_subdomains``, ``probe_host``,
``collect_content``), the ``run_recon`` orchestration, the scope gate and
the finding store all run byte-for-byte unmodified. Originals are
restored on exit even if the run raises (context-manager try/finally).
"""

from __future__ import annotations

from types import ModuleType
from typing import List, Tuple

from levi.bounty import content as content_mod
from levi.bounty import enum as enum_mod
from levi.bounty import probe as probe_mod
from levi.sim.world import SimWorld


class SimShim:
    """Patch the pipeline's low-level network functions with world-backed
    fakes for the duration of the ``with`` block."""

    _TARGETS: List[Tuple[ModuleType, str, str]] = [
        (enum_mod, "_fetch_text", "fetch_text"),
        (enum_mod, "_resolve", "resolve"),
        (probe_mod, "_tcp_open", "tcp_open"),
        (probe_mod, "_http_get", "http_get"),
        (probe_mod, "_tls_cert", "tls_cert"),
        (content_mod, "wayback_urls", "wayback"),
        (content_mod, "_fetch_text", "fetch_text"),
    ]

    def __init__(self, world: SimWorld):
        self._world = world
        self._saved: List[Tuple[ModuleType, str, object]] = []

    def __enter__(self) -> "SimShim":
        for mod, attr, meth in self._TARGETS:
            self._saved.append((mod, attr, getattr(mod, attr)))
            setattr(mod, attr, getattr(self._world, meth))
        return self

    def __exit__(self, *exc: object) -> bool:
        for mod, attr, original in reversed(self._saved):
            setattr(mod, attr, original)
        self._saved.clear()
        return False
