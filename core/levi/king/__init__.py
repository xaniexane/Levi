"""King — the single control plane for narrative operations.

King is an orchestration/control layer OVER the two real content
engines, NOT a third content engine:

* ``graph.story_fabric.StoryFabric`` — multi-story engine (many distinct
  stories, per-story Direction/Modes).
* ``lwp.model_engine.LWPModelEngine`` — single-continuous-manuscript
  engine (REIM forks, RIEM deny→ghost, ROM/Wyrd-Rupture, gold path).

Both engines are imported via try/except optional-imports, so King
degrades gracefully if either is absent: engine-backed methods return a
plain-language "unavailable" message instead of raising.

What King layers on top of both (blueprint §4):

* **Continuity ledger** (``ledger.py``) — entities, causal edges, and a
  D2→D5 rank derived from word count + bank count. The ONE place
  word-count/rank totals accrue. Every King method that drives either
  engine harvests into this same ledger.
* **Its own Wyrd-ROM** (``rom.py``) — rupture-lock for multi-engine
  sessions; deliberately distinct from
  ``LWPModelEngine.wyrd_rupture()`` (see that module's header for the
  division; do not collapse them).
* **Social pack generation** (``social.py``) — caption + hashtags per
  platform, sanitized of markdown; content generation only.
* **Visual checkpoint URLs** (``visual.py``) — URL strings only, never
  the HTTP request.
* **Review queue** (``review.py``) — HITL surface for deny/approve and
  the mandatory approval step before any social post.

Method ↔ CLI surface map (``levi king <action>``):
``status`` → :meth:`status`; ``pulse`` → :meth:`pulse` (StoryFabric);
``manuscript`` → :meth:`pulse_manuscript` (model_engine);
``social`` → :meth:`social`; ``social-post`` → :meth:`social_post`
(confirmation-gated, review-approved only, routes through
``levi.plugins.registry``); ``reim``/``deny``/``approve``/``rupture``
→ manuscript-engine pass-throughs; ``d5`` → :meth:`d5` (documented
baseline promotion for demoing rank progression, sealed by King's own
ROM).
"""

from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from .ledger import ContinuityLedger, _default_data_dir
from .review import ReviewQueue, ReviewError
from .rom import SessionRom
from .social import PLATFORMS, assert_pack_clean, build_pack
from .visual import visual_checkpoint_for_ledger

#: platform -> plugin connector id. Only the local loopback stub exists
#: today; real platform connectors register here when they ship.
PLATFORM_CONNECTORS: Dict[str, str] = {p: "social-stub" for p in PLATFORMS}


def _words(text: str) -> int:
    return len([w for w in (text or "").split() if w])


def _try_import(module_path: str, attr: str):
    try:
        module = importlib.import_module(module_path)
        return getattr(module, attr, None)
    except Exception:
        return None


class King:
    """Control plane over StoryFabric + LWPModelEngine."""

    def __init__(
        self,
        data_dir: Optional[Path] = None,
        story_fabric: Any = "auto",
        model_engine: Any = "auto",
    ) -> None:
        self.data_dir = Path(data_dir) if data_dir else _default_data_dir()
        self.ledger = ContinuityLedger(self.data_dir)
        self.review = ReviewQueue(self.data_dir)
        self.rom = SessionRom(self.data_dir)
        self._fabric_opt = story_fabric
        self._engine_opt = model_engine
        self._fabric_inst = None
        self._engine_inst = None
        self._fabric_tried = False
        self._engine_tried = False

    # -- engine access (optional imports, graceful degradation) ----------

    def _fabric(self):
        if not self._fabric_tried:
            self._fabric_tried = True
            opt = self._fabric_opt
            if opt == "auto":
                cls = _try_import("levi.graph.story_fabric", "StoryFabric")
                self._fabric_inst = cls() if cls else None
            elif opt is None:
                self._fabric_inst = None
            else:
                self._fabric_inst = opt
        return self._fabric_inst

    def _engine(self):
        if not self._engine_tried:
            self._engine_tried = True
            opt = self._engine_opt
            if opt == "auto":
                cls = _try_import("levi.lwp.model_engine", "LWPModelEngine")
                self._engine_inst = cls() if cls else None
            elif opt is None:
                self._engine_inst = None
            else:
                self._engine_inst = opt
        return self._engine_inst

    @property
    def fabric_available(self) -> bool:
        return self._fabric() is not None

    @property
    def engine_available(self) -> bool:
        return self._engine() is not None

    # -- harvest ----------------------------------------------------------

    def _harvest(
        self, source: str, words: int, banks: int, event: str
    ) -> Dict[str, Any]:
        return self.ledger.harvest(source, words, banks, event)

    def _manuscript_node(self) -> None:
        self.ledger.register_entity("manuscript", "manuscript", "L.W.P. manuscript")

    # -- status -----------------------------------------------------------

    def status(self, visual: bool = False) -> str:
        s = self.ledger.summary()
        fab = "yes" if self.fabric_available else "no (graceful)"
        eng = "yes" if self.engine_available else "no (graceful)"
        rv = self.review.summary()
        lines = [
            "=== King Control Plane ===",
            f"rank={s['rank']}  words={s['total_words']}  banks={s['total_banks']}",
            f"entities={s['entities']}  edges={s['edges']}  harvests={s['harvests']}",
            f"fingerprint={s['fingerprint']}",
            f"engines: story_fabric={fab}  model_engine={eng}",
            f"review: pending={rv['pending']} approved={rv['approved']} "
            f"denied={rv['denied']} decisions={rv['decisions']}",
            f"session_rom_locks={self.rom.count()}",
        ]
        if self.ledger.promoted:
            p = self.ledger.promoted
            lines.append(
                f"baseline: D5 PROMOTED (demo) at {p.get('ts')} — {p.get('reason')}"
            )
        else:
            lines.append("baseline: derived from ledger (no demo promotion)")
        for h in self.ledger.harvests[-3:]:
            lines.append(
                f"  harvest {h['source']}: +{h['words']}w +{h['banks']}b · {h['event']}"
            )
        if visual:
            for cp in visual_checkpoint_for_ledger(s):
                lines.append(f"  visual {cp['name']}: {cp['url']}")
        return "\n".join(lines)

    # -- pulse: StoryFabric-backed ----------------------------------------

    def pulse(self, story_id: Optional[str] = None) -> str:
        """Drive the multi-story engine one beat; harvest into the ledger."""
        fab = self._fabric()
        if fab is None:
            return (
                "StoryFabric unavailable — pulse skipped. "
                "Install/keep core/levi/graph/story_fabric.py importable to enable."
            )
        stories = fab.list()
        story = None
        if story_id:
            story = fab.get(story_id)
            if story is None:
                return f"Unknown story {story_id!r} — nothing pulsed."
        elif not stories:
            return (
                "No stories yet — King does not auto-create artifacts "
                "(blueprint §1.5: creation needs an explicit confirm). "
                'Create one first: levi story --create "<premise>" --genre <genre>'
            )
        else:
            story = max(stories, key=lambda s: s.updated_at or "")
        before_words = _words(story.body)
        beats_before = len(story.beats)
        story = fab.expand(story.id)
        words = _words(story.body) - before_words
        banks = max(1, len(story.beats) - beats_before)
        self.ledger.register_entity(
            story.id,
            "story",
            story.title,
            {"genre": story.genre, "beats": len(story.beats)},
        )
        for c in story.characters[:8]:
            self.ledger.register_entity(
                f"{story.id}:{c.id}",
                "character",
                c.name,
                {
                    "archetype": c.archetype.value
                    if hasattr(c.archetype, "value")
                    else str(c.archetype)
                },
            )
        new_beat = story.beats[-1] if story.beats else None
        if new_beat:
            beat_id = f"{story.id}:beat:{new_beat.order}"
            self.ledger.register_entity(beat_id, "beat", new_beat.name)
            self.ledger.add_edge(story.id, beat_id, "advances", new_beat.summary[:120])
        self._harvest("story_fabric", words, banks, f"pulse {story.id}")
        return (
            f"=== King pulse (story_fabric) ===\n"
            f"story={story.id} title={story.title!r}\n"
            f"+{words} words, +{banks} bank(s) harvested\n"
            f"ledger: rank={self.ledger.rank()} "
            f"words={self.ledger.total_words} banks={self.ledger.total_banks}"
        )

    # -- manuscript: model_engine-backed ------------------------------------

    def pulse_manuscript(self, n: int = 1) -> str:
        """Drive the single-manuscript engine; harvest into the ledger."""
        eng = self._engine()
        if eng is None:
            return (
                "LWPModelEngine unavailable — manuscript skipped. "
                "Install/keep core/levi/lwp/model_engine.py importable to enable."
            )
        n = max(1, min(8, int(n)))
        before_words = eng.state.words
        scenes_before = len(eng.state.scenes)
        out = eng.expand(n=n)
        words = eng.state.words - before_words
        new_scenes = eng.state.scenes[scenes_before:]
        banks = max(1, len(new_scenes))
        self._manuscript_node()
        for sc in new_scenes:
            self.ledger.register_entity(
                f"scene:{sc.get('id')}",
                "scene",
                (sc.get("event") or "")[:80],
                {"words": sc.get("words"), "status": sc.get("status")},
            )
            self.ledger.add_edge("manuscript", f"scene:{sc.get('id')}", "contains")
        self._harvest("model_engine", words, banks, f"expand {n} scene(s)")
        return (
            f"=== King manuscript pulse (model_engine) ===\n{out}\n"
            f"harvested: +{words} words, +{banks} bank(s)\n"
            f"ledger: rank={self.ledger.rank()} "
            f"words={self.ledger.total_words} banks={self.ledger.total_banks}"
        )

    # -- manuscript-engine pass-throughs -------------------------------------

    def reim(self, tracks: int = 3, seed: Optional[str] = None) -> str:
        eng = self._engine()
        if eng is None:
            return "LWPModelEngine unavailable — reim skipped."
        out = eng.reim_forks(seed=seed, tracks=tracks)
        self._manuscript_node()
        for t in eng.state.tracks:
            tid = f"track:{t.get('id')}"
            self.ledger.register_entity(
                tid,
                "reim_track",
                f"track {t.get('index')}",
                {"direction": t.get("direction"), "words": t.get("words")},
            )
            self.ledger.add_edge("manuscript", tid, "forks")
        # Forks are not canon until crowned: harvest records the drive
        # with zero words/banks so the audit trail stays honest.
        self._harvest("model_engine", 0, 0, f"reim {len(eng.state.tracks)} tracks")
        self.review.log_decision("reim", f"{len(eng.state.tracks)} tracks forked")
        return out

    def deny(self, review_id: Optional[str] = None, note: str = "") -> str:
        if review_id:
            try:
                item = self.review.deny(review_id, note)
            except ReviewError as e:
                return str(e)
            return f"Denied review item {item['id']} ({item.get('kind')})."
        eng = self._engine()
        if eng is None:
            return "LWPModelEngine unavailable — deny skipped."
        before = eng.state.words
        out = eng.deny_last()
        self._harvest("model_engine", eng.state.words - before, 0, "deny last scene")
        self.review.log_decision("deny", out[:200])
        return out

    def approve(self, review_id: Optional[str] = None, note: str = "") -> str:
        if review_id:
            try:
                item = self.review.approve(review_id, note)
            except ReviewError as e:
                return str(e)
            return f"Approved review item {item['id']} ({item.get('kind')})."
        eng = self._engine()
        if eng is None:
            return "LWPModelEngine unavailable — approve skipped."
        out = eng.approve_last()
        self._harvest("model_engine", 0, 0, "approve last scene")
        self.review.log_decision("approve", out[:200])
        return out

    def rupture(self, lens: str = "mccarthy") -> str:
        """Pass-through to the MANUSCRIPT engine's wyrd_rupture.

        This is the single-manuscript ROM lock. King's own session ROM
        (rom.py) is a different commitment — see ``d5``.
        """
        eng = self._engine()
        if eng is None:
            return "LWPModelEngine unavailable — rupture skipped."
        before = eng.state.words
        out = eng.wyrd_rupture(lens=lens)
        words = eng.state.words - before
        self.ledger.register_entity(
            f"rom:{lens}",
            "rom_lock",
            f"manuscript ROM ({lens})",
            {"words": words},
        )
        self._harvest("model_engine", words, 1, f"wyrd-rupture/{lens}")
        self.review.log_decision("rupture", f"manuscript wyrd-rupture lens={lens}")
        return out

    # -- d5: documented baseline promotion -------------------------------------

    def d5(self, reset: bool = False) -> str:
        """Baseline promotion for demoing rank progression.

        Floors the ledger's derived rank at D5 (recorded as an explicit
        demo override with timestamp — no words or banks are fabricated)
        and seals the promoted session state with King's OWN Wyrd-ROM
        (``rom.py``): a rupture-lock over the multi-engine ledger
        fingerprint. ``reset=True`` clears the promotion.
        """
        if reset:
            had = self.ledger.reset_promotion()
            self.review.log_decision("d5-reset", "demo baseline promotion cleared")
            return "D5 demo baseline cleared." if had else "No D5 promotion was set."
        self.ledger.promote_d5()
        lock = self.rom.rupture_session(
            "d5 baseline promotion (demo)", self.ledger.fingerprint()
        )
        self.review.log_decision("d5", f"promoted to D5 baseline; rom={lock['id']}")
        return (
            "=== D5 baseline promotion (demo) ===\n"
            f"ledger rank is now floored at D5 "
            f"(words={self.ledger.total_words}, banks={self.ledger.total_banks} — unchanged)\n"
            f"King session-ROM lock: {lock['id']} at {lock['ts']}\n"
            f"fingerprint: {self.ledger.fingerprint()[:16]}\n"
            "This is a demo override for rank progression, recorded in the ledger. "
            "Clear it with: levi king d5 --reset"
        )

    # -- social ---------------------------------------------------------------

    def _source_text(self) -> Tuple[str, str]:
        """Pick the freshest source text for a social pack."""
        eng = self._engine()
        if eng is not None and getattr(eng.state, "last_text", ""):
            return eng.state.last_text, "model_engine.last_text"
        fab = self._fabric()
        if fab is not None:
            stories = fab.list()
            if stories:
                story = max(stories, key=lambda s: s.updated_at or "")
                if story.body:
                    return story.body[-4000:], f"story_fabric:{story.id}"
        events = [h.get("event", "") for h in self.ledger.harvests[-5:]]
        fallback = " ".join(e for e in events if e) or "L.W.P. continuity under King"
        return fallback, "ledger"

    def social(self, platform: str = "x", title: str = "") -> str:
        """Generate a sanitized social pack and queue it for review.

        Content generation only — no network. The pack enters the
        review queue as ``pending``; it cannot be posted until
        ``approve <id>`` moves it out.
        """
        source, origin = self._source_text()
        pack = build_pack(source, platform=platform, title=title)
        assert_pack_clean(pack)  # contract enforced on every real output
        item = self.review.queue_pack(pack)
        tags = " ".join(str(t) for t in pack["hashtags"])
        return (
            f"=== Social pack · {platform} · queued for review ===\n"
            f"review id: {item['id']}\n"
            f"source: {origin}\n\n"
            f"{pack['caption']}\n\n"
            f"[{pack['caption_chars']} chars · tags: {tags}]\n\n"
            f"Next: levi king approve {item['id']}   (then social-post --id {item['id']} --yes)"
        )

    def social_post(
        self, pack_id: str, platform: Optional[str] = None, confirm: bool = False
    ) -> Dict[str, Any]:
        """Post a review-approved pack through the plugin connector contract.

        Two independent HITL gates, both required:
        1. the pack must be ``approved`` in the review queue;
        2. ``confirm=True`` (CLI: ``--yes``) — the connector enforces this
           again inside ``execute()``; King never bypasses it.
        """
        item = self.review.get(pack_id)
        if item is None:
            return {
                "ok": False,
                "gate": "approval",
                "message": f"Unknown review item {pack_id!r} — nothing was sent.",
            }
        if item.get("status") != "approved":
            return {
                "ok": False,
                "gate": "approval",
                "message": (
                    f"Pack {pack_id} is {item.get('status')!r} — approve it first "
                    f"(`levi king approve {pack_id}`). Nothing was sent."
                ),
            }
        if not confirm:
            return {
                "ok": False,
                "gate": "confirmation",
                "message": (
                    "Refusing: social-post writes to a third-party account and "
                    "requires explicit confirmation — re-run with --yes. "
                    "Nothing was sent."
                ),
            }
        plat = platform or item.get("platform") or "x"
        if plat not in PLATFORMS:
            return {
                "ok": False,
                "gate": "connector",
                "message": f"Unknown platform {plat!r} — nothing was sent.",
            }
        try:
            import levi.plugins.social_stub  # noqa: F401  (registers the loopback)
        except Exception:
            pass
        from levi.plugins.registry import get_connector

        connector_id = PLATFORM_CONNECTORS.get(plat, "social-stub")
        connector = get_connector(connector_id)
        if connector is None:
            return {
                "ok": False,
                "gate": "connector",
                "message": (
                    f"No connector {connector_id!r} registered for platform "
                    f"{plat!r} — nothing was sent."
                ),
            }
        result = connector.execute(
            "publish",
            {
                "platform": plat,
                "caption": item.get("caption"),
                "hashtags": item.get("hashtags"),
            },
            confirm=True,
        )
        self.review.log_decision(
            "social-post",
            f"{pack_id} via {connector_id}: {result.status}",
        )
        detail = ""
        if isinstance(result.data, dict) and result.data.get("message"):
            detail = " " + str(result.data["message"])
        return {
            "ok": result.ok,
            "gate": None if result.ok else "connector",
            "message": (
                f"[{connector_id}] {result.status}: {result.message}{detail}"
                + ("" if result.ok else " — nothing was sent.")
            ),
            "result": {
                "status": result.status,
                "data": result.data,
                "request_made": result.request_made,
            },
        }
