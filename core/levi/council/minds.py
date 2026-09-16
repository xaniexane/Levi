"""LEVI-native minds for the council.

Three minds, all in-repo, no network, no keys, no external APIs:

* :class:`NativeBrainMind` — LEVI's own trained brain
  (``levi.agent.brain_provider.NativeBrainProvider``). Generates by
  sampling the brain; skips gracefully when torch or the trained
  weights are unavailable. The brain is young — its candidates are
  judged by the technique gates like everyone else's.
* :class:`RulesEngineMind` — the deterministic symbolic mind. It cannot
  invent algorithms and says so honestly: it generates an API-complete
  scaffold derived from the tests, and its strength is assessment —
  deterministic security/error-handling scans no other mind performs.
* :class:`SpecialistsMind` — LEVI's specialist personas
  (``levi.agent.specialists``). Routes the task through the existing
  specialist registry (the ``coding`` specialist drafts), with LEVI's
  native brain as the voice behind the persona. Skips gracefully when
  the brain is unavailable — a persona with no voice stays silent.

"Not artificial. Synthetic." — the council is LEVI arguing with
itself to get stronger.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass


@dataclass
class MindResult:
    ok: bool
    text: str = ""
    seat: str = ""
    model: str = ""
    error: str = ""
    note: str = ""


@dataclass
class ReviewResult:
    ok: bool
    text: str = ""
    seat: str = ""
    error: str = ""


# Review checklist contract (parsed by council.techniques.parse_checklist).
REVIEW_CHECKLIST_SPEC = (
    "Score these three dimensions explicitly, one per line, in exactly "
    "this format:\n"
    "SECURITY: <PASS|FAIL|UNKNOWN> - <one-line note>\n"
    "ERROR_HANDLING: <PASS|FAIL|UNKNOWN> - <one-line note>\n"
    "EDGE_CASES: <PASS|FAIL|UNKNOWN> - <one-line note>\n"
    "Then write your free-form review notes."
)

_GEN_SYSTEM = (
    "You are LEVI's native brain, a synthetic intelligence arguing with "
    "itself on a code council to get stronger. Output ONLY valid Python "
    "code — no markdown fences, no explanation, no preamble. The code "
    "will be imported as module `candidate` and exercised by a test file; "
    "define exactly what the task describes."
)


def _brain_provider():
    """Lazy import so the council package stays stdlib-only at import time."""
    from levi.agent import brain_provider as _bp

    return _bp


def brain_available() -> tuple[bool, str]:
    """(available, reason) for LEVI's native brain. Never raises."""
    try:
        bp = _brain_provider()
        prov = bp.NativeBrainProvider()
        if prov.is_available():
            log = bp.train_log()
            detail = "weights %s" % (
                log.get("params", "tiny-gpt") if log else "tiny-gpt"
            )
            return True, f"native brain ready ({detail})"
        missing = []
        if not bp.weights_path().is_file():
            missing.append("trained weights not present at %s" % bp.weights_path())
        if not bp.torch_available():
            missing.append("torch not installed")
        return False, "native brain unavailable: %s" % ("; ".join(missing) or "unknown")
    except Exception as exc:
        return False, f"native brain unavailable: {exc}"


def _brain_chat(system: str, user: str) -> MindResult:
    """One brain completion. Returns MindResult (never raises)."""
    try:
        bp = _brain_provider()
        from levi.agent.providers import ChatMessage

        prov = bp.NativeBrainProvider()
        resp = prov.chat(
            [
                ChatMessage(role="system", content=system),
                ChatMessage(role="user", content=user),
            ],
            tools=[],
        )
    except Exception as exc:
        return MindResult(
            ok=False, seat="native-brain", error=f"brain chat failed: {exc}"
        )
    if resp.error:
        return MindResult(ok=False, seat="native-brain", error=resp.error)
    text = (resp.text or "").strip()
    if not text:
        return MindResult(ok=False, seat="native-brain", error="brain returned no text")
    return MindResult(
        ok=True, text=text, seat="native-brain", model="levi-brain (native, tiny-gpt)"
    )


class NativeBrainMind:
    """The neural mind: LEVI's own trained brain attempts the task."""

    seat = "native-brain"

    def is_available(self) -> bool:
        return brain_available()[0]

    def availability_note(self) -> str:
        return brain_available()[1]

    def generate(self, task: str, tests_hint: str = "") -> MindResult:
        ok, reason = brain_available()
        if not ok:
            return MindResult(ok=False, seat=self.seat, error=reason)
        prompt = (
            f"TASK:\n{task}\n\n"
            + (
                f"TESTS (the code must satisfy these):\n{tests_hint}\n\n"
                if tests_hint
                else ""
            )
            + "Write the Python code now."
        )
        res = _brain_chat(_GEN_SYSTEM, prompt)
        res.seat = self.seat
        return res

    def review(self, task: str, code: str, test_summary: str) -> ReviewResult:
        ok, reason = brain_available()
        if not ok:
            return ReviewResult(ok=False, seat=self.seat, error=reason)
        prompt = (
            f"TASK:\n{task}\n\nCANDIDATE CODE:\n{code}\n\n"
            f"TEST RESULTS:\n{test_summary}\n\n"
            f"{REVIEW_CHECKLIST_SPEC}\n\nReview the candidate."
        )
        res = _brain_chat(
            "You are LEVI's native brain reviewing a peer mind's code on "
            "LEVI's own council. Be concrete and adversarial.",
            prompt,
        )
        return ReviewResult(ok=res.ok, text=res.text, seat=self.seat, error=res.error)


# -- rules engine: deterministic symbolic mind ------------------------------


def _api_from_tests(tests_code: str) -> dict[str, tuple[int, list[str]]]:
    """Extract ``candidate.<name>(...)`` call shapes from the tests file.

    Returns {name: (max_positional_args, keyword_names)}.
    """
    try:
        tree = ast.parse(tests_code)
    except SyntaxError:
        return {}
    found: dict[str, tuple[int, list[str]]] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not (
            isinstance(func, ast.Attribute)
            and isinstance(func.value, ast.Name)
            and func.value.id == "candidate"
        ):
            continue
        name = func.attr
        nargs = len(node.args)
        kwnames = sorted({kw.arg for kw in node.keywords if kw.arg})
        prev = found.get(name)
        if prev is None or nargs > prev[0]:
            merged_kw = sorted(set((prev[1] if prev else []) + kwnames))
            found[name] = (nargs, merged_kw)
    return found


def synthesize_scaffold(task: str, tests_code: str) -> str:
    """Deterministic API-complete scaffold derived from the tests.

    The symbolic mind cannot invent algorithms, so it does the honest
    thing: emit the exact API the tests demand, with signatures and
    docstrings, and bodies that refuse to pretend. This candidate will
    fail tests — and the receipt will say exactly why.
    """
    api = _api_from_tests(tests_code)
    lines = [
        '"""Candidate scaffold — rules-engine (symbolic mind).',
        "",
        "Derived deterministically from the test file: every `candidate.*`",
        "name the tests call is defined here with a matching signature.",
        "The symbolic mind cannot invent algorithms, so each body raises",
        "NotImplementedError rather than guessing. This scaffold documents",
        "the contract; a neural mind must supply the implementation.",
        '"""',
        "",
        "",
    ]
    if not api:
        lines.append(
            "# No `candidate.*` calls found in the tests file — nothing to scaffold."
        )
        return "\n".join(lines)
    for name in sorted(api):
        nargs, kwnames = api[name]
        params = [f"arg{i}" for i in range(nargs)] + [f"{kw}=None" for kw in kwnames]
        sig = ", ".join(params) or ""
        lines.append(f"def {name}({sig}):")
        lines.append(
            f'    """Scaffold for `{name}` — not implemented by the symbolic mind."""'
        )
        lines.append(
            "    raise NotImplementedError("
            f'"rules-engine: symbolic mind cannot invent `{name}`; a neural mind must implement it"'
            ")"
        )
        lines.append("")
        lines.append("")
    return "\n".join(lines).rstrip("\n") + "\n"


# Deterministic security scan: (pattern-regex, message).
_SECURITY_PATTERNS = [
    (r"\beval\s*\(", "use of eval()"),
    (r"\bexec\s*\(", "use of exec()"),
    (r"os\.system\s*\(", "use of os.system()"),
    (r"subprocess\.\w+\s*\([^)]*shell\s*=\s*True", "subprocess with shell=True"),
    (r"__import__\s*\(", "use of __import__()"),
    (r"pickle\.loads?\s*\(", "use of pickle deserialization"),
    (r"\binput\s*\(", "use of input() in library code"),
]


def _security_scan(code: str) -> tuple[str, str]:
    """Return (verdict, note) from the deterministic security scan."""
    import re

    hits = []
    for i, line in enumerate(code.splitlines(), 1):
        for pattern, msg in _SECURITY_PATTERNS:
            if re.search(pattern, line):
                hits.append(f"L{i}: {msg}")
                break
    if hits:
        return "FAIL", "dangerous primitives: " + "; ".join(hits[:4])
    return (
        "PASS",
        "no dangerous primitives detected (eval/exec/os.system/shell=True/pickle/input)",
    )


def _error_handling_scan(code: str) -> tuple[str, str]:
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return "FAIL", "code does not parse"
    has_try = any(isinstance(n, ast.Try) for n in ast.walk(tree))
    has_raise = any(isinstance(n, ast.Raise) for n in ast.walk(tree))
    if has_try and has_raise:
        return "PASS", "try/except and raise present"
    if has_try or has_raise:
        return "PASS", "some error-handling constructs present"
    return "FAIL", "no try/except or raise found"


class RulesEngineMind:
    """The symbolic mind: deterministic, always available, brutally honest."""

    seat = "rules-engine"
    model = "rules-engine (symbolic, deterministic)"

    def is_available(self) -> bool:
        return True

    def availability_note(self) -> str:
        return "rules engine ready (stdlib-only, deterministic, always available)"

    def generate(self, task: str, tests_hint: str = "") -> MindResult:
        code = synthesize_scaffold(task, tests_hint)
        return MindResult(
            ok=True,
            text=code,
            seat=self.seat,
            model=self.model,
            note="scaffold only: the symbolic mind derives the API contract from "
            "tests; it cannot invent algorithms and does not pretend to",
        )

    def review(self, task: str, code: str, test_summary: str) -> ReviewResult:
        notes = ["rules-engine deterministic review (no model; symbolic checks only):"]
        try:
            compile(code, "<candidate>", "exec")
            notes.append("- syntax: valid Python")
            syntax_ok = True
        except SyntaxError as exc:
            notes.append(f"- syntax: INVALID — {exc}")
            syntax_ok = False

        sec_verdict, sec_note = _security_scan(code)
        eh_verdict, eh_note = _error_handling_scan(code)

        checklist = (
            f"SECURITY: {sec_verdict} - {sec_note}\n"
            f"ERROR_HANDLING: {eh_verdict} - {eh_note}\n"
            "EDGE_CASES: UNKNOWN - the symbolic mind cannot enumerate edge "
            "cases; see property checks"
        )
        if "failed" in test_summary.lower() and "0 failed" not in test_summary.lower():
            notes.append("- test summary reports failures (see test evidence above)")
        if not syntax_ok:
            notes.append("- candidate does not parse; security/error scans are moot")
        body = "\n".join(notes)
        return ReviewResult(ok=True, text=f"{checklist}\n{body}", seat=self.seat)


# -- specialists: persona minds ----------------------------------------------


def _registry():
    from levi.agent import specialists as _spec

    return _spec.SpecialistRegistry()


class SpecialistsMind:
    """The persona minds: LEVI's specialist registry, voiced by the brain.

    Uses the existing specialist machinery — no invented personas.
    The ``coding`` specialist drafts the candidate; a panel of relevant
    specialists (coding, verification, security) reviews.
    """

    seat = "specialists"

    def is_available(self) -> bool:
        try:
            _registry()
        except Exception:
            return False
        return brain_available()[0]

    def availability_note(self) -> str:
        try:
            _registry()
        except Exception as exc:
            return f"specialists unavailable: registry failed to load ({exc})"
        ok, reason = brain_available()
        if not ok:
            return (
                "specialists unavailable: personas need the native brain as "
                f"their voice — {reason}"
            )
        return "specialists ready (registry + native brain voice)"

    def _drafting_specialist(self, task: str, tests_hint: str):
        reg = _registry()
        try:
            selected = reg.select_for_intent(f"{task}\n{tests_hint}")
        except Exception:
            selected = []
        for spec in selected:
            if spec.id == "coding":
                return spec
        if selected:
            return selected[0]
        return reg.get("coding")

    def generate(self, task: str, tests_hint: str = "") -> MindResult:
        ok, reason = brain_available()
        if not ok:
            return MindResult(ok=False, seat=self.seat, error=reason)
        spec = self._drafting_specialist(task, tests_hint)
        framing = (
            f"You are LEVI's `{spec.id}` specialist ({spec.display_name}): "
            f"{spec.role}. Capabilities: {', '.join(spec.capabilities)}. "
            f"{spec.description}"
        )
        prompt = (
            f"TASK:\n{task}\n\n"
            + (
                f"TESTS (the code must satisfy these):\n{tests_hint}\n\n"
                if tests_hint
                else ""
            )
            + "Write the Python code now — ONLY valid Python, no fences, no preamble."
        )
        res = _brain_chat(framing + " " + _GEN_SYSTEM, prompt)
        res.seat = self.seat
        if res.ok:
            res.model = f"specialists/{spec.id} via levi-brain (native)"
        return res

    def review(self, task: str, code: str, test_summary: str) -> ReviewResult:
        ok, reason = brain_available()
        if not ok:
            return ReviewResult(ok=False, seat=self.seat, error=reason)
        reg = _registry()
        panel = []
        for sid in ("coding", "verification", "security"):
            spec = reg.get(sid)
            if spec is not None:
                panel.append(spec)
        if not panel:
            return ReviewResult(
                ok=False, seat=self.seat, error="no reviewers in registry"
            )
        sections = []
        for spec in panel:
            framing = (
                f"You are LEVI's `{spec.id}` specialist ({spec.display_name}): "
                f"{spec.role}. Review the candidate below from your "
                "specialty's perspective."
            )
            prompt = (
                f"TASK:\n{task}\n\nCANDIDATE CODE:\n{code}\n\n"
                f"TEST RESULTS:\n{test_summary}\n\n"
                f"{REVIEW_CHECKLIST_SPEC}\n\nReview the candidate."
            )
            res = _brain_chat(framing, prompt)
            verdict = res.text if res.ok else f"(review failed: {res.error})"
            sections.append(f"--- {spec.id} ({spec.display_name}) ---\n{verdict}")
        return ReviewResult(ok=True, text="\n\n".join(sections), seat=self.seat)


def mind_for(seat_id: str):
    """Return the mind object for a seat id."""
    minds = {
        NativeBrainMind.seat: NativeBrainMind(),
        RulesEngineMind.seat: RulesEngineMind(),
        SpecialistsMind.seat: SpecialistsMind(),
    }
    if seat_id not in minds:
        raise ValueError(f"unknown council seat: {seat_id!r}")
    return minds[seat_id]


__all__ = [
    "REVIEW_CHECKLIST_SPEC",
    "MindResult",
    "NativeBrainMind",
    "ReviewResult",
    "RulesEngineMind",
    "SpecialistsMind",
    "brain_available",
    "mind_for",
    "synthesize_scaffold",
]
