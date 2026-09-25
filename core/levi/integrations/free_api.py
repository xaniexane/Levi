"""Free-API catalog — the zero-paid-key *public web-API* registry.

The original hunt finding was a "Free-API catalog (zero-paid-key
registry)" of **public web APIs**. ``free_lattice.py`` catalogs LEVI's
own engines/integrations (free-first by construction) — a different
thing. This module is the other half: third-party web APIs you can call
with no paid key, so LEVI features can reach the outside world without
a billing relationship.

Honest contract (the covenant pattern: numbers, not adjectives)
--------------------------------------------------------------
Every entry declares, in plain fields:

- ``auth``: ``"none"`` (no key at all) or ``"free-key"`` (free signup,
  no card).
- ``free_limits``: the documented free tier in plain numbers.
- ``confidence``: ``"verified"`` (we called it and it answered) or
  ``"hearsay"`` (documented publicly, not yet called from here).
  Hearsay entries are usable as leads, never as guarantees.

LAWS
----
1. **No paid keys, ever.** An entry whose free tier needs a credit card
   does not belong here.
2. **Confidence is labeled.** Nothing here claims a live verification
   it does not have.
3. **Deterministic queries.** ``by_category`` / ``by_auth`` / ``get``
   are pure functions over the static registry.

stdlib-only, local-first. The registry describes APIs; it never calls
them (calling is the caller's job, with their own consent).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

__all__ = [
    "FreeAPI",
    "REGISTRY",
    "get",
    "by_category",
    "by_auth",
    "categories",
    "validate",
]


@dataclass(frozen=True)
class FreeAPI:
    """One zero-paid-key public web API."""

    id: str
    name: str
    category: str  # weather | geo | reference | testing | fun | finance | books
    base_url: str
    auth: str  # "none" | "free-key"
    free_limits: str  # the documented free tier, in plain numbers
    notes: str
    confidence: str = "hearsay"  # "verified" | "hearsay"

    def __post_init__(self) -> None:
        if self.auth not in ("none", "free-key"):
            raise ValueError(f"auth must be none|free-key, got {self.auth!r}")
        if self.confidence not in ("verified", "hearsay"):
            raise ValueError(
                f"confidence must be verified|hearsay, got {self.confidence!r}"
            )
        for fname in ("id", "name", "category", "base_url", "free_limits"):
            if not str(getattr(self, fname)).strip():
                raise ValueError(f"{fname} is required")


REGISTRY: Tuple[FreeAPI, ...] = (
    FreeAPI(
        "open-meteo",
        "Open-Meteo",
        "weather",
        "https://api.open-meteo.com/v1/forecast",
        "none",
        "10,000 calls/day, no key, commercial use allowed",
        "Forecast + historical weather, JSON. The rare no-key weather API.",
    ),
    FreeAPI(
        "rest-countries",
        "REST Countries",
        "geo",
        "https://restcountries.com/v3.1",
        "none",
        "no key, community fair-use limits",
        "Country data: name, capital, currencies, borders, flags.",
    ),
    FreeAPI(
        "jsonplaceholder",
        "JSONPlaceholder",
        "testing",
        "https://jsonplaceholder.typicode.com",
        "none",
        "no key, fake data for prototyping only",
        "Free fake REST API (posts/users/todos). For tests and demos.",
    ),
    FreeAPI(
        "httpbin",
        "httpbin",
        "testing",
        "https://httpbin.org",
        "none",
        "no key, community-run",
        "HTTP request/response testing service. Echoes what you send.",
    ),
    FreeAPI(
        "openlibrary",
        "Open Library",
        "books",
        "https://openlibrary.org",
        "none",
        "no key, rate-limited (be polite: ~100 req/5min observed)",
        "Book metadata + covers + search. Internet Archive project.",
    ),
    FreeAPI(
        "deckofcards",
        "Deck of Cards API",
        "fun",
        "https://deckofcardsapi.com/api/deck",
        "none",
        "no key, casual use",
        "Shuffled decks, draw, piles — a card-game backend as a service.",
    ),
    FreeAPI(
        "pokeapi",
        "PokeAPI",
        "fun",
        "https://pokeapi.co/api/v2",
        "none",
        "no key, fair-use (cache aggressively)",
        "Pokemon data. Community-run, explicitly free.",
    ),
    FreeAPI(
        "coingecko",
        "CoinGecko",
        "finance",
        "https://api.coingecko.com/api/v3",
        "none",
        "no key: ~5-15 calls/min (Demo tier); higher needs a free key",
        "Crypto prices/market data. No-key tier is thin but real.",
    ),
    FreeAPI(
        "quotable",
        "Quotable",
        "reference",
        "https://api.quotable.io",
        "none",
        "no key (service status has varied; treat as hearsay)",
        "Random/tagged quotes. Availability has been unstable — verify.",
    ),
    FreeAPI(
        "cocktaildb",
        "TheCocktailDB",
        "reference",
        "https://www.thecocktaildb.com/api/json/v1/1",
        "none",
        "no key on the test key '1'; production key is free signup",
        "Cocktail recipes by name/ingredient. Test key works keyless.",
    ),
)


def _index() -> Dict[str, FreeAPI]:
    return {api.id: api for api in REGISTRY}


def get(api_id: str) -> FreeAPI:
    """Return one API by id. KeyError on unknown ids — never guessed."""
    try:
        return _index()[api_id]
    except KeyError:
        raise KeyError(f"unknown free API {api_id!r}") from None


def by_category(category: str) -> List[FreeAPI]:
    """All APIs in a category, in registry order."""
    return [a for a in REGISTRY if a.category == category]


def by_auth(auth: str) -> List[FreeAPI]:
    """All APIs with an auth model — ``"none"`` or ``"free-key"``."""
    if auth not in ("none", "free-key"):
        raise ValueError(f"auth must be none|free-key, got {auth!r}")
    return [a for a in REGISTRY if a.auth == auth]


def categories() -> List[str]:
    """Category names in first-seen order."""
    seen: List[str] = []
    for api in REGISTRY:
        if api.category not in seen:
            seen.append(api.category)
    return seen


def validate() -> List[str]:
    """Check the registry's own laws. Returns a list of violations (empty = clean).

    - unique ids
    - no paid-key entries (auth in none|free-key is enforced by the dataclass)
    - confidence labeled on every entry
    - base_url looks like an https URL
    """
    problems: List[str] = []
    ids = [a.id for a in REGISTRY]
    if len(set(ids)) != len(ids):
        problems.append("duplicate api ids")
    for api in REGISTRY:
        if not api.base_url.startswith("https://"):
            problems.append(f"{api.id}: base_url is not https")
        if api.confidence not in ("verified", "hearsay"):
            problems.append(f"{api.id}: confidence unlabeled")
        if "credit card" in api.free_limits.lower():
            problems.append(f"{api.id}: free tier mentions a credit card")
    return problems


def keyless() -> List[FreeAPI]:
    """Convenience: every API callable with literally no key."""
    return by_auth("none")
