"""The Turn Packet — Minimal Sufficient Context, LEVI-native.

REIM compost of the feed pattern (a "minimal sufficient context" runtime):
  1. Fragile single-maintainer beta that warns against load-bearing use.
     LEVI's answer: stdlib-only, fully tested, honest degradation.
  2. Model-swapping as identity — swap Claude/GPT/DeepSeek/Gemini mid-project.
     LEVI's answer: the packet is brain-agnostic but LEVI-first. LEVI's own
     brain is the identity; providers are transports, never the self.
  3. Silent lossiness — "minimal" with no accounting of what was cut.
     LEVI's answer: every packet carries a manifest. Every section is
     recorded as included / truncated / excluded, with the reason.
     Nothing is cut silently.

RIEM genome:
  - One deterministic packet per turn: priority-ordered sections under a
    hard character budget (chars, not estimated tokens — deterministic).
  - The packet is reproducible evidence: its SHA-256 digest is stable for
    identical inputs, so a turn's context is auditable after the fact and
    slots into the bloodstream's Verify -> Receipt discipline.
  - Sections in priority order:
      oath      pinned LEVI identity line (always first, tiny)
      task      the current task (always)
      receipts  sealed turn receipts — evidence, not raw history
      summary   rolling summary of compressed history
      recent    unsummarized tail, bounded
      facts     pinned durable facts from session scratch memory
      growth    growth-loop advisory addendum
      tools     the tool schemas this turn may call (documented, bounded)
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Iterable, Sequence

#: Default per-turn budget, in characters. Deterministic: chars, not tokens.
DEFAULT_BUDGET_CHARS = 8000

#: Floor for a partial section: below this many chars a section is excluded
#: outright instead of being truncated to a stub.
MIN_PARTIAL_CHARS = 64

#: Truncation marker appended to cut sections. Never silent.
CUT_MARKER = "…[cut {n} chars]"

#: Pinned identity line. Small on purpose: it rides every packet.
OATH_LINE = (
    "Not artificial. Synthetic. LEVI-native brain; "
    "providers are transports, never the self."
)

# (section name, priority, max chars when fully included)
SECTION_SPECS: tuple[tuple[str, int, int], ...] = (
    ("oath", 0, 400),
    ("task", 1, 2000),
    ("receipts", 2, 1500),
    ("summary", 3, 2500),
    ("recent", 4, 4000),
    ("facts", 5, 1500),
    ("growth", 6, 1000),
    ("tools", 7, 3000),
)


@dataclass(frozen=True)
class SectionResult:
    """One section's fate inside a packet."""

    name: str
    status: str  # "included" | "truncated" | "excluded"
    chars: int
    reason: str = ""
    content: str = ""  # only for included/truncated


@dataclass
class Packet:
    """A built turn packet: sections, manifest, and content digest."""

    sections: list[SectionResult] = field(default_factory=list)
    budget_chars: int = DEFAULT_BUDGET_CHARS

    @property
    def used_chars(self) -> int:
        return sum(s.chars for s in self.sections if s.status != "excluded")

    def digest(self) -> str:
        """SHA-256 over the canonical render. Stable for identical inputs."""
        h = hashlib.sha256()
        h.update(self._canonical().encode("utf-8"))
        return h.hexdigest()

    def _canonical(self) -> str:
        parts = [f"budget={self.budget_chars}"]
        for s in self.sections:
            if s.status == "excluded":
                parts.append(f"[{s.name}:excluded:{s.reason}]")
            else:
                parts.append(f"[{s.name}:{s.status}:{s.chars}]\n{s.content}")
        return "\n".join(parts)

    def manifest(self) -> dict[str, Any]:
        return {
            "budget_chars": self.budget_chars,
            "used_chars": self.used_chars,
            "digest": self.digest(),
            "sections": [
                {
                    "name": s.name,
                    "status": s.status,
                    "chars": s.chars,
                    "reason": s.reason,
                }
                for s in self.sections
            ],
        }

    def render(self) -> str:
        """Human- and model-readable packet text."""
        lines = [
            "═══ TURN PACKET ═══",
            f"digest sha256:{self.digest()[:16]}…  "
            f"budget {self.budget_chars} chars / used {self.used_chars}",
            "",
        ]
        for s in self.sections:
            if s.status == "excluded":
                continue
            tag = "" if s.status == "included" else f" ({s.status}: {s.reason})"
            lines.append(f"[§{s.name} · {s.chars} chars{tag}]")
            lines.append(s.content)
            lines.append("")
        lines.append("─── manifest ───")
        for s in self.sections:
            detail = f"{s.status} ({s.chars} chars)"
            if s.reason:
                detail += f" — {s.reason}"
            lines.append(f"{s.name}: {detail}")
        return "\n".join(lines).rstrip() + "\n"


def _truncate(content: str, allowance: int) -> tuple[str, int]:
    """Cut content to fit allowance, marking the cut honestly.

    The marker itself lives inside the allowance, and the reported count
    is the true number of removed characters. Converges in <=2 passes
    (the marker only shifts length when the digit count of n changes).
    """
    if len(content) <= allowance:
        return content, 0
    keep = allowance
    for _ in range(3):
        marker = CUT_MARKER.format(n=len(content) - keep)
        new_keep = max(0, allowance - len(marker))
        if new_keep == keep:
            break
        keep = new_keep
    marker = CUT_MARKER.format(n=len(content) - keep)
    return content[:keep] + marker, len(content) - keep


def build_packet(
    sources: dict[str, str] | None = None,
    *,
    budget_chars: int = DEFAULT_BUDGET_CHARS,
) -> Packet:
    """Assemble a turn packet from named source strings.

    ``sources`` maps section names (oath/task/receipts/summary/recent/facts/
    growth/tools) to their text. Missing or empty sections are recorded as
    excluded with reason "empty". Sections are filled in priority order;
    when the budget runs out, remaining sections are excluded with reason
    "budget exhausted" — never silently dropped.
    """
    sources = sources or {}
    packet = Packet(budget_chars=max(1, int(budget_chars)))
    remaining = packet.budget_chars

    for name, _prio, cap in SECTION_SPECS:
        raw = (sources.get(name) or "").strip()
        if not raw:
            packet.sections.append(SectionResult(name, "excluded", 0, reason="empty"))
            continue
        allowance = min(cap, remaining)
        if allowance <= 0:
            packet.sections.append(
                SectionResult(name, "excluded", 0, reason="budget exhausted")
            )
            continue
        if len(raw) <= allowance:
            packet.sections.append(
                SectionResult(name, "included", len(raw), content=raw)
            )
            remaining -= len(raw)
        elif allowance >= MIN_PARTIAL_CHARS:
            cut_text, _cut = _truncate(raw, allowance)
            packet.sections.append(
                SectionResult(
                    name,
                    "truncated",
                    len(cut_text),
                    reason=f"cut {len(raw) - len(cut_text)} chars (over section cap / budget)",
                    content=cut_text,
                )
            )
            remaining -= len(cut_text)
        else:
            packet.sections.append(
                SectionResult(
                    name,
                    "excluded",
                    0,
                    reason=f"only {allowance} chars left (below {MIN_PARTIAL_CHARS} floor)",
                )
            )
    return packet


def format_receipts(turn_metas: Sequence[dict[str, Any]], limit: int = 5) -> str:
    """Render sealed turn receipts: evidence lines, newest last."""
    lines = []
    for meta in list(turn_metas)[-limit:]:
        ok = "ok" if meta.get("ok") else "FAILED"
        lines.append(
            "turn: provider=%s status=%s steps=%s"
            % (meta.get("provider", "?"), ok, meta.get("steps", "?"))
        )
    return "\n".join(lines)


def format_tools(tools: Iterable[tuple[str, str]], desc_chars: int = 80) -> str:
    """Render tool inventory: name + short description, one per line."""
    return "\n".join(f"{name}: {desc[:desc_chars]}" for name, desc in tools)


def packet_for_conversation(
    conv: Any,
    *,
    task: str = "",
    budget_chars: int = DEFAULT_BUDGET_CHARS,
    tool_names: Sequence[str] | None = None,
) -> Packet:
    """Build a turn packet from a live ``ConversationManager``.

    Pulls only through the conversation's own public seams: session summary,
    working-context tail, sealed turn receipts, scratch-memory facts, and
    the tool registry. Growth context is attached when available; its
    absence is recorded in the manifest, not hidden.
    """
    sources: dict[str, str] = {"oath": OATH_LINE, "task": task}

    records = list(getattr(conv.session, "records", []) or [])
    sources["receipts"] = format_receipts(
        [r for r in records if r.get("kind") == "turn-meta"]
    )

    summary_text, _covers = conv.session.summary()
    sources["summary"] = summary_text or ""

    try:
        tail = conv._context_messages()[-12:]
    except Exception:
        tail = []
    sources["recent"] = "\n".join(
        f"{m.role}: {m.content}" for m in tail if getattr(m, "content", "")
    )

    try:
        sources["facts"] = conv.read_facts() or ""
    except Exception:
        sources["facts"] = ""

    growth_text = ""
    try:
        from levi.agent import growth_context as _growth_context

        growth_text = _growth_context.context_addendum(task or "", limit=3) or ""
    except Exception:
        growth_text = ""
    sources["growth"] = growth_text

    registry = getattr(conv, "registry", None)
    if registry is None:
        try:
            from levi.agent.tools import build_default_registry

            registry = build_default_registry(
                workspace_root=getattr(conv, "workspace_root", None)
            )
        except Exception:
            registry = None
    tool_list: list[tuple[str, str]] = []
    if registry is not None:
        try:
            for tool in registry.list():
                if tool_names is not None and tool.name not in tool_names:
                    continue
                tool_list.append((tool.name, tool.description or ""))
        except Exception:
            tool_list = []
    sources["tools"] = format_tools(tool_list)

    return build_packet(sources, budget_chars=budget_chars)
