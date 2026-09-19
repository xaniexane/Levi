"""CLI: python -m levi.offline <status|demo|journal-demo>

- status: print the standing offline-first policy.
- demo: run a scripted chain scenario (local answers, escalation denied
  by the keeper gate, escalation granted) and print the receipts.
- journal-demo: log the demo turns to a temp journal, purge, and export.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

from .chain import Answer, Offliner, RuleBackend
from .gates import GatePolicy, default_policy
from .journal import Journal


class ScriptedBackend:
    """A deterministic local backend for demos and tests."""

    def __init__(self, name: str, confidence: float, text: str):
        self.name = name
        self._confidence = confidence
        self._text = text

    def generate(self, prompt: str, context: str = "") -> Answer:
        return Answer(text=self._text, confidence=self._confidence, backend=self.name)


class CloudStub:
    name = "cloud:stub"

    def generate(self, prompt: str, context: str = "") -> Answer:
        return Answer(
            text="(cloud stub: escalation path works; no real call made)",
            confidence=0.5,
            backend=self.name,
        )


def _cmd_status(_args: argparse.Namespace) -> int:
    p = default_policy()
    print("LEVI offline-first policy")
    print("  keeper_allows_cloud :", p.keeper_allows_cloud)
    print("  confidence_threshold:", p.confidence_threshold)
    print("  log_retention_days  :", p.log_retention_days)
    print("Doctrine: local first, always. One gate alone never opens the wire.")
    return 0


def _show(title: str, result) -> None:
    print("== %s" % title)
    print("   backend :", result.answer.backend)
    print("   conf    : %.3f" % result.answer.confidence)
    print("   escalated:", result.receipt.escalated)
    print("   reason  :", result.receipt.escalation_reason)
    print("   answer  :", result.answer.text[:90])


def _cmd_demo(_args: argparse.Namespace) -> int:
    confident = ScriptedBackend(
        "local:brain", 0.9, "The vault code is 1234. Kidding — local answer."
    )
    unsure = ScriptedBackend("local:brain", 0.3, "Not sure locally.")

    chain = Offliner(confident, cloud=CloudStub())
    _show(
        "confident local (no escalation considered)",
        chain.answer("my email is demo@example.com, what time is it?"),
    )

    chain2 = Offliner(unsure, cloud=CloudStub())  # keeper gate closed
    _show(
        "unsure local, keeper gate closed (denied)",
        chain2.answer("help me", allow_cloud=True),
    )

    open_policy = GatePolicy(keeper_allows_cloud=True)
    chain3 = Offliner(unsure, cloud=CloudStub(), policy=open_policy)
    _show(
        "unsure local, dual gate open (escalated)",
        chain3.answer("help me", allow_cloud=True),
    )

    chain4 = Offliner(RuleBackend())
    _show(
        "rule stub with context",
        chain4.answer("summarize", context="LEVI is local-first."),
    )
    _show("rule stub without context", chain4.answer("summarize"))
    return 0


def _cmd_journal_demo(_args: argparse.Namespace) -> int:
    tmp = Path(tempfile.mkdtemp(prefix="levi-offline-"))
    journal = Journal(tmp / "turns.db")
    chain = Offliner(ScriptedBackend("local:brain", 0.9, "Local answer."))
    res = chain.answer("my password is hunter2, hello")
    turn_id = journal.log(res, "my password is hunter2, hello", session="demo")
    rows = journal.recent()
    print("logged turn id:", turn_id)
    print("stored prompt:", rows[0]["prompt"])
    out = tmp / "corpus.jsonl"
    n = journal.export_jsonl(out)
    print("exported %d records to %s" % (n, out))
    print("purged %d old rows" % journal.purge(30))
    journal.close()
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="levi.offline")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status").set_defaults(fn=_cmd_status)
    sub.add_parser("demo").set_defaults(fn=_cmd_demo)
    sub.add_parser("journal-demo").set_defaults(fn=_cmd_journal_demo)
    args = parser.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
