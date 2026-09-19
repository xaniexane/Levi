#!/usr/bin/env python3
"""Readiness check for a fleet node machine. Run before run_node.py.

Hard checks (all must pass): Python >= 3.8, mesh package importable,
bind port available, data dir writable.
Warnings only: a known peer not reachable yet (peers may join later),
old Windows release (Python 3.8+ cannot install there — use another
machine as the anchor instead).

Exit 0 only if every hard check passes.
"""

from __future__ import annotations

import json
import platform
import socket
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

MIN_PY = (3, 8)
failures = []
warnings = []


def check(name, ok, detail=""):
    mark = "PASS" if ok else ("WARN" if detail == "warn" else "FAIL")
    print(f"[{mark}] {name}" + ("" if ok or detail in ("", "warn") else f" — {detail}"))
    if not ok and detail != "warn":
        failures.append(name)
    elif not ok:
        warnings.append(name)


def main() -> None:
    cfg_path = Path(
        sys.argv[2]
        if len(sys.argv) > 2 and sys.argv[1] == "--config"
        else "node_config.json"
    )
    print(f"fleet node readiness — config: {cfg_path}")
    print(f"OS: {platform.system()} {platform.release()} ({platform.machine()})")
    print(f"Python: {platform.python_version()}")

    # 0. Old-Windows honesty: Python 3.8+ is the floor, and it does not
    #    install on Windows 2000/XP/2003/Vista-era stacks.
    if platform.system() == "Windows":
        if platform.release() in ("2000", "XP", "2003", "2003Server", "Vista"):
            check(
                "windows version",
                False,
                f"Windows {platform.release()} cannot run Python 3.8+ — "
                "this machine cannot host a node; use the Chromebook as the anchor instead.",
            )
        else:
            check("windows version", True)
    else:
        check(
            "os",
            True,
            "warn" if platform.system() not in ("Windows", "Linux", "Darwin") else "",
        )

    check(
        "python >= 3.8",
        sys.version_info >= MIN_PY,
        ""
        if sys.version_info >= MIN_PY
        else f"need 3.8+, have {platform.python_version()}",
    )

    try:
        import mesh.node  # noqa: F401
        import mesh.tasks  # noqa: F401
        import mesh.transport  # noqa: F401

        check("mesh package importable", True)
    except Exception as exc:
        check("mesh package importable", False, f"{exc}")

    try:
        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        check("config parses", True)
    except Exception as exc:
        check("config parses", False, f"{exc}")
        cfg = {}

    port = int(cfg.get("bind_port", 47911)) if cfg else 47911
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("0.0.0.0", port))
        check(f"bind port {port} free", True)
    except OSError as exc:
        check(f"bind port {port} free", False, f"{exc}")
    finally:
        s.close()

    data_dir = Path(str(cfg.get("data_dir", "mesh_data"))) if cfg else Path("mesh_data")
    try:
        data_dir.mkdir(parents=True, exist_ok=True)
        probe = data_dir / ".write_test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        check(f"data dir writable ({data_dir})", True)
    except OSError as exc:
        check(f"data dir writable ({data_dir})", False, f"{exc}")

    for p in cfg.get("known_peers", []) if cfg else []:
        host, prt = p[0], int(p[1])
        s2 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s2.settimeout(2.0)
        try:
            s2.connect((host, prt))
            check(f"peer {host}:{prt} reachable", True)
        except OSError:
            check(f"peer {host}:{prt} reachable", False, "warn")
        finally:
            s2.close()

    print()
    if failures:
        print(
            f"NOT READY — {len(failures)} hard check(s) failed: {', '.join(failures)}"
        )
        sys.exit(1)
    if warnings:
        print(f"READY with {len(warnings)} warning(s): {', '.join(warnings)}")
    else:
        print(
            "READY — run start_node.bat (or: python run_node.py --config node_config.json)"
        )


if __name__ == "__main__":
    main()
