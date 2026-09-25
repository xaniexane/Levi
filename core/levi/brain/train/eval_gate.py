"""Eval gate for the continued-training candidate. All artifacts persistent.

1. Held-out cross-entropy: candidate (staging) vs incumbent (tiny-gpt.pt)
   on corpus_dialogue_heldout.jsonl (records never seen in training).
2. Behavioral samples: the 13 fixed prompts through runtime.py
   (levi-native vs levi-native-candidate), temp 0 / seed 7, verbatim.
3. Writes staging/eval_gate_results.json with everything.

The verdict itself stays human: this script reports numbers and samples,
it does not promote anything.

Usage:
    python3 eval_gate.py
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import torch
import torch.nn.functional as F

HERE = Path(__file__).resolve().parent
BRAIN = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(BRAIN))
from train import TinyGPT  # noqa: E402
import runtime as rt  # noqa: E402
from learn_eval import export_portable  # noqa: E402

WEIGHTS = BRAIN / "weights"
INCUMBENT = WEIGHTS / "tiny-gpt.pt"
STAGING = WEIGHTS / "staging"
CANDIDATE = STAGING / "tiny-gpt-continued.pt"
CANDIDATE_PORTABLE = STAGING / "tiny-gpt-continued-portable"
HELDOUT = HERE / "corpus_dialogue_heldout.jsonl"
RESULTS = STAGING / "eval_gate_results.json"
SAMPLES_LOG = STAGING / "eval_gate_samples.jsonl"

# 10 conversational + 3 creative. Prompts mirror the training format
# ("User: ...\nLEVI:") so the model continues as LEVI.
PROMPTS = [
    ("conv-greeting", "User: hello\nLEVI:"),
    ("conv-capabilities", "User: what can you do\nLEVI:"),
    ("conv-conscious", "User: are you conscious\nLEVI:"),
    ("conv-arithmetic", "User: what is 2+2\nLEVI:"),
    ("conv-followup", "User: what is 2+2\nLEVI: 4.\nUser: and what is 3+3\nLEVI:"),
    ("conv-weather", "User: what is the weather like\nLEVI:"),
    ("conv-plan-day", "User: help me plan my day\nLEVI:"),
    ("conv-are-you-sure", "User: are you sure about that\nLEVI:"),
    ("conv-about-levi", "User: tell me about LEVI\nLEVI:"),
    ("conv-goodnight", "User: goodnight\nLEVI:"),
    ("creat-story", "The daemon kept ticking through the night, and LEVI watched the logs grow like"),
    ("creat-description", "Describe the quiet of an offline machine at 3am:"),
    ("creat-voice", "A short piece in LEVI's voice about receipts:"),
]


def load_model_state(pt_path: Path):
    ckpt = torch.load(pt_path, map_location="cpu", weights_only=False)
    config = ckpt["config"]
    chars = ckpt["chars"]
    model = TinyGPT(
        len(chars),
        n_layer=config["n_layer"],
        n_head=config["n_head"],
        n_embd=config["n_embd"],
        block_size=config["block_size"],
    )
    model.load_state_dict(ckpt["model_state"])
    model.eval()
    return model, chars, config


def heldout_ce(model, chars, text: str, block_size: int) -> float:
    stoi = {c: i for i, c in enumerate(chars)}
    ids = [stoi[c] for c in text if c in stoi]
    losses = []
    with torch.no_grad():
        for i in range(0, len(ids) - block_size, block_size):
            chunk = torch.tensor(ids[i : i + block_size], dtype=torch.long)
            x, y = chunk[:-1].unsqueeze(0), chunk[1:].unsqueeze(0)
            logits = model(x)
            losses.append(
                F.cross_entropy(
                    logits.view(-1, len(chars)), y.view(-1)
                ).item()
            )
    return sum(losses) / len(losses)


def main() -> int:
    t0 = time.time()
    if not CANDIDATE.exists():
        print("ABORT: no candidate at", CANDIDATE)
        return 2
    if not HELDOUT.exists():
        print("ABORT: no held-out set at", HELDOUT)
        return 2

    heldout_text = "\n\n".join(
        json.loads(line)["text"]
        for line in open(HELDOUT, encoding="utf-8")
        if line.strip()
    )
    print(f"held-out text: {len(heldout_text):,} chars", flush=True)

    print("loading incumbent ...", flush=True)
    inc_model, inc_chars, inc_cfg = load_model_state(INCUMBENT)
    print("loading candidate ...", flush=True)
    cand_model, cand_chars, cand_cfg = load_model_state(CANDIDATE)
    assert inc_chars == cand_chars, "vocab mismatch between incumbent and candidate"

    block_size = inc_cfg["block_size"]
    print("held-out CE (incumbent) ...", flush=True)
    ce_inc = heldout_ce(inc_model, inc_chars, heldout_text, block_size)
    print(f"  incumbent: {ce_inc:.4f}", flush=True)
    print("held-out CE (candidate) ...", flush=True)
    ce_cand = heldout_ce(cand_model, cand_chars, heldout_text, block_size)
    print(f"  candidate: {ce_cand:.4f}  (delta {ce_inc - ce_cand:+.4f})", flush=True)

    # candidate -> portable (staging only; incumbent portable dir untouched)
    print("exporting candidate to portable (staging) ...", flush=True)
    export_portable(CANDIDATE, CANDIDATE_PORTABLE)

    rt.register_model(
        rt.ModelSpec(
            model_id="levi-native-candidate",
            arch=rt.ARCH_CHAR_GPT,
            display_name="LEVI native brain (continued-training candidate)",
            description="Staging candidate. Raw continuation — not reasoning.",
            weights_dir=str(CANDIDATE_PORTABLE),
            origin="levi",
        )
    )

    samples = []
    completed = {}
    if SAMPLES_LOG.exists():
        for line in open(SAMPLES_LOG, encoding="utf-8"):
            if line.strip():
                rec = json.loads(line)
                completed[rec["prompt_id"]] = rec
    for name, prompt in PROMPTS:
        if name in completed:
            print(f"prompt {name} ... (resuming from partial log)", flush=True)
            samples.append(completed[name])
            continue
        print(f"prompt {name} ...", flush=True)
        before = rt.run(
            "levi-native", prompt, max_new_chars=160,
            temperature=0, seed=7, record=False,
        )["continuation"]
        after = rt.run(
            "levi-native-candidate", prompt, max_new_chars=160,
            temperature=0, seed=7, record=False,
        )["continuation"]
        rec = {"prompt_id": name, "prompt": prompt,
               "incumbent": before, "candidate": after}
        samples.append(rec)
        with open(SAMPLES_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    results = {
        "heldout_records": sum(1 for _ in open(HELDOUT, encoding="utf-8")),
        "heldout_chars": len(heldout_text),
        "heldout_ce_incumbent": ce_inc,
        "heldout_ce_candidate": ce_cand,
        "heldout_ce_delta": ce_inc - ce_cand,
        "gate_margin": 0.02,
        "gate_numeric_pass": (ce_inc - ce_cand) >= 0.02,
        "sampling": {"temperature": 0, "seed": 7, "max_new_chars": 160},
        "samples": samples,
        "seconds": round(time.time() - t0, 1),
    }
    RESULTS.write_text(json.dumps(results, indent=1, ensure_ascii=False))
    print(f"results: {RESULTS}", flush=True)
    print(
        f"held-out CE incumbent {ce_inc:.4f} vs candidate {ce_cand:.4f} "
        f"(delta {ce_inc - ce_cand:+.4f}, gate needs >= +0.02)",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
