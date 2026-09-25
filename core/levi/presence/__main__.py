"""CLI: python -m levi.presence <serve|peers|rooms|create|join|say>

Mirrors the future ``levi presence`` surface. Display name defaults to
the config at ~/.levi/presence/config.json (resolved at call time), else
the login name.
"""

from __future__ import annotations

import argparse
import getpass
import json
import os
import socket
import sys
import threading
import time
from pathlib import Path

from levi.presence.discovery import (
    Beacon,
    BeaconListener,
    BeaconSender,
    DISCOVERY_PORT,
    MULTICAST_GROUP,
)
from levi.presence.rooms import new_id
from levi.presence.server import PresenceHub, send_request


def _home() -> Path:
    return Path(os.path.expanduser("~"))


def _config_path() -> Path:
    return _home() / ".levi" / "presence" / "config.json"


def default_name() -> str:
    try:
        raw = _config_path().read_text(encoding="utf-8")
        name = json.loads(raw).get("display_name", "")
        if name:
            return str(name)[:64]
    except (OSError, ValueError):
        pass
    try:
        return getpass.getuser()
    except Exception:
        return "anonymous"


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="levi.presence", description="LAN drop-in rooms, no account."
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("serve", help="run a hub + discovery beacon")
    s.add_argument("--name", default=None)
    s.add_argument("--host", default="0.0.0.0")
    s.add_argument("--port", type=int, default=0)
    s.add_argument("--no-beacon", action="store_true")

    s = sub.add_parser("peers", help="listen for hubs and list them")
    s.add_argument("--seconds", type=float, default=6.0)

    s = sub.add_parser("rooms", help="list rooms on a hub")
    s.add_argument("--host", required=True)
    s.add_argument("--port", type=int, required=True)

    s = sub.add_parser("create", help="create a room on a hub")
    s.add_argument("--host", required=True)
    s.add_argument("--port", type=int, required=True)
    s.add_argument("--room", required=True)
    s.add_argument("--topic", default="")

    s = sub.add_parser("join", help="join a room interactively (Ctrl-D quits)")
    s.add_argument("--host", required=True)
    s.add_argument("--port", type=int, required=True)
    s.add_argument("--room", required=True)
    s.add_argument("--name", default=None)

    s = sub.add_parser("say", help="send one message to a room")
    s.add_argument("--host", required=True)
    s.add_argument("--port", type=int, required=True)
    s.add_argument("--room", required=True)
    s.add_argument("--name", default=None)
    s.add_argument("text", nargs="+")
    return p


def _hello(host: str, port: int, name: str) -> tuple:
    resp = send_request(host, port, {"op": "hello", "name": name})
    if not resp.get("ok"):
        raise SystemExit("hello failed: %s" % resp.get("error"))
    sock = socket.create_connection((host, port), timeout=5.0)
    sock.sendall(
        (
            json.dumps({"op": "hello", "name": name, "client_id": resp["client_id"]})
            + "\n"
        ).encode("utf-8")
    )
    return sock, resp["client_id"]


def cmd_serve(args) -> int:
    name = args.name or default_name()
    hub = PresenceHub(args.host, args.port).start()
    host, port = hub.address
    print("hub %r on %s:%d  (no account, LAN only)" % (name, host, port))
    sender = None
    if not args.no_beacon:
        beacon = Beacon(
            hub_id=new_id("hub"),
            name=name,
            host=host if host != "0.0.0.0" else "127.0.0.1",
            port=port,
            rooms=[],
        )
        sender = BeaconSender(beacon)
        sender.start()
        print("announcing on %s:%d" % (MULTICAST_GROUP, DISCOVERY_PORT))
    try:
        while True:
            time.sleep(30)
            hub.sweep()
    except KeyboardInterrupt:
        print("\nstopping hub")
    finally:
        if sender:
            sender.stop()
        hub.stop()
    return 0


def cmd_peers(args) -> int:
    listener = BeaconListener().start()
    try:
        time.sleep(args.seconds)
        peers = listener.peers()
    finally:
        listener.stop()
    if not peers:
        print("no hubs heard in %.1fs" % args.seconds)
        return 1
    for b in sorted(peers, key=lambda b: b.name):
        rooms = ", ".join(b.rooms) if b.rooms else "(no rooms yet)"
        print("%s  %s:%d  rooms: %s" % (b.name, b.host, b.port, rooms))
    return 0


def cmd_rooms(args) -> int:
    resp = send_request(args.host, args.port, {"op": "hello", "name": default_name()})
    if not resp.get("ok"):
        print("hello failed: %s" % resp.get("error"), file=sys.stderr)
        return 1
    resp = send_request(args.host, args.port, {"op": "rooms"})
    rooms = resp.get("rooms", [])
    if not rooms:
        print("(no rooms — create one with `create`)")
        return 0
    for r in rooms:
        print("#%-20s %2d members  %s" % (r["name"], r["members"], r["topic"]))
    return 0


def cmd_create(args) -> int:
    resp = send_request(args.host, args.port, {"op": "hello", "name": default_name()})
    cid = resp.get("client_id", "")
    # One-shot create: re-attach with the fresh id, then create the room.
    with socket.create_connection((args.host, args.port), timeout=5.0) as sock:
        sock.sendall(
            (
                json.dumps({"op": "hello", "name": default_name(), "client_id": cid})
                + "\n"
            ).encode("utf-8")
        )
        sock.recv(65536)
        sock.sendall(
            (
                json.dumps({"op": "create", "room": args.room, "topic": args.topic})
                + "\n"
            ).encode("utf-8")
        )
        buf = b""
        while b"\n" not in buf:
            buf += sock.recv(65536)
        resp = json.loads(buf.split(b"\n", 1)[0].decode("utf-8"))
    if resp.get("ok"):
        print("created #%s" % args.room)
        return 0
    print("create failed: %s" % resp.get("error"), file=sys.stderr)
    return 1


def _read_line(sock) -> dict:
    buf = b""
    while b"\n" not in buf:
        chunk = sock.recv(65536)
        if not chunk:
            raise ConnectionError("hub closed the connection")
        buf += chunk
    return json.loads(buf.split(b"\n", 1)[0].decode("utf-8"))


def cmd_say(args) -> int:
    sock, _cid = _hello(args.host, args.port, args.name or default_name())
    try:
        sock.sendall(
            (json.dumps({"op": "join", "room": args.room}) + "\n").encode("utf-8")
        )
        join_ack = _read_line(sock)
        if join_ack.get("ok") is False:
            print("join failed: %s" % join_ack.get("error"), file=sys.stderr)
            return 1
        text = " ".join(args.text)
        sock.sendall(
            (json.dumps({"op": "say", "room": args.room, "text": text}) + "\n").encode(
                "utf-8"
            )
        )
        ack = _read_line(sock)
    finally:
        sock.close()
    if ack.get("ok") is False:
        print("say failed: %s" % ack.get("error"), file=sys.stderr)
        return 1
    print("sent to #%s" % args.room)
    return 0


def cmd_join(args) -> int:
    name = args.name or default_name()
    sock, _cid = _hello(args.host, args.port, name)
    sock.sendall((json.dumps({"op": "join", "room": args.room}) + "\n").encode("utf-8"))
    stop = threading.Event()

    def reader():
        buf = b""
        while not stop.is_set():
            try:
                chunk = sock.recv(65536)
            except OSError:
                break
            if not chunk:
                break
            buf += chunk
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                if line.strip():
                    _print_event(line)

    def _print_event(line: bytes) -> None:
        try:
            obj = json.loads(line.decode("utf-8"))
        except ValueError:
            return
        if obj.get("event") == "message":
            print("\n[%s] %s: %s" % (obj["room"], obj["from"], obj["text"]))
        elif obj.get("event") == "presence":
            print("\n* %s %s #%s" % (obj["name"], obj["state"], obj["room"]))
        print("> ", end="", flush=True)

    t = threading.Thread(target=reader, daemon=True)
    t.start()
    print("joined #%s as %s — type messages, Ctrl-D to leave" % (args.room, name))
    try:
        print("> ", end="", flush=True)
        for line in sys.stdin:
            text = line.strip()
            if text:
                sock.sendall(
                    (
                        json.dumps({"op": "say", "room": args.room, "text": text})
                        + "\n"
                    ).encode("utf-8")
                )
            print("> ", end="", flush=True)
    except (BrokenPipeError, OSError):
        pass
    finally:
        stop.set()
        sock.close()
    print("\nleft #%s" % args.room)
    return 0


def main(argv=None) -> int:
    args = _parser().parse_args(argv)
    if args.cmd == "serve":
        return cmd_serve(args)
    if args.cmd == "peers":
        return cmd_peers(args)
    if args.cmd == "rooms":
        return cmd_rooms(args)
    if args.cmd == "create":
        return cmd_create(args)
    if args.cmd == "say":
        return cmd_say(args)
    if args.cmd == "join":
        return cmd_join(args)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
