"""L.W.P. x Legion Pipeline — Direction-2 convenience (the queued item).

A READ-ONLY helper: lifts a sealed press run's assembled draft text from the
press store (the ``<ledger-stem>.store.json`` file beside the press ledger)
into a :class:`DraftSkeleton` the drafter reviews and completes by hand.

The skeleton is not a brief. It never writes to ``01-creation/`` — only
``creation_writer.write_concept_brief`` writes, and only after the drafter
fills the human-required fields. That is the staged-by-hand contract: the
drafter reviews the skeleton, supplies what the machine has no business
supplying, and only then does anything reach the pipeline.

LAWS (invariants — declared first, per the law->guard->prove rule):

1. Read-only, always. The store file is opened for reading only; the module
   never instantiates ``ContentMachine``, never imports it (or the console —
   the console is contested and the store's on-disk JSON contract is the
   committed interface, read here directly), and never writes to the store,
   the ledger, or ``01-creation/``. stdlib-only at import.
2. Sealed runs only. ``status`` must be ``"sealed"`` (a ``"published"`` run is
   sealed+receipted+cleared — its draft text is equally honest). Anything else
   is refused: ``running`` / ``awaiting_approval`` / ``needs_attention`` have
   no finished draft or a human gate not yet crossed; ``denied`` is refused
   outright — denied-by-him is compost, never a second door (the same refusal
   as ``creation_writer``'s ``denied_by_him``).
3. Nothing is invented. ``proposed_name`` is the press brief's own title
   (working title — Chauncey renames); ``nature`` is the draft's own prose
   (``final_text``, verbatim — the drafter tightens at review, the helper
   never edits); ``typeline_sketch`` is the draft's own first non-empty line
   (a placeholder the drafter replaces, never a declared typeline);
   ``source_label`` is the factual run citation. Canon grounding, loop
   commits, and the lane are the HUMAN'S — they are left blank, never
   auto-cited, and ``to_draft_input()`` refuses until they are filled.
4. The machine never cites his words. The press store contains the press's
   own text, never his canon grounding — so grounding is not lifted from
   anywhere; the drafter supplies it.

Store path derivation mirrors the committed machine (machine.py:383):
``Path.home() / ".levi" / "lwp_machine" / "ledger.store.json"``. The derivation
is duplicated here deliberately so the helper stays read-only and
never imports the contested module.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

try:  # the skeleton hands a completed draft to the writer; the writer is
    # uncontested loop-owned code (commit 0b118e47). Import is lazy-safe:
    # only to_draft_input() needs it.
    from levi.lwp.creation_writer import DraftInput
except Exception:  # pragma: no cover - defensive; tests import with core on path
    DraftInput = None  # type: ignore[assignment]


# -- store location ----------------------------------------------------------
# Mirrors the committed machine's DEFAULT_LEDGER / store_path derivation
# (machine.py:90,383): the store sits beside the ledger as <stem>.store.json.
DEFAULT_LEDGER = Path.home() / ".levi" / "lwp_machine" / "ledger.jsonl"
DEFAULT_STORE = DEFAULT_LEDGER.parent / (DEFAULT_LEDGER.stem + ".store.json")

_SEALED_STATUSES = ("sealed", "published")


class SkeletonError(Exception):
    """Raised when the skeleton helper refuses a store, run, or completion.

    The message always says what the drafter must do — which run, which
    status, which blanks — never a silent fix.
    """


@dataclass
class DraftSkeleton:
    """A hand-reviewable skeleton of a sealed press run's draft.

    Pre-filled fields carry the run's own words, verbatim. Human-required
    fields start blank; :meth:`blanks` names them and :meth:`to_draft_input`
    refuses until they are filled.
    """

    run_id: str
    run_status: str
    sealed_at: str
    brief_title: str
    brief_kind: str
    # Pre-filled verbatim from the run -------------------------------------
    proposed_name: str  # brief title; working title — Chauncey renames
    nature: str  # final_text verbatim; the drafter tightens at review
    typeline_sketch: str  # draft's own first line; placeholder, not a type
    source_label: str  # factual run citation
    compost_fed: bool = False  # True when the run composted failures
    draft_words: int = 0
    # Human's to supply -----------------------------------------------------
    canon_grounding: str = ""
    lane: str = ""
    loop_commits: List[str] = field(default_factory=list)

    HUMAN_FIELDS = ("canon_grounding", "lane", "loop_commits")

    def blanks(self) -> List[str]:
        """The human-required fields still empty. Empty list = reviewable."""
        out = []
        if not self.canon_grounding.strip():
            out.append("canon_grounding")
        if not self.lane.strip():
            out.append("lane")
        if not self.loop_commits:
            out.append("loop_commits")
        return out

    def to_draft_input(self) -> "DraftInput":
        """Hand a COMPLETED skeleton to the Direction-2 writer.

        Refuses until every human field is filled — staged-by-hand is the
        contract: the drafter, not the machine, supplies grounding, the lane,
        and the cited commits.
        """
        if DraftInput is None:  # pragma: no cover - import is live in tests
            raise SkeletonError("creation_writer is unavailable on this host")
        missing = self.blanks()
        if missing:
            raise SkeletonError(
                "the skeleton is not finished — the drafter must supply: "
                + ", ".join(missing)
                + " (the machine never auto-cites grounding, commits, or lane)"
            )
        return DraftInput(
            proposed_name=self.proposed_name,
            lane=self.lane,
            nature=self.nature,
            typeline_sketch=self.typeline_sketch,
            canon_grounding=self.canon_grounding,
            loop_commits=list(self.loop_commits),
            source_label=self.source_label,
            compost_fed=self.compost_fed,
        )


@dataclass
class SkeletonReceipt:
    """Provenance for one lifted skeleton: what mapped, what stayed absent."""

    run_id: str
    store_path: str
    mapped: Dict[str, str] = field(default_factory=dict)
    absent: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


def _read_store(store_path: Path) -> Dict:
    try:
        payload = json.loads(store_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise SkeletonError(
            f"no press store at {store_path} — no press runs have been "
            "recorded at this ledger (run a brief first, or pass the right "
            "store path)"
        ) from None
    except (OSError, ValueError) as exc:
        raise SkeletonError(f"press store unreadable at {store_path}: {exc}") from None
    if not isinstance(payload, dict):
        raise SkeletonError(
            f"press store at {store_path} is not a JSON object — refusing to guess"
        )
    return payload


def _first_line(text: str) -> str:
    for line in text.splitlines():
        if line.strip():
            return line.strip()
    return ""


def skeleton_from_store(
    run_id: str, store_path: Optional[Path] = None
) -> "tuple[DraftSkeleton, SkeletonReceipt]":
    """Lift one sealed press run's draft into a hand-reviewable skeleton.

    Read-only: the store file is read, never written; nothing else is touched.
    """
    path = Path(store_path) if store_path is not None else DEFAULT_STORE
    payload = _read_store(path)
    runs = payload.get("runs")
    if not isinstance(runs, dict) or run_id not in runs:
        raise SkeletonError(f"unknown run {run_id!r} in the press store at {path}")
    run = runs[run_id]
    if not isinstance(run, dict):
        raise SkeletonError(f"run {run_id!r} is malformed in the press store at {path}")

    status = run.get("status", "")
    if status not in _SEALED_STATUSES:
        if status == "denied":
            raise SkeletonError(
                f"run {run_id!r} was denied — denied-by-him is compost, "
                "never a second door; the skeleton helper refuses it outright"
            )
        raise SkeletonError(
            f"run {run_id!r} has status {status!r} — the skeleton helper lifts "
            "sealed press runs only (sealed or published). A run that is "
            "running / awaiting_approval / needs_attention has no finished "
            "draft or a human gate not yet crossed."
        )

    final_text = run.get("final_text", "")
    if not isinstance(final_text, str) or not final_text.strip():
        raise SkeletonError(
            f"run {run_id!r} ({status}) has no assembled draft text "
            "(final_text is empty) — nothing to lift"
        )

    brief = run.get("brief") or {}
    title = brief.get("title") if isinstance(brief, dict) else None
    if not isinstance(title, str) or not title.strip():
        raise SkeletonError(
            f"run {run_id!r} carries no brief title in the store — "
            "the skeleton needs the press brief's own title (proposed name)"
        )
    kind = brief.get("kind") if isinstance(brief, dict) else None

    compost = run.get("compost") or []
    sealed_at = run.get("created_at", "") or ""

    skeleton = DraftSkeleton(
        run_id=run_id,
        run_status=status,
        sealed_at=str(sealed_at),
        brief_title=title.strip(),
        brief_kind=str(kind) if kind else "",
        proposed_name=title.strip(),
        nature=final_text,
        typeline_sketch=_first_line(final_text),
        source_label=f"press store {path.name}, run {run_id}, {status} {sealed_at}",
        compost_fed=bool(compost),
        draft_words=len(final_text.split()),
    )
    receipt = SkeletonReceipt(
        run_id=run_id,
        store_path=str(path),
        mapped={
            "proposed_name": "run.brief.title (verbatim; working title, Chauncey renames)",
            "nature": "run.final_text (verbatim; drafter tightens at review)",
            "typeline_sketch": "draft's own first non-empty line (placeholder)",
            "source_label": "store filename + run_id + status + created_at",
            "compost_fed": f"run.compost ({len(compost)} record(s))",
        },
        absent=["canon_grounding", "lane", "loop_commits"],
        warnings=[
            "commits are cited by the drafter, never verified by the helper",
            "nature carries the FULL draft text verbatim — tighten at review",
            "typeline_sketch is the draft's own first line, not a declared typeline",
            "canon grounding is the human's — the press store never cites his words",
        ],
    )
    return skeleton, receipt


def render_review(skeleton: DraftSkeleton) -> str:
    """A readable review sheet: what is pre-filled vs what the drafter owes.

    Never writes anything — the drafter reads, fills the blanks, and only
    then hands the skeleton to the writer.
    """
    blanks = set(skeleton.blanks())
    lines = [
        f"press-run skeleton — run {skeleton.run_id} "
        f"({skeleton.run_status}, {skeleton.sealed_at})",
        f"brief: {skeleton.brief_title!r} [{skeleton.brief_kind}]",
        "",
    ]
    prefilled = [
        ("proposed_name", skeleton.proposed_name),
        ("nature", skeleton.nature),
        ("typeline_sketch", skeleton.typeline_sketch),
        ("source_label", skeleton.source_label),
    ]
    for name, value in prefilled:
        tag = (
            "[PRE-FILLED — run's own words]"
            if name != "source_label"
            else "[PRE-FILLED — factual]"
        )
        shown = value if len(value) <= 400 else value[:400] + "…"
        lines.append(f"{tag} {name}: {shown}")
    lines.append(f"[PRE-FILLED] compost_fed: {skeleton.compost_fed}")
    lines.append(f"[PRE-FILLED] draft_words: {skeleton.draft_words}")
    lines.append("")
    human = [
        ("canon_grounding", skeleton.canon_grounding),
        ("lane", skeleton.lane),
        ("loop_commits", ", ".join(skeleton.loop_commits)),
    ]
    for name, value in human:
        state = "[HUMAN NEEDED]" if name in blanks else "[supplied]"
        lines.append(f"{state} {name}: {value or '—'}")
    if blanks:
        lines.append("")
        lines.append(
            "to_draft_input() refuses until the [HUMAN NEEDED] fields are filled."
        )
    return "\n".join(lines)
