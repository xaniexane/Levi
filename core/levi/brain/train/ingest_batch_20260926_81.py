"""Ingest Chauncey's 81-lesson teacher batch (2026-09-26, pasted in chat).

Source: ~/workspace/levi-batches/levi_batch_20260926_81.jsonl
81 lines, 9 teachers x 9 (gemini/chatgpt/claude/grok/qwen/deepseek/mistral/kimi/omega).
The paste was cut off mid-line 82; only the 81 complete lines are in the
source file and only those are ingested. The truncated 82nd line is excluded
deliberately, never fabricated.

Validates every row (schema, non-empty, ASCII, teacher in known set,
topic kebab-case), dedupes exact-duplicate prompts against the ENTIRE
existing corpus (train/*.jsonl + train/batches/*.jsonl), quarantines
duplicates and hazmat rows into quarantine_batch_20260926_81.jsonl,
and appends accepted rows to corpus_dialogue_train.jsonl (train) and
corpus_dialogue.jsonl (union) in the established corpus dialogue format.
Nothing is silently dropped. Provenance recorded per row.
"""
import json
import re
from pathlib import Path

SOURCE = Path("/home/hatch/workspace/levi-batches/levi_batch_20260926_81.jsonl")
TRAIN_DIR = Path("/home/hatch/workspace/levi/core/levi/brain/train")
BATCH_OUT = TRAIN_DIR / "batches" / "levi_batch_20260926_81.jsonl"
QUAR = TRAIN_DIR / "quarantine_batch_20260926_81.jsonl"
REQUIRED = {"teacher", "prompt", "response", "topic"}
TEACHERS = {"gemini", "chatgpt", "claude", "grok", "qwen", "deepseek", "mistral", "kimi", "omega"}
EXPECTED = 81
TOPIC_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

# Light hazmat screen: flag rows that look like leaked secrets or
# wrongdoing-instruction material. Expected to find nothing in this batch;
# any hit is quarantined with reason, never silently dropped.
HAZMAT_PATTERNS = [
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"), "secret-private-key"),
    (re.compile(r"(?i)(api[_-]?key|secret|passwd|password)\s*[:=]\s*\S{8,}"), "secret-credential"),
    (re.compile(r"(?i)\b(ssn|social security)\s*[:#]?\s*\d{3}-\d{2}-\d{4}"), "pii-ssn"),
]


def norm_prompt(text):
    first = text.split("\n", 1)[0]
    return first[5:].strip().lower() if first.startswith("User:") else first.strip().lower()


def hazmat_reason(rec):
    blob = rec["prompt"] + "\n" + rec["response"]
    for rx, reason in HAZMAT_PATTERNS:
        if rx.search(blob):
            return reason
    return None


def main():
    # 1. Build the seen-prompt set from the entire existing corpus.
    seen = set()
    for p in list(TRAIN_DIR.glob("*.jsonl")) + list((TRAIN_DIR / "batches").glob("*.jsonl")):
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
                if isinstance(rec, dict):
                    t = rec.get("text", "")
                    if t:
                        seen.add(norm_prompt(t))
                    pr = rec.get("prompt", "")
                    if pr:
                        seen.add(pr.strip().lower())

    # 2. Load + validate source batch.
    rows = [json.loads(l) for l in SOURCE.read_text().splitlines() if l.strip()]
    assert len(rows) == EXPECTED, f"batch row count drift: {len(rows)}"
    teachers = {}
    for i, rec in enumerate(rows):
        assert REQUIRED.issubset(rec.keys()), f"row {i}: schema drift"
        for k in REQUIRED:
            v = rec[k]
            assert isinstance(v, str) and v.strip(), f"row {i}: {k} empty/non-str"
        assert rec["teacher"] in TEACHERS, f"row {i}: unknown teacher"
        for k in ("prompt", "response", "topic"):
            assert rec[k].isascii(), f"row {i}: {k} non-ASCII"
        assert TOPIC_RE.match(rec["topic"].strip()), f"row {i}: topic not kebab-case"
        teachers[rec["teacher"]] = teachers.get(rec["teacher"], 0) + 1
    assert teachers == {t: 9 for t in TEACHERS}, f"teacher rotation drift: {teachers}"

    # 3. Dedupe + hazmat screen.
    accepted = []
    quarantined = []  # (reason, row)
    batch_seen = set()
    for rec in rows:
        np = rec["prompt"].strip().lower()
        hr = hazmat_reason(rec)
        if hr:
            quarantined.append((hr, rec))
        elif np in batch_seen:
            quarantined.append(("duplicate-in-batch", rec))
        elif np in seen:
            quarantined.append(("duplicate-of-corpus", rec))
        else:
            batch_seen.add(np)
            seen.add(np)
            accepted.append(rec)

    # 4. Write canonical batch file (accepted rows only, canonical key order).
    BATCH_OUT.parent.mkdir(exist_ok=True)
    with open(BATCH_OUT, "w") as fb:
        for rec in accepted:
            canon = {
                "teacher": rec["teacher"].strip(),
                "prompt": rec["prompt"].strip(),
                "response": rec["response"].strip(),
                "topic": rec["topic"].strip(),
                "ingested_at": "2026-09-26",
            }
            fb.write(json.dumps(canon, ensure_ascii=True) + "\n")

    # 5. Append accepted rows to train + union corpus files.
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
                "batch": "pasted-20260926-81",
            }
            js = json.dumps(out, ensure_ascii=True) + "\n"
            ft.write(js)
            fu.write(js)

    # 6. Write quarantine file (raw rows; reasons reported to stdout).
    with open(QUAR, "w") as fq:
        for reason, rec in quarantined:
            fq.write(json.dumps({"reason": reason, **rec}, ensure_ascii=True) + "\n")

    # 7. Final corpus counts (same method as prior batches).
    nt = sum(1 for _ in open(train_p))
    nh = sum(1 for _ in open(TRAIN_DIR / "corpus_dialogue_heldout.jsonl"))
    nu = sum(1 for _ in open(union_p))
    assert nu == nt + nh, f"union mismatch {nu} != {nt}+{nh}"

    print(f"accepted: {len(accepted)}, quarantined: {len(quarantined)}")
    for reason, rec in quarantined:
        print(f"  quarantined [{reason}]: {rec['prompt'][:80]}")
    print(f"corpus train: {nt}, union: {nu}, held-out: {nh}")
    return len(accepted), len(quarantined), nt, nu, nh


if __name__ == "__main__":
    main()
