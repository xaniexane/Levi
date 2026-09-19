# SECTION 0 — Hybrid IP Protection Block
# Date of Invention: mid-March 2026.
# This work is the exclusive property of Chauncey Logan. All rights reserved.
# Protections are retroactive to the date of invention and extend to all versions, expansions, and derivatives.
# Reproduction, distribution, modification, reverse-engineering, or imitation is prohibited — including training AI systems on this content or embedding its structures into other platforms.
# This work is closed and owner-controlled: not open-source, not licensed for reuse. Unauthorized use triggers immediate legal action.
# SPDX-License-Identifier: LicenseRef-LEVI-Proprietary
"""Threadweaver — Thread+Waves: agent message threads with media woven in.

A thread is a draft→challenge→consolidate cycle; every step is a
sealed receipt, and steps link to each other by receipt-hash ancestry
(``prev``). Consolidation walks that ancestry — never timestamps.

Unreplicable attribute — **hashline-consolidation**: a thread is
consolidated by receipt-hash ancestry, never by timestamps — the
thread's truth is its chain, not its clock. A step whose sealed
receipt is unreadable, mismatched, or unlinked breaks the walk and
the consolidation is refused outright. There is no timestamp mode;
asking for one is refused.

Local media plugin (milestone slice): ``graft_media`` registers a
local-library file — name, sha256, source "local-library" — sealed as
a receipt. Network sources are refused: grafts are local-only, and a
missing file is refused before anything is sealed.

Honest limits: no real playback engine yet (grafts are indexed, not
played); no cloud sync — local is the source of truth until the money
rail exists.
"""

from __future__ import annotations

import contextlib
import fcntl
import hashlib
import json
import os
import threading
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, List, Optional

from levi.dynasty.dna import AgentError, DynastyAgent, WareError, scrub_text

_STEP_KIND = "wave.thread_step"
_STEP_NAMES = ("draft", "challenge", "consolidate")

_tls = threading.local()


def _checked_payload(payload: Any) -> Dict[str, Any]:
    """Type the payload gate: the DNA's ``do_task`` json.dumps the
    payload, which raises bare ``TypeError``/``ValueError`` on
    unserializable input (purge finding F-BARE-PAYLOAD). Fail typed,
    before anything is planned or sealed."""
    if not isinstance(payload, dict):
        raise AgentError("do_task payload must be a dict")
    try:
        json.dumps(payload)
    except (TypeError, ValueError) as exc:
        raise AgentError(f"do_task payload must be JSON-serializable: {exc}") from exc
    return payload


def _refuse_root_wipe(argv: Any) -> None:
    """Defense in depth for the runner deny-list (purge finding
    F-DENY-DOUBLESLASH): the core deny-list regex does not match
    ``rm -rf //`` (or ``///``, ``/./``) — and on Linux ``//`` IS ``/``.
    Refuse any rm invocation whose target normalizes to the filesystem
    root before it reaches the runner. Typed :class:`WareError`."""
    import posixpath

    if not isinstance(argv, list) or not argv:
        return  # the runner's own argv contract handles non-lists
    if posixpath.basename(str(argv[0])) != "rm":
        return
    flags = [str(a) for a in argv[1:] if str(a).startswith("-")]
    if not any("r" in f and "f" in f for f in flags):
        return
    for arg in argv[1:]:
        s = str(arg)
        if s.startswith("-") or not s:
            continue
        if posixpath.normpath(s) in ("/", "//"):
            raise WareError(f"refused rm against filesystem root: {argv!r}")


@contextlib.contextmanager
def _chain_locked(home: Any) -> Iterator[None]:
    """Cross-instance mint lock (purge finding F-XINST-CHAIN).

    The receipt chain is one global file sequence per home, and
    ``receipts.mint_receipt`` does read→mint with no locking — two
    agent instances minting concurrently fork the chain (or read a
    half-written receipt). The flock on ``.mint.lock`` serializes every
    minter that passes through a wave-B agent, across threads AND
    processes. Re-entrant per thread: nested ``do_task`` calls (act →
    handle → do_task, or a three-step thread cycle) ride the outer
    hold instead of deadlocking on their own lock.
    """
    key = str(home)
    held = getattr(_tls, "chain_holds", None)
    if held and held.get("home") == key:
        held["depth"] += 1
        try:
            yield
        finally:
            held["depth"] -= 1
        return
    lockpath = Path(key) / "dynasty" / "receipts" / ".mint.lock"
    lockpath.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(lockpath), os.O_WRONLY | os.O_CREAT, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        _tls.chain_holds = {"home": key, "depth": 1}
        try:
            yield
        finally:
            _tls.chain_holds = None
            fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)


class Threadweaver(DynastyAgent):
    """Weaves agent threads; consolidates by hashline, not clock."""

    agent_id = "threadweaver"
    display_name = "Threadweaver"
    owns = "Thread+Waves"
    first_milestone = "agent threads + local media plugin"
    proficiency = {"messaging": 10, "media": 8, "general": 6}
    specialties = [
        "draft → challenge → consolidate thread cycles",
        "hashline thread truth (receipt ancestry, never timestamps)",
        "local-library media grafts",
    ]
    attributes = [
        {
            "name": "hashline-consolidation",
            "assertion": (
                "a thread is consolidated by receipt-hash ancestry, never by "
                "timestamps — the thread's truth is its chain, not its clock; "
                "a broken, tampered, or unlinked step refuses the whole "
                "consolidation"
            ),
        },
    ]

    def __init__(self, home: Optional[object] = None) -> None:
        super().__init__(home)
        self._task_lock = threading.RLock()
        self._threads: Dict[str, List[Dict[str, Any]]] = {}

    # -- guarded entry points: the global receipt chain is minted
    # -- through here. The per-instance RLock serializes one agent's
    # -- threads; _chain_locked serializes every wave-B minter sharing
    # -- the home (threads and processes) so the chain never forks.
    def act(self, task: Dict[str, Any]) -> Dict[str, Any]:
        with self._task_lock:
            return super().act(task)

    def do_task(
        self,
        kind: str,
        payload: Dict[str, Any],
        task: str = "",
        verify: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> Dict[str, Any]:
        with self._task_lock:
            _checked_payload(payload)
            with _chain_locked(self._home):
                return super().do_task(kind, payload, task, verify)

    def _ware_run_command(
        self, argv: List[str], timeout: int = 30
    ) -> Dict[str, object]:
        # Registered as the "run_command" ware during DNA __init__ via
        # dynamic lookup, so this override IS the ware: the root-wipe
        # guard runs before the runner's own deny-list.
        _refuse_root_wipe(argv)
        return super()._ware_run_command(argv, timeout)

    # -- thread steps -------------------------------------------------
    def _verify_step(
        self, expected_step: str, expected_prev: Optional[str]
    ) -> Callable[[Dict[str, Any]], None]:
        def _check(payload: Dict[str, Any]) -> None:
            if payload.get("step") != expected_step:
                raise AgentError(
                    f"thread step out of order: expected {expected_step!r}, "
                    f"got {payload.get('step')!r}"
                )
            if payload.get("prev") != expected_prev:
                raise AgentError(
                    f"thread step {expected_step!r} broke ancestry: "
                    "prev link does not match the previous step's receipt"
                )
            if not payload.get("text") or not str(payload["text"]).strip():
                raise AgentError(f"thread step {expected_step!r} needs non-empty text")

        return _check

    def _index_step(
        self, thread_id: str, step: str, receipt: Dict[str, Any], text: str
    ) -> None:
        entry = {
            "step": step,
            "text": scrub_text(str(text)),
            "receipt_hash": receipt["receipt_hash"],
            "prev": receipt["payload"].get("prev"),
        }
        self._threads.setdefault(thread_id, []).append(entry)

    def _step_receipt(self, receipt_hash: str) -> Dict[str, Any]:
        path = self._home / "dynasty" / "receipts" / f"{receipt_hash[:16]}.json"
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise AgentError(
                f"thread step receipt unreadable — tampered or missing: {exc}"
            ) from exc
        if not isinstance(data, dict):
            raise AgentError("thread step receipt is not a record — refused")
        return data

    def thread_cycle(self, thread_id: str, text: str) -> Dict[str, Any]:
        """Run one draft→challenge→consolidate cycle; seal every step.

        Returns the three step receipts plus the sealed consolidation.
        """
        thread_id = scrub_text(str(thread_id or "")).strip()
        text = scrub_text(str(text or "")).strip()
        if not thread_id:
            raise AgentError("thread_cycle needs a thread id")
        if not text:
            raise AgentError("thread_cycle needs non-empty text")
        with self._task_lock:
            if thread_id in self._threads:
                raise AgentError(
                    f"thread {thread_id!r} already woven — threads are write-once"
                )
            draft = self.do_task(
                _STEP_KIND,
                {
                    "thread": thread_id,
                    "step": "draft",
                    "text": text,
                    "prev": None,
                },
                task=f"threadweaver:{thread_id}/draft",
                verify=self._verify_step("draft", None),
            )
            self._index_step(thread_id, "draft", draft, text)
            challenge = self.do_task(
                _STEP_KIND,
                {
                    "thread": thread_id,
                    "step": "challenge",
                    "text": f"challenge: {text}",
                    "prev": draft["receipt_hash"],
                },
                task=f"threadweaver:{thread_id}/challenge",
                verify=self._verify_step("challenge", draft["receipt_hash"]),
            )
            self._index_step(thread_id, "challenge", challenge, text)
            ordered = self.consolidate(thread_id)
            final = self.do_task(
                _STEP_KIND,
                {
                    "thread": thread_id,
                    "step": "consolidate",
                    "text": f"consolidated {len(ordered)} steps by hashline",
                    "prev": challenge["receipt_hash"],
                    "order": [s["receipt_hash"] for s in ordered],
                },
                task=f"threadweaver:{thread_id}/consolidate",
                verify=self._verify_step("consolidate", challenge["receipt_hash"]),
            )
            self._index_step(thread_id, "consolidate", final, text)
            return {
                "thread": thread_id,
                "draft": draft["receipt_hash"],
                "challenge": challenge["receipt_hash"],
                "consolidate": final["receipt_hash"],
                "order": [s["step"] for s in self.consolidate(thread_id)],
            }

    def consolidate(self, thread_id: str, by: str = "hashline") -> List[Dict[str, Any]]:
        """Consolidate a thread by walking receipt-hash ancestry.

        ``by`` is accepted for interface honesty and refused for
        anything but ``"hashline"`` — threads are never consolidated by
        timestamp. Each step's sealed receipt is re-read from disk and
        cross-checked before the walk; a tampered, mismatched, or
        unlinked step refuses the whole consolidation.
        """
        if by != "hashline":
            raise AgentError(
                f"thread consolidation by {by!r} refused — "
                "the thread's truth is its chain, not its clock"
            )
        thread_id = scrub_text(str(thread_id or "")).strip()
        with self._task_lock:
            steps = self._threads.get(thread_id)
            if not steps:
                raise AgentError(f"unknown thread {thread_id!r}")
            steps = [dict(s) for s in steps]
        by_hash = {s["receipt_hash"]: s for s in steps}
        # Cross-check every step against its sealed receipt on disk.
        for step in steps:
            sealed = self._step_receipt(step["receipt_hash"])
            if sealed.get("kind") != _STEP_KIND:
                raise AgentError(
                    f"step {step['step']!r} is not a sealed thread step — refused"
                )
            payload = sealed.get("payload") or {}
            if payload.get("thread") != thread_id:
                raise AgentError(
                    f"step {step['step']!r} belongs to another thread — refused"
                )
            if payload.get("step") != step["step"]:
                raise AgentError(
                    f"step {step['step']!r} mismatches its sealed record — refused"
                )
            if payload.get("prev") != step["prev"]:
                raise AgentError(f"step {step['step']!r} broke ancestry — refused")
        # The tip is the step no other step points back to.
        pointed = {s["prev"] for s in steps if s["prev"]}
        tips = [h for h in by_hash if h not in pointed]
        if len(tips) != 1:
            raise AgentError(
                f"thread {thread_id!r} has {len(tips)} tips — ancestry is broken"
            )
        ordered: List[Dict[str, Any]] = []
        seen = set()
        cursor: Optional[str] = tips[0]
        while cursor is not None:
            if cursor in seen:
                raise AgentError(f"thread {thread_id!r} ancestry loops — refused")
            seen.add(cursor)
            step = by_hash.get(cursor)
            if step is None:
                raise AgentError(f"thread {thread_id!r} ancestry dangles — refused")
            ordered.append(step)
            cursor = step["prev"]
        ordered.reverse()
        return [
            {
                "step": s["step"],
                "text": s["text"],
                "receipt_hash": s["receipt_hash"],
            }
            for s in ordered
        ]

    # -- local media plugin (milestone slice) --------------------------
    def graft_media(self, name: str, path: str) -> Dict[str, Any]:
        """Graft a local-library media file: indexed, hashed, sealed.

        Network sources are refused — grafts are local-only. A missing
        file is refused before anything is sealed.
        """
        name = scrub_text(str(name or "")).strip()
        raw_path = str(path or "").strip()
        if not name:
            raise AgentError("graft_media needs a name")
        if "://" in raw_path:
            raise AgentError("media grafts are local-only — network sources refused")
        if not raw_path:
            raise AgentError("graft_media needs a local file path")
        # Purge finding F-TW-01: the ware shelf scrubs 64-hex strings out
        # of ware RESULTS by design (a hash-shaped string could be key
        # material), so `wares.invoke("hash_file", ...)` returns
        # "[redacted: hash]" — useless as a sealed integrity digest.
        # Sealed receipt payloads are the documented exception (do_task
        # scrubs markers but keeps real content hashes), so the graft
        # hashes below the shelf, with hashlib directly.
        target = Path(raw_path)
        if not target.is_file():
            raise AgentError(f"graft_media refused: not a file: {raw_path!r}")
        digest = hashlib.sha256()
        with open(target, "rb") as fh:
            for chunk in iter(lambda: fh.read(65536), b""):
                digest.update(chunk)
        hex_digest = digest.hexdigest()
        receipt = self.do_task(
            "wave.media_graft",
            {
                "name": name,
                "sha256": hex_digest,
                "source": "local-library",
            },
            task=f"threadweaver:graft/{name}",
        )
        self.note(f"grafted local media {name} sha={hex_digest[:16]}")
        return receipt

    # -- jack-of-all-trades dispatch ----------------------------------
    def handle(self, task: Dict[str, Any]) -> Dict[str, Any]:
        shape = task.get("shape", "echo")
        if shape == "thread_cycle":
            return self.thread_cycle(
                str(task.get("thread", "")), str(task.get("text", ""))
            )
        if shape == "consolidate":
            return {
                "thread": scrub_text(str(task.get("thread", ""))),
                "order": self.consolidate(
                    str(task.get("thread", "")), str(task.get("by", "hashline"))
                ),
            }
        if shape == "media_graft":
            return self.graft_media(
                str(task.get("name", "")), str(task.get("path", ""))
            )
        return super().handle(task)

    # -- first green task ----------------------------------------------
    def first_task(self) -> Dict[str, Any]:
        cycle = self.thread_cycle(
            "threadweaver:first", "the first thread the weaver ever wove"
        )
        return self.do_task(
            "wave.first_task",
            {
                "thread": cycle["thread"],
                "steps": {
                    "draft": cycle["draft"],
                    "challenge": cycle["challenge"],
                    "consolidate": cycle["consolidate"],
                },
                "consolidated_by": "hashline",
                "milestone": self.first_milestone,
            },
            task="threadweaver:first",
        )
