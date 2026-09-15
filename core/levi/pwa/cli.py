"""`levi pwa` — serve LEVI's chat PWA (the Xeno rebirth, done right)."""

from __future__ import annotations

import argparse
import socket
from typing import Any


def _lan_ip() -> str | None:
    """Best-effort LAN address for phone access. No packets are sent:
    a UDP socket is 'connected' (which never transmits) and its own
    address is read back."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
        finally:
            s.close()
    except OSError:
        return None


def cmd_pwa(args: argparse.Namespace) -> None:
    action = getattr(args, "pwa_action", None) or "serve"
    if action != "serve":
        print(f"Unknown pwa action {action!r}")
        raise SystemExit(2)
    from levi.pwa.server import run

    host = getattr(args, "host", None) or "127.0.0.1"
    port = int(getattr(args, "port", None) or 8000)
    provider = getattr(args, "provider", None) or None
    register = getattr(args, "register", None) or None

    if register:
        from levi.persona.kai9000 import get as _get

        if _get(register) is None:
            from levi.persona.kai9000 import all_variants

            valid = ", ".join(v.id for v in all_variants())
            print(f"Unknown register {register!r}. Valid ids: {valid}")
            raise SystemExit(2)

    def _factory():
        from levi.agent.providers import select_provider

        return select_provider(provider)

    lan = _lan_ip()
    print("LEVI PWA — chat through your own agent loop, in your browser.")
    print(f"  local:  http://127.0.0.1:{port}/")
    if lan and lan != "127.0.0.1":
        print(f"  phone:  http://{lan}:{port}/   (same Wi-Fi; server binds {host})")
    else:
        print("  phone:  (no LAN address detected — use --host 0.0.0.0 on your LAN)")
    print("  tip:    'Add to Home screen' in your phone browser to install it.")
    run(host, port, provider_factory=_factory, default_register=register)


def register_pwa(sub: Any) -> None:
    p = sub.add_parser("pwa", help="Serve LEVI's chat PWA (installable web UI)")
    pwa_sub = p.add_subparsers(dest="pwa_action")
    s = pwa_sub.add_parser("serve", help="Serve the PWA (stdlib HTTP server)")
    s.add_argument("--port", type=int, default=8000)
    s.add_argument(
        "--host",
        default="127.0.0.1",
        help="Bind host (use 0.0.0.0 for LAN/phone access; set LEVI_PWA_TOKEN first)",
    )
    s.add_argument(
        "--provider",
        default=None,
        help="Agent provider override (default: normal selection chain)",
    )
    s.add_argument(
        "--register", default=None, help="Default register id (see the sidebar picker)"
    )
