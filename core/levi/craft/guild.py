"""guild — the indenture ladder for LEVI skills.

From arch-craft-apprenticeship-indentures and
arch-craft-masterpiece-gate (hunt wave-014):

The indenture was not a wage contract but a transfer of authority with
reputational underwriting: the master was liable for the apprentice, and
instruction was scaffolded from mimicry to supervised subcomponents —
tacit knowledge through embodiment, not text. The masterpiece was a
public, peer-judged performance credential: the artifact embodied the
candidate's full skill set and was judged by practitioners, not
credential-issuers; retained pieces became the guild's quality reference
corpus.

LEVI's clean-room remix: every LEVI skill carries an indenture —
  apprentice: read-only tool calls (observe, never mutate);
  journeyman: writes allowed, each with explicit confirmation;
  master:     autonomous within policy.
Promotion is earned and recorded, never self-declared: journeyman needs
logged practice plus a mentor's sign-off; master needs a judged
masterpiece whose hash is retained in the guildhall reference corpus.

Deny-closed throughout: unknown transitions raise; the register is the
source of truth, not memory or vibes.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Dict, List, Optional

RANKS = ("apprentice", "journeyman", "master")

# Practice tasks required before a journeyman promotion may be sought.
PRACTICE_REQUIRED = 5

# Permissions per rank: what the agent runtime should enforce.
PERMISSIONS: Dict[str, Dict[str, bool]] = {
    "apprentice": {"read": True, "write": False, "autonomous": False},
    "journeyman": {"read": True, "write": True, "autonomous": False},
    "master": {"read": True, "write": True, "autonomous": True},
}


class GuildError(ValueError):
    """Deny-closed refusal from the guild register."""


def _home() -> str:
    return os.environ.get("LEVI_HOME", os.path.expanduser("~/.levi"))


def _register_path() -> str:
    return os.path.join(_home(), "craft", "guild.jsonl")


def _hall_path() -> str:
    return os.path.join(_home(), "craft", "guildhall.jsonl")


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _append(path: str, record: Dict[str, object]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, sort_keys=True) + "\n")


def _read(path: str) -> List[Dict[str, object]]:
    if not os.path.isfile(path):
        return []
    records = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def indenture(skill: str, apprentice: str, master: str) -> Dict[str, object]:
    """Open an indenture: bind an apprentice to a master for a skill.

    The master is reputationally liable — recorded on the indenture.
    """
    skill, apprentice, master = skill.strip(), apprentice.strip(), master.strip()
    if not skill or not apprentice or not master:
        raise GuildError("skill, apprentice, and master are all required")
    if apprentice == master:
        raise GuildError("one cannot be one's own master")
    if rank_of(skill, apprentice) is not None:
        raise GuildError("%s is already indentured in %s" % (apprentice, skill))
    record = {
        "event": "indenture",
        "skill": skill,
        "apprentice": apprentice,
        "master": master,
        "at": _now(),
        "note": "master reputationally liable for apprentice's conduct",
    }
    _append(_register_path(), record)
    return record


def rank_of(skill: str, name: str) -> Optional[str]:
    """Current rank of name in skill, or None if never indentured."""
    rank = None
    for rec in _read(_register_path()):
        if rec.get("skill") == skill and rec.get("apprentice") == name:
            if rec.get("event") == "indenture":
                rank = "apprentice"
            elif rec.get("event") == "promotion":
                rank = rec.get("to")
    return rank  # type: ignore[return-value]


def practice_count(skill: str, name: str) -> int:
    """Logged, completed practice tasks for name in skill."""
    return sum(
        1
        for rec in _read(_register_path())
        if rec.get("event") == "practice"
        and rec.get("skill") == skill
        and rec.get("apprentice") == name
        and rec.get("result") == "completed"
    )


def log_practice(
    skill: str, apprentice: str, task: str, result: str = "completed"
) -> Dict[str, object]:
    """Log one supervised practice task (mimicry -> subcomponents)."""
    if rank_of(skill, apprentice) is None:
        raise GuildError("%s holds no indenture in %s" % (apprentice, skill))
    if result not in ("completed", "failed"):
        raise GuildError("result must be completed|failed, got %r" % result)
    record = {
        "event": "practice",
        "skill": skill,
        "apprentice": apprentice,
        "task": task,
        "result": result,
        "at": _now(),
    }
    _append(_register_path(), record)
    return record


def promote(
    skill: str, apprentice: str, *, mentor: str, signoff: str
) -> Dict[str, object]:
    """Promote apprentice -> journeyman. Requires logged practice and a
    mentor's explicit sign-off. Deny-closed: anything missing is refused."""
    if rank_of(skill, apprentice) != "apprentice":
        raise GuildError(
            "%s is not an apprentice of %s; only apprentices promote"
            % (apprentice, skill)
        )
    done = practice_count(skill, apprentice)
    if done < PRACTICE_REQUIRED:
        raise GuildError(
            "refused: %d/%d practice tasks logged; the ladder is not shortened"
            % (done, PRACTICE_REQUIRED)
        )
    if not (mentor or "").strip() or not (signoff or "").strip():
        raise GuildError("refused: promotion needs a named mentor's sign-off")
    record = {
        "event": "promotion",
        "skill": skill,
        "apprentice": apprentice,
        "from": "apprentice",
        "to": "journeyman",
        "mentor": mentor.strip(),
        "signoff": signoff.strip(),
        "at": _now(),
    }
    _append(_register_path(), record)
    return record


def submit_masterpiece(
    skill: str, journeyman: str, artifact: str, summary: str
) -> Dict[str, object]:
    """A journeyman submits their chef-d'oeuvre for peer judgment."""
    if rank_of(skill, journeyman) != "journeyman":
        raise GuildError(
            "%s is not a journeyman of %s; only journeymen submit masterpieces"
            % (journeyman, skill)
        )
    record = {
        "event": "masterpiece",
        "skill": skill,
        "apprentice": journeyman,
        "artifact": artifact,
        "summary": summary,
        "verdict": "pending",
        "at": _now(),
    }
    _append(_register_path(), record)
    return record


def judge_masterpiece(
    skill: str,
    journeyman: str,
    verdict: str,
    judges: List[str],
    artifact_sha256: str = "",
) -> Dict[str, object]:
    """Peer judgment of a masterpiece. 'accepted' promotes to master and the
    piece is retained in the guildhall reference corpus (hash + summary),
    as guilds kept the physical piece."""
    if verdict not in ("accepted", "rejected"):
        raise GuildError("verdict must be accepted|rejected")
    judges = [j.strip() for j in judges if j.strip()]
    if len(judges) < 2:
        raise GuildError("a masterpiece needs at least two peer judges")
    pending = [
        rec
        for rec in _read(_register_path())
        if rec.get("event") == "masterpiece"
        and rec.get("skill") == skill
        and rec.get("apprentice") == journeyman
        and rec.get("verdict") == "pending"
    ]
    if not pending:
        raise GuildError("no pending masterpiece for %s in %s" % (journeyman, skill))
    record = {
        "event": "judgment",
        "skill": skill,
        "apprentice": journeyman,
        "verdict": verdict,
        "judges": judges,
        "artifact_sha256": artifact_sha256,
        "at": _now(),
    }
    _append(_register_path(), record)
    if verdict == "accepted":
        _append(
            _register_path(),
            {
                "event": "promotion",
                "skill": skill,
                "apprentice": journeyman,
                "from": "journeyman",
                "to": "master",
                "mentor": "guild peer judgment",
                "signoff": "masterpiece accepted by " + ", ".join(judges),
                "at": _now(),
            },
        )
        # Retain the piece in the guildhall corpus (the guild keeps the work).
        _append(
            _hall_path(),
            {
                "skill": skill,
                "master": journeyman,
                "artifact": pending[-1].get("artifact"),
                "summary": pending[-1].get("summary"),
                "artifact_sha256": artifact_sha256,
                "judges": judges,
                "at": _now(),
            },
        )
    return record


def permissions(rank: str) -> Dict[str, bool]:
    """What the agent runtime should enforce for a rank."""
    if rank not in PERMISSIONS:
        raise GuildError("unknown rank %r" % (rank,))
    return dict(PERMISSIONS[rank])


def status(skill: Optional[str] = None) -> List[Dict[str, object]]:
    """Indenture ledger, optionally filtered by skill."""
    recs = _read(_register_path())
    if skill:
        recs = [r for r in recs if r.get("skill") == skill]
    return recs


def guildhall(skill: Optional[str] = None) -> List[Dict[str, object]]:
    """Retained masterpieces — the guild's quality reference corpus."""
    recs = _read(_hall_path())
    if skill:
        recs = [r for r in recs if r.get("skill") == skill]
    return recs
