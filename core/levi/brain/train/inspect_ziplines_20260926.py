"""Inspect Chauncey's three training zips: validate, dedupe, quarantine.

Checks per row: valid JSON, required keys (teacher/prompt/response/topic),
non-empty prompt+response, plain ASCII (per LEVI-voice spec), duplicate
prompts (within/across files, and against the existing training corpus).
Bad rows go to quarantine — never silently dropped.
"""
import json
from pathlib import Path

INSP = Path("/home/hatch/workspace/hidden-tmp/zip-inspect")
TRAIN_DIR = Path("/home/hatch/workspace/levi/core/levi/brain/train")
QUAR = INSP / "quarantine.jsonl"
REPORT = INSP / "inspect_report.json"

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


def existing_prompts():
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
    return seen


def main():
    seen = existing_prompts()
    report = {"files": {}, "totals": {"rows": 0, "good": 0, "quarantined": 0}}
    quar_reasons = {}
    with open(QUAR, "w") as qf:
        for name in FILES:
            p = INSP / name
            stats = {"rows": 0, "good": 0, "bad_json": 0, "bad_schema": 0,
                     "empty": 0, "non_ascii": 0, "dupe_in_file": 0,
                     "dupe_cross_file": 0, "dupe_existing_corpus": 0,
                     "teachers": {}, "topics": 0}
            file_prompts = set()
            with open(p) as f:
                for ln, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue
                    stats["rows"] += 1
                    try:
                        rec = json.loads(line)
                    except json.JSONDecodeError:
                        stats["bad_json"] += 1
                        qf.write(json.dumps({"file": name, "line": ln,
                                             "reason": "bad_json"}) + "\n")
                        continue
                    if not isinstance(rec, dict) or not REQUIRED.issubset(rec.keys()):
                        stats["bad_schema"] += 1
                        qf.write(json.dumps({"file": name, "line": ln,
                                             "reason": "bad_schema",
                                             "keys": list(rec.keys()) if isinstance(rec, dict) else None}) + "\n")
                        continue
                    prompt = str(rec.get("prompt", ""))
                    response = str(rec.get("response", ""))
                    if not prompt.strip() or not response.strip():
                        stats["empty"] += 1
                        qf.write(json.dumps({"file": name, "line": ln,
                                             "reason": "empty_prompt_or_response"}) + "\n")
                        continue
                    if not (prompt.isascii() and response.isascii()):
                        stats["non_ascii"] += 1
                        qf.write(json.dumps({"file": name, "line": ln,
                                             "reason": "non_ascii",
                                             "prompt": prompt[:80]}) + "\n")
                        continue
                    np = prompt.strip().lower()
                    if np in file_prompts:
                        stats["dupe_in_file"] += 1
                        qf.write(json.dumps({"file": name, "line": ln,
                                             "reason": "dupe_in_file",
                                             "prompt": prompt[:80]}) + "\n")
                        continue
                    file_prompts.add(np)
                    if np in seen:
                        # distinguish: already in the existing corpus vs in an earlier zip file
                        stats["dupe_cross_file"] += 1
                        qf.write(json.dumps({"file": name, "line": ln,
                                             "reason": "dupe_seen_before",
                                             "prompt": prompt[:80]}) + "\n")
                        continue
                    seen.add(np)
                    stats["good"] += 1
                    t = str(rec.get("teacher", "?"))
                    stats["teachers"][t] = stats["teachers"].get(t, 0) + 1
            report["files"][name] = stats
            for k in ("rows", "good"):
                report["totals"][k] += stats[k]
            report["totals"]["quarantined"] += stats["rows"] - stats["good"]

    # split dupe_cross_file into existing-corpus vs earlier-file is
    # informational; keep simple. Report teachers overall.
    all_teachers = {}
    for name, st in report["files"].items():
        for t, c in st["teachers"].items():
            all_teachers[t] = all_teachers.get(t, 0) + c
    report["teachers_overall"] = dict(sorted(all_teachers.items()))
    REPORT.write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2)[:3000])
    print("...")
    print(f"TOTALS: rows={report['totals']['rows']} good={report['totals']['good']} "
          f"quarantined={report['totals']['quarantined']}")
    print(f"quarantine file: {QUAR} ({QUAR.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
