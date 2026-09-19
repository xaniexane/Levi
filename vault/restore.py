#!/usr/bin/env python3
"""List, verify, and restore LEVI vault snapshots.

Usage:
    python3 vault/restore.py list [--vault-dir DIR]
    python3 vault/restore.py verify <bundle> [--vault-dir DIR]
    python3 vault/restore.py restore <bundle> --dest DIR [--force] [--vault-dir DIR]

The passphrase is NEVER invented or stored: it is read from
``LEVI_VAULT_PASSPHRASE`` or prompted interactively.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import vault as V

VAULT_DIR = os.path.dirname(os.path.abspath(__file__))


def _passphrase() -> str:
    try:
        return V.get_passphrase()
    except V.VaultError as e:
        print("vault: %s" % e, file=sys.stderr)
        sys.exit(1)


def cmd_list(args) -> int:
    infos = V.list_snapshots(args.vault_dir)
    if not infos:
        print("no snapshots in %s/snapshots" % args.vault_dir)
        return 0
    for i in infos:
        lock = V.check_locked(i.path)
        print("%s\n  label=%s created=%s backend=%s kdf=%s files=%d "
              "plain=%dB bundle=%dB perms=%s locked=%s"
              % (i.path, i.label, i.created_utc, i.backend, i.kdf,
                 i.file_count, i.plaintext_bytes, i.bundle_bytes,
                 lock["mode"], lock["locked"]))
    return 0


def cmd_verify(args) -> int:
    pw = _passphrase()
    try:
        rep = V.verify_snapshot(args.bundle, pw)
    except V.VaultError as e:
        print("vault: %s" % e, file=sys.stderr)
        return 1
    print("OK: %d files verified against manifest" % rep["files_verified"])
    print("label=%s created=%s backend=%s kdf=%s"
          % (rep["label"], rep["created_utc"], rep["backend"], rep["kdf"]))
    return 0


def cmd_restore(args) -> int:
    pw = _passphrase()
    try:
        rep = V.restore_snapshot(args.bundle, args.dest, pw, force=args.force)
    except V.VaultError as e:
        print("vault: %s" % e, file=sys.stderr)
        return 1
    print("restored %d files to %s (label=%s)"
          % (rep["files_restored"], rep["dest"], rep["label"]))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="LEVI vault: list, verify, restore.")
    ap.add_argument("--vault-dir", default=VAULT_DIR, help="vault directory")
    sub = ap.add_subparsers(dest="command", required=True)
    sub.add_parser("list")
    pv = sub.add_parser("verify")
    pv.add_argument("bundle")
    pr = sub.add_parser("restore")
    pr.add_argument("bundle")
    pr.add_argument("--dest", required=True)
    pr.add_argument("--force", action="store_true", help="overwrite non-empty dest")
    args = ap.parse_args()
    return {"list": cmd_list, "verify": cmd_verify, "restore": cmd_restore}[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
