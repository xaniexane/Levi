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
from . import arxiv, github, hn, registry, rss, weather, webhook  # noqa: F401
from . import http as http  # noqa: F401 (stdlib HTTP helper)
from .arxiv import ArxivConnector  # noqa: F401
from .github import GitHubConnector  # noqa: F401
from .hn import HackerNewsConnector  # noqa: F401
from .rss import RssConnector  # noqa: F401
from .weather import WeatherConnector  # noqa: F401
from .webhook import WebhookConnector  # noqa: F401
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
from . import selfcaps  # noqa: F401 (local self-knowledge surface, not a Connector)
from .selfcaps import (  # noqa: F401
    SelfcapsError,
    all_modules,
    find_capability,
    list_capabilities,
    module_summary,
    render_index,
    render_module,
    who_provides,
)
