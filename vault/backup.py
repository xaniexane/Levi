#!/usr/bin/env python3
"""Create an encrypted LEVI vault snapshot.

Usage:
    python3 vault/backup.py create [--label NAME] [--source DIR]
                                   [--vault-dir DIR] [--exclude PAT ...]

The passphrase is NEVER invented or stored: it is read from
``LEVI_VAULT_PASSPHRASE`` or prompted interactively (twice, to confirm).
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import vault as V


def main() -> int:
    ap = argparse.ArgumentParser(description="Create an encrypted LEVI vault snapshot.")
    ap.add_argument("command", choices=["create"])
    ap.add_argument("--label", default="levi", help="snapshot label")
    ap.add_argument("--source", default=os.path.abspath(os.path.join(os.path.dirname(__file__), "..")),
                    help="repo root to back up (default: the LEVI repo)")
    ap.add_argument("--vault-dir", default=os.path.join(os.path.dirname(os.path.abspath(__file__))),
                    help="vault directory (default: vault/)")
    ap.add_argument("--exclude", action="append", default=[], help="extra exclude pattern (repeatable)")
    args = ap.parse_args()

    print("crypto: %s" % V.backend())
    print("kdf:    %s" % V.crypto_report()["kdf"])
    try:
        pw = V.get_passphrase(confirm=True)
    except V.VaultError as e:
        print("vault: %s" % e, file=sys.stderr)
        return 1
    try:
        info = V.create_snapshot(args.source, args.vault_dir, args.label, pw,
                                 extra_excludes=tuple(args.exclude))
    except V.VaultError as e:
        print("vault: %s" % e, file=sys.stderr)
        return 1
    finally:
        pw = "x" * len(pw) if "pw" in dir() else ""
    print("snapshot: %s" % info.path)
    print("label:    %s" % info.label)
    print("created:  %s" % info.created_utc)
    print("backend:  %s" % info.backend)
    print("files:    %d (%d bytes plaintext -> %d bytes bundle)"
          % (info.file_count, info.plaintext_bytes, info.bundle_bytes))
    print("perms:    %s" % V.check_locked(os.path.dirname(info.path)))
    print("Copy the bundle to your external drives. The passphrase lives only in your head.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
