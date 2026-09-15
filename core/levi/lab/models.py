"""Model cards for the models LEVI actually supports.

These are the only models the lab talks about: if a model isn't here,
``levi lab card`` says so instead of inventing specs. Sizes for the GGUF
quants come from LEVI's own ``local_model.py`` registry; the tiny-gpt
numbers come from ``core/levi/brain/weights/README.md``.
"""

from __future__ import annotations

MODEL_CARDS: dict[str, dict] = {
    "qwen3-0.6b": {
        "name": "Qwen3 0.6B (GGUF)",
        "params": 600_000_000,
        "provider": "levi-local",
        "license": "Apache-2.0",
        "quants": {
            # From local_model.py MODEL_CHOICES: Q8_0 ~640MB pinned by sha256.
            "q8_0": {"size_gb": 0.64, "note": "default; pinned weights"},
            # int4/int8/fp16 are footprint-math estimates, not downloads.
            "int4": {"size_gb": 0.30, "note": "estimated from params × 0.5 B/param"},
            "int8": {"size_gb": 0.60, "note": "estimated from params × 1 B/param"},
            "fp16": {"size_gb": 1.20, "note": "estimated from params × 2 B/param"},
        },
        "ctx_tokens": 32768,
        "ctx_note": "32k default (LEVI_LOCAL_CTX_SIZE; clamped to GGUF metadata)",
        "ram_envelope_gb": "~1.5",
        "ram_note": "documented requirement: ~1.5 GB free RAM",
        "capabilities": (
            "Small, CPU-friendly. Good for short tool-use turns and the lab "
            "demos. Struggles with long reasoning chains and precise "
            "instruction-following at this size."
        ),
        "status": "supported",
        "get": "levi agent model pull   (then: levi agent chat --provider levi-local)",
    },
    "qwen3-4b": {
        "name": "Qwen3 4B (GGUF)",
        "params": 4_000_000_000,
        "provider": "levi-local",
        "license": "Apache-2.0",
        "quants": {
            # From local_model.py MODEL_CHOICES: Q4_K_M ~2.5GB pinned by sha256.
            "q4_k_m": {"size_gb": 2.5, "note": "default; pinned weights"},
            "int4": {"size_gb": 2.0, "note": "estimated from params × 0.5 B/param"},
            "int8": {"size_gb": 4.0, "note": "estimated from params × 1 B/param"},
            "fp16": {"size_gb": 8.0, "note": "estimated from params × 2 B/param"},
        },
        "ctx_tokens": 32768,
        "ctx_note": "32k default (LEVI_LOCAL_CTX_SIZE; clamped to GGUF metadata)",
        "ram_envelope_gb": "4–6",
        "ram_note": "documented requirement: ~4–6 GB free RAM",
        "capabilities": (
            "Noticeably stronger reasoning than the 0.6B. The practical "
            "on-device choice for real agentic work on a laptop. Still a "
            "small model: verify consequential outputs."
        ),
        "status": "supported",
        "get": "levi agent model pull --model qwen3-4b",
    },
    "tiny-gpt": {
        "name": "tiny-gpt.pt — LEVI native-brain proof",
        "params": 3_271_168,
        "provider": "levi-brain",
        "license": "LEVI project (trained in-repo)",
        "quants": {
            "fp32": {"size_gb": 0.0134, "note": "actual checkpoint size on disk"},
        },
        "ctx_tokens": 128,
        "ctx_note": "block size 128 chars (character-level model)",
        "ram_envelope_gb": "~0.1",
        "ram_note": "trivially small; loads anywhere torch runs",
        "capabilities": (
            "Training-pipeline proof, NOT a usable brain. Loss 5.2830 → "
            "2.1067 over 600 steps on the course corpus, but samples are "
            "garbled character soup. It cannot reason, converse, or replace "
            "levi-local. Included so the lab is honest about what 'trained "
            "from scratch' currently means."
        ),
        "status": "experimental",
        "get": "ships in-repo at core/levi/brain/weights/tiny-gpt.pt (gitignored binary; see README)",
    },
}


def get_card(model: str) -> dict | None:
    """Return the card for a model key, or None when LEVI doesn't support it."""
    return MODEL_CARDS.get(model.strip().lower())


def format_card(key: str, card: dict) -> str:
    """Human-readable rendering of a model card."""
    lines = [
        f"══ {card['name']} ══",
        f"  key      : {key}",
        f"  params   : {card['params']:,}",
        f"  provider : {card['provider']}  [{card['status']}]",
        f"  license  : {card['license']}",
        f"  context  : {card['ctx_tokens']:,} tokens — {card['ctx_note']}",
        f"  RAM      : {card['ram_envelope_gb']} GB — {card['ram_note']}",
        "  quants   :",
    ]
    for q, info in card["quants"].items():
        lines.append(f"    {q:8s} {info['size_gb']:>7} GB — {info['note']}")
    lines.append(f"  honest   : {card['capabilities']}")
    lines.append(f"  get      : {card['get']}")
    return "\n".join(lines)
