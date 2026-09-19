"""Life coach — personal-refinement SUB-ENGINE of the learning engine.

Chauncey's canon: "life coach was sub engine of learning engine."

Nested module boundary: ``levi.sidewinder.platform.learning_engine.life_coach``.
It is owned by the ``LearningEngine`` (``engine.life_coach``) and reached
only through it — never standalone, never a sibling of the engine, never
re-exported at the platform top level.

What it does: consumes the career packs' team/skill outputs (edition
views, pack entries, learning paths) and turns them into personal
refinement tooling — practice plans with drills, safety checklists, and
prerequisite ordering. Career refinement first, personal refinement as the
horizon: the same machinery that sharpens a trade sharpens the person.

Every plan carries the Sidewinder stop conditions verbatim — refinement
never means pushing past the stop.

DemandPulse canon (Chauncey, 2026-09-18): "Life coach is somewhat
DemandPulse as a different persona — he was the opportunity engine,
opportunity to improve your life." DemandPulse is the origin-chain root —
"See Demand Before It Exists": scan signals, score opportunities, surface
them. The coach carries that same opportunity-engine PATTERN as a
different persona, pointed inward: instead of market demand, it senses
opportunities to improve YOUR life. ``opportunities()`` is that pattern:
scan the corpus/packs/learning history, score each candidate with a
transparent breakdown, surface the best. The persona stays life coach —
warm, direct, improvement-focused — never a demand scout.

No invented user data: opportunities derive from the corpus, the packs,
and the learning loop. User-specific signals arrive through the defined
``user_signals`` seam (completed / interests / avoid) — and are never
faked when absent.

FOUNDER GATING (Chauncey's law, 2026-09-18): "Be careful with DemandPulse
— his true potential is not for everyone; most of his capabilities were
founder-only." The DemandPulse-derived deep sensing is FOUNDER-GATED,
wired to the existing Cybrus founder mechanism
(``levi.cybrus.identity.is_founder`` — founder tier is keeper-bound, not
reinvented here):

* ``full`` (founder tier): the whole scan -> score -> surface — leverage
  (latent demand mined from the prerequisite graph), team_momentum
  (sensing where the crews are moving), preparedness (crisis sensing),
  interest personalization. This is the DemandPulse magic, pointed inward.
* ``restricted`` (everyone else, and the default when no identity is
  known): a limited surface — accessibility, foundation, refinement only.
  No deep graph mining, no crew sensing, no crisis sensing, no
  personalization. Basic refinement plans (``refine_plan``,
  ``career_refinement``) are NOT DemandPulse-derived and stay ungated
  for all tiers.

The engine carries the caller's identity record (``LearningEngine(...,
identity=<record dict>)``); callers holding an ``IdentityStore`` pass
``store.get(name)``. Absent identity = restricted. The boundary is
stated in every restricted response — never silent.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from levi.sidewinder import LEVEL_ORDER

# Tracks that refine a career rather than just fix a thing.
REFINE_TRACKS = ("improve", "combine")


# ── DemandPulse pattern, pointed inward: opportunity surfacing ────

# Scoring components. Every point has a stated reason — the coach shows
# its work, DemandPulse-style: scan -> score -> surface.
#
# Founder-gated split (Chauncey's law): the DEEP components are the
# DemandPulse magic — sensing latent demand before it exists — and run
# for the founder tier only. The BASIC components are the honest obvious
# surface everyone gets.
_BASIC_COMPONENTS = ("accessibility", "foundation", "refinement")
_DEEP_COMPONENTS = ("leverage", "team_momentum", "preparedness", "interest")

_SCORE_REFINEMENT = 3      # improve/combine tracks: refines the career
_SCORE_FOUNDATION = 2      # foundation level: basics compound
_SCORE_PREPAREDNESS = 2    # crisis-domain improvisation: readiness
_SCORE_LEVERAGE_CAP = 5    # +1 per dependent skill, capped
_SCORE_MOMENTUM_CAP = 3    # +1 per team already working it, capped
_SCORE_INTEREST = 2        # user-signals seam: stated interest match


def _is_founder(identity_record) -> bool:
    """Founder check via the existing Cybrus mechanism — never reinvented."""
    if not identity_record:
        return False
    from levi.cybrus.identity import is_founder  # lazy: identity is a leaf

    return bool(is_founder(identity_record))


class LifeCoach:
    """Personal-refinement sub-engine. Constructed only by LearningEngine."""

    def __init__(self, engine):
        self._engine = engine

    # ── one entry -> personal practice plan ─────────────────────────
    def refine_plan(
        self, entry_id: str, team: Optional[str] = None
    ) -> Dict[str, Any]:
        """Turn one curriculum entry into a personal refinement plan."""
        entry = self._engine.get(entry_id, team=team)
        if entry is None:
            raise KeyError(f"unknown entry {entry_id!r}")
        path = self._engine.learning_path(entry_id, team=team)
        prereqs = [{"id": e["id"], "title": e["title"]} for e in path[:-1]]
        return {
            "kind": "refine_plan",
            "entry_id": entry["id"],
            "title": entry["title"],
            "domain": entry["domain"],
            "tracks": list(entry["tracks"]),
            "level": entry["level"],
            "goal": entry["title"],
            "mechanism": list(entry["mechanism_check"]),
            "prerequisites": prereqs,
            "drills": self.skill_drills(entry),
            "safety_checklist": list(entry["stop_conditions"]),
            "doctrine": "Know the stop before you start. Forcing it is how practice becomes damage.",
        }

    def skill_drills(self, entry: Dict[str, Any]) -> List[str]:
        """Entry steps rewritten as repeatable practice drills."""
        drills = []
        for i, step in enumerate(entry["steps"], 1):
            drills.append(
                f"Drill {i}: {step} — rep it clean three times, then teach it back from memory."
            )
        if entry.get("mechanism_check"):
            drills.insert(
                0,
                "Read the mechanism cold: "
                + " / ".join(entry["mechanism_check"])
                + " — say it back before touching tools.",
            )
        return drills

    # ── one career pack -> refinement program ───────────────────────
    def career_refinement(
        self,
        edition_id: str,
        team: Optional[str] = None,
        limit: int = 10,
    ) -> Dict[str, Any]:
        """Turn a career edition pack into a refinement program.

        Improve/combine-track entries first (they refine the career);
        falls back to the whole pack view when a pack has none, and says so.
        """
        manifest = self._engine.edition_manifest(edition_id)
        view = self._engine.edition_view(edition_id) if team is None else self._engine.team_view(team)
        entries = sorted(
            view.entries, key=lambda e: (LEVEL_ORDER[e["level"]], e["id"])
        )
        refined = [e for e in entries if set(e["tracks"]) & set(REFINE_TRACKS)]
        fell_back = False
        if not refined:
            refined, fell_back = entries, True
        items = []
        for entry in refined[:limit]:
            items.append(
                {
                    "entry_id": entry["id"],
                    "title": entry["title"],
                    "level": entry["level"],
                    "tracks": list(entry["tracks"]),
                    "drills": self.skill_drills(entry),
                    "safety_checklist": list(entry["stop_conditions"]),
                }
            )
        return {
            "kind": "career_refinement",
            "edition": edition_id,
            "edition_title": manifest.get("title", edition_id),
            "fell_back_to_full_pack": fell_back,
            "items": items,
            "count": len(items),
            "doctrine": "Refine the career, and the person follows. Stop conditions ride along — always.",
        }

    # ── DemandPulse pattern, pointed inward ─────────────────────────
    def opportunities(
        self,
        edition: Optional[str] = None,
        team: Optional[str] = None,
        limit: int = 10,
        user_signals: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Scan -> score -> surface: personal-improvement opportunities.

        The DemandPulse opportunity-engine pattern as a life-coach persona:
        instead of market demand, it senses opportunities to improve YOUR
        life. Signals are real curriculum data only — corpus entries,
        edition/team views, the prerequisite graph. Nothing is invented.

        ``user_signals`` is the defined seam for later user-specific input:
        ``{"completed": [entry ids], "interests": [domains or tracks],
        "avoid": [entry ids]}``. When absent (or None), scoring is purely
        corpus-derived and the result says so. The seam is never faked.

        Founder gating: the deep scan (leverage, team_momentum,
        preparedness, interest) runs for the founder tier only. Everyone
        else gets the restricted surface — accessibility, foundation,
        refinement — and the response says so.
        """
        signals = self._validate_user_signals(user_signals)
        full_access = _is_founder(getattr(self._engine, "identity_record", None))
        view = self._opportunity_view(edition=edition, team=team)
        entries = list(view)
        access = "full" if full_access else "restricted"
        if not entries:
            return {
                "kind": "opportunities",
                "access": access,
                "scope": {"edition": edition, "team": team},
                "items": [],
                "count": 0,
                "seam": "user_signals absent — corpus-derived only"
                if signals is None
                else "user_signals applied",
                "note": "Corpus is empty — nothing to surface yet.",
                "doctrine": "See demand before it exists — in yourself.",
            }

        # No deep scan for non-founders: the DemandPulse sensing stays off.
        dependents = self._dependent_counts() if full_access else {}
        team_hit = self._team_hit_counts() if full_access else {}
        completed = set(signals["completed"]) if signals else set()
        avoid = set(signals["avoid"]) if signals else set()
        interests = set(signals["interests"]) if signals and full_access else set()

        items = []
        for entry in entries:
            eid = entry["id"]
            if eid in completed or eid in avoid:
                continue
            score, breakdown, reasons = self._score_entry(
                entry,
                dependents.get(eid, 0),
                team_hit.get(eid, 0),
                interests,
                full_access,
            )
            items.append(
                {
                    "entry_id": eid,
                    "title": entry["title"],
                    "domain": entry["domain"],
                    "level": entry["level"],
                    "tracks": list(entry["tracks"]),
                    "difficulty": entry["difficulty"],
                    "kind": self._opportunity_kind(entry, breakdown),
                    "score": score,
                    "score_breakdown": breakdown,
                    "reasons": reasons,
                    "persona_line": self._persona_line(entry, breakdown, dependents.get(eid, 0)),
                }
            )
        # Deterministic: score desc, then entry id. No ties left to chance.
        items.sort(key=lambda i: (-i["score"], i["entry_id"]))
        items = items[:limit]
        payload = {
            "kind": "opportunities",
            "access": access,
            "scope": {"edition": edition, "team": team},
            "items": items,
            "count": len(items),
            "seam": "user_signals absent — corpus-derived only"
            if signals is None
            else "user_signals applied",
            "doctrine": "See demand before it exists — in yourself.",
        }
        if not full_access:
            payload["note"] = (
                "Restricted surface: deep opportunity sensing "
                "(latent-demand leverage, crew momentum, crisis sensing, "
                "personalization) is founder-only. What you see here — "
                "startable basics that sharpen the trade — is yours regardless."
            )
        return payload

    def _opportunity_view(self, edition=None, team=None) -> List[Dict[str, Any]]:
        if team is not None:
            return list(self._engine.team_view(team).entries)
        if edition is not None:
            return list(self._engine.edition_view(edition).entries)
        return list(self._engine.manual())

    def _dependent_counts(self) -> Dict[str, int]:
        """How many corpus entries list each entry as a prerequisite."""
        counts: Dict[str, int] = {}
        for entry in self._engine.manual():
            for pre in entry.get("prerequisites", []):
                counts[pre] = counts.get(pre, 0) + 1
        return counts

    def _team_hit_counts(self) -> Dict[str, int]:
        """How many agent teams' views include each entry."""
        counts: Dict[str, int] = {}
        try:
            teams = self._engine.list_teams()
        except Exception:  # noqa: BLE001 — teams are a bonus signal, never fatal
            return counts
        for team in teams:
            tid = team.id if hasattr(team, "id") else team["id"]
            try:
                view = self._engine.team_view(tid)
            except Exception:  # noqa: BLE001
                continue
            for entry in view.entries:
                counts[entry["id"]] = counts.get(entry["id"], 0) + 1
        return counts

    @staticmethod
    def _validate_user_signals(signals: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """The seam: validate shape, never invent content."""
        if signals is None:
            return None
        if not isinstance(signals, dict):
            raise ValueError("user_signals must be a dict or None")
        out = {"completed": [], "interests": [], "avoid": []}
        for key in out:
            val = signals.get(key, [])
            if not isinstance(val, list) or not all(isinstance(v, str) for v in val):
                raise ValueError(f"user_signals[{key!r}] must be a list of strings")
            out[key] = [v.strip().lower() for v in val if v.strip()]
        return out

    def _score_entry(self, entry, n_dependents, n_teams, interests, full_access):
        breakdown: Dict[str, int] = {}
        reasons: List[str] = []
        tracks = set(entry["tracks"])

        if tracks & set(REFINE_TRACKS):
            breakdown["refinement"] = _SCORE_REFINEMENT
            reasons.append("Refines your career, not just fixes a thing (improve/combine track).")
        if entry["level"] == "foundation":
            breakdown["foundation"] = _SCORE_FOUNDATION
            reasons.append("Foundation level — basics compound into everything else.")
        if full_access and entry["domain"] == "crisis" and "improvise" in tracks:
            breakdown["preparedness"] = _SCORE_PREPAREDNESS
            reasons.append("Crisis improvisation — readiness you hope you never need.")
        if full_access and n_dependents:
            pts = min(n_dependents, _SCORE_LEVERAGE_CAP)
            breakdown["leverage"] = pts
            reasons.append(
                f"Unlocks {n_dependents} other skill{'s' if n_dependents != 1 else ''} — "
                "learn it before you need it."
            )
        access = 4 - int(entry.get("difficulty", 2))
        if access > 0:
            breakdown["accessibility"] = access
            reasons.append("You can start this today — low barrier, real payoff.")
        if full_access and n_teams:
            pts = min(n_teams, _SCORE_MOMENTUM_CAP)
            breakdown["team_momentum"] = pts
            reasons.append(f"Crews are already working this ({n_teams} team{'s' if n_teams != 1 else ''}).")
        if full_access and interests:
            hits = interests & (set(entry["tracks"]) | {entry["domain"]})
            if hits:
                breakdown["interest"] = _SCORE_INTEREST * len(hits)
                reasons.append(f"Matches your stated interest: {', '.join(sorted(hits))}.")

        score = sum(breakdown.values())
        return score, breakdown, reasons

    @staticmethod
    def _opportunity_kind(entry, breakdown) -> str:
        if breakdown.get("preparedness"):
            return "preparedness"
        if breakdown.get("leverage"):
            return "foundation_leverage"
        if breakdown.get("refinement"):
            return "career_refinement"
        if breakdown.get("team_momentum"):
            return "team_signal"
        return "quick_win"

    @staticmethod
    def _persona_line(entry, breakdown, n_dependents) -> str:
        """Warm, direct, improvement-focused — life coach, not demand scout."""
        title = entry["title"]
        if breakdown.get("preparedness"):
            return f"{title}: you hope you never need it. That is exactly why you learn it now."
        if breakdown.get("leverage"):
            return (
                f"{title}: learn this one skill and {n_dependents} others open up. "
                "That is leverage — take it."
            )
        if breakdown.get("refinement"):
            return f"{title}: this does not just fix things, it makes you better at the work itself."
        if breakdown.get("team_momentum"):
            return f"{title}: the crews are already on it. Do not train alone when you do not have to."
        return f"{title}: small, startable, real. Begin here and let it compound."

    # ── text rendering ──────────────────────────────────────────────
    def format_plan(self, plan: Dict[str, Any]) -> str:
        lines = []
        if plan["kind"] == "career_refinement":
            lines.append(
                f"REFINEMENT PROGRAM — {plan['edition_title']} [{plan['edition']}]"
            )
            if plan["fell_back_to_full_pack"]:
                lines.append("(no improve/combine entries in this pack — full pack view used)")
            for n, item in enumerate(plan["items"], 1):
                lines.append(
                    f"\n{n}. {item['title']} [{item['entry_id']} · {item['level']} · "
                    + "/".join(item["tracks"])
                    + "]"
                )
                for drill in item["drills"]:
                    lines.append(f"   - {drill}")
                lines.append("   STOP: " + " / ".join(item["safety_checklist"]))
        else:
            lines.append(f"REFINE PLAN — {plan['title']} [{plan['entry_id']}]")
            lines.append(f"domain={plan['domain']} level={plan['level']} tracks=" + "/".join(plan["tracks"]))
            if plan["prerequisites"]:
                lines.append("PREREQS FIRST:")
                for pre in plan["prerequisites"]:
                    lines.append(f"  - {pre['title']} [{pre['id']}]")
            lines.append("MECHANISM: " + " / ".join(plan["mechanism"]))
            lines.append("DRILLS:")
            for drill in plan["drills"]:
                lines.append(f"  - {drill}")
            lines.append("SAFETY: " + " / ".join(plan["safety_checklist"]))
        lines.append("")
        lines.append(plan["doctrine"])
        return "\n".join(lines)

    def format_opportunities(self, result: Dict[str, Any]) -> str:
        """Warm, direct, improvement-focused rendering of opportunities."""
        lines = ["YOUR NEXT MOVES — opportunities to improve your life"]
        scope = result.get("scope", {})
        if scope.get("edition"):
            lines[0] += f"  [edition: {scope['edition']}]"
        if scope.get("team"):
            lines[0] += f"  [team: {scope['team']}]"
        access = result.get("access", "restricted")
        lines.append(f"(access: {access})")
        if result.get("note"):
            lines.append(result["note"])
        if not result["items"]:
            if "empty" not in result.get("note", "").lower():
                lines.append("Nothing on the board yet.")
            return "\n".join(lines)
        for n, item in enumerate(result["items"], 1):
            lines.append(
                f"\n{n}. {item['title']} [{item['entry_id']} · {item['level']} · "
                + "/".join(item["tracks"])
                + f" · score {item['score']}]"
            )
            lines.append(f"   {item['persona_line']}")
            for reason in item["reasons"]:
                lines.append(f"   · {reason}")
            lines.append(
                "   score: "
                + ", ".join(f"{k}={v}" for k, v in item["score_breakdown"].items())
            )
        lines.append("")
        lines.append(result.get("seam", ""))
        lines.append(result.get("doctrine", ""))
        return "\n".join(lines)


__all__ = ["LifeCoach", "REFINE_TRACKS"]
