"""Ingest Chauncey's second 24-lesson batch (2026-09-26, pasted in chat).

Same validate-then-ingest protocol as ingest_batch_20260926_24.py:
validates every row (schema, non-empty, ASCII, teacher in known set),
dedupes exact-duplicate prompts against the existing corpus,
converts accepted rows to corpus dialogue format and appends to
train + union files. Dupes land in quarantine_batch_20260926_24b.jsonl.
Nothing is silently dropped. Provenance recorded per row.
"""
import json
from pathlib import Path

BATCH = Path("/home/hatch/workspace/levi/core/levi/brain/train/batches/levi_batch_20260926_24b.jsonl")
TRAIN_DIR = BATCH.parent.parent
REQUIRED = {"teacher", "prompt", "response", "topic"}
TEACHERS = {"gemini", "chatgpt", "claude", "grok", "qwen", "deepseek", "mistral", "kimi", "omega"}
QUAR = TRAIN_DIR / "quarantine_batch_20260926_24b.jsonl"


def norm_prompt(rec_text):
    first = rec_text.split("\n", 1)[0]
    return first[5:].strip().lower() if first.startswith("User:") else first.strip().lower()


def main():
    seen = set()
    for p in TRAIN_DIR.glob("*.jsonl"):
        if p == QUAR:
            continue
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

    rows = [json.loads(l) for l in BATCH.read_text().splitlines() if l.strip()]
    assert len(rows) == 24, f"batch row count drift: {len(rows)}"
    for i, rec in enumerate(rows):
        assert REQUIRED.issubset(rec.keys()), f"row {i}: schema drift"
        for k in REQUIRED:
            v = rec[k]
            assert isinstance(v, str) and v.strip(), f"row {i}: {k} empty/non-str"
        assert rec["teacher"] in TEACHERS, f"row {i}: unknown teacher"
        for k in ("prompt", "response", "topic"):
            assert rec[k].isascii(), f"row {i}: {k} non-ASCII"

    added = 0
    quarantined = []
    accepted = []
    for rec in rows:
        np = rec["prompt"].strip().lower()
        if np in seen:
            quarantined.append(rec)
        else:
            seen.add(np)
            accepted.append(rec)

    train_p = TRAIN_DIR / "corpus_dialogue_train.jsonl"
    union_p = TRAIN_DIR / "corpus_dialogue.jsonl"
    with open(train_p, "a") as ft, open(union_p, "a") as fu:
        for rec in accepted:
            out = {
                "text": f"User: {rec['prompt'].strip()}\nLEVI: {rec['response'].strip()}",
                "kind": "dialogue",
                "source": f"teacher-{rec['teacher']}",
                "topic": rec["topic"].strip(),
                "register": "levi",
                "ingested": "2026-09-26",
                "batch": "pasted-20260926-24b",
            }
            js = json.dumps(out, ensure_ascii=True) + "\n"
            ft.write(js)
            fu.write(js)
            added += 1

    with open(QUAR, "w") as fq:
        for rec in quarantined:
            fq.write(json.dumps(rec, ensure_ascii=True) + "\n")

    nt = sum(1 for _ in open(train_p))
    nh = sum(1 for _ in open(TRAIN_DIR / "corpus_dialogue_heldout.jsonl"))
    nu = sum(1 for _ in open(union_p))
    assert nu == nt + nh, f"union mismatch {nu} != {nt}+{nh}"
    print(f"ingested: {added} new, {len(quarantined)} dupes quarantined")
    print(f"train lines now: {nt}, union: {nu} (heldout {nh})")
    return added, len(quarantined), nt


if __name__ == "__main__":
    main()
