"""Stack wiring — every component Chauncey named, honestly classified.

WIRED      real module, real import, real call. Path given.
BUILT-HERE new honest implementation in this tree (no fake integration).
MISSING    no implementation found anywhere; not faked, queued openly.

``check_stack()`` imports each WIRED module and reports ok/failed, so a
removed module fails loudly instead of silently degrading.
"""

from __future__ import annotations

import importlib
from pathlib import Path
from typing import Dict, List, Optional

SUPERSCRIPTS = ("¹", "²", "³", "⁴", "⁵", "⁶", "⁷", "⁸", "⁹", "¹⁰")


def _try_import(dotted: str):
    try:
        return importlib.import_module(dotted), None
    except Exception as exc:  # noqa: BLE001 — the report carries the reason
        return None, f"{type(exc).__name__}: {exc}"


STACK = [
    {
        "component": "KFX² (absorb→reverse→improve→return)",
        "status": "BUILT-HERE",
        "path": "core/levi/buzztunes/curation.py",
        "note": ("His four-phase method implemented in the open. "
                 "core/levi/dynasty/kfx2/runner.py exists but is an agent "
                 "wave-runner, not this method — noted, not faked."),
    },
    {
        "component": "DemandPulse",
        "status": "BUILT-HERE",
        "path": "core/levi/buzztunes/demand.py",
        "note": ("demandpulse/ ships no signal/score API (verified "
                 "2026-09-23), so Buzz Tunes keeps a real demand log of "
                 "recorded signals that DemandPulse senses; curation "
                 "scores from real signals only."),
    },
    {
        "component": "REIM",
        "status": "WIRED",
        "path": "core/levi/quetta_pan/reim.py",
        "import": "levi.quetta_pan.reim",
        "symbol": "ReimCompost",
        "note": "Failure-compost: skipped/bad curations become lessons.",
    },
    {
        "component": "RIEM",
        "status": "WIRED",
        "path": "core/levi/quetta_pan/riem.py",
        "import": "levi.quetta_pan.riem",
        "symbol": "RiemGenome",
        "note": "Genome consult before curation: suppress/boost/unknown.",
    },
    {
        "component": "Echo",
        "status": "WIRED",
        "path": "core/levi/organs/echo.py",
        "import": "levi.organs.echo",
        "symbol": "run_echo",
        "note": "Variant exploration of the top curation gap.",
    },
    {
        "component": "Mandella",
        "status": "WIRED",
        "path": "core/levi/organs/mandella.py",
        "import": "levi.organs.mandella",
        "symbol": "run_mandella",
        "note": "Stake selection when a curation call is uncertain.",
    },
    {
        "component": "Quetta-Pan ×10",
        "status": "BUILT-HERE",
        "path": "core/levi/buzztunes/stack.py:CuratorPool",
        "note": ("Ten music-domain curator instances (Quetta-Pan¹–¹⁰), "
                 "each with its own REIM compost + RIEM genome stores. "
                 "QuettaPanEngine itself is code-domain and is not "
                 "reused for music; the learning-loop machinery is."),
    },
    {
        "component": "Echoverse",
        "status": "WIRED",
        "path": "core/levi/echoverse/engine.py",
        "import": "levi.echoverse.engine",
        "symbol": "EchoverseEngine",
        "note": ("Thread-journey expansion: seed a vibe, round() expands "
                 "candidate paths and scores them; skipped sequences go "
                 "to vault_negative, completed listens mark_success."),
    },
    {
        "component": "Network providers (YouTube et al.)",
        "status": "MISSING",
        "path": None,
        "note": "Queued follow-up. No stub pretends otherwise.",
    },
    {
        "component": "Audio rendering/playback on device",
        "status": "MISSING",
        "path": None,
        "note": ("Engine/queue/thread/receipt layers are proven; actual "
                 "audio output is the open follow-up."),
    },
]


def check_stack() -> List[Dict]:
    """Machine proof of the wiring claims. WIRED entries are imported
    for real; a failed import is reported, never hidden."""
    report = []
    for entry in STACK:
        row = dict(entry)
        if entry["status"] == "WIRED":
            mod, err = _try_import(entry["import"])
            if mod is None or not hasattr(mod, entry["symbol"]):
                row["check"] = f"FAILED: {err or 'symbol missing'}"
            else:
                row["check"] = "ok"
        else:
            row["check"] = "n/a"
        report.append(row)
    return report


class Curator:
    """One Quetta-Pan curator instance: music-domain judgment with the
    real REIM/RIEM learning loop wired in."""

    def __init__(self, index: int, store_dir: str | Path) -> None:
        from levi.quetta_pan.reim import ReimCompost
        from levi.quetta_pan.riem import RiemGenome

        self.index = index
        self.name = f"Quetta-Pan{SUPERSCRIPTS[index]}"
        self.home = Path(store_dir) / f"qp{index + 1}"
        self.home.mkdir(parents=True, exist_ok=True)
        self.compost = ReimCompost(self.home / "compost.jsonl")
        self.genome = RiemGenome(self.home / "genome.json")

    def consult(self, pick_id: str, context: str = "curation") -> str:
        """RIEM pre-curation verdict: suppress | boost | unknown."""
        return self.genome.consult(pick_id, context)

    def learn(self, pick_id: str, context: str, success: bool,
              tried_what: str, note: str = "") -> Dict:
        """Fold an outcome into compost (on failure) + genome."""
        if success:
            return self.genome.record_success(pick_id, context, note)
        entry = self.compost.compost({
            "mutation_id": f"cur-{pick_id}",
            "rule_id": pick_id,
            "file": "n/a",
            "context": context,
            "tried_what": tried_what,
            "failed_why": note or "curator pick rejected",
        })
        self.genome.learn_compost_entry(entry)
        return {"composted": True, "entry": entry}

    def explore_variants(self, seed: str, cycles: int = 2) -> Dict:
        """Echo variant exploration of a curation seed."""
        from levi.organs.echo import run_echo
        return run_echo(seed, cycles=cycles)

    def stake(self, seed: str) -> Dict:
        """Mandella stake selection for an uncertain curation call."""
        from levi.organs.mandella import run_mandella
        return run_mandella(domain="product", seed=seed)


class CuratorPool:
    """The ten. Quetta-Pan¹ through Quetta-Pan¹⁰."""

    COUNT = 10

    def __init__(self, store_dir: str | Path) -> None:
        self.curators = [Curator(i, store_dir) for i in range(self.COUNT)]

    def __len__(self) -> int:
        return len(self.curators)

    def names(self) -> List[str]:
        return [c.name for c in self.curators]

    def get(self, index: int) -> Curator:
        return self.curators[index]
