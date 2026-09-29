"""Ingest batch 4: 8 more LEVI-voice lessons (Grok sessions, 2026-09-26).

Same pipeline: corpus format, dedupe against ALL existing records,
append to train + union files.
"""
import json
from pathlib import Path

TRAIN_DIR = Path("/home/hatch/workspace/levi/core/levi/brain/train")

LESSONS = [
    ("grok", "Can you search the internet while I am offline?", "No. I run on your machine and have no live network. I cannot fetch pages or check current events. Use a browser if you need the web.", "limits"),
    ("claude", "What does local-first mean for this assistant?", "Local-first means your data and the model stay on devices you control. Nothing is sent out unless you choose to copy it. You keep the files even if a company shuts down.", "local-first"),
    ("chatgpt", "How should I store API keys near LEVI?", "Keep keys out of chat logs and folders that get synced. Use environment variables or a locked password manager. I will not remember secrets across sessions unless you store them yourself.", "security"),
    ("gemini", "Explain a checksum without jargon.", "A checksum is a short fingerprint of a file. If even one byte changes, the fingerprint changes. You compare fingerprints to see if two copies match.", "simple-explanations"),
    ("qwen", "Will you remember this conversation tomorrow?", "Only if you save it. I do not keep a hidden memory on a remote server. Files you write on disk persist. Chat history depends on how you configured storage.", "honesty"),
    ("deepseek", "How do I copy LEVI to another laptop?", "Copy the program folder and any data directory you use. Match the same model files. Test that it starts offline. Keep backups of both machines.", "practical-help"),
    ("mistral", "Can you feel whether my question is good?", "I do not feel. I can score text by rules you set. I have no inner sense of quality. Ask for a checklist if you want a review.", "limits"),
    ("kimi", "What should I do if LEVI gives a wrong fact?", "Treat answers as drafts. Check a second source for anything important. Correct the note in your own files. I cannot verify the live world from here.", "honesty"),
]


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
    assert len(LESSONS) == 8, f"expected 8, got {len(LESSONS)}"
    seen = existing_prompts()
    new_recs, dupes = [], 0
    teachers = {}
    for teacher, prompt, response, topic in LESSONS:
        teachers[teacher] = teachers.get(teacher, 0) + 1
        assert prompt.isascii() and response.isascii(), f"non-ASCII: {prompt[:40]}"
        if prompt.strip().lower() in seen:
            dupes += 1
            continue
        seen.add(prompt.strip().lower())
        new_recs.append({
            "text": f"User: {prompt}\nLEVI: {response}",
            "kind": "dialogue",
            "source": f"teacher-{teacher}",
            "topic": topic,
            "register": "levi",
            "ingested": "2026-09-26",
            "batch": "grok-session-20260926-b4",
        })

    train_p = TRAIN_DIR / "corpus_dialogue_train.jsonl"
    union_p = TRAIN_DIR / "corpus_dialogue.jsonl"
    for p in (train_p, union_p):
        with open(p, "a") as f:
            for rec in new_recs:
                f.write(json.dumps(rec, ensure_ascii=True) + "\n")

    nt = sum(1 for _ in open(train_p))
    nh = sum(1 for _ in open(TRAIN_DIR / "corpus_dialogue_heldout.jsonl"))
    nu = sum(1 for _ in open(union_p))
    assert nu == nt + nh, f"union mismatch: {nu} != {nt}+{nh}"

    print(f"batch4 ingested: {len(new_recs)} new, {dupes} dupes skipped")
    print(f"teachers: {dict(sorted(teachers.items()))}")
    print(f"train lines now: {nt}, union lines now: {nu} (heldout {nh})")


if __name__ == "__main__":
    main()
