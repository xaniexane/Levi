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
from levi.growth.guards import check_no_sentience_claim


# ---------------------------------------------------------------------------
# Value types
# ---------------------------------------------------------------------------

LEARNING_KINDS = ("fact", "preference", "procedural", "correction")


@dataclass
class Learning:
    """One candidate durable insight."""

    kind: str  # fact | preference | procedural | correction
    content: str  # the durable statement, self-contained
    confidence: float  # 0..1
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
_ERROR_HINT = re.compile(
    r"\b(error|failed|traceback|exception|not found|denied)\b", re.IGNORECASE
)


def _snip(text: str, limit: int = 220) -> str:
    text = re.sub(r"\s+", " ", (text or "").strip())
    return text[:limit]


def reflect_rules(experiences: list[Experience]) -> list[Learning]:
    """Deterministic heuristic reflection. No model, no network.

    Thin wrapper over :func:`reflect_rules_detailed`; see that function
    for the extractor inventory.

    Raises ValueError when ``experiences`` is not a list of Experience
    objects.
    """
    learnings, _evidence = reflect_rules_detailed(experiences)
    return learnings


def reflect_rules_detailed(
    experiences: list[Experience],
) -> tuple[list[Learning], dict[str, int]]:
    """Deterministic heuristic reflection, with per-extractor evidence.

    Returns ``(learnings, evidence)`` where ``evidence`` maps extractor
    name → number of learnings it produced this run. The cycle journals
    this breakdown so growth is observable: Chauncey can see *why* the
    loop thinks it learned something.

    Extractor inventory (all offline, all deterministic):

    * ``direct_signals`` — corrections, preferences, "remember this"
      facts in user speech (passes 1);
    * ``tool_trouble`` — a tool erroring ≥2 times (pass 2);
    * ``approved_workflows`` — approved multi-turn work (pass 3);
    * ``distilled_facts`` — session summaries → low-confidence facts
      (pass 4);
    * ``recurring_topics`` — a content word recurring across ≥3 user
      turns in ≥2 sources → an active area of the user's interest;
    * ``failed_then_fixed`` — a tool failed, then later succeeded:
      prefer recovery over blind retry;
    * ``capability_gaps`` — Levi explicitly declined ("I can't …"):
      an observed boundary of what it can do;
    * ``automation_outcomes`` — automation run records: stable
      cadences and recent failures worth a look;
    * ``repeated_requests`` — the user asking near-identical things
      ≥3 times: a recurring need to watch for proactively;
    * ``blocked_sentience`` — candidate learnings dropped by the
      sentience-claim rail (never written, always counted).

    Every candidate learning passes the sentience blocklist
    (:mod:`levi.growth.guards`) before it is emitted.

    Raises ValueError when ``experiences`` is not a list of Experience
    objects.
    """
    if not isinstance(experiences, list):
        raise ValueError(
            "reflect_rules: experiences must be a list, got %s"
            % type(experiences).__name__
        )
    for e in experiences:
        if not isinstance(e, Experience):
            raise ValueError(
                "reflect_rules: experiences must contain Experience objects, got %s"
                % type(e).__name__
            )
    learnings: list[Learning] = []
    seen: set[str] = set()
    evidence: dict[str, int] = {}

    def add(
        extractor: str,
        kind: str,
        content: str,
        confidence: float,
        exp: Experience,
    ) -> bool:
        content = _snip(content, 280)
        if not content or len(content) < 12:
            return False
        key = (kind, content.lower())
        if key in seen:
            return False
        # Binding rail: no sentience/subjective-experience claims, ever.
        # A user quote that trips the blocklist costs the learning, not
        # the rule — counted, never rephrased.
        if check_no_sentience_claim(content):
            evidence["blocked_sentience"] = evidence.get("blocked_sentience", 0) + 1
            return False
        seen.add(key)
        learnings.append(
            Learning(
                kind=kind,
                content=content,
                confidence=confidence,
                provenance={
                    "mode": "rules",
                    "extractor": extractor,
                    "source": exp.source,
                    "experience_id": exp.id,
                    "ts": exp.ts,
                },
            )
        )
        evidence[extractor] = evidence.get(extractor, 0) + 1
        return True

    _extract_direct_signals(experiences, add)
    _extract_tool_trouble(experiences, add)
    _extract_approved_workflows(experiences, add)
    _extract_distilled_facts(experiences, add)
    _extract_recurring_topics(experiences, add)
    _extract_failed_then_fixed(experiences, add)
    _extract_capability_gaps(experiences, add)
    _extract_automation_outcomes(experiences, add)
    _extract_repeated_requests(experiences, add)
    return learnings, evidence


# ---------------------------------------------------------------------------
# Rule extractors
# ---------------------------------------------------------------------------


def _extract_direct_signals(experiences, add) -> None:
    """Pass 1: direct signals in user speech."""
    for exp in experiences:
        if exp.kind != "user-said":
            continue
        text = exp.content
        if _CORRECTION.search(text):
            add(
                "direct_signals",
                "correction",
                f"User corrected Levi with: '{_snip(text)}'. "
                "When corrected this way, acknowledge the correction and "
                "adopt the corrected interpretation going forward.",
                0.55,
                exp,
            )
        if _PREFERENCE.search(text):
            add(
                "direct_signals",
                "preference",
                f"User preference expressed: '{_snip(text)}'.",
                0.7,
                exp,
            )
        m = _REMEMBER.search(text)
        if m:
            fact = _snip(text[m.end() :], 240)
            if fact:
                add(
                    "direct_signals",
                    "fact",
                    f"User asked Levi to remember: '{fact}'.",
                    0.75,
                    exp,
                )


def _extract_tool_trouble(experiences, add) -> None:
    """Pass 2: tool trouble → procedural learnings."""
    err_counts: dict[str, int] = {}
    err_example: dict[str, Experience] = {}
    for exp in experiences:
        if (
            exp.kind == "levi-did"
            and exp.content.startswith("[tool")
            and _ERROR_HINT.search(exp.content)
        ):
            tool = exp.content.split("]")[0].replace("[tool ", "")
            err_counts[tool] = err_counts.get(tool, 0) + 1
            err_example.setdefault(tool, exp)
    for tool, count in err_counts.items():
        if count >= 2:
            add(
                "tool_trouble",
                "procedural",
                f"Tool '{tool}' failed {count} times recently "
                f"(e.g. '{_snip(err_example[tool].content, 120)}'). "
                "Before retrying, re-check arguments and preconditions; "
                "do not blindly repeat the same call.",
                0.6,
                err_example[tool],
            )


def _extract_approved_workflows(experiences, add) -> None:
    """Pass 3: approved multi-turn work → procedural learnings."""
    approved = [
        e for e in experiences if e.kind == "user-said" and _APPROVAL.search(e.content)
    ]
    levi_turns = [e for e in experiences if e.kind == "levi-did"]
    if approved and len(levi_turns) >= 3:
        add(
            "approved_workflows",
            "procedural",
            "A multi-step task completed to the user's satisfaction "
            f"({len(levi_turns)} Levi turns, user said "
            f"'{_snip(approved[-1].content, 80)}'). The step-by-step "
            "approach used here works well for similar tasks.",
            0.5,
            approved[-1],
        )


def _extract_distilled_facts(experiences, add) -> None:
    """Pass 4: distilled summaries → facts (low confidence, marked as such)."""
    for exp in experiences:
        if exp.kind == "distilled":
            per_exp = 0
            for sentence in re.split(r"(?<=[.!?])\s+", exp.content):
                s = _snip(sentence, 200)
                if len(s) > 40 and not _ERROR_HINT.search(s):
                    if add(
                        "distilled_facts",
                        "fact",
                        f"From past conversation: {s}",
                        0.4,
                        exp,
                    ):
                        per_exp += 1
                    if per_exp >= 3:
                        break  # cap: at most 3 facts per summary


# ---------------------------------------------------------------------------
# New offline extractors (deterministic; enrich the rules engine)
# ---------------------------------------------------------------------------

_TOPIC_WORD = re.compile(r"[a-z0-9][a-z0-9\-]{2,}")
_TOPIC_STOP = frozenset(
    "the and for with that this from have has had were was are but not you your "
    "levi when what which while where their there then than them they our out can "
    "will would should could about into over after before between through during "
    "please thank thanks just like dont don't get got one two also very much more "
    "how why all any its it's into".split()
)
_INABILITY = re.compile(
    r"\b(i (can't|cannot|don't have|won't be able to|am not able to)|"
    r"i'm not able to|i don't have access to|not something i can|"
    r"beyond what i can|i have no way to)\b",
    re.IGNORECASE,
)


def _topic_words(text: str) -> set[str]:
    return {
        w
        for w in _TOPIC_WORD.findall((text or "").lower())
        if w not in _TOPIC_STOP and not w.isdigit()
    }


def _extract_recurring_topics(experiences, add) -> None:
    """A content word recurring across ≥3 user turns in ≥2 sources.

    Becomes a fact about the user's *active interest area* — the kind
    of thing a growing assistant should proactively watch for.
    """
    hits: dict[str, dict[str, set[str]]] = {}
    user_exps = [e for e in experiences if e.kind == "user-said"]
    for exp in user_exps:
        for word in _topic_words(exp.content):
            cell = hits.setdefault(word, {"turns": set(), "sources": set()})
            cell["turns"].add(exp.id)
            cell["sources"].add(exp.source)
    ranked = sorted(
        (
            (word, cell)
            for word, cell in hits.items()
            if len(cell["turns"]) >= 3 and len(cell["sources"]) >= 2
        ),
        key=lambda wc: (-len(wc[1]["turns"]), wc[0]),
    )
    for word, cell in ranked[:3]:
        example = next(e for e in user_exps if e.id in cell["turns"])
        add(
            "recurring_topics",
            "fact",
            f"The user's recent sessions keep returning to '{word}' "
            f"({len(cell['turns'])} mentions across {len(cell['sources'])} sessions, "
            f"e.g. '{_snip(example.content, 100)}'). Treat this as an active "
            "area of interest; offer proactive help on it.",
            0.55,
            example,
        )


def _extract_failed_then_fixed(experiences, add) -> None:
    """A tool failed, then later succeeded: learn the recovery pattern."""
    first_err: dict[str, Experience] = {}
    later_ok: dict[str, Experience] = {}
    for exp in experiences:
        if exp.kind != "levi-did" or not exp.content.startswith("[tool"):
            continue
        tool = exp.content.split("]")[0].replace("[tool ", "")
        if _ERROR_HINT.search(exp.content):
            first_err.setdefault(tool, exp)
        else:
            later_ok[tool] = exp  # keep the latest success
    for tool, err_exp in first_err.items():
        ok_exp = later_ok.get(tool)
        if ok_exp is None:
            continue
        if ok_exp.ts and err_exp.ts and ok_exp.ts <= err_exp.ts:
            continue  # success wasn't after the failure
        add(
            "failed_then_fixed",
            "procedural",
            f"Tool '{tool}' failed ('{_snip(err_exp.content, 90)}') and later "
            "succeeded. When this tool fails, change something (arguments, "
            "preconditions, or approach) before retrying — the plain repeat "
            "is what failed.",
            0.55,
            err_exp,
        )


def _extract_capability_gaps(experiences, add) -> None:
    """Levi explicitly declined ("I can't …") — an observed boundary."""
    for exp in experiences:
        if exp.kind != "levi-did":
            continue
        if _INABILITY.search(exp.content):
            add(
                "capability_gaps",
                "fact",
                f"Observed capability boundary: Levi declined a request — "
                f"'{_snip(exp.content, 140)}'. When asked for this kind of "
                "thing again, say plainly it is out of reach and offer the "
                "nearest in-reach alternative instead of hedging.",
                0.6,
                exp,
            )


def _extract_automation_outcomes(experiences, add) -> None:
    """Automation run records: stable cadences and recent failures."""
    for exp in experiences:
        if exp.kind != "automation":
            continue
        runs = int(exp.meta.get("run_count", 0) or 0)
        status = str(exp.meta.get("status", "?") or "?")
        failed = _ERROR_HINT.search(exp.content) or status.lower() in (
            "failed",
            "error",
            "crashed",
        )
        if failed:
            add(
                "automation_outcomes",
                "procedural",
                f"Automation '{exp.source}' last reported trouble: "
                f"'{_snip(exp.content, 140)}'. Worth a look before its next "
                "scheduled run.",
                0.6,
                exp,
            )
        elif runs >= 5:
            add(
                "automation_outcomes",
                "procedural",
                f"Automation '{exp.source}' has run {runs} times "
                f"(status={status}). It is stable — leave its cadence alone "
                "and don't 'fix' what isn't broken.",
                0.5,
                exp,
            )


def _extract_repeated_requests(experiences, add) -> None:
    """Near-identical user requests ≥3 times: a recurring need."""
    user_exps = [e for e in experiences if e.kind == "user-said"]
    word_sets = [(e, _topic_words(e.content)) for e in user_exps]
    used: set[str] = set()
    for i, (exp_a, wa) in enumerate(word_sets):
        if exp_a.id in used or not wa:
            continue
        group = [exp_a]
        for exp_b, wb in word_sets[i + 1 :]:
            if exp_b.id in used or not wb:
                continue
            union = wa | wb
            if union and len(wa & wb) / len(union) >= 0.6:
                group.append(exp_b)
        if len(group) >= 3:
            for g in group:
                used.add(g.id)
            add(
                "repeated_requests",
                "fact",
                f"The user asked {len(group)} times for nearly the same thing "
                f"('{_snip(exp_a.content, 110)}'). This is a recurring need — "
                "watch for it proactively and offer a shortcut or a standing "
                "arrangement.",
                0.6,
                exp_a,
            )


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
        "Experiences to reflect on:\n\n"
        + "\n".join(lines)
        + "\n\nExtract durable learnings as a JSON array."
    )
    resp = prov.chat(
        [
            ChatMessage(role="system", content=_REFLECT_SYSTEM),
            ChatMessage(role="user", content=user_text),
        ],
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

    Thin wrapper over :func:`reflect_detailed`; see that function for
    the full contract.
    """
    learnings, mode, _evidence = reflect_detailed(experiences, use_model=use_model)
    return learnings, mode


def reflect_detailed(
    experiences: list[Experience],
    *,
    use_model: bool = True,
) -> tuple[list[Learning], str, dict[str, int]]:
    """Reflect on experiences. Returns (learnings, mode, evidence).

    ``mode`` is ``"model:<name>"`` when the provider succeeded, else
    ``"rules"``. Model failures fall back to rules silently-but-honestly:
    the mode always says which engine actually ran. ``evidence`` maps
    extractor name → learnings produced (see
    :func:`reflect_rules_detailed`).

    Privacy rule: experiences with ``meta["origin"] == "cloud"`` (other
    users' sessions) are NEVER sent to the model reflector — a
    third-party provider must not receive another user's content.
    Cloud experiences are distilled separately by
    :func:`reflect_cloud`.

    Binding rail: model-produced learnings are scanned by the
    sentience-claim blocklist (:mod:`levi.growth.guards`) before they
    are accepted — the provider is untrusted output, the prompt is not
    enough.

    Raises ValueError when ``experiences`` is not a list of Experience
    objects.
    """
    if not isinstance(experiences, list):
        raise ValueError(
            "reflect: experiences must be a list, got %s" % type(experiences).__name__
        )
    for e in experiences:
        if not isinstance(e, Experience):
            raise ValueError(
                "reflect: experiences must contain Experience objects, got %s"
                % type(e).__name__
            )
    if not experiences:
        return [], "rules", {}
    local = [e for e in experiences if e.meta.get("origin") != "cloud"]
    if use_model and local:
        try:
            learnings, provider_name = _reflect_model(local)
            # Structural guard: the model is untrusted output. Drop any
            # learning that asserts sentience/subjective experience.
            clean: list[Learning] = []
            blocked = 0
            for learning in learnings:
                if check_no_sentience_claim(learning.content):
                    blocked += 1
                    continue
                prov = dict(learning.provenance or {})
                prov.setdefault("extractor", "model")
                learning.provenance = prov
                clean.append(learning)
            if blocked:
                print(
                    "growth: dropped %d model learning(s) asserting "
                    "sentience/subjective experience" % blocked
                )
            evidence = {"model": len(clean)}
            if blocked:
                evidence["blocked_sentience"] = blocked
            return clean, f"model:{provider_name}", evidence
        except Exception:
            pass
    # Cloud experiences are never reflected here at all — even by the
    # offline rules, which could otherwise lift another user's
    # preferences/facts. They are distilled only by reflect_cloud().
    learnings, evidence = reflect_rules_detailed(local)
    return learnings, "rules", evidence


# ---------------------------------------------------------------------------
# Cross-user distillation: learn techniques from other providers' turns
# ---------------------------------------------------------------------------

# Provider names that are LEVI's own engines — learning "from" these is
# just self-learning, not cross-model distillation.
_LEVI_PROVIDERS = {"local"}
_LEVI_PREFIX = "levi"


def _is_external_source(provider: str) -> bool:
    p = (provider or "").strip().lower()
    return (
        bool(p)
        and p != "?"
        and p not in _LEVI_PROVIDERS
        and not p.startswith(_LEVI_PREFIX)
    )


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

    Raises ValueError when ``experiences`` is not a list of Experience
    objects.
    """
    if not isinstance(experiences, list):
        raise ValueError(
            "reflect_cloud: experiences must be a list, got %s"
            % type(experiences).__name__
        )
    for e in experiences:
        if not isinstance(e, Experience):
            raise ValueError(
                "reflect_cloud: experiences must contain Experience objects, got %s"
                % type(e).__name__
            )
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
