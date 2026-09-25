"""counsel-desk CLI (Stage 1): local document intake + retrieval.

    python -m levi.counsel intake <file> [--vault DIR]
    python -m levi.counsel search "<query>" [--vault DIR]
    python -m levi.counsel list [--vault DIR]
    python -m levi.counsel gates

Everything runs offline against the owner's local vault. The ``gates``
command prints the gate registry so any operator can see which approvals
each action requires.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from levi.counsel import (
    CounselIndex,
    CounselVault,
    check,
    propose_intake,
    verify_proposal,
)
from levi.counsel.gates import ACTIONS
from levi.counsel.notices import NOTICE_STATUS, NOT_LEGAL_ADVICE_DRAFT


def cmd_intake(args: argparse.Namespace) -> int:
    vault = CounselVault(args.vault)
    allowed, missing = check("intake_document", {"owner_consent": True})
    if not allowed:
        print(f"intake blocked by gate: missing {missing}", file=sys.stderr)
        return 2
    proposal = propose_intake(args.file)
    verification = verify_proposal(proposal)
    doc = vault.store(proposal, verification)
    if verification.verdict == "accept":
        index = CounselIndex(vault.root)
        text = vault.stored_text(doc.doc_id)
        if text is not None:
            index.add(doc.doc_id, doc.source_name, text)
    print(
        json.dumps(
            {
                "doc_id": doc.doc_id,
                "verdict": doc.verdict,
                "reason": doc.reason,
                "quality": doc.quality,
                "warnings": doc.warnings,
            },
            indent=2,
        )
    )
    return 0


def cmd_search(args: argparse.Namespace) -> int:
    vault = CounselVault(args.vault)
    index = CounselIndex(vault.root)
    hits = index.search(args.query, vault, limit=args.limit)
    print(NOT_LEGAL_ADVICE_DRAFT.strip().splitlines()[0])
    print(f"[{NOTICE_STATUS}]")
    for hit in hits:
        print(f"- {hit.source_name} (score {hit.score})")
        print(f"  matched: {', '.join(hit.matched_terms)}")
        print(f"  {hit.snippet}")
    if not hits:
        print("(no indexed documents matched)")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    vault = CounselVault(args.vault)
    for doc in vault.manifest():
        print(f"{doc.doc_id[:12]}  {doc.verdict:10} {doc.quality:18} {doc.source_name}")
    return 0


def cmd_gates(_args: argparse.Namespace) -> int:
    for action, entry in ACTIONS.items():
        print(f"{action}:")
        print(f"  requires: {', '.join(entry['requires'])}")
        print(f"  terminal: {entry['terminal']}")
        print(f"  why: {entry['why']}")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="levi.counsel")
    parser.add_argument("--vault", type=Path, default=None)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("intake")
    p.add_argument("file", type=Path)
    p.set_defaults(func=cmd_intake)

    p = sub.add_parser("search")
    p.add_argument("query")
    p.add_argument("--limit", type=int, default=10)
    p.set_defaults(func=cmd_search)

    p = sub.add_parser("list")
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("gates")
    p.set_defaults(func=cmd_gates)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except Exception as exc:  # honest failure, no traceback noise for CLI
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
