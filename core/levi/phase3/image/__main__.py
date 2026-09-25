"""Demo: snapshot, journal, checkpoint, crash-resume, and diff.

Run: ``python -m levi.phase3.image`` (from the repo root with ``core/``
on ``sys.path``). Uses a temporary directory; nothing is kept.
"""

from __future__ import annotations

import json
import tempfile
from typing import Any

from . import ImageRefusal, ImageStore


class Counter:
    """Toy module honoring the state_view / restore_view contract."""

    def __init__(self) -> None:
        self.n = 0

    def state_view(self) -> dict[str, Any]:
        return {"n": self.n}

    def restore_view(self, view: dict[str, Any]) -> None:
        self.n = int(view["n"])


class Ledger:
    """Toy module honoring the state_view / restore_view contract."""

    def __init__(self) -> None:
        self.items: list[str] = []

    def state_view(self) -> dict[str, Any]:
        return {"items": list(self.items)}

    def restore_view(self, view: dict[str, Any]) -> None:
        self.items = list(view["items"])


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="levi-image-demo-") as tmp:
        store = ImageStore(tmp, retention=3)
        counter, ledger = Counter(), Ledger()
        store.register("counter", counter)
        store.register("ledger", ledger)

        store.commit("counter", "incr", {"n": 1})
        store.commit("ledger", "add", {"items": ["first"]})
        cp1 = store.checkpoint(note="demo checkpoint one")
        print("checkpoint 1:", cp1["detail"]["root"][:12], "...")

        store.commit("counter", "incr", {"n": 2})
        store.commit("ledger", "add", {"items": ["first", "second"]})
        cp2 = store.checkpoint(note="demo checkpoint two")
        print("checkpoint 2:", cp2["detail"]["root"][:12], "...")

        print("diff:", store.diff(cp1["detail"]["root"], cp2["detail"]["root"]))

        # Simulate a crash: brand-new objects, same directory.
        store2 = ImageStore(tmp, retention=3)
        counter2, ledger2 = Counter(), Ledger()
        store2.register("counter", counter2)
        store2.register("ledger", ledger2)
        receipt = store2.resume()
        print("resumed:", receipt["detail"])
        print("counter:", counter2.state_view(), "ledger:", ledger2.state_view())
        assert counter2.n == 2 and ledger2.items == ["first", "second"]

        # Corruption is refused, receipted — never a silent wrong state.
        # Corrupt a blob the latest checkpoint's manifest references.
        manifest_path = next((store.root / "images").glob("*.json"))
        manifest = json.loads(manifest_path.read_text())
        victim = next(iter(manifest["tree"].values()))
        blob = store.root / "blobs" / victim[:2] / victim[2:]
        data = bytearray(blob.read_bytes())
        data[0] ^= 0xFF
        blob.write_bytes(bytes(data))
        store3 = ImageStore(tmp, retention=3)
        store3.register("counter", Counter())
        store3.register("ledger", Ledger())
        try:
            store3.resume()
        except ImageRefusal as exc:
            print("refused as required:", exc.receipt_id, exc.reason)
        else:
            raise AssertionError("corruption was not refused")


if __name__ == "__main__":
    main()
