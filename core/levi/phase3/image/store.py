"""The image store: snapshots, checkpoints, journal, resume, diff.

Layout under the store root::

    blobs/<xx>/<rest>      content-addressed blobs (deduped by hash)
    images/<root>.json     image manifests: {"tree": {module: blob_hash},
                                             "state_hash": ...}
    checkpoints/<seq>.json checkpoint records, hash-chained via "prev"
    journal.jsonl          append-only entries, hash-chained via "prev"
    receipts.jsonl         receipts (the only place wall-clock appears)
    meta.json              {receipt_seq, checkpoint_seq}

Resume is stop-and-restart: the latest valid checkpoint is verified,
journal entries after it are replayed into *staging* (never into the
live modules until everything verifies), and the final state hash must
match the journal's last ``after_hash``. Any verification failure is a
receipted refusal (:class:`ImageRefusal`) — a corrupt journal never
silently yields a wrong state.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from .cycle import CycleClock
from .hashing import canonical, hash_json, sha256_hex


class ImageRefusal(Exception):
    """Receipted refusal: resume/verify would not produce a trusted state."""

    def __init__(self, receipt_id: str, reason: str, detail: str = "") -> None:
        super().__init__("%s: %s %s" % (receipt_id, reason, detail))
        self.receipt_id = receipt_id
        self.reason = reason
        self.detail = detail


@runtime_checkable
class ModuleView(Protocol):
    """The state_view / restore_view contract every module honors."""

    def state_view(self) -> dict[str, Any]: ...
    def restore_view(self, view: dict[str, Any]) -> None: ...


class ImageStore:
    """Content-addressed image store with a hash-chained journal."""

    def __init__(self, root: str | Path, retention: int = 5) -> None:
        self.root = Path(root)
        if retention < 1:
            raise ValueError("image: retention must be >= 1")
        self.retention = retention
        self._modules: dict[str, ModuleView] = {}
        for sub in ("blobs", "images", "checkpoints"):
            (self.root / sub).mkdir(parents=True, exist_ok=True)
        self._meta = self._load_meta()
        # A fresh store over an existing directory continues the journal
        # sequence where the previous writer left off.
        last_seq, _ = self._journal_tip()
        self.cycle = CycleClock(last_seq)

    # -- persistence helpers --------------------------------------------
    def _load_meta(self) -> dict[str, int]:
        path = self.root / "meta.json"
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        return {"receipt_seq": 0, "checkpoint_seq": 0}

    def _save_meta(self) -> None:
        (self.root / "meta.json").write_text(
            json.dumps(self._meta, sort_keys=True), encoding="utf-8"
        )

    def _receipt(self, op: str, detail: dict[str, Any]) -> dict[str, Any]:
        self._meta["receipt_seq"] += 1
        receipt = {
            "id": "img-r%d" % self._meta["receipt_seq"],
            "t": datetime.now(timezone.utc).isoformat(),
            "op": op,
            "detail": detail,
        }
        with (self.root / "receipts.jsonl").open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(receipt, sort_keys=True) + "\n")
        self._save_meta()
        return receipt

    def _refuse(self, reason: str, detail: str = "") -> ImageRefusal:
        receipt = self._receipt("refuse", {"reason": reason, "detail": detail})
        return ImageRefusal(receipt["id"], reason, detail)

    # -- modules ----------------------------------------------------------
    def register(self, name: str, module: ModuleView) -> None:
        if not isinstance(module, ModuleView):
            raise ValueError("image: module %r lacks state_view/restore_view" % (name,))
        # Fail fast on non-JSON state: the contract is JSON-able views.
        canonical(module.state_view())
        self._modules[name] = module

    def _current_state(self) -> dict[str, Any]:
        return {name: mod.state_view() for name, mod in self._modules.items()}

    # -- blobs / images ---------------------------------------------------
    def _blob_path(self, blob_hash: str) -> Path:
        return self.root / "blobs" / blob_hash[:2] / blob_hash[2:]

    def _write_blob(self, data: bytes) -> str:
        blob_hash = sha256_hex(data)
        path = self._blob_path(blob_hash)
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        return blob_hash

    def _read_blob(self, blob_hash: str) -> bytes:
        path = self._blob_path(blob_hash)
        if not path.exists():
            raise FileNotFoundError("missing blob %s" % blob_hash)
        data = path.read_bytes()
        if sha256_hex(data) != blob_hash:
            raise ValueError("blob %s failed hash verification" % blob_hash)
        return data

    def snapshot(self) -> dict[str, Any]:
        """Snapshot all module views into a content-addressed image."""
        tree = {}
        for name in sorted(self._modules):
            tree[name] = self._write_blob(canonical(self._modules[name].state_view()))
        state_hash = hash_json(self._current_state())
        root = hash_json({"tree": tree})
        manifest = {"tree": tree, "state_hash": state_hash}
        (self.root / "images" / (root + ".json")).write_text(
            json.dumps(manifest, sort_keys=True), encoding="utf-8"
        )
        return {"root": root, "tree": tree, "state_hash": state_hash}

    # -- journal ------------------------------------------------------------
    def _journal_path(self) -> Path:
        return self.root / "journal.jsonl"

    def read_journal(self) -> list[dict[str, Any]]:
        path = self._journal_path()
        if not path.exists():
            return []
        return [
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    def _journal_tip(self) -> tuple[int, str]:
        entries = self.read_journal()
        if not entries:
            return 0, ""
        return entries[-1]["seq"], entries[-1]["entry_hash"]

    def commit(
        self, module: str, op: str, new_view: dict[str, Any], note: str = ""
    ) -> dict[str, Any]:
        """Record one state transition: apply ``new_view`` and journal it.

        ``before_hash``/``after_hash`` are full-state hashes, so the
        journal is complete: every transition between checkpoints has an
        entry, whatever mutated the module beforehand.
        """
        if module not in self._modules:
            raise ValueError("image: unknown module %r" % (module,))
        canonical(new_view)  # fail fast on non-JSON views
        seq = self.cycle.tick()
        _, tip = self._journal_tip()
        before = self._current_state()
        self._modules[module].restore_view(new_view)
        after = self._current_state()
        entry = {
            "seq": seq,
            "cycle": self.cycle.peek(),
            "module": module,
            "op": op,
            "note": note,
            "before_hash": hash_json(before),
            "after_hash": hash_json(after),
            "view": new_view,
            "prev": tip,
        }
        entry["entry_hash"] = hash_json(entry)
        with self._journal_path().open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, sort_keys=True) + "\n")
        return self._receipt(
            "journal",
            {"seq": seq, "module": module, "op": op, "after_hash": entry["after_hash"]},
        )

    # -- checkpoints ----------------------------------------------------------
    def _checkpoint_files(self) -> list[Path]:
        return sorted((self.root / "checkpoints").glob("*.json"))

    def checkpoint(self, note: str = "") -> dict[str, Any]:
        """Seal a checkpoint: image + hash-chained record. HOUSEKEEPING only."""
        image = self.snapshot()
        self._meta["checkpoint_seq"] += 1
        seq = self._meta["checkpoint_seq"]
        prev = ""
        files = self._checkpoint_files()
        if files:
            prev = json.loads(files[-1].read_text(encoding="utf-8"))["record_hash"]
        journal_seq, journal_tip = self._journal_tip()
        record = {
            "seq": seq,
            "cycle": self.cycle.peek(),
            "journal_seq": journal_seq,
            "journal_tip": journal_tip,
            "root": image["root"],
            "state_hash": image["state_hash"],
            "prev": prev,
            "note": note,
        }
        record["record_hash"] = hash_json(record)
        (self.root / "checkpoints" / ("%08d.json" % seq)).write_text(
            json.dumps(record, sort_keys=True), encoding="utf-8"
        )
        self._save_meta()
        self._prune()
        return self._receipt(
            "checkpoint",
            {"seq": seq, "root": image["root"], "state_hash": image["state_hash"]},
        )

    def _prune(self) -> None:
        """Retention: keep the newest ``retention`` checkpoints; GC the rest."""
        files = self._checkpoint_files()
        drop = files[: max(0, len(files) - self.retention)]
        kept_roots = set()
        for path in files[len(drop) :]:
            kept_roots.add(json.loads(path.read_text(encoding="utf-8"))["root"])
        for path in drop:
            path.unlink()
        # Drop manifests no kept checkpoint references.
        for manifest in (self.root / "images").glob("*.json"):
            if manifest.stem not in kept_roots:
                manifest.unlink()
        # GC blobs unreferenced by kept manifests.
        referenced: set[str] = set()
        for root in kept_roots:
            manifest = self.root / "images" / (root + ".json")
            if manifest.exists():
                tree = json.loads(manifest.read_text(encoding="utf-8"))["tree"]
                referenced.update(tree.values())
        for shard in (self.root / "blobs").iterdir():
            if not shard.is_dir():
                continue
            for blob in shard.iterdir():
                if shard.name + blob.name not in referenced:
                    blob.unlink()

    # -- verification ---------------------------------------------------------
    def _load_checkpoints(self) -> list[dict[str, Any]]:
        records = []
        for path in self._checkpoint_files():
            try:
                records.append(json.loads(path.read_text(encoding="utf-8")))
            except (OSError, ValueError) as exc:
                raise self._refuse(
                    "checkpoint-corrupt", "unreadable %s: %s" % (path.name, exc)
                ) from None
        return records

    def _verify_journal_entries(self) -> str:
        """Verify the journal hash chain; return the tip entry hash."""
        tip = ""
        for entry in self.read_journal():
            check = {k: v for k, v in entry.items() if k != "entry_hash"}
            if hash_json(check) != entry.get("entry_hash"):
                raise self._refuse(
                    "journal-corrupt",
                    "entry %s failed hash verification" % entry.get("seq"),
                )
            if entry.get("prev", "") != tip:
                raise self._refuse(
                    "journal-chain-broken",
                    "entry %s does not link its predecessor" % entry.get("seq"),
                )
            tip = entry["entry_hash"]
        return tip

    def verify_journal(self) -> int:
        """Verify the journal hash chain; return the entry count."""
        self._verify_journal_entries()
        return len(self.read_journal())

    def verify_chain(self) -> dict[str, int]:
        """Verify checkpoint + journal hash chains. Refuses on corruption."""
        records = self._load_checkpoints()
        if not records:
            raise self._refuse("no-checkpoint", "no checkpoints to verify")
        prev = ""
        for rec in records:
            check = {k: v for k, v in rec.items() if k != "record_hash"}
            if hash_json(check) != rec.get("record_hash"):
                raise self._refuse(
                    "checkpoint-corrupt",
                    "record %s failed hash verification" % rec.get("seq"),
                )
            if rec.get("prev", "") != prev:
                raise self._refuse(
                    "checkpoint-chain-broken",
                    "record %s does not link its predecessor" % rec.get("seq"),
                )
            prev = rec["record_hash"]
        self._verify_journal_entries()
        # Every checkpoint's image must be intact and content-addressed:
        # a corrupt historical blob is refused now, not at resume time.
        for rec in records:
            manifest_path = self.root / "images" / (rec["root"] + ".json")
            if not manifest_path.exists():
                raise self._refuse(
                    "checkpoint-corrupt",
                    "missing image manifest for checkpoint %s" % rec.get("seq"),
                )
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except ValueError as exc:
                raise self._refuse(
                    "checkpoint-corrupt",
                    "unreadable manifest for checkpoint %s: %s" % (rec.get("seq"), exc),
                ) from None
            if hash_json({"tree": manifest["tree"]}) != rec["root"]:
                raise self._refuse(
                    "checkpoint-corrupt",
                    "manifest for checkpoint %s does not match its root"
                    % rec.get("seq"),
                )
            try:
                for blob_hash in manifest["tree"].values():
                    self._read_blob(blob_hash)
            except (OSError, ValueError) as exc:
                raise self._refuse("blob-corrupt", str(exc)) from None
        return {"checkpoints": len(records), "entries": len(self.read_journal())}

    # -- resume ---------------------------------------------------------------
    def resume(self) -> dict[str, Any]:
        """Load the latest valid checkpoint and replay the journal.

        Everything verifies before any live module is touched: staging
        first, ``restore_view`` only on success. Any failure is a
        receipted refusal — never a silent wrong state.
        """
        records = self._load_checkpoints()
        if not records:
            raise self._refuse("no-checkpoint", "nothing to resume from")
        # Verify the whole checkpoint chain, then use the latest record.
        self.verify_chain()
        rec = records[-1]
        manifest_path = self.root / "images" / (rec["root"] + ".json")
        if not manifest_path.exists():
            raise self._refuse(
                "checkpoint-corrupt", "missing image manifest for latest checkpoint"
            )
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except ValueError as exc:
            raise self._refuse(
                "checkpoint-corrupt", "unreadable image manifest: %s" % exc
            ) from None
        if hash_json({"tree": manifest["tree"]}) != rec["root"]:
            raise self._refuse(
                "checkpoint-corrupt", "image manifest does not match checkpoint root"
            )
        staged: dict[str, Any] = {}
        try:
            for name, blob_hash in manifest["tree"].items():
                staged[name] = json.loads(self._read_blob(blob_hash).decode("utf-8"))
        except (OSError, ValueError) as exc:
            raise self._refuse("blob-corrupt", str(exc)) from None
        if hash_json(staged) != rec["state_hash"]:
            raise self._refuse("checkpoint-corrupt", "checkpoint state hash mismatch")
        # Replay journal entries after the checkpoint, verifying each step.
        tip = rec.get("journal_tip", "")
        entries = [e for e in self.read_journal() if e["seq"] > rec["journal_seq"]]
        for entry in entries:
            if entry.get("prev", "") != tip:
                raise self._refuse(
                    "journal-chain-broken",
                    "entry %s does not continue the checkpoint tip" % entry.get("seq"),
                )
            check = {k: v for k, v in entry.items() if k != "entry_hash"}
            if hash_json(check) != entry.get("entry_hash"):
                raise self._refuse(
                    "journal-corrupt",
                    "entry %s failed hash verification" % entry.get("seq"),
                )
            if entry["module"] not in staged:
                raise self._refuse(
                    "journal-corrupt",
                    "entry %s names unknown module %r"
                    % (entry.get("seq"), entry["module"]),
                )
            if hash_json(staged) != entry["before_hash"]:
                raise self._refuse(
                    "journal-corrupt",
                    "entry %s before_hash mismatch: journal disagrees with replayed state"
                    % entry.get("seq"),
                )
            staged[entry["module"]] = entry["view"]
            if hash_json(staged) != entry["after_hash"]:
                raise self._refuse(
                    "journal-corrupt",
                    "entry %s after_hash mismatch" % entry.get("seq"),
                )
            tip = entry["entry_hash"]
        if entries and hash_json(staged) != entries[-1]["after_hash"]:
            raise self._refuse(
                "journal-corrupt", "final state does not match journal tip"
            )
        # All verified: restore into the live modules.
        for name, view in staged.items():
            if name in self._modules:
                self._modules[name].restore_view(view)
        return self._receipt(
            "resume",
            {
                "checkpoint_seq": rec["seq"],
                "replayed": len(entries),
                "state_hash": hash_json(staged),
            },
        )

    # -- diff -------------------------------------------------------------------
    def diff(self, root_a: str, root_b: str) -> list[dict[str, str]]:
        """Mechanical diff between two images, entry by entry."""
        manifests = {}
        for root in (root_a, root_b):
            path = self.root / "images" / (root + ".json")
            if not path.exists():
                raise ValueError("image: unknown image root %s" % root)
            manifests[root] = json.loads(path.read_text(encoding="utf-8"))["tree"]
        tree_a, tree_b = manifests[root_a], manifests[root_b]
        out = []
        for name in sorted(set(tree_a) | set(tree_b)):
            ha, hb = tree_a.get(name), tree_b.get(name)
            if ha is None:
                out.append({"path": name, "kind": "added"})
            elif hb is None:
                out.append({"path": name, "kind": "removed"})
            elif ha != hb:
                out.append({"path": name, "kind": "changed"})
        return out
