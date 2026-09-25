"""Proof script for the Echoverse simulation corpora (law-guard-prove: the PROVE).

Checks, each machine-checkable:
  P1 DETERMINISM: regenerating with the same seed yields byte-identical JSONL.
  P2 STRUCTURE: every record carries all eight section markers.
  P3 VOCAB: every character of every record is ASCII (ord < 128), a strict
      subset of the v1 162-char vocabulary.
  P4 VALIDITY: every line is valid JSON with the required fields and a legal
      verdict.
  P5 PROVENANCE: every record carries engine_variant + lineage matching the
      declared values; no record attributes itself to the LEVI narrative
      variant or the LWP variant.
  P6 LOOP HEALTH: all three verdict classes appear (a corpus of only
      CONFIRMED would mean the engine never tests a wrong theory).
  P7 HELD-OUT DISJOINTNESS: when given a held-out path, no held-out record
      text appears in the training corpus.

Usage:
  python3 prove_echoverse.py <corpus.jsonl> <corpus_seed> <n_per_family> [heldout.jsonl]
Exits 0 iff every check passes; prints the verdict or the first failure.
"""

import hashlib
import json
import sys
import tempfile
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from echoverse_sim import (generate_corpus, ENGINE_VARIANT, LINEAGE,
                           VERDICTS, FAMILIES)

MARKERS = ("HYPOTHESIS", "EPISTEMIC:", "DOMAIN:", "SIMULATION:", "TRACE:",
           "OBSERVED OUTCOME:", "PREDICTION CHECK:", "REFINED UNDERSTANDING:")
REQUIRED_FIELDS = ("text", "kind", "engine", "loop", "lens", "hypothesis_id",
                   "domain", "verdict", "seed", "engine_variant", "lineage",
                   "family")


def fail(msg):
    print(f"PROOF FAILED: {msg}")
    sys.exit(1)


def main():
    corpus_path, seed, n = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
    heldout_path = sys.argv[4] if len(sys.argv) > 4 else None

    with open(corpus_path, "rb") as fh:
        raw = fh.read()
    disk_sha = hashlib.sha256(raw).hexdigest()

    # P1: determinism
    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as tf:
        tmp = tf.name
    try:
        m = generate_corpus(tmp, seed, n)
        with open(tmp, "rb") as fh:
            regen_sha = hashlib.sha256(fh.read()).hexdigest()
    finally:
        os.unlink(tmp)
        mp = tmp + ".manifest.json"
        if os.path.exists(mp):
            os.unlink(mp)
    if regen_sha != disk_sha:
        fail(f"P1 determinism: disk sha {disk_sha[:16]} != regen {regen_sha[:16]}")
    print(f"P1 determinism OK (sha256 {disk_sha[:16]}...)")

    # P2-P5 over records
    verdict_counts = {}
    n_records = 0
    for i, line in enumerate(raw.decode("ascii").splitlines()):
        if not line.strip():
            continue
        n_records += 1
        try:
            rec = json.loads(line)
        except json.JSONDecodeError as e:
            fail(f"P4 validity: line {i} bad JSON: {e}")
        for f in REQUIRED_FIELDS:
            if f not in rec:
                fail(f"P4 validity: line {i} missing field {f}")
        text = rec["text"]
        for mk in MARKERS:
            if mk not in text:
                fail(f"P2 structure: line {i} ({rec.get('hypothesis_id')}) missing {mk}")
        if any(ord(c) >= 128 for c in text):
            fail(f"P3 vocab: line {i} has non-ASCII")
        if rec["verdict"] not in VERDICTS:
            fail(f"P4 validity: line {i} bad verdict {rec['verdict']!r}")
        if rec["engine_variant"] != ENGINE_VARIANT:
            fail(f"P5 provenance: line {i} variant {rec['engine_variant']!r}")
        if rec["lineage"] != LINEAGE:
            fail(f"P5 provenance: line {i} lineage mismatch")
        verdict_counts[rec["verdict"]] = verdict_counts.get(rec["verdict"], 0) + 1
    print(f"P2 structure OK ({n_records} records, all markers)")
    print(f"P3 vocab OK (all ASCII)")
    print(f"P4 validity OK")
    print(f"P5 provenance OK (variant {ENGINE_VARIANT})")

    # P6: loop health
    missing = [v for v in VERDICTS if v not in verdict_counts]
    if missing:
        fail(f"P6 loop health: verdict classes absent: {missing}")
    print(f"P6 loop health OK {verdict_counts}")

    # P7: held-out disjointness
    if heldout_path:
        train_texts = set()
        for line in raw.decode("ascii").splitlines():
            if line.strip():
                train_texts.add(json.loads(line)["text"])
        overlap = 0
        with open(heldout_path) as fh:
            for line in fh:
                if line.strip() and json.loads(line)["text"] in train_texts:
                    overlap += 1
        if overlap:
            fail(f"P7 held-out disjointness: {overlap} held-out records in training")
        print("P7 held-out disjointness OK")

    print(f"ALL PROOFS PASS: {corpus_path} ({n_records} records)")


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print(__doc__)
        sys.exit(2)
    main()
