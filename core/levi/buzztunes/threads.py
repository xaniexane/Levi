"""Shared listening threads — the Bloome half of the mix.

A thread is agent-messaging with native media woven in: members join,
agents curate and play INTO the thread, everyone shares the queue.
L5: agent actions reach a queue ONLY through this surface. The engine
exposes no agent-inject method — there is deliberately nothing to call.

Thread journeys use the real EchoverseEngine: a vibe seed expands into
candidate paths, the thread scores them; skipped sequences are vaulted
(good qualities salvaged), completed listens are marked success.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

from .engine import BuzzEngine
from .providers import Track
from .receipts import ReceiptLog


class ListeningThread:
    def __init__(self, thread_id: str, name: str, engine: BuzzEngine,
                 data_dir: str | Path) -> None:
        self.id = thread_id
        self.name = name
        self.engine = engine
        self.receipts = ReceiptLog(Path(data_dir) / "threads" / thread_id)
        self.members: List[str] = []
        self.curations: List[Dict] = []  # agent curations, in order
        from levi.echoverse.engine import EchoverseEngine
        self.journey = EchoverseEngine(
            Path(data_dir) / "threads" / thread_id / "journey")

    def join(self, member: str) -> Dict:
        if member not in self.members:
            self.members.append(member)
        self.engine.demand.record("thread_join", self.id, {"member": member})
        return self.receipts.emit("thread.join", actor=member,
                                  details={"thread": self.id})

    def add_curation(self, agent_name: str, tracks: List[Track]) -> Dict:
        """THE thread surface (L5). Agents curate here or nowhere."""
        entry = {"agent": agent_name,
                 "tracks": [t.to_record() for t in tracks]}
        self.curations.append(entry)
        for t in tracks:
            self.engine.queue_add(t, actor=f"thread:{self.id}:{agent_name}")
        return self.receipts.emit("thread.curate", actor=agent_name, details={
            "thread": self.id, "tracks": [t.id for t in tracks]})

    def journey_round(self, vibe_seed: str) -> Dict:
        """Expand the vibe into candidate paths; the thread scores them."""
        result = self.journey.round(vibe_seed)
        self.receipts.emit("thread.journey", actor="thread", details={
            "thread": self.id, "seed": vibe_seed,
            "paths": len(result.get("optionalPaths", []))})
        return result

    def journey_skip(self, label: str, note: str = "") -> Dict:
        node = self.journey.vault_negative(label, note=note)
        return self.receipts.emit("thread.journey.skip", actor="thread",
                                  details={"thread": self.id,
                                           "vaulted": label})

    def journey_complete(self, seed: str, path_id: str, label: str) -> Dict:
        self.journey.mark_success(seed, path_id, label)
        return self.receipts.emit("thread.journey.complete", actor="thread",
                                  details={"thread": self.id,
                                           "path": path_id})

    def shared_queue(self) -> List[Dict]:
        return [t.to_record() for t in self.engine.queue_list()]


class ThreadStore:
    def __init__(self, engine: BuzzEngine, data_dir: str | Path) -> None:
        self.engine = engine
        self.data_dir = Path(data_dir)
        self._threads: Dict[str, ListeningThread] = {}
        self._counter = 0

    def create(self, name: str, actor: str = "owner") -> ListeningThread:
        self._counter += 1
        tid = f"thread-{self._counter:03d}"
        thread = ListeningThread(tid, name, self.engine, self.data_dir)
        self._threads[tid] = thread
        thread.receipts.emit("thread.create", actor=actor,
                             details={"thread": tid, "name": name})
        return thread

    def get(self, thread_id: str) -> ListeningThread:
        try:
            return self._threads[thread_id]
        except KeyError:
            raise KeyError(f"unknown thread {thread_id!r}") from None

    def list(self) -> List[Dict]:
        return [{"id": t.id, "name": t.name, "members": t.members,
                 "curations": len(t.curations)} for t in self._threads.values()]
