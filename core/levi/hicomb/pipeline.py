"""The Hicomb save pipeline: Pollen runs before EVERY write.

LAW (I1 POLLEN-ABORT, from pollen.py): if the formatter fails, the write
aborts — the target file's bytes are guaranteed identical to before the
call, and the buffer keeps its pre-format text (undoable, dirty flag
preserved). A broken formatter can never corrupt a file. This is the
nothing-thrown-away law applied to saves: nothing is written, nothing is
lost, everything stays recoverable.

The pipeline is the ONLY sanctioned path from buffer to disk for the
studio UI. Buffer.save() stays atomic (temp file + os.replace); the
pipeline adds the format gate in front of it, and an optional
Quetta-Pan refine stage (quetta_refine.py) between format and write:
format -> refine -> re-validate -> write-or-abort. The refine pass is
advisory (Q2) and its output re-runs Pollen's gates (Q1/Q5) — a broken
agent pass can never corrupt a file either.

Snapshot-every-stage (Chauncey, 2026-09-23): the pollen format and the
final write each run under pre/post snapshots from
``levi.hicomb.snapshots`` (S1–S5) — snapshot before Pollen formats,
snapshot before the final write. A write without its pre-snapshot
raises StageViolation, build-breaking (S4).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from levi.hicomb.buffer import Buffer, BufferError
from levi.hicomb.pollen import FormatterError, format_text, language_for_path
from levi.hicomb.quetta_refine import QuettaRefiner, RefineReport
from levi.hicomb.snapshots import SnapshotStore, StageGuard, snapshotted


@dataclass(frozen=True)
class SaveResult:
    ok: bool
    path: str | None = None
    formatted: bool = False  # pollen changed the text before the write
    aborted: str = ""  # reason when ok is False
    bytes_written: int = 0
    quetta_refined: bool = False  # quetta-pan pass applied with builder confirm
    quetta_suggestions: int = 0  # suggestions the refine pass surfaced


def _read_bytes(path: str) -> bytes | None:
    try:
        with open(path, "rb") as fh:
            return fh.read()
    except OSError:
        return None


def save_pipeline(
    buffer: Buffer,
    path: str | None = None,
    language: str | None = None,
    run_pollen: bool = True,
    run_quetta: bool = False,
    confirm_refine: Callable[[RefineReport], bool] | None = None,
    refine_store_dir: str | None = None,
    refine_log_path: str | None = None,
    snapshot_store_dir: str | None = None,
    on_quetta_skip: Callable[[str], None] | None = None,
) -> SaveResult:
    """Format (Pollen), optionally refine (Quetta-Pan), then atomically save.

    - run_pollen=True is the law; the parameter exists only so tests and
      tooling can name the bypass explicitly. The studio UI never passes
      False.
    - Formatter failure -> ok=False, file untouched, buffer text restored
      to its pre-format state (the format edit is undone, not left dirty).
    - run_quetta=True adds the advisory refine pass (Q2): suggestions are
      applied ONLY when confirm_refine(report) returns True; without a
      callback they are receipted and dropped. The agent-refined text
      re-runs Pollen's gates (Q1/Q5) — a broken agent pass aborts the
      save exactly like a pollen refusal. A crashing refiner never
      breaks the save: the pass is skipped (reported via on_quetta_skip)
      and the write proceeds on the formatted text.
    - Disk failure -> ok=False; Buffer.save's temp+replace means no
      half-written file can exist.
    """
    target = path or buffer.path
    if target is None:
        return SaveResult(ok=False, aborted="no path: nothing to save to")

    # S1: snapshot-every-stage store for this save.
    snaps = SnapshotStore(
        Path(snapshot_store_dir) / ".snapshots"
        if snapshot_store_dir
        else Path.home() / ".levi" / "hicomb" / "ide" / ".snapshots"
    )
    guard = StageGuard(snaps)

    before_bytes = _read_bytes(target)
    original_text = buffer.get_text()
    lang = language or language_for_path(target)

    formatted = False
    if run_pollen:
        try:
            # S1: snapshot before Pollen formats.
            refined, _pre, _post = snapshotted(
                snaps, "pollen-format",
                {"path": target, "language": lang,
                 "before": original_text},
                format_text, lang, original_text,
                post=lambda r: {"after": r, "changed": r != original_text},
            )
        except FormatterError as exc:
            # I1: abort. Restore buffer text if the format edit already
            # landed, then verify the file is byte-identical. The check
            # is explicit (not assert) — it must hold under -O too.
            if buffer.get_text() != original_text:
                buffer.set_text(original_text)
            after = _read_bytes(target)
            if after != before_bytes:
                raise BufferError(
                    "pollen-abort violated: file changed") from None
            return SaveResult(ok=False, aborted=f"pollen refused: {exc}")
        if refined != original_text:
            buffer.set_text(refined)  # one undo step; user can undo pollen
            formatted = True

    quetta_refined = False
    quetta_suggestions = 0
    if run_quetta:
        # Advisory must never break the save: a crashing refiner
        # degrades to skipped (reported via on_quetta_skip), not a
        # failed save. The file is untouched either way.
        try:
            refiner = QuettaRefiner(
                store_dir=refine_store_dir, log_path=refine_log_path
            )
            report = refiner.review(buffer.get_text(), lang, target)
        except Exception as exc:
            if on_quetta_skip is not None:
                on_quetta_skip(f"quetta advisory pass skipped: {exc}")
            report = None
        if report is not None:
            quetta_suggestions = len(report.suggestions)
            final_text: str | None = None
            if report.has_changes and confirm_refine is not None:
                if confirm_refine(report):
                    final_text, receipts = refiner.decide(report, "confirmed")
                else:
                    _, receipts = refiner.decide(report, "declined")
            else:
                _, receipts = refiner.decide(report, "advisory")
            refiner.log_receipts(receipts)

            if final_text is not None and final_text != buffer.get_text():
                # Q1/Q5: the agent-refined text re-runs Pollen's safety gates.
                # Anything the gates reject aborts the save like a refusal.
                gate_reason = ""
                try:
                    rechecked = format_text(lang, final_text)
                except FormatterError as exc:
                    gate_reason = f"quetta refine produced unformattable text: {exc}"
                else:
                    if rechecked != final_text:
                        gate_reason = "quetta refine broke pollen idempotency"
                if gate_reason:
                    if buffer.get_text() != original_text:
                        buffer.set_text(original_text)
                    after = _read_bytes(target)
                    if after != before_bytes:
                        raise BufferError("quetta-abort violated: file changed")
                    return SaveResult(ok=False, aborted=gate_reason)
                buffer.set_text(final_text)  # one undo step; user can undo quetta
                quetta_refined = True

    # S1: snapshot before the final write — the pre-snapshot is the
    # rollback point if the write half-finishes.
    write_run = guard.begin(
        "final-write",
        {"path": target, "formatted": formatted,
         "quetta_refined": quetta_refined,
         "buffer_head": buffer.get_text()[:500]},
    )
    try:
        write_run.act()
        written = buffer.save(target)
    except (BufferError, OSError) as exc:
        write_run.abort()
        return SaveResult(ok=False, formatted=formatted, aborted=f"write failed: {exc}")

    with open(written, "rb") as fh:
        nbytes = len(fh.read())
    write_run.end({"path": written, "bytes_written": nbytes})
    return SaveResult(
        ok=True,
        path=written,
        formatted=formatted,
        bytes_written=nbytes,
        quetta_refined=quetta_refined,
        quetta_suggestions=quetta_suggestions,
    )
