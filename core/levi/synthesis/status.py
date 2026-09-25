"""Vital signs: one honest dashboard for the organism.

``collect_status()`` checks each organ without disturbing it — import checks
and file checks, no writes, no network. Anything unverifiable is reported
as unverifiable, never guessed.
"""

from __future__ import annotations

import hashlib
import importlib.util
import os
from pathlib import Path
from typing import Any, Dict

ORIGIN = "levi-synthesis/status"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def brain_status(weights_path: Path) -> Dict[str, Any]:
    """Weights file presence, checksum, and torch availability — no torch import."""
    info: Dict[str, Any] = {
        "weights_path": str(weights_path),
        "weights_present": weights_path.is_file(),
        "sha256_match": None,
        "torch_available": importlib.util.find_spec("torch") is not None,
        "detail": "",
    }
    if not info["weights_present"]:
        info["detail"] = "no native-brain weights found — the mind runs rules-only"
        return info
    try:
        expected = None
        try:
            from levi.brain.inference import EXPECTED_SHA256

            expected = EXPECTED_SHA256
        except ImportError:
            pass
        digest = _sha256(weights_path)
        info["sha256_match"] = (digest == expected) if expected else None
        info["detail"] = (
            "weights present; sha256 "
            + (
                "matches the shipped checkpoint"
                if info["sha256_match"]
                else "UNVERIFIED"
            )
            + "; torch "
            + ("available" if info["torch_available"] else "NOT available")
        )
    except OSError as exc:
        info["detail"] = f"weights file unreadable: {exc.__class__.__name__}"
    return info


def _skills_status() -> Dict[str, Any]:
    try:
        from levi.skill.registry import SkillRegistry

        count = len(SkillRegistry().list())
        return {"registered": count, "detail": f"{count} skills registered"}
    except Exception as exc:  # noqa: BLE001 - the reason IS the report
        return {"registered": None, "detail": f"unverifiable: {exc.__class__.__name__}"}


def _growth_status() -> Dict[str, Any]:
    base = Path(os.environ.get("LEVI_GROWTH_DIR", Path.home() / ".levi" / "growth"))
    journal = base / "journal.jsonl"
    info: Dict[str, Any] = {
        "journal": str(journal),
        "journal_present": journal.is_file(),
        "records": None,
        "detail": "",
    }
    if journal.is_file():
        try:
            with open(journal, "rb") as fh:
                info["records"] = sum(1 for _ in fh)
            info["detail"] = f"{info['records']} journal records"
        except OSError:
            info["detail"] = "journal unreadable"
    else:
        info["detail"] = "no growth journal yet — the loop has not run here"
    return info


def _lwp_status() -> Dict[str, Any]:
    try:
        from levi.lwp.machine import ContentMachine  # noqa: F401

        return {
            "press_console": "available",
            "detail": "L.W.P. (Logan Wyrd Press) press console importable",
        }
    except Exception as exc:  # noqa: BLE001 - the reason IS the report
        return {
            "press_console": "unavailable",
            "detail": f"unverifiable: {exc.__class__.__name__}",
        }


def _finance_status() -> Dict[str, Any]:
    try:
        from levi.finance.broker import live_enabled

        live = bool(live_enabled())
        return {
            "mode": "live" if live else "paper-only",
            "live_enabled": live,
            "detail": "SIMULATED paper broker" if not live else "LIVE TRADING ENABLED",
        }
    except Exception as exc:  # noqa: BLE001 - the reason IS the report
        return {
            "mode": "unknown",
            "live_enabled": None,
            "detail": f"unverifiable: {exc.__class__.__name__}",
        }


def _daemon_status() -> Dict[str, Any]:
    kernel = Path.home() / ".levi" / "daemon_kernel.json"
    return {
        "kernel_file": str(kernel),
        "kernel_present": kernel.is_file(),
        "detail": "daemon kernel state present"
        if kernel.is_file()
        else "no daemon kernel state on this machine",
    }


def collect_status(config=None) -> Dict[str, Any]:
    """Check every organ; return the dashboard dict."""
    from levi.synthesis.config import SynthesisConfig

    cfg = config if config is not None else SynthesisConfig.load()
    return {
        "origin": ORIGIN,
        "brain_policy": cfg.brain_policy,
        "offline_enforced": cfg.offline_enforced,
        "config_file": str(cfg.config_file),
        "brain": brain_status(cfg.weights_path()),
        "skills": _skills_status(),
        "growth": _growth_status(),
        "lwp": _lwp_status(),
        "finance": _finance_status(),
        "daemon": _daemon_status(),
    }


def render_status(status: Dict[str, Any]) -> str:
    """Render the dashboard dict as human-readable text."""
    brain = status["brain"]
    lines = [
        "levi synthesis — vital signs (offline-first)",
        f"  brain policy : {status['brain_policy']}",
        f"  brain weights: {'present' if brain['weights_present'] else 'MISSING'}"
        f" — {brain['detail']}",
        f"  skills       : {status['skills']['detail']}",
        f"  growth       : {status['growth']['detail']}",
        f"  lwp press    : {status['lwp']['detail']}",
        f"  finance      : {status['finance']['detail']}",
        f"  daemon       : {status['daemon']['detail']}",
        f"  config       : {status['config_file']}",
    ]
    return "\n".join(lines)


__all__ = [
    "ORIGIN",
    "brain_status",
    "collect_status",
    "render_status",
]
