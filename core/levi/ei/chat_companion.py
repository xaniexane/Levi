"""
Chat Companion — enterprise-ready conversational surface for LEVI × L.W.P.

The session layer: wraps Orchestrator + offline synthesizer + persona lattice
+ nervous system + daemon control + memory into a session with history, modes,
and REPL. Sibling of ei.companion (guidance layer) and ei.offline_companion
(reply engine) — this one owns the session.

Wraps Orchestrator + offline synthesizer + persona lattice + nervous system +
daemon control + memory into a session with history, modes, and REPL.

Features:
  - Multi-turn history (persisted under ~/.levi/chat_sessions/)
  - Persona lock / auto nervous selection / 230 personas
  - Crisis floor (offline, always-on)
  - Modes: companion | mentor | challenger | writer | builder | quiet
  - Wit calibration + monotropism awareness
  - Optional model relay; offline path always works
  - Export transcript
  - Enterprise: HITL-aware, no silent customer contact, local-first
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional
from pathlib import Path
from datetime import datetime, timezone
import json
import uuid
import re


DEFAULT_DIR = Path.home() / ".levi" / "chat_sessions"

MODES = {
    "companion": "Warm continuity, hold goals, co-regulate.",
    "mentor": "Teach structure; equations, chess, next bridge.",
    "challenger": "Pressure-test plans; no false comfort.",
    "writer": "Literary / L.W.P. bias; offer model expand hooks.",
    "builder": "Factory / rail / scaffold bias; ship next artifact.",
    "quiet": "Minimal words; only the next move.",
}


@dataclass
class ChatMessage:
    role: str  # user | assistant | system
    content: str
    persona_id: str = ""
    mode: str = "companion"
    at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ChatSession:
    id: str
    title: str = "LEVI chat"
    mode: str = "companion"
    persona_id: Optional[str] = None
    messages: List[ChatMessage] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    meta: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "mode": self.mode,
            "persona_id": self.persona_id,
            "messages": [m.to_dict() for m in self.messages],
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "meta": self.meta,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ChatSession":
        msgs = [ChatMessage(**m) for m in d.get("messages") or [] if isinstance(m, dict)]
        return cls(
            id=d.get("id") or str(uuid.uuid4())[:10],
            title=d.get("title") or "LEVI chat",
            mode=d.get("mode") or "companion",
            persona_id=d.get("persona_id"),
            messages=msgs,
            created_at=d.get("created_at") or datetime.now(timezone.utc).isoformat(),
            updated_at=d.get("updated_at") or datetime.now(timezone.utc).isoformat(),
            meta=dict(d.get("meta") or {}),
        )


class ChatCompanion:
    """Enterprise chat companion session."""

    def __init__(
        self,
        session_id: Optional[str] = None,
        persona_id: Optional[str] = None,
        mode: str = "companion",
        directory: Optional[Path] = None,
        profile: Optional[str] = None,
    ):
        self.dir = Path(directory) if directory else DEFAULT_DIR
        self.dir.mkdir(parents=True, exist_ok=True)
        # profile kwarg kept for compat; traits are hardwired — not identity presets
        self.session = self._load_or_create(session_id, persona_id, mode)
        self._orch = None
        if profile:
            self.session.meta["trait_emphasis_request"] = profile

    def _load_or_create(
        self,
        session_id: Optional[str],
        persona_id: Optional[str],
        mode: str,
    ) -> ChatSession:
        if session_id:
            path = self.dir / f"{session_id}.json"
            if path.exists():
                try:
                    return ChatSession.from_dict(json.loads(path.read_text(encoding="utf-8")))
                except Exception:
                    pass
        sid = session_id or str(uuid.uuid4())[:10]
        return ChatSession(id=sid, persona_id=persona_id, mode=mode if mode in MODES else "companion")

    def _persist(self) -> None:
        self.session.updated_at = datetime.now(timezone.utc).isoformat()
        path = self.dir / f"{self.session.id}.json"
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.session.to_dict(), indent=2), encoding="utf-8")
        tmp.replace(path)

    def _get_orch(self):
        if self._orch is None:
            from levi.orchestration.loop import Orchestrator
            self._orch = Orchestrator(persona_id=self.session.persona_id, soft_power=True)
        return self._orch

    def set_persona(self, persona_id: str) -> str:
        from levi.persona.lattice import PersonaLattice
        lat = PersonaLattice()
        if persona_id not in lat.keys() and persona_id != "auto":
            return f"Unknown persona '{persona_id}'. Try: levi personas"
        if persona_id == "auto":
            self.session.persona_id = None
            orch = self._get_orch()
            orch.unlock_persona()
            self._persist()
            return "Persona unlocked — nervous matrix will select."
        self.session.persona_id = persona_id
        self._get_orch().set_persona(persona_id)
        self._persist()
        p = lat.get(persona_id)
        name = p.display_name if p else persona_id
        return f"Persona locked: {name} ({persona_id})"

    def set_profile(self, profile_id: str) -> str:
        """Deprecated name — traits are hardwired, not presets."""
        from levi.ei.mass_chat import format_traits
        return (
            "Traits are hardwired into LEVI (not presets to cosplay other products).\n"
            + format_traits()
        )

    def welcome(self) -> str:
        lines = [
            "I'm LEVI — local synthetic intelligence. No account required.",
            "Hardwired traits (always on): breadth · craft · careful · edge · precision · care · continuity",
            "Tech-giant quality bars inspired these standards — identity stays LEVI SI.",
            "Try: help me plan today · pressure-test this · who are you?",
            "Commands: /traits · /mode quiet · /persona kai_9000_care · /help",
        ]
        return "\n".join(lines)

    def set_mode(self, mode: str) -> str:

        if mode not in MODES:
            return f"Unknown mode. Choose: {', '.join(MODES)}"
        self.session.mode = mode
        self._persist()
        return f"Mode: {mode} — {MODES[mode]}"

    def _mode_prefix(self) -> str:
        m = self.session.mode
        if m == "quiet":
            return "[Mode: quiet — answer in ≤3 short sentences. Only the next move.] "
        if m == "challenger":
            return "[Mode: challenger — pressure-test; name the weakest hinge.] "
        if m == "mentor":
            return "[Mode: mentor — teach structure; use equation/chess when useful.] "
        if m == "writer":
            return "[Mode: writer — literary clarity; offer L.W.P. expand if relevant.] "
        if m == "builder":
            return "[Mode: builder — prefer concrete artifacts, scaffolds, next ship step.] "
        return ""

    def say(self, text: str, verbose: bool = False) -> str:
        """One companion turn. Always returns a usable string (offline-safe)."""
        text = (text or "").strip()
        if not text:
            return "I'm here. Say a goal, a stuck point, or the next move."

        # slash commands inside chat
        if text.startswith("/"):
            return self._slash(text)

        self.session.messages.append(ChatMessage(role="user", content=text, mode=self.session.mode))

        try:
            from levi.ei.mass_chat import trait_block_for_prompt, emphasize_for_text
            trait_prefix = trait_block_for_prompt()
            emp = emphasize_for_text(text)
            if emp:
                trait_prefix += f"[emphasize traits: {', '.join(emp)}] "
        except Exception:
            trait_prefix = ""
        prompt = trait_prefix + self._mode_prefix() + text
        reply = ""
        persona_used = self.session.persona_id or ""
        try:
            orch = self._get_orch()
            result = orch.turn(prompt)
            reply = result.response or ""
            persona_used = result.persona_id or persona_used
            if verbose:
                reply = (
                    f"[intent={result.intent} persona={result.persona_id} "
                    f"specialists={','.join(result.specialists)}]\n\n{reply}"
                )
        except Exception as e:
            # hard fallback offline
            try:
                from levi.ei.offline_companion import synthesize
                reply = synthesize(text)
            except Exception:
                reply = (
                    f"I'm still here (fallback). Core issue: {e}. "
                    "Try a shorter ask, or: levi model status / levi ops"
                )

        if not reply or not str(reply).strip():
            from levi.ei.offline_companion import synthesize
            reply = synthesize(text)

        self.session.messages.append(
            ChatMessage(role="assistant", content=str(reply), persona_id=persona_used, mode=self.session.mode)
        )
        # title from first user line
        if len([m for m in self.session.messages if m.role == "user"]) == 1:
            self.session.title = text[:48] + ("…" if len(text) > 48 else "")
        self._persist()
        return str(reply)

    def _slash(self, text: str) -> str:
        parts = text.strip().split(maxsplit=1)
        cmd = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ""
        if cmd in ("/help", "/?"):
            lines = [
                "Chat commands:",
                "  /traits              hardwired LEVI quality traits (not presets)",
                "  /welcome             mass-friendly intro",
                "  /persona <id|auto>   lock or unlock persona",
                "  /mode <name>         companion|mentor|challenger|writer|builder|quiet",
                "  /personas [q]        list personas (optional filter)",
                "  /status              session + nervous + daemon snapshot",
                "  /history [n]         last n messages",
                "  /export              transcript path",
                "  /clear               clear messages (keep session id)",
                "  /model ...           Full Cloud Model status/expand",
                "  /quit                end REPL",
            ]
            return "\n".join(lines)
        if cmd in ("/traits", "/profile"):
            from levi.ei.mass_chat import format_traits
            return format_traits()
        if cmd == "/welcome":
            return self.welcome()
        if cmd == "/persona":
            return self.set_persona(arg.strip() or "auto")
        if cmd == "/mode":
            return self.set_mode(arg.strip() or "companion")
        if cmd == "/personas":
            return self.list_personas(arg.strip() or None)
        if cmd == "/status":
            return self.status()
        if cmd == "/history":
            n = 10
            if arg.strip().isdigit():
                n = int(arg.strip())
            return self.history(n)
        if cmd == "/export":
            return self.export_transcript()
        if cmd == "/clear":
            self.session.messages.clear()
            self._persist()
            return "Messages cleared."
        if cmd == "/model":
            from levi.cloud.model import FullCloudModel
            m = FullCloudModel()
            sub = (arg.split() or ["status"])[0]
            if sub == "expand":
                return m.expand(1)
            if sub == "status":
                return m.report()
            return m.report()
        if cmd in ("/quit", "/exit"):
            return "__QUIT__"
        return (
            "Try /help /profile spark|edge|care|kai|workbench|careful /mode /persona\n"
            f"Unknown command {cmd}. /help for list."
        )


    def list_personas(self, query: Optional[str] = None) -> str:
        from levi.persona.lattice import PersonaLattice
        lat = PersonaLattice()
        keys = lat.keys()
        core = [k for k in keys if not k.startswith("lens_") and not k.startswith("mood_")]
        q = (query or "").lower()
        if q:
            core = [k for k in core if q in k or q in (lat.get(k).display_name or "").lower()]
            keys_f = [k for k in keys if q in k]
        else:
            keys_f = core[:40]
        lines = [f"Personas: {len(keys)} total · showing {len(keys_f)}"]
        for k in keys_f[:50]:
            p = lat.get(k)
            mark = "▶" if k == self.session.persona_id else " "
            lines.append(f"{mark} {k:28} {p.display_name if p else ''}")
        if not q:
            lines.append("… use /personas <filter> · lenses/moods included in full lattice")
        return "\n".join(lines)

    def history(self, n: int = 10) -> str:
        msgs = self.session.messages[-n:]
        lines = [f"Session {self.session.id} · last {len(msgs)}"]
        for m in msgs:
            prefix = "You" if m.role == "user" else f"LEVI({m.persona_id or '—'})"
            lines.append(f"{prefix}: {m.content[:240]}")
        return "\n".join(lines)

    def export_transcript(self) -> str:
        out = self.dir / f"{self.session.id}_transcript.md"
        lines = [
            f"# LEVI Chat — {self.session.title}",
            f"id={self.session.id} mode={self.session.mode} persona={self.session.persona_id or 'auto'}",
            "",
        ]
        for m in self.session.messages:
            who = "**You**" if m.role == "user" else f"**LEVI** ({m.persona_id or 'auto'})"
            lines.append(f"{who}  \n{m.content}\n")
        out.write_text("\n".join(lines), encoding="utf-8")
        return f"Exported: {out}"

    def status(self) -> str:
        lines = [
            f"══ Chat Companion · session {self.session.id} ══",
            f"title: {self.session.title}",
            f"mode: {self.session.mode} — {MODES.get(self.session.mode, '')}",
            f"persona: {self.session.persona_id or 'auto (nervous matrix)'}",
            f"messages: {len(self.session.messages)}",
        ]
        try:
            from levi.persona.nervous_system import NervousSystem
            from levi.persona.lattice import PersonaLattice
            ns = NervousSystem(persona_ids=PersonaLattice().keys())
            lines.append("")
            lines.append(ns.format_status().split("\n")[0] if hasattr(ns, "format_status") else "nervous: ok")
        except Exception as e:
            lines.append(f"nervous: {e}")
        try:
            from levi.daemon.kernel import DaemonKernel
            k = DaemonKernel()
            lines.append(f"daemon estop={k.state.estop} cycle={getattr(k.state, 'cycle', 0)}")
        except Exception:
            pass
        try:
            from levi.cloud.stages import current_stage
            cp = current_stage()
            lines.append(f"phase: {cp.id}/{cp.status}")
        except Exception:
            pass
        lines.append(f"path: {self.dir / (self.session.id + '.json')}")
        return "\n".join(lines)

    def repl(self) -> None:
        """Interactive REPL (stdin)."""
        print(self.status())
        print(self.welcome()); print("\nType /help · /quit to exit\n")
        while True:
            try:
                line = input("you> ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n[session saved]")
                break
            if not line:
                continue
            out = self.say(line)
            if out == "__QUIT__":
                print("[session saved]")
                break
            print(f"\nlevi> {out}\n")


def list_sessions(directory: Optional[Path] = None) -> List[Dict[str, Any]]:
    d = Path(directory) if directory else DEFAULT_DIR
    if not d.exists():
        return []
    rows = []
    for p in sorted(d.glob("*.json")):
        if p.name.endswith("_transcript.md"):
            continue
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            rows.append({
                "id": data.get("id"),
                "title": data.get("title"),
                "mode": data.get("mode"),
                "messages": len(data.get("messages") or []),
                "updated_at": data.get("updated_at"),
            })
        except Exception:
            continue
    return rows
