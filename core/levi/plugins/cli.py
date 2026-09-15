"""`levi reference` CLI — the universal provider-reference plug-in point.

Provider and model names are *references*, never sources and never LEVI
identity (see levi.plugins.references). This command plugs providers in
as references from anywhere: MCP servers, plugin connectors, models,
media adapters.
"""

from __future__ import annotations


def cmd_reference(args) -> None:
    """Manage universal provider references: add | remove | list."""
    from levi.plugins import references as _refs

    action = getattr(args, "reference_action", None) or "list"

    if action == "list":
        refs = _refs.list_references()
        if not refs:
            print("No provider references plugged in.")
            print("Add one with: levi reference add <provider> --kind plugin|mcp-server|model|media")
            print("Or: levi mcp add <name> --url ... --reference <provider>")
            return
        print("══ Provider references ══\n")
        for rid in sorted(refs):
            print(_refs.describe(refs[rid]))
            print()
        print("References are external providers LEVI points at —")
        print("never sources LEVI draws on, never LEVI identity.")
        return

    if action == "add":
        provider = (getattr(args, "provider", None) or "").strip()
        if not provider:
            print("Usage: levi reference add <provider> --kind <kind> [--detail k=v] [--id <id>]")
            raise SystemExit(2)
        kind = (getattr(args, "kind", None) or "other").strip()
        detail: dict[str, str] = {}
        for item in getattr(args, "detail", None) or []:
            if "=" not in item:
                print(f"Ignoring malformed --detail {item!r} (want k=v)")
                continue
            k, v = item.split("=", 1)
            detail[k.strip()] = v.strip()
        try:
            ref = _refs.add_reference(
                provider,
                kind=kind,
                detail=detail or None,
                ref_id=(getattr(args, "ref_id", None) or None),
            )
        except _refs.ReferenceError as exc:
            print(f"reference add failed: {exc}")
            raise SystemExit(1) from None
        print(f"Plugged in {ref.id} — reference: {ref.provider}  [{ref.kind}]")
        return

    if action == "remove":
        rid = (
            getattr(args, "ref_id", None) or getattr(args, "provider", None) or ""
        ).strip()
        if not rid:
            print("Usage: levi reference remove <id>")
            raise SystemExit(2)
        try:
            _refs.remove_reference(rid)
        except _refs.ReferenceError as exc:
            print(f"reference remove failed: {exc}")
            raise SystemExit(1) from None
        print(f"Unplugged provider reference {rid!r}.")
        return

    raise SystemExit(f"unknown reference action: {action}")
