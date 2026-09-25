"""Acceptance tests for phase3/image (A7 salvage formal spec, T1-T6).

Hermetic: no network, no daemons, no HOME writes (all state lives in
pytest tmp dirs). Sockets are blocked in the T6 offline test by a local
fixture (no import of the beginning team's synthesis/offline.py).
"""

from __future__ import annotations

import json
import random
import shutil
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from levi.phase3.image import ImageRefusal, ImageStore, hash_json


@pytest.fixture
def no_sockets(monkeypatch):
    """Block all socket use: the offline test must not touch the network."""
    import socket

    def _blocked(*args, **kwargs):
        raise AssertionError("network access is disabled in this test")

    monkeypatch.setattr(socket, "socket", _blocked)
    monkeypatch.setattr(socket, "create_connection", _blocked)
    monkeypatch.setattr(socket, "getaddrinfo", _blocked)
    return True


class Counter:
    def __init__(self) -> None:
        self.n = 0

    def state_view(self) -> dict[str, Any]:
        return {"n": self.n}

    def restore_view(self, view: dict[str, Any]) -> None:
        self.n = int(view["n"])


class Ledger:
    def __init__(self) -> None:
        self.items: list[str] = []

    def state_view(self) -> dict[str, Any]:
        return {"items": list(self.items)}

    def restore_view(self, view: dict[str, Any]) -> None:
        self.items = list(view["items"])


class Flag:
    def __init__(self) -> None:
        self.on = False

    def state_view(self) -> dict[str, Any]:
        return {"on": self.on}

    def restore_view(self, view: dict[str, Any]) -> None:
        self.on = bool(view["on"])


def _two_module_store(root: Path) -> tuple[ImageStore, Counter, Ledger]:
    store = ImageStore(root)
    counter, ledger = Counter(), Ledger()
    store.register("counter", counter)
    store.register("ledger", ledger)
    return store, counter, ledger


def _dir_bytes(root: Path) -> int:
    return sum(p.stat().st_size for p in root.rglob("*") if p.is_file())


# ---------------------------------------------------------------- T1
def _build_run(root: Path, n_commits: int = 80) -> list[dict[str, Any]]:
    """80 commits; returns the full state after each commit (states[0]
    is the pre-run state, sealed by a baseline checkpoint)."""
    store, counter, ledger = _two_module_store(root)
    states = [
        deepcopy({"counter": counter.state_view(), "ledger": ledger.state_view()})
    ]
    store.checkpoint(note="t1 baseline")
    for i in range(1, n_commits + 1):
        if i % 2 == 1:
            store.commit("counter", "incr", {"n": i})
        else:
            store.commit("ledger", "add", {"items": [f"item-{j}" for j in range(i)]})
        states.append(
            deepcopy({"counter": counter.state_view(), "ledger": ledger.state_view()})
        )
    assert len(store.read_journal()) == n_commits
    return states


def test_t1_resume_fidelity_50_seeded_crashes(tmp_path):
    base = tmp_path / "base"
    base.mkdir()
    states = _build_run(base)
    n_commits = len(states) - 1
    rng = random.Random(20260920)
    cuts = [rng.randrange(0, n_commits + 1) for _ in range(50)]
    assert len(set(cuts)) > 1  # the cuts actually vary
    for t, k in enumerate(cuts):
        trial = tmp_path / f"trial-{t}"
        shutil.copytree(base, trial)
        journal = trial / "journal.jsonl"
        lines = journal.read_text(encoding="utf-8").splitlines()
        journal.write_text("\n".join(lines[:k]) + ("\n" if k else ""), encoding="utf-8")
        store = ImageStore(trial)
        counter, ledger = Counter(), Ledger()
        store.register("counter", counter)
        store.register("ledger", ledger)
        receipt = store.resume()
        assert receipt["op"] == "resume"
        assert receipt["detail"]["replayed"] == k
        # Byte-identical to the pre-crash committed state at cut k.
        assert hash_json(counter.state_view()) == hash_json(states[k]["counter"])
        assert hash_json(ledger.state_view()) == hash_json(states[k]["ledger"])
        assert counter.state_view() == states[k]["counter"]
        assert ledger.state_view() == states[k]["ledger"]


# ---------------------------------------------------------------- T2
def test_t2_journal_completeness_1000_transitions(tmp_path):
    store, _, _ = _two_module_store(tmp_path)
    for i in range(1000):
        if i % 2 == 0:
            store.commit("counter", "incr", {"n": i + 1})
        else:
            store.commit("ledger", "add", {"items": [f"e-{i}"]})
    entries = store.read_journal()
    assert len(entries) == 1000
    assert [e["seq"] for e in entries] == list(range(1, 1001))  # zero gaps
    assert all(e["before_hash"] != e["after_hash"] for e in entries)
    report = store.verify_journal()  # hash-chained, every entry
    assert report == 1000


# ---------------------------------------------------------------- T3
def _corrupt_setup(root: Path) -> ImageStore:
    store, _, _ = _two_module_store(root)
    store.commit("counter", "incr", {"n": 1})
    store.commit("ledger", "add", {"items": ["a"]})
    store.commit("counter", "incr", {"n": 2})
    store.checkpoint(note="c1")
    store.commit("ledger", "add", {"items": ["a", "b"]})
    store.checkpoint(note="c2")
    return store


def _flip_blob(root: Path, manifest_root: str) -> None:
    manifest = json.loads((root / "images" / (manifest_root + ".json")).read_text())
    victim = next(iter(sorted(manifest["tree"].values())))
    blob = root / "blobs" / victim[:2] / victim[2:]
    data = bytearray(blob.read_bytes())
    data[0] ^= 0xFF
    blob.write_bytes(bytes(data))


def _tamper_journal(root: Path, mode: str) -> None:
    path = root / "journal.jsonl"
    lines = path.read_text(encoding="utf-8").splitlines()
    entry = json.loads(lines[1])
    if mode == "view":
        entry["view"] = {"tampered": True}
    else:
        entry["prev"] = "00" * 32
    lines[1] = json.dumps(entry, sort_keys=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _tamper_checkpoint(root: Path, mode: str) -> None:
    files = sorted((root / "checkpoints").glob("*.json"))
    path = files[-1]
    rec = json.loads(path.read_text(encoding="utf-8"))
    if mode == "root":
        rec["root"] = "ff" * 64
    else:
        rec["prev"] = "00" * 64
    path.write_text(json.dumps(rec, sort_keys=True), encoding="utf-8")


def test_t3_corruption_refusal_30_injections(tmp_path):
    modes = ["blob", "journal-view", "journal-prev", "cp-root", "cp-prev"]
    for t in range(30):
        mode = modes[t % len(modes)]
        trial = tmp_path / f"corrupt-{t}"
        trial.mkdir()
        _corrupt_setup(trial)
        cp_root = json.loads(
            sorted((trial / "checkpoints").glob("*.json"))[-1].read_text()
        )["root"]
        if mode == "blob":
            _flip_blob(trial, cp_root)
        elif mode == "journal-view":
            _tamper_journal(trial, "view")
        elif mode == "journal-prev":
            _tamper_journal(trial, "prev")
        elif mode == "cp-root":
            _tamper_checkpoint(trial, "root")
        else:
            _tamper_checkpoint(trial, "prev")

        store2 = ImageStore(trial)
        counter, ledger = Counter(), Ledger()
        store2.register("counter", counter)
        store2.register("ledger", ledger)
        before = (counter.state_view(), ledger.state_view())
        receipts_before = sum(
            1
            for _ in (trial / "receipts.jsonl").read_text(encoding="utf-8").splitlines()
            if _.strip()
        )
        with pytest.raises(ImageRefusal) as excinfo:
            store2.resume()
        # Receipted refusal, never a silent wrong state.
        assert excinfo.value.receipt_id.startswith("img-r")
        receipts = [
            json.loads(line)
            for line in (trial / "receipts.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
            if line.strip()
        ]
        assert len(receipts) == receipts_before + 1
        assert receipts[-1]["id"] == excinfo.value.receipt_id
        assert receipts[-1]["op"] == "refuse"
        # Live modules were never touched with a wrong state.
        assert (counter.state_view(), ledger.state_view()) == before


# ---------------------------------------------------------------- T4
def test_t4_diffability_20_image_pairs(tmp_path):
    store = ImageStore(tmp_path, retention=25)  # keep every pair's manifests
    alpha, beta, gamma = Counter(), Counter(), Flag()
    store.register("alpha", alpha)
    store.register("beta", beta)
    store.register("gamma", gamma)
    rng = random.Random(13579)
    roots = []
    cp = store.checkpoint(note="pair baseline")
    roots.append(cp["detail"]["root"])
    journal_marks = [0]
    for _ in range(20):
        touched: set[str] = set()
        for _ in range(rng.randrange(1, 4)):
            name = rng.choice(["alpha", "beta", "gamma"])
            touched.add(name)
            if name == "gamma":
                store.commit(name, "flip", {"on": not gamma.on})
            else:
                mod = alpha if name == "alpha" else beta
                store.commit(name, "incr", {"n": mod.n + 1})
        cp = store.checkpoint(note="pair")
        roots.append(cp["detail"]["root"])
        journal_marks.append(len(store.read_journal()))
    for i in range(20):
        diff = store.diff(roots[i], roots[i + 1])
        entries = store.read_journal()[journal_marks[i] : journal_marks[i + 1]]
        journal_modules = {e["module"] for e in entries}
        diff_paths = {d["path"] for d in diff}
        # The mechanical diff matches the journal entries between them.
        assert diff_paths == journal_modules, (diff, journal_modules)
        assert all(d["kind"] == "changed" for d in diff)
        assert [d["path"] for d in diff] == sorted(diff_paths)


# ---------------------------------------------------------------- T5
def test_t5_retention_bounds_disk(tmp_path):
    store = ImageStore(tmp_path, retention=5)
    counter, ledger = Counter(), Ledger()
    store.register("counter", counter)
    store.register("ledger", ledger)
    store.commit("counter", "set", {"n": 7})
    store.commit("ledger", "add", {"items": ["steady"]})

    def blob_count() -> int:
        return sum(1 for _ in (tmp_path / "blobs").rglob("*") if _.is_file())

    for _ in range(10):
        store.checkpoint()
    blobs_10 = blob_count()
    bytes_10 = _dir_bytes(tmp_path)
    for _ in range(90):
        store.checkpoint()
    # Retention holds: exactly 5 checkpoints; dedupe holds: blob count
    # constant; disk growth bounded despite 10x the checkpoints.
    assert len(list((tmp_path / "checkpoints").glob("*.json"))) == 5
    assert blob_count() == blobs_10
    assert _dir_bytes(tmp_path) <= bytes_10 + 65536


# ---------------------------------------------------------------- T6
def test_t6_offline_checkpoint_and_resume(no_sockets, tmp_path):
    assert no_sockets
    store, counter, ledger = _two_module_store(tmp_path)
    store.commit("counter", "incr", {"n": 42})
    store.checkpoint(note="offline")
    store.commit("ledger", "add", {"items": ["offline"]})
    store2 = ImageStore(tmp_path)
    c2, l2 = Counter(), Ledger()
    store2.register("counter", c2)
    store2.register("ledger", l2)
    receipt = store2.resume()
    assert receipt["detail"]["replayed"] == 1
    assert c2.state_view() == {"n": 42}
    assert l2.state_view() == {"items": ["offline"]}
    assert store2.verify_chain() == {"checkpoints": 1, "entries": 2}
