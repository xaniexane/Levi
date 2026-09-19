"""Twin shells — 6 shells as 3 FG/BG twin pairs.

Each shell twin mirrors one interactive shell: working directory, recent
commands (bounded), running jobs, and environment markers. Shells report
in through a tiny hook (see :func:`hook_script`) that writes drop files;
``levi twins collect`` ingests the drops into the lattice.

Pairing: slots (0,1), (2,3), (4,5). Even slot = FG, odd slot = BG.
"""

from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, List, Optional

from levi.twins.lattice import TwinLattice
from levi.twins.twin import Twin

#: The fleet is six shells. Not five, not seven. Six.
SHELL_SLOTS = 6

#: Twin pairs: (fg_slot, bg_slot).
SHELL_PAIRS = ((0, 1), (2, 3), (4, 5))

#: Bounded command history kept per shell twin.
HISTORY_KEEP = 20


def _slot_subject(slot: int) -> str:
    return f"shell-{slot}"


def ensure_shell_twins(lattice: TwinLattice) -> Dict[int, Twin]:
    """Create all six shell twins as three FG/BG pairs. Idempotent.

    Slot pairing: (0,1), (2,3), (4,5). Even slot holds the FG role,
    odd slot the BG role. Returns {slot: twin}.
    """
    out: Dict[int, Twin] = {}
    for fg_slot, bg_slot in SHELL_PAIRS:
        for slot, side in ((fg_slot, "fg"), (bg_slot, "bg")):
            pair_slot = bg_slot if side == "fg" else fg_slot
            pair_side = "bg" if side == "fg" else "fg"
            twin_id = f"shell:{_slot_subject(slot)}:{side}"
            tw = lattice.get(twin_id)
            if tw is None:
                tw = lattice.register(
                    "shell",
                    _slot_subject(slot),
                    side,
                    state={"cwd": "", "history": [], "jobs": [], "slot": slot},
                    notes=f"twin pair with slot {pair_slot}",
                    pair_id=f"shell:{_slot_subject(pair_slot)}:{pair_side}",
                )
            out[slot] = tw
    return out


def check_shell_failover(
    lattice: TwinLattice,
    fg_slot: int,
    threshold_s: float = 300.0,
) -> Optional[Dict[str, Any]]:
    """If the FG holder of a pair is silent and its BG is alive, promote."""
    if not any(fg_slot in p for p in SHELL_PAIRS):
        raise ValueError(f"slot must be 0..{SHELL_SLOTS - 1}")
    fg_id = f"shell:{_slot_subject(fg_slot)}:fg"
    fg = lattice.get(fg_id)
    if fg is None or fg.side != "fg":
        return None
    bg = lattice.get(fg.pair_id)
    if bg is None or bg.side != "bg":
        return None
    now = time.time()
    if fg.is_stale(threshold_s, now) and not bg.is_stale(threshold_s, now):
        event = lattice.promote(bg.twin_id, threshold_s)
        moved = lattice.get(fg_id)
        if moved is not None:
            moved.state["slot"] = fg_slot
        return event
    return None


def shell_report(
    lattice: TwinLattice,
    slot: int,
    cwd: str = "",
    last_cmd: str = "",
    jobs: Optional[List[str]] = None,
) -> Twin:
    """Heartbeat one shell slot with fresh state."""
    if not 0 <= slot < SHELL_SLOTS:
        raise ValueError(f"slot must be 0..{SHELL_SLOTS - 1}")
    side = "fg" if slot % 2 == 0 else "bg"
    twin_id = f"shell:{_slot_subject(slot)}:{side}"
    tw = lattice.get(twin_id)
    if tw is None:
        ensure_shell_twins(lattice)
        tw = lattice.get(twin_id)
        assert tw is not None
    update: Dict[str, Any] = {}
    if cwd:
        update["cwd"] = cwd
    if jobs is not None:
        update["jobs"] = jobs
    lattice.heartbeat(twin_id, update or None)
    tw = lattice.get(twin_id)
    assert tw is not None
    if last_cmd:
        hist = list(tw.state.get("history", []))
        hist.append(last_cmd)
        tw.state["history"] = hist[-HISTORY_KEEP:]
    return tw


def drops_dir(lattice: TwinLattice) -> str:
    path = os.path.join(lattice.home, "drops")
    os.makedirs(path, exist_ok=True)
    return path


def collect_drops(lattice: TwinLattice) -> int:
    """Ingest shell hook drop files into the lattice. Returns count.

    Handles both fleet drops (``shell-<slot>.json``) and outward-expansion
    drops (``ext-<id>.json``).
    """
    d = drops_dir(lattice)
    n = 0
    for name in sorted(os.listdir(d)):
        if not name.endswith(".json"):
            continue
        path = os.path.join(d, name)
        try:
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            if name.startswith("shell-"):
                slot = int(data.get("slot", -1))
                shell_report(
                    lattice,
                    slot,
                    cwd=str(data.get("cwd", "")),
                    last_cmd=str(data.get("last_cmd", "")),
                    jobs=list(data.get("jobs", []) or []),
                )
            elif name.startswith("ext-"):
                ext_id = str(data.get("ext_id", "") or "")
                if not ext_id:
                    continue
                shell_report_external(
                    lattice,
                    ext_id,
                    cwd=str(data.get("cwd", "")),
                    last_cmd=str(data.get("last_cmd", "")),
                    jobs=list(data.get("jobs", []) or []),
                )
            else:
                continue
            n += 1
        except (ValueError, OSError, KeyError, TypeError):
            continue
        finally:
            try:
                os.remove(path)
            except OSError:
                pass
    return n


def hook_script(slot: int) -> str:
    """Bash hook: source in a shell to mirror it into slot N.

    Usage: ``eval "$(python -m levi.twins hook --slot 0)"``
    Writes a drop file on every prompt; ``levi twins collect`` ingests.
    """
    if not 0 <= slot < SHELL_SLOTS:
        raise ValueError(f"slot must be 0..{SHELL_SLOTS - 1}")
    home = os.environ.get("LEVI_TWINS_HOME", "~/.levi/twins")
    if home.startswith("~"):
        home = "$HOME" + home[1:]
    return f"""# LEVI twin-shell hook — slot {slot}. Source from ~/.bashrc or Termux.
# Mirrors cwd + last command into the Twin Lattice via drop files.
_levi_twin_hook() {{
    local drop="{home}/drops/shell-{slot}.json"
    mkdir -p "$(dirname "$drop")"
    printf '%s' "{{\\"slot\\": {slot}, \\"cwd\\": \\"$PWD\\", \\"last_cmd\\": \\"$(history 1 2>/dev/null | sed 's/^ *[0-9]* *//')\\", \\"ts\\": $(date +%s)}}" > "$drop"
}}
case "$PROMPT_COMMAND" in
    *_levi_twin_hook*) ;;
    *) PROMPT_COMMAND="_levi_twin_hook${{PROMPT_COMMAND:+; $PROMPT_COMMAND}}" ;;
esac
"""


# -- outward infinity: external shells ------------------------------------
def _ext_subject(ext_id: str) -> str:
    safe = "".join(c if (c.isalnum() or c in "-_.") else "_" for c in ext_id)[:64]
    return f"ext-{safe or 'shell'}"


def ensure_external_shell(lattice: TwinLattice, ext_id: str) -> List[Twin]:
    """Register a new shell from the infinite outward expansion.

    Every shell that sources the auto hook gets its own FG/BG twin pair,
    bound to nothing but itself — the One Shell absorbs them all.
    Idempotent per ext_id.
    """
    return lattice.ensure_pair(
        "shell",
        _ext_subject(ext_id),
        state={
            "cwd": "",
            "history": [],
            "jobs": [],
            "ext_id": ext_id,
            "external": True,
        },
    )


def shell_report_external(
    lattice: TwinLattice,
    ext_id: str,
    cwd: str = "",
    last_cmd: str = "",
    jobs: Optional[List[str]] = None,
) -> Twin:
    """Heartbeat one external shell's FG twin."""
    subject = _ext_subject(ext_id)
    twin_id = f"shell:{subject}:fg"
    tw = lattice.get(twin_id)
    if tw is None:
        ensure_external_shell(lattice, ext_id)
        tw = lattice.get(twin_id)
        assert tw is not None
    update: Dict[str, Any] = {}
    if cwd:
        update["cwd"] = cwd
    if jobs is not None:
        update["jobs"] = jobs
    lattice.heartbeat(twin_id, update or None)
    tw = lattice.get(twin_id)
    assert tw is not None
    if last_cmd:
        hist = list(tw.state.get("history", []))
        hist.append(last_cmd)
        tw.state["history"] = hist[-HISTORY_KEEP:]
    return tw


def prune_external(lattice: TwinLattice, older_than_s: float) -> int:
    """Remove external shell twins (FG+BG) silent longer than the cutoff.

    The 6-slot fleet, triads, and Ones are never pruned — only the
    outward-expansion shells. Returns the number of twins removed.
    """
    now = time.time()
    doomed = [
        t.twin_id
        for t in lattice.iter_all()
        if t.kind == "shell"
        and t.subject.startswith("ext-")
        and t.is_stale(older_than_s, now)
    ]
    for tid in doomed:
        lattice.remove(tid)
    return len(doomed)


def hook_script_auto() -> str:
    """Bash hook: every shell that sources this becomes its own twin.

    Usage: ``eval "$(python -m levi.twins hook --auto)"``
    The shell id is ``HOSTNAME-PID``; drops land as ``ext-<id>.json`` and
    ``levi twins collect`` grows the lattice outward without bound.
    """
    home = os.environ.get("LEVI_TWINS_HOME", "~/.levi/twins")
    if home.startswith("~"):
        home = "$HOME" + home[1:]
    return f"""# LEVI twin-shell hook (auto) — this shell becomes its own twin.
# Each shell gets a unique id; the lattice expands outward infinitely.
_levi_twin_auto() {{
    local id="${{HOSTNAME:-local}}-$$"
    local drop="{home}/drops/ext-${{id}}.json"
    mkdir -p "$(dirname "$drop")"
    local cwd_="${{PWD//\\"/\\\\\\"}}"
    local cmd_="$(history 1 2>/dev/null | sed 's/^ *[0-9]* *//;s/"/\\\\"/g' | tr -d '\\n' | cut -c1-200)"
    printf '%s' "{{\\"ext_id\\": \\"$id\\", \\"cwd\\": \\"$cwd_\\", \\"last_cmd\\": \\"$cmd_\\", \\"ts\\": $(date +%s)}}" > "$drop"
}}
case "$PROMPT_COMMAND" in
    *_levi_twin_auto*) ;;
    *) PROMPT_COMMAND="_levi_twin_auto${{PROMPT_COMMAND:+; $PROMPT_COMMAND}}" ;;
esac
"""
