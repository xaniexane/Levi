"""SOXI pattern — LEVI's offline-first intelligence classification.

Canon (Chauncey, 2026-09-19/20): SOXI is what LEVI *is classified as* —
Levi's synthetic offline-first half x XI's class half — not a separate
product, module, or legion member. These twelve classes are the internal
pattern LEVI instantiates: small local intelligences, each a different
*nature* of learning, routed by LN. No network required at runtime.

Every class here runs on stdlib Python + SQLite unless noted. The one
exception is BT, which shells to a local model runner (Ollama / llama.cpp)
only if one is installed — never to a cloud API.
"""

from .ln_router import LoomRouter, CLASS_SPECS

__all__ = ["LoomRouter", "CLASS_SPECS"]
