# SOXI pattern — honest build notes

SOXI is LEVI's intelligence classification (Chauncey, 2026-09-19/20):
Levi's synthetic offline-first half × XI's class half. Not a separate
product, not a legion member. These twelve classes are the internal
pattern LEVI instantiates.

## What each class really is

| Code | Name | Real mechanism | Honest limit |
|------|------|----------------|--------------|
| FR | Friction | SQLite corrections table + token-overlap retrieval | Needs ~50+ corrections before it feels personal |
| GR | Gleaner | Metadata-only walk + SQLite FTS | No vectors until a local embed model is wired; never reads contents |
| SH | Shadow | Abandonment log + quit-hour heuristics | Cannot see tabs/drafts without OS hooks — log is fed manually or by tools |
| ET | Etch | Hash-chained append-only JSONL | Tamper-*detectable*, not tamper-proof, against disk access |
| BT | Bent | Domain-locked small model via local runner | "2-bit QLoRA in 15 min" is fiction — see train_bt.py |
| CV | Cadence | 12-byte rhythm vector from explicit samples | No keylogger ships here; real capture needs OS permission |
| DR | Drift | Statement timeline + lexical distance | Lexical until embeddings wired; format is embedding-ready |
| LN | Loom | Keyword + win/loss scoreboard router | Dumb until the scoreboard has data — which is the point |
| RT | Root | Shutdown-hook markdown writer | Bookkeeping, not dreaming |
| WC | Witness | Append-only log, 30-day reveal gate | A commitment device, nothing more |
| TH | Threshold | Counter that speaks on Nth repeat | Trivial — and that's why it works |
| XI | Gremlin | Nano-operation experiment ledger | A lab notebook, not a model |

## The sever protocol (real version)

1. `config.toml`: `online = false` — the daemon refuses to run otherwise.
2. One-time online gathering: `ollama pull phi3:mini`, `nomic-embed-text`,
   llama.cpp — then nothing phones home.
3. Ghost sync is opt-in, explicit, and never carries GR data.

## What "train-then-sever" gets right

Training = living life is real for 11 of 12 classes: every correction,
abandoned draft, rhythm sample, and etched law is training data, and all
of it is collected offline by construction. Only BT involves weight
training, and train_bt.py documents the honest pipeline.
