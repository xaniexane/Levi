"""
LEVI × L.W.P. Full Cloud Model — unified literary + organism surface.

Local SSA is the oxygen. Cloud (Phase B/C) is optional wings:
  - optional model relay polish
  - encrypted sync dry-run
  - never owns continuity / keys / HITL

This is the “next cloud model people would use”: offline-first literary engine
with full L.W.P. organs, fused into the LEVI symbiotic kernel.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

from levi.lwp.model_engine import LWPModelEngine, DIRS, PHASES, POWERS, ROM_LENSES
from levi.cloud.stages import StageMap, current_stage
from levi.cloud.crypto_protocol import CryptoProtocol
from levi.cloud.sync_dryrun import SyncDryRun
from levi.cloud.zk import ZeroKnowledgeDesign


@dataclass
class ModelCapabilities:
    """What the full cloud model exposes."""

    directions: List[str] = field(default_factory=lambda: list(DIRS.keys()))
    phases: List[str] = field(default_factory=lambda: list(PHASES.keys()))
    powers: List[str] = field(default_factory=lambda: list(POWERS.keys()))
    rom_lenses: List[str] = field(default_factory=lambda: list(ROM_LENSES.keys()))
    organs: List[str] = field(
        default_factory=lambda: [
            "expand",
            "deny",
            "approve",
            "reim",
            "crown",
            "rupture",
            "causal_bleed",
            "manuscript",
            "set_phase",
            "set_power",
            "set_direction",
            "genres",
            "status",
            "polish",
        ]
    )
    integrations: List[str] = field(
        default_factory=lambda: [
            "story_fabric",
            "genre_registry_97",
            "mirror_cascade",
            "opportunity_rail",
            "character_graph",
            "premium_craft",
            "model_relay",
            "vault_seal",
            "corpus_brain",
            "hitl",
            "phase_abc",
            "zk_sync_dryrun",
        ]
    )


class FullCloudModel:
    """
    Single facade: L.W.P. literary SSA + LEVI organism + Phase A/B/C protocol.

    Usage:
      m = FullCloudModel()
      print(m.expand(n=1))
      print(m.reim(tracks=3))
      print(m.crown(0))
      print(m.rupture("morrison"))
      print(m.manuscript())
      print(m.report())
    """

    def __init__(self) -> None:
        self.engine = LWPModelEngine()
        self.phases = StageMap()
        self.crypto = CryptoProtocol()
        self.sync = SyncDryRun()
        self.zk = ZeroKnowledgeDesign()
        self.caps = ModelCapabilities()

    # ── L.W.P. literary organs ─────────────────────────────────

    def expand(
        self, n: int = 1, seed: Optional[str] = None, polish: bool = False
    ) -> str:
        out = self.engine.expand(n=n, seed=seed)
        if polish and self.engine.state.last_text:
            polished = self.engine.optional_polish(self.engine.state.last_text)
            if polished != self.engine.state.last_text:
                self.engine.state.last_text = polished
                if self.engine.state.scenes:
                    self.engine.state.scenes[-1]["text"] = polished
                    self.engine.state.scenes[-1]["words"] = len(polished.split())
                self.engine._persist()
                out += "\n\n[optional polish applied]"
        return out

    def deny(self) -> str:
        return self.engine.deny_last()

    def approve(self) -> str:
        return self.engine.approve_last()

    def reim(self, tracks: int = 3, seed: Optional[str] = None) -> str:
        return self.engine.reim_forks(seed=seed, tracks=tracks)

    def crown(self, index: int = 0) -> str:
        return self.engine.crown_track(index)

    def rupture(self, lens: str = "mccarthy") -> str:
        return self.engine.wyrd_rupture(lens=lens)

    def causal(self) -> str:
        return self.engine.causal_bleed()

    def manuscript(self, limit: int = 0) -> str:
        return self.engine.manuscript(limit=limit)

    def configure(
        self,
        direction: Optional[str] = None,
        phase: Optional[str] = None,
        power: Optional[str] = None,
        genres: Optional[str] = None,
        pov: Optional[str] = None,
        seed: Optional[str] = None,
    ) -> str:
        if direction:
            self.engine.set_direction(direction)
        if phase:
            self.engine.set_phase(phase)
        if power:
            self.engine.set_power(power)
        if genres:
            self.engine.resolve_genres(genres)
        kw = {}
        if pov:
            kw["pov"] = pov
        if seed:
            kw["seed"] = seed
        if kw:
            self.engine.configure(**kw)
        return self.engine.status()

    def status(self) -> str:
        return self.engine.status()

    def snapshot(self) -> Dict[str, Any]:
        snap = self.engine.full_snapshot()
        snap["phase_abc"] = current_stage().id
        snap["phase_abc_status"] = current_stage().status
        return snap

    # ── Story fabric bridge ────────────────────────────────────

    def story_create(
        self, premise: str, genre: str = "literary", title: str = ""
    ) -> str:
        from levi.graph.story_fabric import StoryFabric

        fab = StoryFabric()
        st = fab.create_story(premise=premise, genre=genre, title=title or None)
        return (
            f"story id={st.id} title={st.title} genre={st.genre} beats={len(st.beats)}"
        )

    def story_expand(self, story_id: str, focus: str = "next_beat") -> str:
        from levi.graph.story_fabric import StoryFabric

        fab = StoryFabric()
        st = fab.expand(story_id, focus=focus)
        body = (st.body or "")[-500:]
        return f"expanded {st.id} · words≈{len((st.body or '').split())}\n{body}"

    def genres_list(self) -> str:
        from levi.graph.genres import GenreRegistry

        r = GenreRegistry()
        info = r.integrity_check()
        lines = [
            f"Genres: {r.count()}/{info['expected']}  Integrity: {'OK' if info.get('ok') else 'FAIL'}"
        ]
        # category counts if available
        try:
            from collections import Counter

            cats = Counter(g.category.value for g in r.list())
            for c, n in sorted(cats.items()):
                lines.append(f"  {c}: {n}")
        except Exception:
            pass
        return "\n".join(lines)

    # ── Organism integrations ──────────────────────────────────

    def mirror(self, seed: str = "cloud model cross-check") -> str:
        from levi.lwp.mirror_cascade import MirrorCascade

        r = MirrorCascade().run(seed)
        return f"MirrorCascade fp={r.fingerprint}\n{getattr(r, 'summary', r)}"

    def rail_status(self) -> str:
        from levi.lwp.opportunity_rail import OpportunityRail

        rail = OpportunityRail()
        cars = list(rail.cars.values()) if hasattr(rail, "cars") else []
        active = sum(1 for c in cars if getattr(c, "status", "") == "active")
        return f"OpportunityRail cars={len(cars)} active={active}"

    def characters(self, genre: str = "literary", count: int = 4) -> str:
        from levi.graph.story_fabric import StoryFabric

        fab = StoryFabric()
        chars = fab.generate_characters(genre=genre, count=count)
        lines = [f"Cast · genre={genre} · n={len(chars)}"]
        for c in chars:
            lines.append(f"  {c.name} · {c.archetype.value} · want={c.want[:40]}")
        return "\n".join(lines)

    def brain_touch(self, note: str = "L.W.P. cloud model event") -> str:
        try:
            from levi.brain.corpus import Corpus

            c = Corpus()
            if hasattr(c, "add"):
                c.add(note, kind="OBSERVED")
            return "corpus noted"
        except Exception as e:
            return f"corpus skip: {e}"

    # ── Phase / crypto wings ───────────────────────────────────

    def phase_report(self) -> str:
        return self.phases.status_block()

    def crypto_report(self) -> str:
        return self.crypto.full_report()

    def sync_dryrun(self) -> str:
        return self.sync.report()

    def zk_report(self) -> str:
        return self.zk.report()

    # ── Unified report ─────────────────────────────────────────

    def report(self) -> str:
        snap = self.snapshot()
        lines = [
            "══ LEVI × L.W.P. Full Cloud Model ══",
            f"Phase {snap['phase_abc']} [{snap['phase_abc_status']}] · seal={snap['seal']}",
            f"words={snap['words']}  gold={snap['gold_pct']:.1f}%  rank={snap['rank']}  anomaly={snap['anomaly']}",
            f"direction={snap['direction']}  phase={snap['phase']}  power={snap['power']}  pov={snap['pov']}",
            f"genres={snap['genres']}",
            f"scenes={snap['scenes']} tracks={snap['tracks']} vault={snap['vault']} "
            f"rom={snap['rom']} ghost={snap['ghost']} causal={snap['causal_notes']}",
            "",
            f"organs: {', '.join(self.caps.organs)}",
            f"integrations: {', '.join(self.caps.integrations[:6])}…",
            "",
            "Cloud role: optional booster — never owns continuity or keys.",
            f"at {datetime.now(timezone.utc).isoformat()}",
        ]
        return "\n".join(lines)

    def run_all_smoke(self) -> str:
        """One-shot capability smoke for gate / demo."""
        parts = [self.report(), "", "--- expand ---", self.expand(1)[:400], ""]
        parts.append("--- reim ---")
        parts.append(self.reim(2)[:350])
        parts.append("")
        parts.append("--- causal ---")
        parts.append(self.causal())
        parts.append("")
        parts.append("--- genres ---")
        parts.append(self.genres_list())
        parts.append("")
        parts.append("--- phase ---")
        parts.append(self.phase_report().split("\n")[0])
        return "\n".join(parts)
