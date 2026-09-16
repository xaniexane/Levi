"""Per-vault export/import: portable bundles, monopoly-minus-one.

Export packs one vault into a ``.tar.gz``::

    <name>.levi-vault.tar.gz
      manifest.json   {format, vault, exported_at, entries, policy}
      policy.json     the retention policy
      entries.jsonl   the entries (MemoryEntry dicts)

Import restores into a vault. Name collision fails closed unless
``--merge`` is given (merges entries by id, keeps the target's policy
unless ``--policy-from-bundle``). The format is plain tar + JSON — no
lock-in, inspectable with system tools.
"""

from __future__ import annotations

import io
import json
import tarfile
import time
from pathlib import Path
from typing import Any, Dict, Optional

from .vault import Vault, VaultError, Vaults

__all__ = ["export_vault", "import_vault", "FORMAT"]

FORMAT = "levi-vault/1"


def export_vault(vault: Vault, dest: Path) -> Path:
    """Export a vault to a .tar.gz bundle. Returns the bundle path."""
    dest = Path(dest)
    manifest = {
        "format": FORMAT,
        "vault": vault.name,
        "exported_at": time.time(),
        "policy": vault.policy,
    }
    entries = [e.to_dict() for e in vault.list(limit=10**9)]
    manifest["entries"] = len(entries)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(dest, "w:gz") as tf:
        for arcname, payload in (
            ("manifest.json", json.dumps(manifest, indent=2)),
            ("policy.json", json.dumps(vault.policy, indent=2)),
            ("entries.jsonl", "\n".join(
                json.dumps(e, separators=(",", ":")) for e in entries)),
        ):
            data = payload.encode("utf-8")
            info = tarfile.TarInfo(arcname)
            info.size = len(data)
            info.mtime = int(time.time())
            tf.addfile(info, io.BytesIO(data))
    return dest


def _read_bundle(path: Path) -> Dict[str, Any]:
    try:
        tf = tarfile.open(path, "r:gz")
    except (tarfile.TarError, OSError) as exc:
        raise VaultError(f"import: cannot read bundle {path} ({exc})") from exc
    with tf:
        try:
            manifest = json.loads(tf.extractfile("manifest.json").read().decode("utf-8"))
        except (KeyError, ValueError, AttributeError) as exc:
            raise VaultError(f"import: bundle {path} has no valid manifest.json") from exc
        if manifest.get("format") != FORMAT:
            raise VaultError(
                f"import: unsupported bundle format {manifest.get('format')!r} "
                f"(expected {FORMAT!r})"
            )
        try:
            policy = json.loads(tf.extractfile("policy.json").read().decode("utf-8"))
            raw_entries = tf.extractfile("entries.jsonl").read().decode("utf-8")
        except (KeyError, AttributeError) as exc:
            raise VaultError(f"import: bundle {path} is missing files") from exc
    entries = []
    for lineno, line in enumerate(raw_entries.splitlines(), 1):
        if not line.strip():
            continue
        try:
            entries.append(json.loads(line))
        except ValueError as exc:
            raise VaultError(
                f"import: bundle entries.jsonl line {lineno} is corrupt ({exc})"
            ) from exc
    return {"manifest": manifest, "policy": policy, "entries": entries}


def import_vault(
    manager: Vaults,
    path: Path,
    *,
    name: Optional[str] = None,
    merge: bool = False,
    policy_from_bundle: bool = False,
) -> Vault:
    """Import a bundle. Fail-closed on name collision unless merge=True."""
    bundle = _read_bundle(Path(path))
    manifest = bundle["manifest"]
    target_name = name or manifest.get("vault")
    if not target_name:
        raise VaultError("import: bundle has no vault name and none was given")
    exists = target_name in manager.list()
    if exists and not merge:
        raise VaultError(
            f"import: vault {target_name!r} already exists "
            "(pass merge=True to merge entries)"
        )
    vault = manager.get(target_name) if exists else manager.create(target_name)
    if policy_from_bundle or not exists:
        vault.policy.update(bundle["policy"])
        vault._policy_path.write_text(json.dumps(vault.policy, indent=2), encoding="utf-8")
    from levi.memory.types import MemoryEntry

    imported = 0
    for raw in bundle["entries"]:
        try:
            entry = MemoryEntry.from_dict(raw)
        except ValueError as exc:
            raise VaultError(f"import: bundle entry failed validation ({exc})") from exc
        if entry.id in vault._entries and not merge:
            raise VaultError(f"import: entry id collision {entry.id}")
        vault._entries[entry.id] = entry
        imported += 1
    vault._persist()
    vault.purge()
    return vault
