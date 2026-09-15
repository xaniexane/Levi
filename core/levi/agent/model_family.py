"""The LEVI model family — LEVI is the model; everything else is a selectable source.

This module is the single registry of LEVI-first weights. It seeds ONLY
what is real:

* ``levi-tiny`` — LEVI's own native brain: a transformer trained from
  scratch on LEVI's own corpus. Weights live at
  ``core/levi/brain/weights/tiny-gpt.pt`` (``LEVI_BRAIN_WEIGHTS``
  overrides). Genuinely LEVI's: LEVI architecture, LEVI data.
* ``levi-0.6b`` / ``levi-4b`` — "Levi remixes": Qwen3-based GGUF bases,
  packaged by LEVI (downloaded with ``levi agent model pull``, run by
  LEVI's own local runner). Each entry records its base honestly
  (``base: qwen3-0.6b``) — a remix is LEVI-packaged, not LEVI-trained.

Future remixes are supported structurally via :func:`register_remix`
(name, base, version, notes) and documented in ``docs/MODELS.md``. Do
not seed entries for weights that do not exist.

Stdlib only. No imports from ``levi.agent`` at module top level (this
module is imported by ``providers.py``); heavier modules are imported
lazily inside functions.
"""

from __future__ import annotations

import json
import os
from pathlib import Path


# ---------------------------------------------------------------------------
# Registry — seed ONLY real weights
# ---------------------------------------------------------------------------

# Each entry: name, kind ("native" | "remix"), and for remixes the key
# into levi.agent.local_model.MODELS plus honest base attribution.
_FAMILY: list[dict] = [
    {
        "name": "levi-tiny",
        "kind": "native",
        "base": None,
        "packaged_by": "levi",
        "version": "tiny-gpt/1",
        "approx_bytes": 13_000_000,
        "ram_note": "Runs anywhere torch runs; CPU-friendly (~13MB weights).",
        "blurb": (
            "LEVI's own native brain — trained from scratch on LEVI's own "
            "corpus. No LLaMA weights, no llama.cpp."
        ),
        "capability": (
            "Prose continuations with corpus flavor; does NOT emit tool "
            "calls (the tool loop treats its answer as final). Quality "
            "today is fluent-ish gibberish — see docs/BRAIN_TRAINING.md. "
            "It earns the loop's default slot by growing, not by branding."
        ),
    },
    {
        "name": "levi-0.6b",
        "kind": "remix",
        "base": "qwen3-0.6b",
        "packaged_by": "levi",
        "version": "qwen3-0.6b-q8_0/levi-pack-1",
        "local_key": "qwen3-0.6b",
        "approx_bytes": 639_446_688,
        "ram_note": "Runs on ~1.5 GB free RAM. The default remix: fast, tiny, always fits.",
        "blurb": (
            "Levi remix of Qwen3-0.6B (Q8_0 quant, Apache-2.0). LEVI-"
            "packaged: downloaded and served by LEVI's own runner."
        ),
        "capability": (
            "Runs the agent loop's tools offline via native tool-call "
            "support. Small-model judgment — good for simple plans, "
            "shaky on long multi-step reasoning."
        ),
    },
    {
        "name": "levi-4b",
        "kind": "remix",
        "base": "qwen3-4b",
        "packaged_by": "levi",
        "version": "qwen3-4b-q4_k_m/levi-pack-1",
        "local_key": "qwen3-4b",
        "approx_bytes": 2_497_280_256,
        "ram_note": "Needs ~4-6 GB of free RAM (weights ~2.5GB plus the 32k-context KV cache).",
        "blurb": (
            "Levi remix of Qwen3-4B (Q4_K_M quant, Apache-2.0). LEVI-"
            "packaged: downloaded and served by LEVI's own runner."
        ),
        "capability": (
            "Smarter than the 0.6B remix at multi-step tool plans; still "
            "CPU-runnable. Noticeably slower per token on CPU."
        ),
    },
]


def family_names() -> list[str]:
    """Names of the LEVI family, in preference order."""
    return [e["name"] for e in _FAMILY]


def get_entry(name: str) -> dict | None:
    """Return the registry entry for ``name``, or None."""
    for e in _FAMILY:
        if e["name"] == name:
            return e
    return None


def register_remix(name: str, *, base: str, version: str,
                   local_key: str, notes: str = "",
                   approx_bytes: int = 0, ram_note: str = "",
                   blurb: str = "", capability: str = "") -> dict:
    """Register a future Levi remix structurally.

    ``local_key`` must already exist in ``levi.agent.local_model.MODELS``
    (the download spec); ``name`` must be new and look like
    ``levi-<something>``. This is the runtime hook — to ship a remix
    permanently, add it to ``_FAMILY`` above and document it in
    ``docs/MODELS.md``. Never register weights that do not exist.
    """
    from levi.agent import local_model

    if not name.startswith("levi-") or name in family_names():
        raise ValueError("remix name must be a new 'levi-*' name, got %r" % name)
    if local_key not in local_model.MODELS:
        raise ValueError(
            "unknown local_model key %r (known: %s)"
            % (local_key, ", ".join(sorted(local_model.MODELS)))
        )
    entry = {
        "name": name,
        "kind": "remix",
        "base": base,
        "packaged_by": "levi",
        "version": version,
        "local_key": local_key,
        "approx_bytes": approx_bytes,
        "ram_note": ram_note,
        "blurb": blurb or "Levi remix of %s, packaged by LEVI." % base,
        "capability": capability,
        "notes": notes,
    }
    _FAMILY.append(entry)
    return entry


# ---------------------------------------------------------------------------
# Live status — what is actually on disk right now
# ---------------------------------------------------------------------------


def _tiny_status() -> dict:
    from levi.agent import brain_provider

    weights = brain_provider.weights_path()
    present = weights.is_file()
    return {
        "downloaded": present and brain_provider.torch_available(),
        "weights_present": present,
        "torch_available": brain_provider.torch_available(),
        "detail": str(weights),
    }


def _remix_status(entry: dict) -> dict:
    from levi.agent import local_model

    spec = local_model.MODELS[entry["local_key"]]
    weights = local_model.model_dir() / spec["file"]
    present = weights.is_file()
    return {
        "downloaded": present,
        "weights_present": present,
        "runner_present": local_model.find_runner() is not None,
        "detail": str(weights),
    }


def status(name: str) -> dict:
    """Live status for one family member. Raises KeyError on unknown name."""
    entry = get_entry(name)
    if entry is None:
        raise KeyError("unknown LEVI family member %r" % name)
    live = _tiny_status() if entry["kind"] == "native" else _remix_status(entry)
    return {"name": name, "kind": entry["kind"], **live}


def entries() -> list[dict]:
    """Family entries with live status attached, in preference order."""
    out = []
    for e in _FAMILY:
        info = dict(e)
        info["status"] = _tiny_status() if e["kind"] == "native" else _remix_status(e)
        out.append(info)
    return out


# ---------------------------------------------------------------------------
# Persisted choice — `levi agent model use <name>`
# ---------------------------------------------------------------------------


def choice_path() -> Path:
    return Path.home() / ".levi" / "agent" / "model_choice.json"


def get_choice() -> str | None:
    """The persisted model choice, or None. Never raises."""
    try:
        data = json.loads(choice_path().read_text(encoding="utf-8"))
        name = data.get("model")
        return name if isinstance(name, str) and get_entry(name) else None
    except Exception:
        return None


def set_choice(name: str) -> str:
    """Persist the model choice. Raises ValueError on unknown name."""
    if get_entry(name) is None:
        raise ValueError(
            "unknown LEVI family member %r (known: %s)"
            % (name, ", ".join(family_names()))
        )
    path = choice_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps({"model": name}, indent=2), encoding="utf-8")
    os.replace(tmp, path)
    return name


def clear_choice() -> None:
    """Forget the persisted choice. Never raises."""
    try:
        choice_path().unlink()
    except OSError:
        pass


# ---------------------------------------------------------------------------
# Default resolution — best available LEVI weight
# ---------------------------------------------------------------------------


def _runner_available() -> bool:
    from levi.agent import local_model

    return local_model.find_runner() is not None


def resolve_family() -> dict | None:
    """Pick the best available LEVI family weight.

    Order: persisted ``model use`` choice (when actually downloaded) →
    ``levi-tiny`` native brain (weights present and torch importable) →
    the largest downloaded remix whose runner is present → None (the
    caller falls back to the deterministic rules planner).

    Returns ``{"entry": name, "provider": provider_name, "reason": str}``
    or None. Never raises, never spawns anything.
    """
    choice = get_choice()
    if choice:
        try:
            st = status(choice)
        except KeyError:
            st = None
        if st and st["downloaded"]:
            if st["kind"] == "remix" and not st["runner_present"]:
                pass  # downloaded but unrunnable — keep looking
            else:
                provider = "levi-brain" if st["kind"] == "native" else "levi-local"
                return {
                    "entry": choice,
                    "provider": provider,
                    "reason": "persisted choice (`levi agent model use %s`)" % choice,
                }

    try:
        tiny = status("levi-tiny")
    except KeyError:
        tiny = None
    if tiny and tiny["downloaded"]:
        return {
            "entry": "levi-tiny",
            "provider": "levi-brain",
            "reason": "native brain weights present",
        }

    if _runner_available():
        downloaded = [
            e for e in entries()
            if e["kind"] == "remix" and e["status"]["weights_present"]
        ]
        if downloaded:
            # Biggest downloaded remix first: more parameters, better plans.
            downloaded.sort(key=lambda e: e["approx_bytes"], reverse=True)
            best = downloaded[0]
            return {
                "entry": best["name"],
                "provider": "levi-local",
                "reason": "downloaded remix (%s)" % best["name"],
            }
    return None


def gguf_file_for(entry_name: str) -> str | None:
    """The GGUF file name for a remix entry (for ``LEVI_LOCAL_MODEL``)."""
    from levi.agent import local_model

    entry = get_entry(entry_name)
    if entry is None or entry["kind"] != "remix":
        return None
    return local_model.MODELS[entry["local_key"]]["file"]
