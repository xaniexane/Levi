"""Head-to-head benchmark: LEVI's BPE brain vs small reference models.

Measures every model on the SAME texts with the SAME metric (perplexity),
then prints a plain caveat: tokenizers differ across models, so perplexities
are not strictly comparable cross-tokenizer. The within-tokenizer delta
between LEVI checkpoints is the fair signal; the cross-model column is
directional only.

Baselines (default): gpt2 (124M) and roneneldan/TinyStories-33M (33M).
Weights are read from local mirrors at ~/workspace/headtohead-models/
(curl'd through the sandbox proxy — huggingface_hub cannot parse this
sandbox's proxy URL, so the harness never depends on it). If a local mirror
is missing the harness tries the HF id, and on failure says so honestly --
it never invents baseline numbers.

LEVI-voice coherence check: N fixed prompts, fixed seeds, deterministic
rubric (ASCII-only, 1-4 sentences, non-repetitive, on-topic keyword overlap).
Same prompts every run, no cherry-picking.

Outputs:
  - results JSON  -> <staging>/headtohead-<step>.json
  - EVAL_HEADTOHEAD.md -> <staging>/EVAL_HEADTOHEAD.md (real numbers only)

Glyph: 📊
"""
import argparse
import hashlib
import json
import math
import re
import sys
import time
from pathlib import Path

import torch
import torch.nn.functional as F

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from tok import ByteBPETokenizer  # noqa: E402
from train import TinyGPT  # noqa: E402

STAGING = HERE.parent / "weights" / "staging_bpe"
BENCH = HERE / "bench_texts.jsonl"
BENCH_HASH_FILE = HERE / "bench_texts.sha256"

TEMPERATURE = 0.8
GEN_TOKENS = 60

# Fixed prompts for the coherence check. Same every run, no cherry-picking.
COHERENCE_PROMPTS = [
    "How do I back up my LEVI notes?",
    "What does local-first mean?",
    "Can two twins share a folder without the internet?",
    "Why does LEVI say it is not alive?",
    "How do I check that no data left my laptop?",
    "What happens if the network drops mid-answer?",
    "Explain a checksum without jargon.",
    "Can LEVI set a reminder while offline?",
]

# Baseline model ids on HuggingFace.
DEFAULT_BASELINES = ["gpt2", "roneneldan/TinyStories-33M"]

# Local mirrors of the baseline weights (curl'd through the sandbox proxy;
# huggingface_hub cannot parse this sandbox's proxy URL, so the harness never
# depends on it). If a local dir is missing, the harness falls back to the HF
# id and says so honestly on failure.
BASELINE_LOCAL = {
    "gpt2": Path.home() / "workspace" / "headtohead-models" / "gpt2",
    "roneneldan/TinyStories-33M":
        Path.home() / "workspace" / "headtohead-models" / "tinystories-33m",
}


# ---------------------------------------------------------------- helpers
def load_bench(path=BENCH):
    recs = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                recs.append(json.loads(line))
    return recs


def verify_bench_pin():
    h = hashlib.sha256(BENCH.read_bytes()).hexdigest()
    if BENCH_HASH_FILE.exists():
        want = BENCH_HASH_FILE.read_text().split()[0]
        assert h == want, f"bench_texts.jsonl changed since pin! {h} != {want}"
    return h


def scoring_texts(recs):
    return [r["prompt"] + "\n" + r["response"] for r in recs]


def chunk_ppl_windows(ids, block_size, stride):
    """Yield (x, y) windows for sliding-window perplexity."""
    for i in range(0, max(1, len(ids) - block_size), stride):
        x = ids[i:i + block_size]
        y = ids[i + 1:i + block_size + 1]
        if len(x) < block_size:
            continue
        yield x, y


def ppl_torch_model(model, ids, block_size, stride=None, device="cpu"):
    model.eval()
    total_nll = 0.0
    total_tok = 0
    stride = stride or block_size
    with torch.no_grad():
        for x, y in chunk_ppl_windows(ids, block_size, stride):
            xt = torch.tensor([x], device=device)
            yt = torch.tensor([y], device=device)
            logits = model(xt)
            if not isinstance(logits, torch.Tensor):  # HF ModelOutput
                logits = logits.logits
            nll = F.cross_entropy(
                logits.view(-1, logits.size(-1)), yt.view(-1),
                reduction="sum").item()
            total_nll += nll
            total_tok += yt.numel()
    return math.exp(total_nll / total_tok), total_nll, total_tok


def load_levi_checkpoint(staging=STAGING):
    ckpts = sorted(staging.glob("tiny-gpt-bpe-ckpt-*.pt"))
    assert ckpts, "no LEVI BPE checkpoints"
    latest = ckpts[-1]
    ckpt = torch.load(latest, map_location="cpu", weights_only=False)
    return latest, ckpt


def levi_model_and_ids(staging, recs):
    latest, ckpt = load_levi_checkpoint(staging)
    cfg = ckpt["config"]
    tok = ByteBPETokenizer.load(str(HERE / "tokenizer.json"))
    model = TinyGPT(
        vocab_size=cfg["vocab_size"], n_layer=cfg["n_layer"],
        n_head=cfg["n_head"], n_embd=cfg["n_embd"],
        block_size=cfg["block_size"])
    model.load_state_dict(ckpt["model_state"])
    ids = []
    for t in scoring_texts(recs):
        ids.extend(tok.encode(t))
    return latest, ckpt, model, tok, ids, cfg


def baseline_ppl(model_id, recs):
    """Perplexity of a HuggingFace causal LM on the same texts.
    Uses the model's OWN tokenizer. Prefers the local mirror dir;
    falls back to the HF id. Returns dict with ppl + meta.
    """
    from transformers import AutoModelForCausalLM, AutoTokenizer
    src = str(BASELINE_LOCAL.get(model_id, model_id))
    local = Path(src)
    if local.is_dir() and not (local / "config.json").exists():
        raise OSError(f"local baseline dir {src} has no config.json")
    tok = AutoTokenizer.from_pretrained(src, local_files_only=local.is_dir())
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    model = AutoModelForCausalLM.from_pretrained(
        src, local_files_only=local.is_dir())
    model.eval()
    ids = []
    for t in scoring_texts(recs):
        ids.extend(tok.encode(t))
    block = min(getattr(model.config, "n_positions", 1024) or 1024,
                getattr(model.config, "max_position_embeddings", 1024) or 1024)
    ppl, nll, ntok = ppl_torch_model(model, ids, block, stride=block // 2)
    params = sum(p.numel() for p in model.parameters())
    return {"model": model_id, "ppl": ppl, "params": params,
            "tokens": ntok, "block": block,
            "vocab": tok.vocab_size}


# ------------------------------------------------------- coherence check
def sentences(text):
    return [s for s in re.split(r"[.!?]\s*", text.strip()) if s.strip()]


def rubric(prompt, text):
    """Deterministic LEVI-voice rubric. Returns dict of pass/fail per check."""
    words = re.findall(r"[A-Za-z]{5,}", prompt.lower())
    low = text.lower()
    fours = re.findall(r"\w+(?:\s+\w+){3}", low)
    rep = 0.0
    if fours:
        top = max(fours.count(g) for g in set(fours))
        rep = top / len(fours)
    n_sent = len(sentences(text))
    domain = ("local", "offline", "machine", "disk", "file", "computer",
              "data", "folder", "note", "server", "network")
    checks = {
        "ascii_only": all(ord(c) < 128 for c in text),
        "non_empty": len(text.strip()) >= 20,
        "short_sentences": 1 <= n_sent <= 4,
        "non_repetitive": rep < 0.50,
        "on_topic": any(w in low for w in words) or any(w in low for w in domain),
    }
    return checks


def coherence_check(model, tok, block_size):
    results = []
    for pi, prompt in enumerate(COHERENCE_PROMPTS):
        torch.manual_seed(20260927 + pi)
        ids = tok.encode(prompt)[-block_size:]
        prompt_len = len(tok.encode(prompt))
        x = torch.tensor([ids])
        with torch.no_grad():
            for _ in range(GEN_TOKENS):
                logits = model(x[:, -block_size:])
                probs = F.softmax(logits[0, -1] / TEMPERATURE, dim=-1)
                nxt = torch.multinomial(probs, 1).item()
                ids.append(nxt)
                x = torch.tensor([ids])
        text = tok.decode(ids[prompt_len:])
        checks = rubric(prompt, text)
        passed = sum(checks.values())
        results.append({
            "prompt": prompt, "text": text[:400],
            "checks": checks, "passed": passed,
            "total": len(checks),
        })
    agg = sum(r["passed"] for r in results) / sum(r["total"] for r in results)
    return results, agg


# ------------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--staging", default=str(STAGING))
    ap.add_argument("--baselines", default=",".join(DEFAULT_BASELINES))
    ap.add_argument("--skip-baselines", action="store_true")
    ap.add_argument("--coherence-only", action="store_true")
    args = ap.parse_args()

    staging = Path(args.staging)
    t0 = time.time()

    pin = verify_bench_pin()
    recs = load_bench()
    print(f"bench: {len(recs)} texts, sha256 {pin[:16]}...")
    print()
    print("TOKENIZER CAVEAT: each model is scored with its own tokenizer.")
    print("Perplexities are NOT strictly comparable across tokenizers.")
    print("The fair signal is LEVI's delta on these texts across checkpoints;")
    print("cross-model columns are directional only.")
    print()

    # --- LEVI ---
    latest, ckpt, model, tok, ids, cfg = levi_model_and_ids(staging, recs)
    step = ckpt["step"]
    block = cfg["block_size"]
    levi_ppl, _, levi_tok = ppl_torch_model(model, ids, block)
    print(f"LEVI  {latest.name} step={step} round={ckpt.get('round')}: "
          f"ppl={levi_ppl:.2f} on {levi_tok} tokens (levi-bpe-v1, {block}-ctx)")

    # --- baselines ---
    rows = [{"name": "LEVI (BPE brain)", "model": latest.name,
             "ppl": levi_ppl, "tokens": levi_tok,
             "params": sum(p.numel() for p in model.parameters()),
             "tokenizer": "levi-bpe-v1 (own)", "step": step}]
    if args.skip_baselines or args.coherence_only:
        print("baselines skipped (--skip-baselines)")
    else:
        for mid in [m for m in args.baselines.split(",") if m]:
            try:
                r = baseline_ppl(mid, recs)
                rows.append({"name": mid, "model": mid, "ppl": r["ppl"],
                             "tokens": r["tokens"], "params": r["params"],
                             "tokenizer": f"{mid} (own)"})
                print(f"BASE  {mid}: ppl={r['ppl']:.2f} "
                      f"params={r['params']/1e6:.1f}M on {r['tokens']} tokens")
            except Exception as e:  # honest: say so, never invent numbers
                print(f"BASE  {mid}: FAILED ({type(e).__name__}: {e})")
                rows.append({"name": mid, "model": mid, "ppl": None,
                             "error": f"{type(e).__name__}: {e}"})

    for r in rows[1:]:
        if r.get("ppl") and levi_ppl:
            d = levi_ppl - r["ppl"]
            better = "LEVI better" if d < 0 else "baseline better"
            print(f"DELTA LEVI vs {r['name']}: {d:+.2f} ppl ({better})")

    # --- coherence ---
    coh, agg = coherence_check(model, tok, block)
    print(f"\nLEVI coherence: {agg:.2%} checks passed "
          f"({len(COHERENCE_PROMPTS)} fixed prompts, temp={TEMPERATURE}, "
          f"seeds fixed)")
    for r in coh:
        fails = [k for k, v in r["checks"].items() if not v]
        print(f"  [{r['passed']}/{r['total']}] {r['prompt'][:44]:46s} "
              f"fails={fails or 'none'}")

    # --- write results ---
    payload = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "bench": {"texts": len(recs), "sha256": pin},
        "levi": {"checkpoint": latest.name, "step": step,
                 "round": ckpt.get("round"), "ppl": levi_ppl,
                 "tokens": levi_tok, "tokenizer": "levi-bpe-v1"},
        "baselines": rows[1:],
        "coherence": {"prompts": len(COHERENCE_PROMPTS),
                      "fraction": agg, "results": coh},
        "caveat": ("Each model scored with its own tokenizer; "
                   "cross-tokenizer perplexities are directional only."),
        "glyph": "📊",
    }
    jf = staging / f"headtohead-step{step}.json"
    jf.write_text(json.dumps(payload, indent=2))
    print(f"\nwrote {jf}")

    # --- EVAL_HEADTOHEAD.md (real numbers only) ---
    md = ["# Head-to-head benchmark — LEVI BPE brain vs small reference models",
          "",
          f"Run: {payload['timestamp']}  |  checkpoint `{latest.name}` "
          f"(step {step}, round {ckpt.get('round')})",
          f"Bench: {len(recs)} brand-new LEVI-voice texts, sha256 `{pin}`",
          "",
          "> **Tokenizer caveat.** Every model is scored with its OWN "
          "tokenizer, so perplexities are not strictly comparable "
          "across tokenizers. The fair signal is LEVI's own delta on "
          "these texts across checkpoints; the cross-model column is "
          "directional only.",
          "",
          "| model | params | ppl (own tok) | delta vs LEVI |",
          "| --- | --- | --- | --- |"]
    for r in rows:
        if r["name"] == "LEVI (BPE brain)":
            md.append(f"| LEVI (BPE brain) | {r['params']/1e6:.1f}M | "
                      f"{r['ppl']:.2f} | — |")
        elif r.get("ppl"):
            d = levi_ppl - r["ppl"]
            md.append(f"| {r['name']} | {r['params']/1e6:.1f}M | "
                      f"{r['ppl']:.2f} | {d:+.2f} |")
        else:
            md.append(f"| {r['name']} | n/a | FAILED | n/a |")
    md += ["",
           f"## LEVI-voice coherence: {agg:.2%} checks passed",
           "",
           f"{len(COHERENCE_PROMPTS)} fixed prompts, temperature "
           f"{TEMPERATURE}, fixed seeds, {GEN_TOKENS} tokens each. "
           "Deterministic rubric: ASCII-only, 1-4 sentences, non-repetitive, "
           "on-topic. No cherry-picking.",
           "",
           "| prompt | passed | failed checks |",
           "| --- | --- | --- |"]
    for r in coh:
        fails = ", ".join(k for k, v in r["checks"].items() if not v) or "none"
        md.append(f"| {r['prompt']} | {r['passed']}/{r['total']} | {fails} |")
    md += ["",
           "## Sample generations (verbatim, fixed seeds)",
           ""]
    for r in coh:
        md.append(f"**Q:** {r['prompt']}")
        md.append(f"**A:** {r['text']}")
        md.append("")
    md.append(f"_eval took {time.time()-t0:.0f}s · glyph 📊_")
    (staging / "EVAL_HEADTOHEAD.md").write_text("\n".join(md) + "\n")
    print(f"wrote {staging / 'EVAL_HEADTOHEAD.md'}")


if __name__ == "__main__":
    main()
