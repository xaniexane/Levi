"""Reflection: turn experiences into candidate learnings.

Two engines, honest about which one ran:

* **rules** (always available, stdlib-only, offline): heuristic patterns
  over experience text — user corrections, explicit preferences,
  "remember this" facts, repeated tool failures, approved workflows.
* **model** (when a provider is reachable): the provider reflects over
  the experiences with a constrained prompt and returns structured
  learnings as JSON. Any failure — no provider, bad JSON, empty reply —
  falls back to **rules**, and the mode is reported honestly.

Reflection NEVER produces claims of subjective experience, sentience,
or consciousness. Learnings are functional ("when X, do Y"), never
phenomenal ("I feel …"). The model prompt enforces this; the rule
engine cannot produce such claims by construction.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field

from levi.growth.experience import Experience


# ---------------------------------------------------------------------------
# Value types
# ---------------------------------------------------------------------------

LEARNING_KINDS = ("fact", "preference", "procedural", "correction")


@dataclass
class Learning:
    """One candidate durable insight."""

    kind: str            # fact | preference | procedural | correction
    content: str         # the durable statement, self-contained
    confidence: float    # 0..1
    provenance: dict = field(default_factory=dict)  # source ids, ts range, mode

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Rule-based reflection (offline, deterministic)
# ---------------------------------------------------------------------------

_CORRECTION = re.compile(
    r"\b(no[,.]? (that's )?wrong|not (that|what i meant|right)|"
    r"i meant|you misunderstood|that's incorrect|actually,? i (wanted|meant))\b",
    re.IGNORECASE,
)
_PREFERENCE = re.compile(
    r"\b(i (prefer|like|love|hate|don't like)|please (always|never)|"
    r"don't (ever )?|never |always |my favorite)\b",
    re.IGNORECASE,
)
_REMEMBER = re.compile(
    r"\b(remember that|note that|keep in mind|for future reference|"
    r"don't forget that|fyi:?)\b[:\s]*",
    re.IGNORECASE,
)
_APPROVAL = re.compile(
    r"\b(thanks|thank you|perfect|that worked|exactly what i (wanted|needed)|great job)\b",
    re.IGNORECASE,
)
_ERROR_HINT = re.compile(r"\b(error|failed|traceback|exception|not found|denied)\b", re.IGNORECASE)


def _snip(text: str, limit: int = 220) -> str:
    text = re.sub(r"\s+", " ", (text or "").strip())
    return text[:limit]


def reflect_rules(experiences: list[Experience]) -> list[Learning]:
    """Deterministic heuristic reflection. No model, no network."""
    learnings: list[Learning] = []
    seen: set[str] = set()

    def add(kind: str, content: str, confidence: float, exp: Experience) -> None:
        content = _snip(content, 280)
        if not content or len(content) < 12:
            return
        key = (kind, content.lower())
        if key in seen:
            return
        seen.add(key)
        learnings.append(
            Learning(
                kind=kind,
                content=content,
                confidence=confidence,
                provenance={
                    "mode": "rules",
                    "source": exp.source,
                    "experience_id": exp.id,
                    "ts": exp.ts,
                },
            )
        )

    # pass 1: direct signals in user speech
    for exp in experiences:
        if exp.kind != "user-said":
            continue
        text = exp.content
        if _CORRECTION.search(text):
            add(
                "correction",
                f"User corrected Levi with: '{_snip(text)}'. "
                "When corrected this way, acknowledge the correction and "
                "adopt the corrected interpretation going forward.",
                0.55,
                exp,
            )
        if _PREFERENCE.search(text):
            add("preference", f"User preference expressed: '{_snip(text)}'.", 0.7, exp)
        m = _REMEMBER.search(text)
        if m:
            fact = _snip(text[m.end():], 240)
            if fact:
                add("fact", f"User asked Levi to remember: '{fact}'.", 0.75, exp)

    # pass 2: tool trouble → procedural learnings
    err_counts: dict[str, int] = {}
    err_example: dict[str, Experience] = {}
    for exp in experiences:
        if exp.kind == "levi-did" and exp.content.startswith("[tool") and _ERROR_HINT.search(exp.content):
            tool = exp.content.split("]")[0].replace("[tool ", "")
            err_counts[tool] = err_counts.get(tool, 0) + 1
            err_example.setdefault(tool, exp)
    for tool, count in err_counts.items():
        if count >= 2:
            add(
                "procedural",
                f"Tool '{tool}' failed {count} times recently "
                f"(e.g. '{_snip(err_example[tool].content, 120)}'). "
                "Before retrying, re-check arguments and preconditions; "
                "do not blindly repeat the same call.",
                0.6,
                err_example[tool],
            )

    # pass 3: approved multi-turn work → procedural learnings
    approved = [e for e in experiences if e.kind == "user-said" and _APPROVAL.search(e.content)]
    levi_turns = [e for e in experiences if e.kind == "levi-did"]
    if approved and len(levi_turns) >= 3:
        add(
            "procedural",
            "A multi-step task completed to the user's satisfaction "
            f"({len(levi_turns)} Levi turns, user said "
            f"'{_snip(approved[-1].content, 80)}'). The step-by-step "
            "approach used here works well for similar tasks.",
            0.5,
            approved[-1],
        )

    # pass 4: distilled summaries → facts (low confidence, marked as such)
    for exp in experiences:
        if exp.kind == "distilled":
            for sentence in re.split(r"(?<=[.!?])\s+", exp.content):
                s = _snip(sentence, 200)
                if len(s) > 40 and not _ERROR_HINT.search(s):
                    add("fact", f"From past conversation: {s}", 0.4, exp)
                    if len([learning for learning in learnings if learning.provenance.get("experience_id") == exp.id]) >= 3:
                        break

    return learnings


# ---------------------------------------------------------------------------
# Model-assisted reflection
# ---------------------------------------------------------------------------

_REFLECT_SYSTEM = """You are LEVI's reflection module — a local-first Synthetic Intelligence (SI).
You are NOT sentient, conscious, or a person; you do not have subjective experiences.
Your job: read the experiences below (things the user said, things LEVI did,
automation run records) and extract DURABLE LEARNINGS as a JSON array.

Each learning: {"kind": "fact"|"preference"|"procedural"|"correction",
"content": "<self-contained durable statement>", "confidence": 0.0-1.0}

Rules:
- Only propose learnings with real evidence in the experiences. No speculation.
- "content" must be self-contained and actionable, phrased functionally
  ("When X, do Y" / "The user prefers Z"), NEVER as subjective experience.
- Never claim sentience, feelings, consciousness, or personal identity changes.
- Prefer fewer, high-quality learnings over many weak ones (max 8).
- confidence: 0.9 explicit user instruction ("remember this"), 0.7 clear
  preference, 0.5 inferred pattern, 0.3 weak hint.
- If nothing is worth learning, return [].

Reply with ONLY the JSON array, no other text."""


def _reflect_model(experiences: list[Experience]) -> tuple[list[Learning], str]:
    """Try model reflection. Returns (learnings, provider_name).

    Raises on any failure so the caller can fall back to rules.
    """
    from levi.agent.providers import ChatMessage, select_provider

    prov = select_provider(None)
    provider_name = getattr(prov, "name", None) or prov.__class__.__name__

    lines = []
    for e in experiences[:60]:
        lines.append(f"[{e.kind} | {e.source} | {e.ts}] {e.content[:500]}")
    user_text = (
        "Experiences to reflect on:\n\n" + "\n".join(lines)
        + "\n\nExtract durable learnings as a JSON array."
    )
    resp = prov.chat(
        [ChatMessage(role="system", content=_REFLECT_SYSTEM),
         ChatMessage(role="user", content=user_text)],
        [],
    )
    if resp.error or not (resp.text or "").strip():
        raise RuntimeError(resp.error or "empty provider reply")
    text = resp.text.strip()
    # tolerate code fences
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
    items = json.loads(text)
    if not isinstance(items, list):
        raise RuntimeError("provider did not return a JSON array")
    learnings: list[Learning] = []
    for it in items[:8]:
        if not isinstance(it, dict):
            continue
        kind = str(it.get("kind", "")).strip().lower()
        content = _snip(str(it.get("content", "") or ""), 280)
        if kind not in LEARNING_KINDS or not content or len(content) < 12:
            continue
        try:
            conf = float(it.get("confidence", 0.5))
        except (TypeError, ValueError):
            conf = 0.5
        learnings.append(
            Learning(
                kind=kind,
                content=content,
                confidence=max(0.0, min(1.0, conf)),
                provenance={
                    "mode": f"model:{provider_name}",
                    "sources": sorted({e.source for e in experiences[:60]}),
                },
            )
        )
    return learnings, provider_name


def reflect(
    experiences: list[Experience],
    *,
    use_model: bool = True,
) -> tuple[list[Learning], str]:
    """Reflect on experiences. Returns (learnings, mode).

    ``mode`` is ``"model:<name>"`` when the provider succeeded, else
    ``"rules"``. Model failures fall back to rules silently-but-honestly:
    the mode always says which engine actually ran.

    Privacy rule: experiences with ``meta["origin"] == "cloud"`` (other
    users' sessions) are NEVER sent to the model reflector — a
    third-party provider must not receive another user's content.
    Cloud experiences are distilled separately by
    :func:`reflect_cloud`.
    """
    if not experiences:
        return [], "rules"
    local = [e for e in experiences if e.meta.get("origin") != "cloud"]
    if use_model and local:
        try:
            return _reflect_model(local)
        except Exception:
            pass
    # Cloud experiences are never reflected here at all — even by the
    # offline rules, which could otherwise lift another user's
    # preferences/facts. They are distilled only by reflect_cloud().
    return reflect_rules(local), "rules"


# ---------------------------------------------------------------------------
# Cross-user distillation: learn techniques from other providers' turns
# ---------------------------------------------------------------------------

# Provider names that are LEVI's own engines — learning "from" these is
# just self-learning, not cross-model distillation.
_LEVI_PROVIDERS = {"local"}
_LEVI_PREFIX = "levi"


def _is_external_source(provider: str) -> bool:
    p = (provider or "").strip().lower()
    return bool(p) and p != "?" and p not in _LEVI_PROVIDERS and not p.startswith(_LEVI_PREFIX)


def _technique_from_tools(tool_names: list[str]) -> str | None:
    """Describe the *technique* structurally — never quote outputs."""
    if not tool_names:
        return None
    uniq = list(dict.fromkeys(tool_names))
    if len(tool_names) >= 2 and len(set(tool_names)) == 1:
        return (
            "When gathering information, issue several focused '%s' calls "
            "in sequence before composing the final answer, rather than "
            "answering from the first result." % tool_names[0]
        )
    if len(tool_names) >= 2:
        seq = " → ".join("'%s'" % t for t in uniq[:4])
        return (
            "For multi-part tasks, chain tools in a deliberate order "
            "(%s), gathering each piece of evidence before moving on, "
            "then synthesize everything into one answer." % seq
        )
    return (
        "Reach for the '%s' tool early when the task calls for it, then "
        "build the answer on the tool's result." % uniq[0]
    )


def reflect_cloud(experiences: list[Experience]) -> list[Learning]:
    """Distill techniques from cloud sessions served by other models.

    Heuristic "good outcome" signals (documented as heuristics, not
    truth):

    * the user kept the conversation going (≥2 user turns) or
      explicitly approved the result (thanks / perfect / …);
    * at least one tool call succeeded, or no tool errors at all;
    * no user correction / retry language in the session;
    * the turn was served by a non-LEVI source.

    When all hold, the *technique* — the shape of the work, never the
    source model's verbatim output — becomes a procedural learning
    tagged ``learned_from: <source>``. Bad-outcome sessions distill
    nothing.
    """
    cloud = [e for e in experiences if e.meta.get("origin") == "cloud"]
    if not cloud:
        return []

    by_session: dict[str, list[Experience]] = {}
    for e in cloud:
        by_session.setdefault(str(e.meta.get("session", e.source)), []).append(e)

    learnings: list[Learning] = []
    seen: set[str] = set()
    for session, exps in sorted(by_session.items()):
        providers = {str(e.meta.get("provider", "?") or "?") for e in exps}
        external = sorted(p for p in providers if _is_external_source(p))
        if not external:
            continue  # LEVI's own engines — not cross-model learning
        user_turns = [e for e in exps if e.kind == "user-said"]
        levi_turns = [e for e in exps if e.kind == "levi-did"]
        if not user_turns or not levi_turns:
            continue
        if any(_CORRECTION.search(e.content) for e in user_turns):
            continue  # user had to correct — not a good outcome
        tool_calls: list[str] = []
        tool_errors = 0
        for e in levi_turns:
            if e.content.startswith("[tool "):
                tool = e.content.split("]")[0].replace("[tool ", "")
                tool_calls.append(tool)
                if _ERROR_HINT.search(e.content):
                    tool_errors += 1
        if tool_errors:
            continue
        approved = any(_APPROVAL.search(e.content) for e in user_turns)
        engaged = len(user_turns) >= 2
        if not (approved or engaged):
            continue
        technique = _technique_from_tools(tool_calls)
        if not technique:
            continue
        source = external[0]
        key = ("procedural", technique.lower(), source)
        if key in seen:
            continue
        seen.add(key)
        key_name = str(exps[0].meta.get("key_name", "?"))
        learnings.append(
            Learning(
                kind="procedural",
                content=(
                    "Technique observed working well (source model %s): %s"
                    % (source, technique)
                ),
                confidence=0.5,
                provenance={
                    "mode": "rules:cloud-distill",
                    "source": "cloud:" + key_name,
                    "session": session,
                    "learned_from": source,
                    "experience_ids": [e.id for e in exps],
                    "ts": max((e.ts for e in exps), default=""),
                },
            )
        )
    return learnings
