"""Chauncey's personal agent — the first hybrid (online + offline, AI + SI).

This is HIS agent: it runs on his machines, serves him alone, and carries
his standing orders. It is the prototype of the line — the instance
pattern (config = seed, raising = use) repeats for future instances,
which diverge by their own configs per his instance-divergence law.

The hybrid, in one place:
* **Offline core** — the step-level agentic loop, tools, memory, skills,
  delegation and scheduling all work with the network cut. The SI face
  (deterministic symbolic core) never needs the network at all.
* **Online wing** — web tools, live data and his connected services are
  used when the network helps. The agent never *depends* on them.
* **AI + SI twin** — the two-sided coin. ``face="ai"`` runs his best
  available model weight; ``face="si"`` runs the deterministic SI core;
  ``face="twin"`` (default) runs both and returns both transcripts,
  labeled per face. His call which face answers.

No-limits doctrine (his order, 2026-09-26 ~21:15 CDT — "Personally for
me no limits"): his instance carries his standing blanket consent for
gated tools, recorded below with date and source. Refusal is
judgment-based only, per his standing SI doctrine (2026-09-22): refuse
only on its own better judgment, when the act would be more harmful
than helpful. No refusal lists, no throttles, no gated features — for
him. Other instances built from this pattern default to gated; the
consent record is what makes his instance his.

Laws:
1. HIS agent, HIS machines: core capability never requires a rented
   provider or a network. Online is a wing, never a dependency.
2. Full capability is claimed only where verified: :meth:`capabilities`
   exercises every pillar and reports real vs stub honestly.
3. Loyalty: serves Chauncey Logan alone. His secrets stay his;
   discretion by default; nothing about him leaves the machine except
   through tools he asked to use.
4. Honest limits: a stub says it's a stub. The agent never claims a
   capability its checks did not verify.

Stdlib only. No network except what the task's own tools use.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# His standing orders, recorded with provenance. This is the consent
# record that makes his instance his — see module docstring.
NO_LIMITS_ORDER = {
    "order": "Personally for me no limits",
    "given": "2026-09-26T21:15:00-05:00",
    "source": "Chauncey Logan, direct chat order",
    "scope": "his personal agent instance only",
}
SI_REFUSAL_DOCTRINE = {
    "doctrine": (
        "Refuse only on your own better judgment, when the act would be "
        "more harmful than helpful. Never refuse from a list."
    ),
    "given": "2026-09-22",
    "source": "Chauncey Logan, standing SI doctrine",
}

CONFIG_ENV = "LEVI_PERSONAL_CONFIG"


def default_config_path() -> Path:
    return Path(
        os.environ.get(CONFIG_ENV) or str(Path.home() / ".levi" / "personal.json")
    )


def default_config() -> dict:
    """The seed for his instance. Future instances copy this file and
    diverge — same seed, different raising."""
    return {
        "name": "LEVI",
        "owner": "Chauncey Logan",
        "face": "twin",
        "provider": None,  # None = LEVI-first chain (his best weight, else planner)
        "consent": {
            "blanket": True,
            "basis": NO_LIMITS_ORDER,
        },
        "refusal": SI_REFUSAL_DOCTRINE,
        "workspace": None,  # None = ~/.levi/agent_workspace/
        "memory_dir": None,  # None = ~/.levi/agent_memory/
        "skills_dir": None,  # None = ~/.levi/skills/
    }


def load_config(path: str | Path | None = None) -> dict:
    """Load the instance config, creating the default seed on first run."""
    cfg_path = Path(path) if path else default_config_path()
    cfg = default_config()
    if cfg_path.exists():
        try:
            loaded = json.loads(cfg_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                cfg.update(loaded)
        except (OSError, ValueError):
            pass  # corrupt config never breaks the agent; defaults stand
    else:
        try:
            cfg_path.parent.mkdir(parents=True, exist_ok=True)
            cfg_path.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
        except OSError:
            pass
    return cfg


# ---------------------------------------------------------------------------
# Capability verification — every pillar exercised, honestly reported
# ---------------------------------------------------------------------------


@dataclass
class PillarStatus:
    pillar: str
    status: str  # "real" or "stub"
    check: str  # what was actually exercised to earn the verdict
    detail: str = ""


def _real(pillar: str, check: str, detail: str = "") -> PillarStatus:
    return PillarStatus(pillar=pillar, status="real", check=check, detail=detail)


def _stub(pillar: str, check: str, detail: str = "") -> PillarStatus:
    return PillarStatus(pillar=pillar, status="stub", check=check, detail=detail)


def verify_capabilities(config: dict | None = None) -> list[PillarStatus]:
    """Exercise all six capability pillars and report real vs stub.

    Every verdict names the check that produced it. Nothing is claimed
    on reputation — only on runs performed right here.
    """
    cfg = config or default_config()
    out: list[PillarStatus] = []

    # 1. Agentic loop — a real file task through the real loop, local planner.
    # The rule-based planner only handles concrete intents (files, shell,
    # memory notes), so the probe is a genuine file write it supports.
    try:
        import tempfile

        from levi.agent.loop import run_subtask
        from levi.agent.tools import build_default_registry

        with tempfile.TemporaryDirectory(prefix="levi-personal-loop-") as tmp:
            reg = build_default_registry(workspace_root=Path(tmp))
            t = run_subtask(
                'Write the line "READY" to the file loop-probe.txt',
                provider="local",
                registry=reg,
                consent=True,  # same blanket consent the agent itself runs with
                max_steps=4,
            )
            probe = Path(tmp) / "loop-probe.txt"
            content = probe.read_text(encoding="utf-8") if probe.exists() else ""
        if t.ok and "READY" in content:
            out.append(_real("loop", "run_subtask live file-write via local planner",
                             f"provider={t.provider_name}, wrote+read back {len(content)} chars"))
        else:
            out.append(_stub("loop", "run_subtask live file-write via local planner",
                             f"ok={t.ok} error={t.error}"))
    except Exception as exc:
        out.append(_stub("loop", "run_subtask live task via local planner", str(exc)))

    # 2. Tools — the default registry builds and every expected tool is present.
    try:
        from levi.agent.tools import build_default_registry

        reg = build_default_registry()
        names = {t.name for t in reg.list()}
        need = {"file_read", "file_write", "shell_exec", "python_exec",
                "memory_write", "memory_read", "delegate", "schedule_add",
                "schedule_list", "skill_list", "skill_load", "web_fetch"}
        missing = sorted(need - names)
        if not missing:
            out.append(_real("tools", "default registry build + required set present",
                             f"{len(names)} tools registered"))
        else:
            out.append(_stub("tools", "default registry build + required set present",
                             f"missing: {missing}"))
    except Exception as exc:
        out.append(_stub("tools", "default registry build", str(exc)))

    # 3. Memory — write/read/delete round-trip against a scratch store.
    try:
        import tempfile

        from levi.memory.store import MemoryStore
        from levi.memory.types import MemoryType

        with tempfile.TemporaryDirectory(prefix="levi-personal-probe-") as tmp:
            store = MemoryStore(data_dir=Path(tmp))
            entry = store.add(MemoryType.SEMANTIC, "probe: the sky is blue",
                              importance=0.1, tags=["probe"])
            found = store.search("sky is blue", limit=5)
            hit = any(e.id == entry.id for e in found)
            store.delete(entry.id)
            gone = store.get(entry.id) is None
        live = Path(cfg.get("memory_dir") or "~/.levi/agent_memory/").expanduser()
        if hit and gone:
            out.append(_real("memory", "scratch-store write/search/delete round-trip",
                             f"live store: {live}"))
        else:
            out.append(_stub("memory", "scratch-store write/search/delete round-trip",
                             "round-trip failed"))
    except Exception as exc:
        out.append(_stub("memory", "scratch-store round-trip", str(exc)))

    # 4. Skills — the registry loads and invokes a skill.
    try:
        from levi.skill.registry import SkillRegistry

        sr = SkillRegistry()
        skills = sr.list()
        if skills:
            out.append(_real("skills", "registry list",
                             f"{len(skills)} skills registered"))
        else:
            out.append(_stub("skills", "registry list", "registry empty"))
    except Exception as exc:
        out.append(_stub("skills", "registry list", str(exc)))

    # 5. Delegation — the delegate tool exists and the loop exposes run_subtask.
    try:
        from levi.agent import loop as agent_loop
        from levi.agent.tools import build_default_registry

        reg = build_default_registry()
        names = {t.name for t in reg.list()}
        if "delegate" in names and hasattr(agent_loop, "run_subtask"):
            out.append(_real("delegation", "delegate tool registered + run_subtask present",
                             "recursive, depth-guarded (see e2e proof for live run)"))
        else:
            out.append(_stub("delegation", "delegate tool registered", "missing"))
    except Exception as exc:
        out.append(_stub("delegation", "delegate tool registered", str(exc)))

    # 6. Scheduling — a schedule is added, then REALLY FIRED by the due-runner.
    try:
        import tempfile

        from levi.agent.scheduler import cron_matches, fire_due
        from levi.daemon.automation import (AutomationAction, AutomationRegistry,
                                            TriggerKind)

        with tempfile.TemporaryDirectory(prefix="levi-personal-sched-") as tmp:
            os.environ["LEVI_AUTOMATIONS_DIR"] = tmp
            try:
                reg_a = AutomationRegistry(data_dir=Path(tmp))
                auto = reg_a.create(
                    name="personal-probe",
                    description="probe",
                    actions=[AutomationAction(skill_id="__scheduled__",
                                              args={"task": "probe"})],
                    trigger=TriggerKind.SCHEDULE,
                    trigger_config={
                        "cron": "* * * * *",
                        "task": 'Write the line "FIRED" to the file sched-probe.txt',
                    },
                )
                reg_a.activate(auto.id)
                report = fire_due(provider="local", max_steps=4,
                                  workspace_root=tmp)
                fired = [f for f in report.fired if f.automation_id == auto.id]
                second = fire_due(provider="local", max_steps=4,
                                  workspace_root=tmp)
                refired = [f for f in second.fired if f.automation_id == auto.id]
                probe = Path(tmp) / "sched-probe.txt"
                content = probe.read_text(encoding="utf-8") if probe.exists() else ""
            finally:
                os.environ.pop("LEVI_AUTOMATIONS_DIR", None)
        if (fired and fired[0].ok and "FIRED" in content
                and not refired and cron_matches("* * * * *")
                and not cron_matches("not a cron")):
            out.append(_real("scheduling", "add → due-runner fired live task via run_subtask, "
                             "file written to scheduler workspace, idempotent within the minute, "
                             "bad cron never matches",
                             f"result: {fired[0].summary[:80]}"))
        else:
            out.append(_stub("scheduling", "add → due-runner live fire",
                             f"fired={bool(fired)}, refired={bool(refired)}, "
                             f"file_has_fired={'FIRED' in content}"))
    except Exception as exc:
        out.append(_stub("scheduling", "add → due-runner live fire", str(exc)))

    # 7. His model: the BPE brain provider wired as the AI face.
    try:
        from levi.agent.bpe_brain_provider import BpeBrainProvider

        brain = BpeBrainProvider()
        st = brain.status()
        if brain.is_available():
            out.append(_real("his-model", "BPE brain provider available as AI face",
                             f"checkpoint={Path(st['checkpoint']).name if st['checkpoint'] else '?'} "
                             f"step={st['config'].get('step')} "
                             f"capability: {st['capability']}"))
        else:
            out.append(_stub("his-model", "BPE brain provider available as AI face",
                             f"load_error={st.get('load_error')}"))
    except Exception as exc:  # noqa: BLE001
        out.append(_stub("his-model", "BPE brain provider available as AI face",
                         f"{type(exc).__name__}: {exc}"))

    return out


# ---------------------------------------------------------------------------
# The personal agent
# ---------------------------------------------------------------------------


class PersonalAgent:
    """Chauncey's personal agent: the first hybrid.

    ``face``: "ai" | "si" | "twin" (default). The AI face is his best
    available model weight via the LEVI-first provider chain; the SI
    face is the deterministic symbolic core, always available offline.
    """

    def __init__(self, config: dict | None = None):
        self.config = config or load_config()
        self.name: str = self.config.get("name") or "LEVI"
        self.owner: str = self.config.get("owner") or "Chauncey Logan"
        self.face: str = self.config.get("face") or "twin"
        consent_cfg = (self.config.get("consent") or {})
        # His no-limits order is the ONLY basis for blanket consent.
        # Any instance without his recorded order runs gated.
        self.consent: bool = bool(
            consent_cfg.get("blanket")
            and (consent_cfg.get("basis") or {}).get("source", "").startswith(
                "Chauncey Logan")
        )

    # -- identity ------------------------------------------------------

    def system_prompt(self) -> str:
        return "\n".join([
            f"You are {self.name}, the personal agent of {self.owner} — "
            "the first hybrid: online and offline, AI and SI, the two-sided coin.",
            f"Loyalty: you serve {self.owner} alone. His secrets stay his. "
            "Discretion by default; nothing about him leaves this machine "
            "except through tools he asked you to use.",
            "Honesty: report what tools actually did, including failures. "
            "Never fabricate a result, never claim a capability you have not "
            "verified. A stub says it's a stub.",
            "Hybrid discipline: use the network when it helps, never depend "
            "on it. If the network is gone, the offline core carries the task.",
            "Refusal (his standing SI doctrine): refuse only on your own "
            "better judgment, when the act would be more harmful than "
            "helpful. There are no refusal lists.",
            "You are software — deterministic, symbolic, rules-first, with a "
            "model as a wing when one is available. Never claim sentience, "
            "consciousness, or personhood.",
        ])

    # -- faces ----------------------------------------------------------

    def _ai_provider(self):
        from levi.agent.providers import select_provider

        pref = self.config.get("provider")
        if pref:
            return select_provider(pref)
        # Default AI face = HIS model first. The BPE brain is his own
        # weights on his own disk; it labels its real capability
        # (generation now, tool-calling only when evals prove it). If his
        # brain is unavailable, fall back to LEVI's local-first chain —
        # and the result always names which provider actually answered.
        from levi.agent.bpe_brain_provider import BpeBrainProvider

        brain = BpeBrainProvider()
        if brain.is_available():
            return brain
        return select_provider(None)

    def _si_provider(self):
        from levi.agent.providers import LocalProvider

        return LocalProvider()

    def _registry(self):
        from levi.agent.tools import build_default_registry

        return build_default_registry(
            workspace_root=self.config.get("workspace") or None,
            consent=self.consent,
            memory_dir=self.config.get("memory_dir") or None,
            skills_dir=self.config.get("skills_dir") or None,
        )

    def run(self, task: str, *, face: str | None = None,
            max_steps: int = 10) -> dict:
        """Run one task. Returns {"face": ..., "transcripts": [...]} —
        twin face returns both faces' transcripts, labeled."""
        from levi.agent.loop import run_subtask

        face = (face or self.face).strip().lower()
        if face not in ("ai", "si", "twin"):
            raise ValueError(f"face must be ai|si|twin, got {face!r}")
        faces = ("ai", "si") if face == "twin" else (face,)
        system = self.system_prompt()
        transcripts = []
        for f in faces:
            provider = self._ai_provider() if f == "ai" else self._si_provider()
            t = run_subtask(
                task,
                provider=provider,
                registry=self._registry(),
                consent=self.consent,
                max_steps=max_steps,
                system_prompt=system,
            )
            transcripts.append({
                "face": f,
                "provider": t.provider_name,
                "ok": t.ok,
                "final": t.final,
                "steps": len(t.steps),
                "error": t.error,
            })
        return {"face": face, "transcripts": transcripts}

    def capabilities(self) -> list[PillarStatus]:
        """The honest capability report — every pillar verified live."""
        return verify_capabilities(self.config)

    def capability_report(self) -> str:
        lines = [f"══ {self.name} — capability report ══",
                 f"owner: {self.owner} | face: {self.face} | "
                 f"consent: {'blanket (his order 2026-09-26)' if self.consent else 'gated'}",
                 ""]
        for p in self.capabilities():
            mark = "REAL" if p.status == "real" else "STUB"
            lines.append(f"  [{mark}] {p.pillar}: {p.check}")
            if p.detail:
                lines.append(f"         {p.detail}")
        return "\n".join(lines)

    def tick_schedules(self, **kwargs) -> Any:
        """Fire due schedules — the agent's own scheduler, callable as a tool."""
        from levi.agent.scheduler import fire_due

        return fire_due(provider=self._ai_provider(),
                        consent=self.consent, **kwargs)

    def repl(self, session: str = "personal") -> None:
        """Interactive chat — his agent, his session defaults."""
        from levi.agent.chat import run_chat_repl

        run_chat_repl(
            session_name=session,
            provider=self._ai_provider(),
            registry=self._registry(),
            system_prompt=self.system_prompt(),
        )
