"""Nephilim grade operators: the premium hybrid form — AI+SI+XI FUSED.

Chauncey's canon, kept VERBATIM as a proper noun everywhere
("Nephilim grade"): the premium hybrid form. Angel-human offspring
were the Nephilim, greater than either parent; the grade is the
superior AI+SI+XI FUSED form — one operator greater than any parent
alone.

This is NOT routing between minds. A Nephilim grade operator
presents ONE face behind the universal Operator contract: a single
``step()`` any seat can resolve by name (e.g.
``{"operator": "nephilim-fused"}`` — the declared Nephilim-grade
seat name from ``levi.legion.tiers``). Internally it fuses:

1. SHARED CONTEXT — every member steps on the SAME messages, with a
   shared scratchpad dict injected at
   ``context["fusion_scratchpad"]``. Members may read and write
   NAMESPACED keys (convention: ``"<member-name>:<key>"``); the
   scratchpad is copied into the result note for auditability.
   Members run SEQUENTIALLY in constructor order, so a later member
   sees what an earlier member wrote.
2. INDEPENDENT MEMBER RUNS — each member steps via
   :func:`levi.operator.registry.scoped_step`, so the capability
   scope still holds per member: a FOREIGN member's offered-tool
   leash applies exactly as if it ran alone. The trust posture is
   never fused — only the minds are.
3. PATTERN SYNTHESIS — a deterministic, HONESTLY-HEURISTIC cross-mind
   pattern layer over the member outputs: AGREEMENTS (key-phrase
   overlap across members), CONTRADICTIONS (keyword-level negation
   heuristic — flagged, never faked as certain), and NOVEL PATTERNS
   (concepts appearing in >=2 members phrased differently,
   synthesized into one statement). This is the human-like pattern
   recognition core, labeled as heuristic wherever it appears.
4. ONE FUSED FACE — a single :class:`OperatorResult` weaving the
   UNION of member insights plus the synthesis layer. "Greater than
   any parent alone" has one concrete meaning: the fused output
   carries every member's insights, and disagreements are
   synthesized, never silently dropped.

KIND RULE (no-mask law, enforced): the fused operator's ``kind``
defaults to the lead member's kind. When ``lead`` is not given, the
highest-capability member becomes lead (deterministic score — see
``_capability_score``). The fused operator is NEVER ``"native"``
unless EVERY member is native; when the lead is native but some
member is not, the kind falls to the highest-capability non-native
member's kind. A fused mind containing outside minds never presents
as LEVI-native. All-native fusions honestly report ``"native"``.

Stdlib only. No torch, no numpy, no network, no imports from other
``levi`` subpackages (``scoped_step`` comes from the sibling
``.registry`` module, same package).

What is REAL vs SCAFFOLD here:
- REAL: shared context + scratchpad, per-member scoped stepping,
  deterministic keyword-level synthesis, union-of-insights fused
  output with provenance, agreement-derived confidence, summed cost,
  lead-health reporting, honest degrade, no-mask kind rule.
- SCAFFOLD (honestly labeled): the synthesis is a heuristic, not
  comprehension — it finds lexical overlap, not meaning. It does
  not judge, merge, or veto member outputs (merge/judge semantics
  stay GATED). Tool calls emitted are the lead's only; other
  members' calls are recorded in the note, never executed.
"""

from __future__ import annotations

import json
import re
import time
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .contract import (
    AI,
    NATIVE,
    SI,
    XI,
    KINDS,
    Operator,
    OperatorCapabilities,
    OperatorContractError,
    OperatorHealth,
    OperatorMessage,
    OperatorResult,
    validate_operator,
)
from .registry import scoped_step

__all__ = [
    "NephilimOperator",
    "fusion_scratchpad_of",
    "synthesize_patterns",
]

#: Context key carrying the shared fusion scratchpad.
SCRATCHPAD_KEY = "fusion_scratchpad"

#: Fused text is a single face — one header names the grade.
_GRADE_LABEL = "Nephilim grade"

# ---------------------------------------------------------------------------
# Lexical machinery (deterministic, keyword-level, honestly heuristic)
# ---------------------------------------------------------------------------

_STOPWORDS = frozenset(
    """
    a an the and or but if then else when while with without for of in on
    at to from by as is are was were be been being has have had do does
    did will would can could should shall may might must this that these
    those it its they them their we our you your he she his her my me i
    also just very much more most less than so such no yes not never only
    each every any some all both into over under between through during
    there here where what which who whom whose how why because until
    """.split()
)

#: Keyword-level negation markers for the contradiction heuristic.
_NEGATIONS = frozenset(
    "not no never n't cannot cant won't wont cannot dont doesn't "
    "isnt arent wasnt werent hasnt havent hadnt didnt wouldnt couldnt "
    "shouldnt without against disagree disagreeing disagreed refute "
    "false wrong incorrect incorrect neither none nothing".split()
)

_WORD_RE = re.compile(r"[a-z0-9][a-z0-9\-']*")
_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")


def _terms(text: str) -> List[str]:
    """Content terms: lowercase word tokens, >= 4 chars, stopwords
    dropped. Keyword-level, nothing smarter — documented as such."""
    return [
        w
        for w in _WORD_RE.findall((text or "").lower())
        if len(w) >= 4 and w not in _STOPWORDS
    ]


def _stem(word: str) -> str:
    """Conservative stemmer for the novel-pattern heuristic only.

    Strips plural/verb endings when the remaining stem is >= 4 chars.
    Overstemming is possible; results are labeled heuristic, and
    clusters require the same stem to appear across >= 2 members.
    """
    w = word
    for suffix in ("ing", "ies", "ed", "es", "s", "ly"):
        if w.endswith(suffix) and len(w) - len(suffix) >= 4:
            w = w[: -len(suffix)]
            break
    return w


def _member_terms(text: str) -> Tuple[Dict[str, int], List[str]]:
    """(term -> count, sentences) for one member's text."""
    sentences = [s for s in _SENTENCE_RE.split(text or "") if s.strip()]
    counts: Dict[str, int] = {}
    for term in _terms(text or ""):
        counts[term] = counts.get(term, 0) + 1
    return counts, sentences


def _term_negated_in(term: str, sentences: List[str]) -> bool:
    """True if any sentence containing the term also contains a
    negation marker (token-level). Honest heuristic, not logic."""
    for sentence in sentences:
        tokens = set(_WORD_RE.findall(sentence.lower()))
        if term in tokens and tokens & _NEGATIONS:
            return True
    return False


def synthesize_patterns(
    member_texts: Dict[str, str],
) -> Dict[str, Any]:
    """Deterministic cross-mind pattern synthesis (heuristic).

    ``member_texts``: member name -> raw text (errored members should
    be passed with empty text; they are excluded). Returns a dict
    with three layers, every layer honestly labeled:

    - ``agreements``: [{term, members}] — key phrases shared by >= 2
      members (surface overlap, not meaning).
    - ``contradictions``: [{term, affirmed_by, negated_by}] — an
      agreement term where some members negate it and others don't
      (keyword-level negation; flagged for review, never certain).
    - ``novel_patterns``: [{stem, forms, members, synthesized}] —
      concepts appearing in >= 2 members phrased DIFFERENTLY
      (distinct surface forms sharing a stem), synthesized into one
      statement.
    - ``agreement_ratio``: |agreements| / |distinct terms|, and
      ``distinct_terms`` for the record.
    """
    counts: Dict[str, Dict[str, int]] = {}
    sentences: Dict[str, List[str]] = {}
    for name, text in member_texts.items():
        term_counts, sents = _member_terms(text or "")
        counts[name] = term_counts
        sentences[name] = sents

    members_with: Dict[str, List[str]] = {}
    for name, term_counts in counts.items():
        for term in term_counts:
            members_with.setdefault(term, []).append(name)

    agreements: List[Dict[str, Any]] = []
    for term in sorted(members_with):
        holders = sorted(members_with[term])
        if len(holders) >= 2:
            agreements.append({"term": term, "members": holders})

    contradictions: List[Dict[str, Any]] = []
    for agreement in agreements:
        term = agreement["term"]
        holders = agreement["members"]
        negated = [m for m in holders if _term_negated_in(term, sentences[m])]
        affirmed = [m for m in holders if m not in negated]
        if negated and affirmed:
            contradictions.append(
                {
                    "term": term,
                    "affirmed_by": affirmed,
                    "negated_by": negated,
                    "note": (
                        "keyword-level negation heuristic — review before "
                        "acting; not a logical proof"
                    ),
                }
            )

    stem_forms: Dict[str, Dict[str, List[str]]] = {}
    for name, term_counts in counts.items():
        for term in term_counts:
            stem = _stem(term)
            entry = stem_forms.setdefault(stem, {})
            entry.setdefault(term, []).append(name)

    novel_patterns: List[Dict[str, Any]] = []
    for stem in sorted(stem_forms):
        forms = sorted(stem_forms[stem])
        holders = sorted({m for form in forms for m in stem_forms[stem][form]})
        if len(forms) >= 2 and len(holders) >= 2:
            form_voices = ", ".join(
                f"{form!r} ({', '.join(sorted(set(stem_forms[stem][form])))})"
                for form in forms
            )
            novel_patterns.append(
                {
                    "stem": stem,
                    "forms": forms,
                    "members": holders,
                    "synthesized": (
                        f"Cross-mind pattern: {', '.join(holders)} describe the "
                        f"same concept as {form_voices} — different phrasing, "
                        "shared root."
                    ),
                    "note": "heuristic lexical clustering, not comprehension",
                }
            )

    distinct = len(members_with)
    agreement_ratio = round(len(agreements) / distinct, 3) if distinct else 0.0
    return {
        "agreements": agreements,
        "contradictions": contradictions,
        "novel_patterns": novel_patterns,
        "agreement_ratio": agreement_ratio,
        "distinct_terms": distinct,
        "method": (
            "deterministic keyword-level heuristic: term overlap >= 4 chars, "
            "sentence-local negation markers, conservative stemming; no "
            "semantic understanding claimed"
        ),
    }


def fusion_scratchpad_of(context: Dict[str, Any]) -> Dict[str, Any]:
    """Return the fusion scratchpad dict from a context (empty dict
    when none is attached)."""
    scratch = context.get(SCRATCHPAD_KEY)
    return scratch if isinstance(scratch, dict) else {}


# ---------------------------------------------------------------------------
# Lead selection + kind rule
# ---------------------------------------------------------------------------


def _capability_score(operator: Operator) -> Tuple[Any, ...]:
    """Deterministic highest-capability ordering.

    Score = (context_window, memory_access, tool_use_loop, #tools,
    streaming, name). The name tie-break keeps selection stable when
    capabilities are identical. Documented as an engineering proxy,
    not a judgment of intelligence.
    """
    try:
        caps = operator.capabilities()
    except Exception:
        return (0, 0, 0, 0, 0, getattr(operator, "name", ""))
    return (
        caps.context_window if isinstance(caps.context_window, int) else 0,
        int(bool(caps.memory_access)),
        int(bool(caps.tool_use_loop)),
        len(caps.tools or ()),
        int(bool(caps.streaming)),
        getattr(operator, "name", ""),
    )


def _fusion_kind(members: Sequence[Operator], lead: Operator) -> str:
    """No-mask kind rule for the fused operator.

    - Every member native -> "native" (honest).
    - Otherwise -> the lead's kind, EXCEPT a native lead over a mixed
      team would present native: then fall to the highest-capability
      NON-native member's kind.
    - The fused kind can never be "native" unless every member is.
    """
    if all(m.kind == NATIVE for m in members):
        return NATIVE
    if lead.kind != NATIVE:
        return lead.kind
    non_native = [m for m in members if m.kind != NATIVE]
    fallback = max(non_native, key=_capability_score)
    return fallback.kind


# ---------------------------------------------------------------------------
# The fused operator
# ---------------------------------------------------------------------------


class NephilimOperator(Operator):
    """The Nephilim grade fused composite operator — AI+SI+XI as one.

    ``NephilimOperator(name, members, *, lead=None)``. ``members`` is
    any mix of 2+ operators (ai/si/xi/native); ``lead`` is a member
    name or the member instance (highest-capability member when
    omitted). One face behind the contract: any seat resolves it by
    name like any operator.

    ``step()`` never raises. Member failures are recorded in the
    fused output and note, and degrade the confidence and the fused
    result honestly.
    """

    def __init__(
        self,
        name: str,
        members: Sequence[Operator],
        *,
        lead: Optional[Any] = None,
    ) -> None:
        members = list(members or [])
        if len(members) < 2:
            raise ValueError(
                "Nephilim grade is fusion: at least 2 member operators are "
                f"required (got {len(members)})"
            )
        for member in members:
            if not isinstance(member, Operator):
                raise TypeError(
                    f"Nephilim grade members must be Operators (got "
                    f"{type(member).__name__})"
                )
            validate_operator(member)  # no-mask + foreign scope per member
        seen = set()
        for member in members:
            if member.name in seen:
                raise ValueError(
                    f"duplicate member name {member.name!r} in Nephilim grade "
                    "fusion — member names must be unique"
                )
            seen.add(member.name)

        self.name = str(name)
        self.members: Tuple[Operator, ...] = tuple(members)
        self.lead: Operator = self._resolve_lead(lead)
        self.kind = _fusion_kind(self.members, self.lead)
        if self.kind not in KINDS:
            raise OperatorContractError(
                f"fused kind {self.kind!r} is not a known kind"
            )
        self.version = "1.0.0"
        self.lineage = (
            f"{_GRADE_LABEL} fusion of "
            + ", ".join(f"{m.name} ({m.kind})" for m in self.members)
        )
        # Self-check: the no-mask law applies to the fusion too.
        validate_operator(self)

    # -- construction helpers -----------------------------------------------

    def _resolve_lead(self, lead: Optional[Any]) -> Operator:
        if lead is None:
            return max(self.members, key=_capability_score)
        if isinstance(lead, Operator):
            for member in self.members:
                if member is lead or member.name == lead.name:
                    return member
            raise ValueError(
                f"lead {lead.name!r} is not a member of this Nephilim grade "
                "fusion"
            )
        wanted = str(lead)
        for member in self.members:
            if member.name == wanted:
                return member
        raise ValueError(
            f"lead {wanted!r} is not a member of this Nephilim grade fusion "
            f"(members: {[m.name for m in self.members]})"
        )

    @property
    def member_names(self) -> List[str]:
        return [m.name for m in self.members]

    # -- contract surface ----------------------------------------------------

    def capabilities(self) -> OperatorCapabilities:
        tools: List[str] = []
        streaming = False
        memory_access = False
        tool_use_loop = False
        max_tool_calls = 0
        windows: List[int] = []
        for member in self.members:
            try:
                caps = member.capabilities()
            except Exception:
                continue
            for tool in caps.tools or ():
                if tool not in tools:
                    tools.append(tool)
            streaming = streaming or bool(caps.streaming)
            memory_access = memory_access or bool(caps.memory_access)
            tool_use_loop = tool_use_loop or bool(caps.tool_use_loop)
            max_tool_calls = max(max_tool_calls, caps.max_tool_calls_per_step or 0)
            if isinstance(caps.context_window, int) and caps.context_window > 0:
                windows.append(caps.context_window)
        return OperatorCapabilities(
            tools=tuple(sorted(tools)),
            streaming=streaming,
            memory_access=memory_access,
            # The tightest window binds the fusion — honest ceiling.
            context_window=min(windows) if windows else 1024,
            tool_use_loop=tool_use_loop,
            max_tool_calls_per_step=max_tool_calls,
            notes=(
                f"{_GRADE_LABEL} fusion of {len(self.members)} members "
                f"({', '.join(self.member_names)}); tool scope is the union, "
                "window is the minimum"
            ),
        )

    def step(
        self,
        messages: List[OperatorMessage],
        tools: List[Dict[str, Any]],
        context: Dict[str, Any],
    ) -> OperatorResult:
        """Fuse: shared context + per-member scoped steps + pattern
        synthesis -> one well-formed result. Never raises."""
        started = time.monotonic()
        ctx = dict(context or {})
        # The shared scratchpad: one dict for all members, namespaced
        # writes by convention ("<member-name>:<key>"). Members run in
        # constructor order, so later members see earlier writes.
        scratchpad: Dict[str, Any] = fusion_scratchpad_of(ctx)
        ctx[SCRATCHPAD_KEY] = scratchpad

        member_runs: List[Dict[str, Any]] = []
        member_texts: Dict[str, str] = {}
        lead_tool_calls: List[Any] = []
        deferred_tool_calls: List[Dict[str, Any]] = []
        ok_count = 0
        latency_sum = 0.0
        prompt_sum = 0
        completion_sum = 0
        cost_sum = 0.0
        cost_metered = False

        for member in self.members:
            result = scoped_step(member, list(messages), list(tools or []), ctx)
            member_ok = result.error is None and result.finish_reason not in (
                "error",
                "degraded",
                "refused",
            )
            if member_ok:
                ok_count += 1
                member_texts[member.name] = result.text or ""
            run: Dict[str, Any] = {
                "name": member.name,
                "kind": member.kind,
                "ok": member_ok,
                "finish_reason": result.finish_reason,
                "error": result.error,
                "text_len": len(result.text or ""),
                "text_preview": (result.text or "")[:400],
                "cost_usd": result.cost_usd,
                "latency_ms": result.latency_ms,
            }
            member_runs.append(run)
            latency_sum += result.latency_ms or 0.0
            prompt_sum += result.prompt_tokens or 0
            completion_sum += result.completion_tokens or 0
            if isinstance(result.cost_usd, (int, float)):
                cost_sum += result.cost_usd
                cost_metered = True
            # Tool calls: the fusion emits the LEAD's calls only; every
            # other member's calls are recorded in the note, never
            # executed here — one voice, one action.
            if member is self.lead or member.name == self.lead.name:
                lead_tool_calls = list(result.tool_calls or [])
            elif result.tool_calls:
                deferred_tool_calls.extend(
                    {
                        "member": member.name,
                        "tool": call.name,
                        "arguments": call.arguments,
                    }
                    for call in result.tool_calls
                )

        synthesis = synthesize_patterns(member_texts)
        ok_fraction = ok_count / len(self.members)
        confidence = round(synthesis["agreement_ratio"] * ok_fraction, 3)

        fused_text = self._weave(member_runs, synthesis, ok_count)

        note_payload: Dict[str, Any] = {
            "grade": _GRADE_LABEL,
            "members": self.member_names,
            "lead": self.lead.name,
            "kind_rule": (
                "kind=lead.kind; never 'native' unless every member is "
                f"native (fused kind: {self.kind})"
            ),
            "provenance": member_runs,
            "ok_members": ok_count,
            "total_members": len(self.members),
            "synthesis": synthesis,
            "confidence": confidence,
            "confidence_basis": (
                "agreement_ratio * ok_member_fraction — heuristic, "
                "keyword-level"
            ),
            "tool_calls_emitted": [
                {"id": c.id, "name": c.name, "arguments": c.arguments}
                for c in lead_tool_calls
            ],
            "tool_calls_deferred": deferred_tool_calls,
            "scratchpad": {k: str(v)[:500] for k, v in scratchpad.items()},
            "cost_basis": (
                "sum of metered member result costs — fusion runs every "
                "member, so fusion costs every member"
            ),
        }
        elapsed_ms = (time.monotonic() - started) * 1000.0

        return OperatorResult(
            text=fused_text,
            tool_calls=lead_tool_calls,
            model="nephilim-fusion",
            operator=self.name,
            kind=self.kind,
            latency_ms=round(latency_sum + elapsed_ms, 3),
            prompt_tokens=prompt_sum,
            completion_tokens=completion_sum,
            cost_usd=round(cost_sum, 6) if cost_metered else None,
            finish_reason="stop" if ok_count else "degraded",
            error=(
                None
                if ok_count
                else (
                    f"{_GRADE_LABEL} operator {self.name!r}: no member "
                    "produced a usable result"
                )
            ),
            note=json.dumps(note_payload, ensure_ascii=False, default=str),
        )

    def _weave(
        self,
        member_runs: List[Dict[str, Any]],
        synthesis: Dict[str, Any],
        ok_count: int,
    ) -> str:
        """Weave member insights + the synthesis layer into ONE text.

        The UNION of member insights is the concrete meaning of
        "greater than any parent alone". Disagreements surface in the
        contradictions layer — never silently dropped.
        """
        lines = [
            f"{_GRADE_LABEL} fusion of {len(self.members)} members "
            f"({', '.join(self.member_names)}); lead: {self.lead.name}.",
        ]
        lines.append("")
        lines.append("--- member insights (union: greater than any parent alone) ---")
        for run in member_runs:
            if run["ok"]:
                lines.append(f"[{run['kind']}] {run['name']}: {run['text_preview']}")
            else:
                reason = run["error"] or f"finish_reason={run['finish_reason']}"
                lines.append(f"[{run['kind']}] {run['name']}: [no insight — {reason}]")
        lines.append("")
        lines.append(
            "--- cross-mind pattern synthesis "
            "(deterministic heuristic; keyword-level, never certainty) ---"
        )
        agreements = synthesis["agreements"]
        lines.append(
            f"agreements ({len(agreements)}): "
            + (
                ", ".join(
                    f"{a['term']!r} ({', '.join(a['members'])})" for a in agreements
                )
                if agreements
                else "none"
            )
        )
        contradictions = synthesis["contradictions"]
        if contradictions:
            lines.append(f"contradictions ({len(contradictions)}):")
            for c in contradictions:
                lines.append(
                    f"  {c['term']!r}: affirmed by {', '.join(c['affirmed_by'])}; "
                    f"negated by {', '.join(c['negated_by'])} — review before acting"
                )
        else:
            lines.append("contradictions (0): none detected")
        novel = synthesis["novel_patterns"]
        if novel:
            lines.append(f"novel cross-mind patterns ({len(novel)}):")
            for n in novel:
                lines.append(f"  {n['synthesized']}")
        else:
            lines.append("novel cross-mind patterns (0): none detected")
        if ok_count < len(self.members):
            lines.append(
                f"note: {len(self.members) - ok_count} member(s) produced no "
                "usable result; their failures are recorded in the result note"
            )
        return "\n".join(lines)

    def health(self) -> OperatorHealth:
        """Healthy iff the lead is healthy. The note lists every
        member's health — no hiding a sick member behind the lead."""
        reports: List[Tuple[str, bool, str]] = []
        for member in self.members:
            try:
                h = member.health()
                reports.append((member.name, bool(h.ok), h.note or ""))
            except Exception as exc:  # noqa: BLE001 — health never raises
                reports.append((member.name, False, f"health() raised: {exc}"))
        lead_ok = next((ok for name, ok, _ in reports if name == self.lead.name), False)
        member_notes = "; ".join(
            f"{name}: {'ok' if ok else 'UNHEALTHY'}{f' ({note})' if note else ''}"
            for name, ok, note in reports
        )
        return OperatorHealth(
            ok=bool(lead_ok),
            note=(
                f"{_GRADE_LABEL} lead {self.lead.name} "
                f"{'ok' if lead_ok else 'UNHEALTHY'}; members — {member_notes}"
            ),
        )

    def cost(self) -> Dict[str, Any]:
        """Operator-level cost reporting: the SUM of metered member
        costs. Fusion runs every member, so fusion costs every
        member — that is the honest unit economics of the grade."""
        per_member: Dict[str, Optional[float]] = {}
        total = 0.0
        metered_any = False
        for member in self.members:
            try:
                reported = member.cost() or {}
            except Exception:
                reported = {}
            usd = reported.get("total_usd", reported.get("usd"))
            if reported.get("metered") and isinstance(usd, (int, float)):
                per_member[member.name] = float(usd)
                total += float(usd)
                metered_any = True
            else:
                per_member[member.name] = None
        return {
            "metered": metered_any,
            "total_usd": round(total, 6) if metered_any else None,
            "per_member": per_member,
            "note": (
                f"{_GRADE_LABEL}: fusion cost is the sum of metered member "
                "costs — every mind that runs, bills"
            ),
        }

    def degrade(self) -> OperatorResult:
        """Graceful degradation: names the failed member(s) honestly.
        No fake work, no raised exceptions."""
        try:
            health = self.health()
        except Exception:
            health = OperatorHealth(ok=False, note="health() unavailable")
        return OperatorResult(
            text="",
            operator=self.name,
            kind=self.kind,
            finish_reason="degraded",
            error=(
                f"{_GRADE_LABEL} operator {self.name!r} is degraded: {health.note}; "
                "no action taken"
            ),
            note="swap to a healthy operator (or repair the failed member) and retry",
        )

    def __repr__(self) -> str:
        return (
            f"<NephilimOperator {self.name} ({self.kind}) "
            f"lead={self.lead.name} members={self.member_names}>"
        )
