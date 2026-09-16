"""Plugin connectors for external services (blueprint §3).

Every connector is a :class:`registry.Connector` that declares the env var
holding its credential and the capabilities it exposes. ``execute()`` is
honest by construction:

* no credential found → says exactly what is missing and sends nothing;
* credential found but no transport wired → says that plainly too;
* never simulates success — an :class:`registry.ExecutionResult` with
  ``ok=False`` is returned instead of pretending a request went out.

Connectors capable of writing to a third-party account or moving money
default to ``requires_confirmation=True`` with no per-feature override
(blueprint §1.5); the registry enforces this at class-definition time.
"""

from __future__ import annotations
from . import github, registry  # noqa: F401
from . import http as http  # noqa: F401 (stdlib HTTP helper)
from .github import GitHubConnector  # noqa: F401
from .http import (  # noqa: F401
    ApiError,
    HttpClient,
    NetworkError,
    ResponseParseError,
    parse_url_host,
)
from .registry import (  # noqa: F401
    Capability,
    Connector,
    ExecutionResult,
    Operation,
    TransportNotWired,
    get_connector,
    list_connectors,
    register_connector,
)
