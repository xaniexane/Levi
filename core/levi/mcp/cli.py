"""`levi mcp` CLI: serve LEVI's tools over MCP, and manage LEVI's own
outbound MCP server connections (LEVI-original)."""

from __future__ import annotations

import shlex


def cmd_mcp(args) -> None:
    """Serve LEVI as an MCP server, or manage MCP client connections."""
    action = getattr(args, "mcp_action", "serve") or "serve"
    if action in ("add", "remove", "list-servers", "catalog"):
        _cmd_mcp_client(args, action)
        return
    if action != "serve":
        raise SystemExit(f"unknown mcp action: {action}")
    from levi.mcp.protocol import build_http_server, build_owner_server
    from levi.mcp.transports import serve_http, serve_stdio

    transport = getattr(args, "transport", "stdio") or "stdio"
    if transport == "http":
        server = build_http_server()
        serve_http(
            server,
            host=getattr(args, "host", None) or "127.0.0.1",
            port=int(getattr(args, "port", None) or 8899),
            token=getattr(args, "token", None) or "",
        )
        return
    if transport == "stdio":
        server = build_owner_server(consent=bool(getattr(args, "consent", False)))
        serve_stdio(server)
        return
    raise SystemExit(f"unknown mcp transport: {transport}")


def _save_and_probe(
    _mc,
    name: str,
    *,
    transport: str,
    url,
    command,
    headers,
    timeout,
    reference,
) -> None:
    """Save a server config, then verify it actually answers.

    Shared by plain ``add`` and ``add --catalog`` so both paths behave the
    same. Raises SystemExit on failure.
    """
    try:
        cfg = _mc.add_server(
            name,
            transport=transport,
            url=url,
            command=command,
            headers=headers,
            timeout=timeout,
            reference=reference,
        )
    except _mc.MCPClientError as exc:
        print(f"mcp add failed: {exc}")
        raise SystemExit(1) from None
    # Verify the server actually answers before declaring success.
    try:
        probe = _mc.connect_server(name, cfg)
        n = len(probe.list_tools())
        probe.close()
        _mc._OPEN_CLIENTS.pop(name, None)
    except _mc.MCPClientError as exc:
        print(f"Saved {name!r}, but the server did not answer: {exc}")
        print("Fix the URL/command, or `levi mcp remove` it.")
        raise SystemExit(1) from None
    ref = cfg.get("reference")
    tag = f"  [reference: {ref}]" if ref else ""
    print(f"Added MCP server {name!r} ({transport}){tag} — {n} tool(s) available.")


def _cmd_mcp_client(args, action: str) -> None:
    from levi.mcp import client as _mc
    from levi.mcp import catalog as _catalog

    if action == "catalog":
        try:
            entries = _catalog.load_catalog()
        except _catalog.CatalogError as exc:
            print(f"mcp catalog failed: {exc}")
            raise SystemExit(1) from None
        print("══ MCP server catalog ══\n")
        print("Third-party references — not LEVI, never sources, never branding.\n")
        for e in entries:
            target = _catalog.describe_target(e)
            print(f"  {e['name']}  [{e['transport']}]  {target}")
            print(f"    {e['description']}")
            print(f"    reference: {e['provider']} (third-party reference — not LEVI)")
            if e.get("note"):
                print(f"    note: {e['note']}")
            print()
        print("Install one with:  levi mcp add --catalog <name>")
        return

    if action == "list-servers":
        servers = _mc.list_servers()
        if not servers:
            print("No MCP servers configured. Add one with:")
            print(
                "  levi mcp catalog                        # browse one-command installs"
            )
            print(
                "  levi mcp add --catalog <name>            # install from the catalog"
            )
            print("  levi mcp add <name> --url http://host:port/mcp")
            print('  levi mcp add <name> --cmd "npx -y some-mcp-server"')
            return
        print("══ MCP servers ══\n")
        for name in sorted(servers):
            cfg = servers[name]
            t = cfg.get("transport", "?")
            where = cfg.get("url") or " ".join(cfg.get("command", []))
            ref = cfg.get("reference")
            tag = f"  (reference: {ref})" if ref else ""
            print(f"  {name}  [{t}]  {where}{tag}")
        print("\n`levi agent run` attaches these servers' tools automatically.")
        return

    if action == "add":
        catalog_key = (getattr(args, "catalog", None) or "").strip() or None
        url = getattr(args, "url", None) or None
        command_s = getattr(args, "cmd", None) or None
        if catalog_key:
            if url or command_s:
                print("mcp add: --catalog cannot be combined with --url or --cmd")
                raise SystemExit(2)
            try:
                entry = _catalog.get_entry(catalog_key)
            except _catalog.CatalogError as exc:
                print(f"mcp add failed: {exc}")
                raise SystemExit(1) from None
            spec = _catalog.install_spec(entry)
            name = (getattr(args, "name", None) or "").strip() or entry["name"]
            _save_and_probe(
                _mc,
                name,
                transport=spec["transport"],
                url=spec.get("url"),
                command=spec.get("command"),
                headers=None,
                timeout=getattr(args, "timeout", None) or None,
                reference=spec["reference"],
            )
            return
        name = (getattr(args, "name", None) or "").strip()
        if not name:
            print(
                'Usage: levi mcp add <name> --url <http-url> | --cmd "<cmd...>"\n'
                "       levi mcp add --catalog <name>   (name defaults to the entry)"
            )
            raise SystemExit(2)
        transport = (getattr(args, "client_transport", None) or "").strip().lower()
        if not transport:
            transport = "http" if url else "stdio"
        headers: dict[str, str] = {}
        for h in getattr(args, "header", None) or []:
            k, sep, v = h.partition("=")
            if sep and k.strip():
                headers[k.strip()] = v.strip()
        command = shlex.split(command_s) if command_s else None
        _save_and_probe(
            _mc,
            name,
            transport=transport,
            url=url,
            command=command,
            headers=headers or None,
            timeout=getattr(args, "timeout", None) or None,
            reference=getattr(args, "reference", None) or None,
        )
        return

    if action == "remove":
        name = (getattr(args, "name", None) or "").strip()
        if not name:
            print("Usage: levi mcp remove <name>")
            raise SystemExit(2)
        try:
            _mc.remove_server(name)
        except _mc.MCPClientError as exc:
            print(f"mcp remove failed: {exc}")
            raise SystemExit(1) from None
        print(f"Removed MCP server {name!r}.")
        return
