"""Pack assembler: spec -> genesis pack directory.

A spec is: {"variants": [{"source": <family>, "mode": <mode>, "seed": <int>}, ...]}
Base config: pack name, optional price quote inputs.

Pack layout (all under <packs_root>/<pack_id>/):
  manifest.json   — pack id, variant roster with lineage hashes, license
                    terms reference, build receipt hash-chain
  variants/       — one self-describing module per variant
  license.json    — minted license record (buyer UNASSIGNED)
  quote.json      — paper price quote + paper checkout receipt
  install.py      — install routine: copies into a target LEVI_HOME,
                    verifies the hash chain, dry-run supported
  README.md       — buyer README with honest limits

Hash-chain: each file hashed in sorted order, chained —
  chain_i = sha256(chain_{i-1} || relpath || file_bytes).
``verify_pack`` re-computes and compares against the manifest.

Operator-contract seam: each forged variant is registered as a real
Operator via ``levi.genesis.operators.register_variant`` (kind ``si``,
backing mind delegated to the default operator registry — local rules
engine unless the keeper picks another substrate). Registration never
fails the build: failures are recorded per-variant in the manifest.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from levi.genesis import license as genesis_license
from levi.genesis import money as genesis_money
from levi.genesis import parts
from levi.genesis import remix

FORM_NAME = "genesis.assemble"
OPERATOR_INTEGRATION_CALL = (
    "levi.genesis.operators.register_variant(variant_dict)  # per forged variant"
)


def packs_root(root: Optional[Path] = None) -> Path:
    import os

    if root is not None:
        return Path(root)
    env = os.environ.get("LEVI_GENESIS_PACKS")
    if env:
        return Path(env)
    return Path.home() / ".levi" / "genesis" / "packs"


def spec_hash(spec: Dict[str, Any]) -> str:
    canonical = json.dumps(spec, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def pack_id_for(spec: Dict[str, Any]) -> str:
    return "gen-pack-%s" % spec_hash(spec)[:12]


def _hash_chain(files: List[Path], root: Path) -> List[Dict[str, str]]:
    chain = "0" * 64
    receipt = []
    for f in sorted(files, key=lambda p: p.relative_to(root).as_posix()):
        rel = f.relative_to(root).as_posix()
        digest = hashlib.sha256(
            (chain + rel).encode("utf-8") + f.read_bytes()
        ).hexdigest()
        receipt.append({"path": rel, "sha256": digest})
        chain = digest
    return receipt


_VARIANT_MODULE_TMPL = '''"""Genesis variant: {name}.

{description}
"""

from __future__ import annotations

VARIANT = {variant_json}


def describe() -> str:
    """Human-readable variant card."""
    lines = [
        "variant: %s (%s)" % (VARIANT["name"], VARIANT["variant_id"]),
        "forged: %s (seed %d)" % (VARIANT["mode"], VARIANT["seed"]),
        "",
        VARIANT["description"],
        "",
        "traits:",
    ]
    lines += ["  - %s" % t for t in VARIANT["traits"]]
    return "\\n".join(lines)


if __name__ == "__main__":
    print(describe())
'''


_README_TMPL = """# {pack_name}

A **genesis pack**: a lifetime, single-copy variant of the LEVI system —
one-time purchase, yours forever.

## What's inside

{variant_bullets}

## Install

```sh
python3 install.py --target ~/levi-home
```

Dry run first to see what it would do:

```sh
python3 install.py --target ~/levi-home --dry-run
```

The installer copies this pack into `<target>/genesis/{pack_id}/` and
verifies every file against the manifest hash-chain before finishing.
`installed.json` is written as the receipt.

## License

See `license.json`. Terms: {terms_summary}. The buyer field is filled in
at the sale step.

## Honest limits — what this pack is NOT

- This is NOT the full LEVI organism. The variants are **remixes** —
  renamed, remixed, recycled, mutated builds derived from capability
  families. They do not carry the full system's memory, growth loop,
  daemon, or native brain.
- Variants are self-describing capability cards with trait behavior,
  not live agents with persistent state.
- Price shown in `quote.json` is a paper quote — no payment was taken,
  no rail was used.
- For sector-tailored editions (government, schools, universities,
  corporate, tiny businesses), see the edition manifests bundled with
  the full system — this pack references them, it does not replace them.

Pack id: `{pack_id}`
Built: {built_at}
"""


def _variant_module_source(variant: Dict[str, Any]) -> str:
    return _VARIANT_MODULE_TMPL.format(
        name=variant["name"],
        description=variant["description"],
        variant_json=json.dumps(variant, indent=2, sort_keys=True),
    )


def _try_operator_register(variant: Dict[str, Any]) -> Dict[str, Any]:
    """Register the forged variant as an Operator. Never fails the build."""
    try:
        from levi.genesis import operators as _gen_operators
    except Exception as exc:
        return {"status": "pending", "reason": "levi.genesis.operators absent: %s" % exc}
    try:
        operator = _gen_operators.register_variant(dict(variant))
    except Exception as exc:
        return {"status": "failed", "reason": "%s: %s" % (type(exc).__name__, exc)}
    return {
        "status": "registered",
        "operator": operator.variant_id,
        "name": operator.name,
        "kind": operator.kind,
    }


def assemble(
    spec: Dict[str, Any],
    root: Optional[Path] = None,
    quote_kwargs: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Assemble a genesis pack from a spec. Returns assembly summary."""
    variants_spec = spec.get("variants") or []
    if not variants_spec:
        raise ValueError("spec needs at least one variant entry")
    roster = remix.forge_roster(variants_spec)

    pack_id = pack_id_for(spec)
    pack_dir = packs_root(root) / pack_id
    if pack_dir.exists():
        shutil.rmtree(pack_dir)
    variants_dir = pack_dir / "variants"
    variants_dir.mkdir(parents=True)

    built_at = datetime.now(timezone.utc).isoformat()
    pack_name = spec.get("name") or "Genesis Pack"

    # 1. variant modules
    for v in roster:
        src = _variant_module_source(v)
        remix._guard_output(src, field="variant module %s" % v["variant_id"])
        (variants_dir / ("%s.py" % v["variant_id"])).write_text(
            src, encoding="utf-8"
        )

    # 2. license
    license_record = genesis_license.mint_license(pack_id, spec_hash(spec))

    # 3. paper money seam
    price = genesis_money.price_receipt(len(roster), **(quote_kwargs or {}))

    # 4. operator seam
    op_status = [_try_operator_register(v) for v in roster]
    operator_integration = {
        "status": (
            "registered"
            if all(s["status"] == "registered" for s in op_status)
            else "pending"
        ),
        "detail": op_status,
        "call": OPERATOR_INTEGRATION_CALL,
    }

    # 5. README
    bullets = "\n".join(
        "- **%s** (%s): %s" % (v["name"], v["mode"], v["description"])
        for v in roster
    )
    (pack_dir / "README.md").write_text(
        _README_TMPL.format(
            pack_name=pack_name,
            variant_bullets=bullets,
            pack_id=pack_id,
            built_at=built_at,
            terms_summary=genesis_license.TERMS["sale"],
        ),
        encoding="utf-8",
    )

    # 6. install routine
    (pack_dir / "install.py").write_text(_INSTALL_PY, encoding="utf-8")

    # 7. manifest (written before hash-chain, then chain computed over all)
    manifest = {
        "form": FORM_NAME,
        "pack_id": pack_id,
        "pack_name": pack_name,
        "built_at": built_at,
        "spec_hash": spec_hash(spec),
        "license_terms": "lifetime single-copy",
        "terms_version": genesis_license.TERMS_VERSION,
        "variants": [
            {
                "variant_id": v["variant_id"],
                "name": v["name"],
                "mode": v["mode"],
                "seed": v["seed"],
                "lineage_hash": v["lineage"]["lineage_hash"],
                "module": "variants/%s.py" % v["variant_id"],
            }
            for v in roster
        ],
        "license": license_record,
        "operator_integration": operator_integration,
        "parts_bin_receipt": parts.catalog_receipt(),
        "receipt_chain": [],  # filled below
    }
    (pack_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8"
    )
    (pack_dir / "license.json").write_text(
        json.dumps(license_record, indent=2, sort_keys=True), encoding="utf-8"
    )
    (pack_dir / "quote.json").write_text(
        json.dumps(price, indent=2, sort_keys=True), encoding="utf-8"
    )

    # 8. hash-chain receipt over every pack file EXCEPT the manifest itself
    #    (the manifest is bound by the closing final link instead).
    all_files = [
        p
        for p in pack_dir.rglob("*")
        if p.is_file() and p.name != "manifest.json"
    ]
    manifest["receipt_chain"] = _hash_chain(all_files, pack_dir)
    (pack_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8"
    )
    # Closing link: bind the manifest's own canonical bytes to the chain.
    canonical = json.dumps(manifest, indent=2, sort_keys=True)
    final = hashlib.sha256(
        (manifest["receipt_chain"][-1]["sha256"] + "manifest.json").encode("utf-8")
        + canonical.encode("utf-8")
    ).hexdigest()
    manifest["receipt_chain"].append({"path": "manifest.json#final", "sha256": final})
    (pack_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8"
    )

    return {
        "pack_id": pack_id,
        "pack_dir": str(pack_dir),
        "variant_count": len(roster),
        "variants": [v["variant_id"] for v in roster],
        "final_hash": final,
        "operator_integration": operator_integration["status"],
    }


def verify_pack(pack_dir: Path) -> Dict[str, Any]:
    """Re-verify a pack's hash-chain against its manifest."""
    pack_dir = Path(pack_dir)
    manifest_path = pack_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    chain = manifest.get("receipt_chain") or []
    if len(chain) < 2:
        return {"ok": False, "reason": "no receipt chain in manifest"}
    entries = chain[:-1]  # last entry is the manifest#final link
    files = [pack_dir / e["path"] for e in entries]
    if not all(f.is_file() for f in files):
        missing = [e["path"] for e, f in zip(entries, files) if not f.is_file()]
        return {"ok": False, "reason": "missing files: %s" % missing}
    recomputed = _hash_chain(files, pack_dir)
    for got, want in zip(recomputed, entries):
        if got["sha256"] != want["sha256"]:
            return {"ok": False, "reason": "hash mismatch at %s" % want["path"]}
    # The final link binds the manifest's own canonical bytes (without the
    # final link itself, exactly as written at assembly time).
    check_manifest = dict(manifest)
    check_manifest["receipt_chain"] = chain[:-1]
    canonical = json.dumps(check_manifest, indent=2, sort_keys=True)
    final = hashlib.sha256(
        (entries[-1]["sha256"] + "manifest.json").encode("utf-8")
        + canonical.encode("utf-8")
    ).hexdigest()
    if final != chain[-1]["sha256"]:
        return {"ok": False, "reason": "manifest final link mismatch"}
    return {"ok": True, "files": len(entries), "final": chain[-1]["sha256"]}


_INSTALL_PY = '''"""Genesis pack install routine.

Copies this pack into <target>/genesis/<pack_id>/, verifies the manifest
hash-chain first, and writes installed.json as the receipt.

Usage:
  python3 install.py --target ~/levi-home [--dry-run]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path


def _hash_chain(files, root):
    chain = "0" * 64
    receipt = []
    for f in sorted(files, key=lambda p: p.relative_to(root).as_posix()):
        rel = f.relative_to(root).as_posix()
        digest = hashlib.sha256(
            (chain + rel).encode("utf-8") + f.read_bytes()
        ).hexdigest()
        receipt.append({"path": rel, "sha256": digest})
        chain = digest
    return receipt


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Install this genesis pack")
    ap.add_argument("--target", required=True, help="target LEVI_HOME")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    pack_dir = Path(__file__).resolve().parent
    manifest = json.loads((pack_dir / "manifest.json").read_text(encoding="utf-8"))
    pack_id = manifest["pack_id"]

    # Verify hash-chain before anything is copied.
    # Entries are every pack file except the manifest; the last link is
    # the manifest#final closing link.
    entries = manifest["receipt_chain"][:-1]
    files = [pack_dir / e["path"] for e in entries]
    recomputed = _hash_chain(files, pack_dir)
    for got, want in zip(recomputed, entries):
        if got["sha256"] != want["sha256"]:
            print("VERIFY FAILED at %s — aborting install" % want["path"])
            return 2
    check = dict(manifest)
    check["receipt_chain"] = manifest["receipt_chain"][:-1]
    canonical = json.dumps(check, indent=2, sort_keys=True)
    final = hashlib.sha256(
        (entries[-1]["sha256"] + "manifest.json").encode("utf-8")
        + canonical.encode("utf-8")
    ).hexdigest()
    if final != manifest["receipt_chain"][-1]["sha256"]:
        print("VERIFY FAILED: manifest final link mismatch — aborting install")
        return 2

    dest = Path(args.target).expanduser() / "genesis" / pack_id
    if args.dry_run:
        print("dry-run: would install %s -> %s" % (pack_id, dest))
        print("dry-run: %d files verified, hash-chain OK" % len(entries))
        return 0

    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(pack_dir, dest, ignore=shutil.ignore_patterns("installed.json"))
    (dest / "installed.json").write_text(
        json.dumps(
            {"pack_id": pack_id, "installed_to": str(dest), "files": len(entries)},
            indent=2,
        ),
        encoding="utf-8",
    )
    print("installed %s -> %s (%d files verified)" % (pack_id, dest, len(entries)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
'''
