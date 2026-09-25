"""Void Box Messenger CLI — the standalone messenger surface.

``python -m levi.voidbox.messenger <subcommand>``

Subcommands:
  serve-relay    run the keeper's ciphertext-only relay
  identity       print this keeper's public identity (id, key, fingerprint)
  dm-start       register a peer and POST a handshake offer to their mailbox
  dm-send        seal a chat message and POST it to a peer's mailbox
  inbox          sweep the inbox: answer handshakes, read DMs and groups
  group-create   create a group room (you become admin)
  group-invite   admin: add a member (re-keys; pushes fresh state to members)
  group-remove   admin: remove a member (re-keys; their reads stop)
  group-send     seal a group message and fan it out to members' mailboxes

Identity comes from flags/env, never from a config file the user didn't
write: --me / VOIDBOX_KEEPER, --passphrase / VOIDBOX_PASSPHRASE,
--relay-host / VOIDBOX_RELAY_HOST, --relay-port / VOIDBOX_RELAY_PORT,
--home / VOIDBOX_HOME.

Every command but serve-relay constructs a Messenger, whose
constructor calls require_adult() FIRST — with the gate closed the CLI
refuses and names the remedy. serve-relay runs the relay server itself
(ungated infrastructure, same as `levi.voidbox.relay serve`); it holds
no keys and performs no crypto.
"""

from __future__ import annotations

import argparse
import base64
import binascii
import getpass
import os
import sys
from pathlib import Path
from typing import Optional

from levi.plaiground.gate import GateLockedError
from levi.voidbox.messenger.app import Messenger, MessengerError
from levi.voidbox.relay import DEFAULT_HOST, DEFAULT_PORT


def _resolve_me(args) -> str:
    me = args.me or os.environ.get("VOIDBOX_KEEPER", "")
    if not me:
        raise MessengerError(
            "no keeper id — pass --me or set VOIDBOX_KEEPER "
            "(1-64 chars of [A-Za-z0-9._-])"
        )
    return me


def _resolve_passphrase(args) -> str:
    pw = args.passphrase or os.environ.get("VOIDBOX_PASSPHRASE", "")
    if not pw:
        if sys.stdin.isatty():
            pw = getpass.getpass("messenger passphrase: ")
        else:
            raise MessengerError(
                "no passphrase — pass --passphrase or set VOIDBOX_PASSPHRASE"
            )
    return pw


def _home(args) -> Optional[Path]:
    raw = args.home or os.environ.get("VOIDBOX_HOME", "")
    return Path(raw).expanduser() if raw else None


def _messenger(args) -> Messenger:
    return Messenger(
        _resolve_passphrase(args),
        _resolve_me(args),
        home=_home(args),
        relay_host=args.relay_host or os.environ.get("VOIDBOX_RELAY_HOST", DEFAULT_HOST),
        relay_port=int(args.relay_port or os.environ.get("VOIDBOX_RELAY_PORT", DEFAULT_PORT)),
    )


def _common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--me", default=None, help="keeper id (or VOIDBOX_KEEPER)")
    parser.add_argument("--passphrase", default=None,
                        help="keeper passphrase (or VOIDBOX_PASSPHRASE)")
    parser.add_argument("--home", default=None,
                        help="state home dir (or VOIDBOX_HOME)")
    parser.add_argument("--relay-host", default=None,
                        help="relay host (or VOIDBOX_RELAY_HOST)")
    parser.add_argument("--relay-port", default=None, type=int,
                        help="relay port (or VOIDBOX_RELAY_PORT)")


# -- subcommands -------------------------------------------------------------


def cmd_identity(args) -> int:
    m = _messenger(args)
    ident = m.my_identity()
    print("keeper_id:   %s" % ident["keeper_id"])
    print("public_key:  %s" % ident["public_key"])
    print("fingerprint: %s" % ident["fingerprint"])
    print("(exchange the public key + fingerprint with your peer OUT OF BAND,")
    print(" then each side registers the other before any handshake:)")
    print("  dm-add --peer <their-id> --pubkey-b64 <their-key>")
    print("the initiator then runs dm-start; both run `inbox` to complete it.")
    return 0


def cmd_dm_add(args) -> int:
    m = _messenger(args)
    try:
        pubkey = base64.b64decode(args.pubkey_b64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise MessengerError("pubkey is not valid base64: %s" % exc) from exc
    rec = m.register_peer(args.peer, pubkey, name=args.name or "")
    print("registered %s" % args.peer)
    print("fingerprint: %s" % rec["fingerprint"])
    print("verify it out of band, then run `inbox` — any parked handshake")
    print("offer from them is retried automatically.")
    return 0


def cmd_dm_start(args) -> int:
    m = _messenger(args)
    try:
        pubkey = base64.b64decode(args.pubkey_b64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise MessengerError("pubkey is not valid base64: %s" % exc) from exc
    rec = m.start_dm(args.peer, pubkey, name=args.name or "",
                     wait_seconds=args.wait)
    print("DM opening with %s (conv %s…)" % (rec["peer_id"], rec["conv_id"][:12]))
    print("peer fingerprint: %s" % rec["fingerprint"])
    if rec["established"]:
        print("handshake ESTABLISHED.")
    else:
        print("peer hasn't answered yet — keep this process alive and run")
        print("`inbox` (the handshake's ephemeral key lives in memory only);")
        print("or re-run dm-start --wait to open a fresh offer.")
    return 0


def cmd_dm_send(args) -> int:
    m = _messenger(args)
    m.send_dm(args.peer, args.text)
    print("sent to %s" % args.peer)
    return 0


def cmd_inbox(args) -> int:
    m = _messenger(args)
    result = m.poll_inbox(limit=args.limit)
    for msg in result["dms"]:
        print("[dm] %s: %s" % (msg["from"], msg["text"]))
    for msg in result["groups"]:
        print("[%s] %s: %s" % (msg["room_id"], msg["sender"], msg["text"]))
    if args.verbose:
        for ev in result["events"]:
            print("(event) %s" % ev)
    elif result["events"]:
        kinds = {}
        for ev in result["events"]:
            kinds[ev["event"]] = kinds.get(ev["event"], 0) + 1
        print("(events: %s — re-run with -v for detail)"
              % ", ".join("%s×%d" % kv for kv in kinds.items()))
    if not result["dms"] and not result["groups"]:
        print("inbox quiet.")
    return 0


def cmd_group_create(args) -> int:
    m = _messenger(args)
    meta = m.create_group(args.name, public=args.public)
    print("room %s (%s) — you are admin" % (meta["room_id"], meta["name"]))
    print("invite members with: group-invite --room %s --peer <keeper-id>"
          % meta["room_id"])
    return 0


def cmd_group_invite(args) -> int:
    m = _messenger(args)
    out = m.invite(args.room, args.peer)
    print("invited %s to %s (epoch %d)" % (args.peer, args.room, out["room"]["epoch"]))
    for fail in out["sync_failed"]:
        print("  NOT SYNCED to %s: %s" % (fail["member_id"], fail["reason"]))
    return 0


def cmd_group_remove(args) -> int:
    m = _messenger(args)
    out = m.remove(args.room, args.peer)
    print("removed %s from %s (epoch %d)" % (args.peer, args.room, out["room"]["epoch"]))
    for fail in out["sync_failed"]:
        print("  NOT SYNCED to %s: %s" % (fail["member_id"], fail["reason"]))
    return 0


def cmd_group_send(args) -> int:
    m = _messenger(args)
    m.send_group(args.room, args.text)
    print("sent to %s" % args.room)
    return 0


def cmd_serve_relay(args) -> int:
    # Deliberately UNGATED: this is the relay server itself — the same
    # ciphertext-only store-and-forward `levi.voidbox.relay serve` anyone
    # can run directly (ungated). It holds no keys, performs no crypto,
    # and grants no messenger capability; the gate lives at the
    # Messenger surface, where keys are actually used. Gating only this
    # alias would be theater.
    from levi.voidbox import relay as _relay_mod

    argv = ["serve", "--host", args.host, "--port", str(args.port)]
    if args.store_dir:
        argv += ["--store-dir", args.store_dir]
    if args.public:
        argv += ["--public"]
    return _relay_mod.main(argv)


# -- parser ------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="levi-voidbox-messenger",
        description="Void Box Messenger — the standalone messenger surface.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    serve = sub.add_parser("serve-relay", help="run the keeper's relay")
    serve.add_argument("--host", default=DEFAULT_HOST)
    serve.add_argument("--port", type=int, default=DEFAULT_PORT)
    serve.add_argument("--store-dir", default=None)
    serve.add_argument("--public", action="store_true",
                       help="EXPLICIT opt-in to bind non-loopback")
    serve.set_defaults(func=cmd_serve_relay)

    for name, help_text, func in (
        ("identity", "show this keeper's public identity", cmd_identity),
        ("dm-add", "register a peer's public key (no handshake yet)", cmd_dm_add),
        ("dm-start", "register a peer and POST a handshake offer", cmd_dm_start),
        ("dm-send", "send a 1:1 chat message", cmd_dm_send),
        ("inbox", "sweep the inbox: handshakes, DMs, groups", cmd_inbox),
        ("group-create", "create a group room", cmd_group_create),
        ("group-invite", "admin: invite a member", cmd_group_invite),
        ("group-remove", "admin: remove a member", cmd_group_remove),
        ("group-send", "send a group message (fanned out to members)", cmd_group_send),
    ):
        p = sub.add_parser(name, help=help_text)
        _common(p)
        p.set_defaults(func=func)

    sub.choices["dm-add"].add_argument("--peer", required=True)
    sub.choices["dm-add"].add_argument("--pubkey-b64", required=True,
                                      help="peer's 32-byte X25519 public key, base64")
    sub.choices["dm-add"].add_argument("--name", default="")
    sub.choices["dm-start"].add_argument("--peer", required=True)
    sub.choices["dm-start"].add_argument("--pubkey-b64", required=True,
                                        help="peer's 32-byte X25519 public key, base64")
    sub.choices["dm-start"].add_argument("--name", default="")
    sub.choices["dm-start"].add_argument("--wait", type=float, default=30.0,
                                      help="seconds to wait for the peer's "
                                      "answer and finish the handshake in "
                                      "this process (0 = post offer only)")
    sub.choices["dm-send"].add_argument("--peer", required=True)
    sub.choices["dm-send"].add_argument("--text", required=True)
    sub.choices["inbox"].add_argument("--limit", type=int, default=50)
    sub.choices["inbox"].add_argument("-v", "--verbose", action="store_true")
    sub.choices["group-create"].add_argument("--name", required=True)
    sub.choices["group-create"].add_argument("--public", action="store_true")
    sub.choices["group-invite"].add_argument("--room", required=True)
    sub.choices["group-invite"].add_argument("--peer", required=True)
    sub.choices["group-remove"].add_argument("--room", required=True)
    sub.choices["group-remove"].add_argument("--peer", required=True)
    sub.choices["group-send"].add_argument("--room", required=True)
    sub.choices["group-send"].add_argument("--text", required=True)
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except GateLockedError as exc:
        print("REFUSED: the adult gate is closed.", file=sys.stderr)
        print("Remedy: %s" % exc, file=sys.stderr)
        return 2
    except MessengerError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
