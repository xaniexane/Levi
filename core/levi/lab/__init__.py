"""LEVI Lab — an interactive lab for on-device agentic AI.

Clean-room original. The *concept* (a hands-on lab showing what a small
on-device model can do agentically) is inspired by public lab repos; every
line of code, every scenario, and every fixture here is written from
scratch against LEVI's own agentic loop.

Modules:
    footprint — memory-envelope math (params × quant + KV cache + headroom)
    models    — model cards for the models LEVI actually supports
    scenarios — 4 demo scenarios with real captured transcripts
    live      — optional chat against any OpenAI-compatible endpoint
"""

from levi.lab.footprint import (
    BYTES_PER_PARAM,
    TYPICAL_ARCH,
    footprint,
    format_footprint,
    kv_cache_bytes,
    parse_ctx,
    parse_params,
    weight_bytes,
)
from levi.lab.models import MODEL_CARDS, get_card
from levi.lab.scenarios import SCENARIOS, get_scenario, playback

__all__ = [
    "BYTES_PER_PARAM",
    "TYPICAL_ARCH",
    "MODEL_CARDS",
    "SCENARIOS",
    "footprint",
    "format_footprint",
    "get_card",
    "get_scenario",
    "kv_cache_bytes",
    "parse_ctx",
    "parse_params",
    "playback",
    "weight_bytes",
]
