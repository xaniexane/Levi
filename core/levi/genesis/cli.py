"""``levi genesis`` CLI: assemble / list / inspect.

Wiring (core/levi/cli/main.py):
  parser:  genesis_p = sub.add_parser("genesis", help="Genesis pack forge")
  subcommands: assemble / list / inspect  (argparse subparsers, dest="genesis_action")
  dispatch: cmds["genesis"] = cmd_genesis   (inside a GENESIS region, try/except import)
See CLI_WIRING_NOTES.md for the exact patch if cli/main.py is ever locked.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from levi.genesis import assemble as genesis_assemble
from levi.genesis import parts, remix


def _print_roster(roster_or_manifest: Any) -> None:
    for v in roster_or_manifest:
        name = v.get("name", "?")
        vid = v.get("variant_id", "?")
        mode = v.get("mode", "?")
        print("  - %s (%s) [%s]" % (name, vid, mode))


def cmd_genesis(args) -> None:
    action = getattr(args, "genesis_action", None) or "list"
    if action == "assemble":
        spec_path = getattr(args, "spec", None)
        spec: dict
        if spec_path:
            spec = json.loads(Path(spec_path).read_text(encoding="utf-8"))
        else:
            raw = getattr(args, "spec_json", None)
            if not raw:
                raise SystemExit(
                    "levi genesis assemble needs --spec <file> or --spec-json '{...}'"
                )
            spec = json.loads(raw)
        out = getattr(args, "out", None)
        summary = genesis_assemble.assemble(
            spec, root=Path(out) if out else None
        )
        print("assembled %s" % summary["pack_id"])
        print("  dir:      %s" % summary["pack_dir"])
        print("  variants: %d" % summary["variant_count"])
        print("  hash:     %s" % summary["final_hash"])
        print("  operator: %s" % summary["operator_integration"])
        return

    if action == "list":
        root = genesis_assemble.packs_root()
        if not root.exists():
            print("no genesis packs assembled yet (root: %s)" % root)
            return
        for pack_dir in sorted(p for p in root.iterdir() if p.is_dir()):
            manifest = pack_dir / "manifest.json"
            if not manifest.exists():
                continue
            m = json.loads(manifest.read_text(encoding="utf-8"))
            print(
                "%s  %s  (%d variants)"
                % (m["pack_id"], m.get("pack_name", ""), len(m.get("variants", [])))
            )
        return

    if action == "inspect":
        pack = getattr(args, "pack", None)
        if not pack:
            raise SystemExit("levi genesis inspect <pack> needs a pack id or directory")
        pack_dir = Path(pack)
        if not (pack_dir / "manifest.json").exists():
            pack_dir = genesis_assemble.packs_root() / pack
        result = genesis_assemble.verify_pack(pack_dir)
        manifest = json.loads(
            (pack_dir / "manifest.json").read_text(encoding="utf-8")
        )
        print("pack: %s" % manifest["pack_id"])
        print("name: %s" % manifest.get("pack_name", ""))
        print("license: %s (%s, buyer %s)" % (
            manifest["license"]["license_id"],
            manifest["license"]["terms_version"],
            manifest["license"]["buyer"],
        ))
        print("chain: %s" % ("OK (%d files)" % result["files"] if result.get("ok") else "BROKEN: %s" % result.get("reason")))
        print("variants:")
        _print_roster(manifest.get("variants", []))
        quote = json.loads((pack_dir / "quote.json").read_text(encoding="utf-8"))
        print("paper quote: $%s lifetime (%s)" % (
            quote["quote"]["recommended_lifetime_price"],
            quote["checkout"]["status"],
        ))
        return

    if action == "parts":
        receipt = parts.catalog_receipt()
        print("parts bin: %d capability families (catalog %s)" % (
            receipt["count"], receipt["catalog_hash"][:12]))
        for agent_id in parts.BASE_AGENTS:
            fam = remix.family_names().get(agent_id, [])
            print("  %s -> remixes as e.g. %s" % (agent_id, ", ".join(fam[:2])))
        return

    raise SystemExit("unknown genesis action: %r" % action)
