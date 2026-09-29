"""Ingest Chauncey's zip training data: 101,951 verified-good lessons.

Re-validates every row with the same rules as the inspection pass
(schema, non-empty, ASCII, dedupe), converts to corpus dialogue format,
appends to train + union files. Provenance: source file recorded per row.
"""
import json
from pathlib import Path

INSP = Path("/home/hatch/workspace/hidden-tmp/zip-inspect")
TRAIN_DIR = Path("/home/hatch/workspace/levi/core/levi/brain/train")
FILES = [
    "levi_batch_01_24.jsonl",
    "levi_batch_02_24.jsonl",
    "levi_batch_03_20.jsonl",
    "levi_batch_04_24.jsonl",
    "levi_training_2000.jsonl",
    "levi_training_100k.jsonl",
]
REQUIRED = {"teacher", "prompt", "response", "topic"}


def norm_prompt(rec_text):
    first = rec_text.split("\n", 1)[0]
    return first[5:].strip().lower() if first.startswith("User:") else first.strip().lower()


def main():
    seen = set()
    for p in TRAIN_DIR.glob("*.jsonl"):
        with open(p) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                t = rec.get("text", "")
                if t:
                    seen.add(norm_prompt(t))
                pr = rec.get("prompt", "")
                if pr:
                    seen.add(pr.strip().lower())

    added = skipped = 0
    train_p = TRAIN_DIR / "corpus_dialogue_train.jsonl"
    union_p = TRAIN_DIR / "corpus_dialogue.jsonl"
    with open(train_p, "a") as ft, open(union_p, "a") as fu:
        for name in FILES:
            with open(INSP / name) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    rec = json.loads(line)
                    assert REQUIRED.issubset(rec.keys()), f"schema drift in {name}"
                    prompt = str(rec["prompt"]).strip()
                    response = str(rec["response"]).strip()
                    assert prompt and response
                    assert prompt.isascii() and response.isascii()
                    np = prompt.lower()
                    if np in seen:
                        skipped += 1
                        continue
                    seen.add(np)
                    out = {
                        "text": f"User: {prompt}\nLEVI: {response}",
                        "kind": "dialogue",
                        "source": f"teacher-{rec['teacher']}",
                        "topic": str(rec["topic"]),
                        "register": "levi",
                        "ingested": "2026-09-26",
                        "batch": f"zip-{Path(name).stem}",
                    }
                    js = json.dumps(out, ensure_ascii=True) + "\n"
                    ft.write(js)
                    fu.write(js)
                    added += 1

    nt = sum(1 for _ in open(train_p))
    nh = sum(1 for _ in open(TRAIN_DIR / "corpus_dialogue_heldout.jsonl"))
    nu = sum(1 for _ in open(union_p))
    assert nu == nt + nh, f"union mismatch {nu} != {nt}+{nh}"
    print(f"ingested: {added} new, {skipped} dupes skipped")
    print(f"train lines now: {nt}, union: {nu} (heldout {nh})")


if __name__ == "__main__":
    main()
