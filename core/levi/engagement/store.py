"""Engagement store — local persistence + the full-circle hub return.

Answers live in ``responses.jsonl`` (mode 600) and never leave the
machine. What returns to the hub is aggregate only: per-question
tallies of which *options* were picked, phrased as a demand signal for
DemandPulse's store via ``scan_seed``. Free-text answers are counted,
never quoted. Inbox analytics gets metadata only (survey id, counts).
"""

from __future__ import annotations

import json
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from .prefs import default_engagement_dir


def _append_line(path: Path, line: str) -> bool:
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        try:
            with os.fdopen(fd, "a", encoding="utf-8") as fh:
                fh.write(line)
        except OSError:
            return False
        return True
    except OSError:
        return False


def _ensure_dir(base: Path) -> None:
    try:
        base.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(base, 0o700)
    except OSError:
        pass


class EngagementStore:
    def __init__(self, base_dir: Optional[Path] = None):
        self.base = Path(base_dir) if base_dir else default_engagement_dir()
        _ensure_dir(self.base)

    # -- state ---------------------------------------------------------
    def _state_path(self) -> Path:
        return self.base / "state.json"

    def load_state(self) -> Dict:
        try:
            raw = json.loads(self._state_path().read_text(encoding="utf-8"))
            return raw if isinstance(raw, dict) else {}
        except (OSError, json.JSONDecodeError, ValueError):
            return {}

    def save_state(self, state: Dict) -> bool:
        try:
            tmp = self.base / "state.json.tmp"
            tmp.write_text(json.dumps(state, indent=2), encoding="utf-8")
            tmp.replace(self._state_path())
            return True
        except OSError:
            return False

    def completed_surveys(self) -> List[str]:
        return list(self.load_state().get("completed_surveys", []) or [])

    def dismissed_campaigns(self) -> List[str]:
        return list(self.load_state().get("dismissed_campaigns", []) or [])

    # -- recording -----------------------------------------------------
    def record_survey(self, result: Dict) -> bool:
        """Persist a survey result and report aggregates to the hub."""
        survey_id = result.get("survey_id", "?")
        ok = _append_line(
            self.base / "responses.jsonl",
            json.dumps(
                {
                    "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    "type": "survey",
                    "survey_id": survey_id,
                    "answers": result.get("answers", {}),
                }
            )
            + "\n",
        )
        state = self.load_state()
        done = set(state.get("completed_surveys", []) or [])
        done.add(survey_id)
        state["completed_surveys"] = sorted(done)
        self.save_state(state)
        self._report_to_hub(survey_id, result)
        self._record_analytics("engagement.survey", survey_id)
        return ok

    def record_campaign(self, campaign_id: str, seen: int, completed: bool) -> bool:
        state = self.load_state()
        done = set(state.get("completed_campaigns", []) or [])
        dismissed = set(state.get("dismissed_campaigns", []) or [])
        if completed:
            done.add(campaign_id)
            dismissed.discard(campaign_id)
            state["completed_campaigns"] = sorted(done)
        else:
            dismissed.add(campaign_id)
            state["dismissed_campaigns"] = sorted(dismissed)
        saved = self.save_state(state)
        _append_line(
            self.base / "responses.jsonl",
            json.dumps(
                {
                    "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    "type": "campaign",
                    "campaign_id": campaign_id,
                    "seen": seen,
                    "completed": completed,
                }
            )
            + "\n",
        )
        self._record_analytics("engagement.campaign", campaign_id)
        return saved

    def aggregate_tallies(self) -> Dict[str, Dict[str, int]]:
        """Aggregate per-question option tallies from local responses.

        Free-text answers are counted as 'text-given', never quoted.
        Individual responses are never exposed — counts only.
        """
        tallies: Dict[str, Counter] = {}
        path = self.base / "responses.jsonl"
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            return {}
        for line in lines:
            try:
                ev = json.loads(line)
            except (json.JSONDecodeError, ValueError):
                continue
            if not isinstance(ev, dict) or ev.get("type") != "survey":
                continue
            from .surveys import get_survey  # local import, avoids cycles

            survey = get_survey(ev.get("survey_id", ""))
            answers = ev.get("answers", {})
            if not isinstance(answers, dict):
                continue
            for qid, ans in answers.items():
                key = f"{ev.get('survey_id')}.{qid}"
                bucket = tallies.setdefault(key, Counter())
                if not ans:
                    bucket["skipped"] += 1
                elif survey and any(q.id == qid and q.kind == "text" for q in survey.questions):
                    bucket["text-given"] += 1
                else:
                    bucket[str(ans)[:60]] += 1
        return {k: dict(v) for k, v in tallies.items()}

    # -- voting ------------------------------------------------------
    def current_vote(self, ballot_id: str) -> str:
        return str((self.load_state().get("votes", {}) or {}).get(ballot_id, ""))

    def record_vote(self, ballot_id: str, choice: str, kind: str) -> bool:
        """Record one vote. Favorites: recast replaces. Never stores identity."""
        choice = (choice or "").strip()
        if not choice:
            return False
        ok = _append_line(
            self.base / "votes.jsonl",
            json.dumps(
                {
                    "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    "type": "vote",
                    "ballot_id": ballot_id,
                    "kind": kind,
                    "choice": choice,
                }
            )
            + "\n",
        )
        state = self.load_state()
        votes = state.get("votes", {}) or {}
        if kind == "favorites":
            votes[ballot_id] = choice  # recast replaces
        state["votes"] = votes
        self.save_state(state)
        self._record_analytics("engagement.vote", ballot_id)
        return ok

    def vote_tallies(self) -> Dict[str, Dict[str, int]]:
        """Aggregate vote counts per ballot. Counts only — no voter identity
        is ever stored, so there is nothing to leak."""
        tallies: Dict[str, Counter] = {}
        path = self.base / "votes.jsonl"
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            return {}
        for line in lines:
            try:
                ev = json.loads(line)
            except (json.JSONDecodeError, ValueError):
                continue
            if not isinstance(ev, dict) or ev.get("type") != "vote":
                continue
            bucket = tallies.setdefault(str(ev.get("ballot_id", "?")), Counter())
            if ev.get("kind") == "favorites":
                # recast replaces: keep only the latest per ballot (single user)
                bucket.clear()
            bucket[str(ev.get("choice", ""))[:80]] += 1
        return {k: dict(v) for k, v in tallies.items()}

    # -- proposals → request box (weighted input, never auto-build) ------
    def upsert_proposal(self, verb: str, text: str) -> Dict:
        """Turn a proposal vote into weighted request-box input.

        One request per distinct proposal (no duplicates, never auto-build:
        status stays 'open' for Chauncey to triage). The vote weight lives
        in engagement state; ``proposals()`` joins weight + request id.
        """
        norm = " ".join((text or "").split())
        if not norm:
            return {"ok": False, "error": "empty proposal"}
        key = f"{verb}:{norm.lower()}"
        state = self.load_state()
        props = state.get("proposals", {}) or {}
        entry = props.get(key, {"weight": 0, "request_id": None})
        entry["weight"] = int(entry.get("weight", 0)) + 1
        if entry.get("request_id") is None:
            try:
                from levi.inbox.requests import RequestBox

                req = RequestBox().add(f"[votes] {verb}: {norm}")
                entry["request_id"] = req.id
            except Exception:
                entry["request_id"] = None
        props[key] = entry
        state["proposals"] = props
        self.save_state(state)
        self.record_vote("ship-it", f"{verb}: {norm}", "proposals")
        self._report_proposals_to_hub()
        return {"ok": True, "key": key, "weight": entry["weight"],
                "request_id": entry["request_id"]}

    def proposals(self) -> List[Dict]:
        """Proposals ranked by vote weight, joined with request-box ids."""
        props = self.load_state().get("proposals", {}) or {}
        out = [
            {
                "proposal": key,
                "weight": int(v.get("weight", 0)),
                "request_id": v.get("request_id"),
            }
            for key, v in props.items()
        ]
        return sorted(out, key=lambda d: (-d["weight"], d["proposal"]))

    def _report_proposals_to_hub(self) -> None:
        """Aggregate proposal signal → DemandPulse. Proposals are
        public-by-design (they become request-box entries), so top
        proposal text may appear in the signal — favorite votes and
        survey answers never do."""
        try:
            from levi.demand.pulse import DemandPulse
        except Exception:
            return
        top = self.proposals()[:3]
        if not top:
            return
        leaders = ", ".join(f"{p['proposal']}×{p['weight']}" for p in top)
        try:
            DemandPulse().scan_seed(
                f"engagement: proposal votes — top: {leaders} (aggregate, local)",
                segment="engagement",
            )
        except Exception:
            pass
    def _report_to_hub(self, survey_id: str, result: Dict) -> bool:
        """Full circle: aggregate learnings → DemandPulse store.

        Only aggregate shapes cross the boundary: which survey, its track
        tag (ai/si/both), how many answered/skipped, and the per-option
        tallies for choice questions. Individual answers and free text
        never leave this store.
        """
        try:
            from levi.demand.pulse import DemandPulse
        except Exception:
            return False
        from .surveys import get_survey  # local import, avoids cycles

        survey = get_survey(survey_id)
        track = survey.track if survey else "both"
        answered = result.get("answered", 0)
        total = result.get("total", 0)
        parts = [
            f"engagement: survey '{survey_id}' [{track}] completed — "
            f"{answered}/{total} answered (aggregate, local)"
        ]
        top = Counter()
        for key, counts in self.aggregate_tallies().items():
            if key.startswith(survey_id + "."):
                for opt, n in counts.items():
                    if opt not in ("skipped", "text-given"):
                        top[f"{key.split('.', 1)[1]}={opt}"] += n
        if top:
            leaders = ", ".join(f"{k}×{n}" for k, n in top.most_common(3))
            parts.append(f"top picks: {leaders}")
        try:
            DemandPulse().scan_seed(" | ".join(parts), segment="engagement")
            return True
        except Exception:
            return False

    def _record_analytics(self, capability: str, detail: str) -> None:
        try:
            from levi.inbox.analytics import record

            record(capability, detail)  # metadata only: survey/campaign id
        except Exception:
            pass
