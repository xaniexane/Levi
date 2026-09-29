# Head-to-head benchmark — LEVI BPE brain vs small reference models

Run: 2026-09-27T02:58:08+0000  |  checkpoint `tiny-gpt-bpe-ckpt-006480.pt` (step 6480, round 4)
Bench: 40 brand-new LEVI-voice texts, sha256 `20bd636577bff9cd6b792cb4e57f55232552fece84835eccf3e034d6dd151cee`

> **Tokenizer caveat.** Every model is scored with its OWN tokenizer, so perplexities are not strictly comparable across tokenizers. The fair signal is LEVI's own delta on these texts across checkpoints; the cross-model column is directional only.

| model | params | ppl (own tok) | delta vs LEVI |
| --- | --- | --- | --- |
| LEVI (BPE brain) | 1.8M | 117.34 | — |
| gpt2 | 124.4M | 41.35 | +75.98 |
| roneneldan/TinyStories-33M | 68.5M | 9543.32 | -9425.99 |

## LEVI-voice coherence: 72.50% checks passed

8 fixed prompts, temperature 0.8, fixed seeds, 60 tokens each. Deterministic rubric: ASCII-only, 1-4 sentences, non-repetitive, on-topic. No cherry-picking.

| prompt | passed | failed checks |
| --- | --- | --- |
| How do I back up my LEVI notes? | 4/5 | on_topic |
| What does local-first mean? | 4/5 | non_repetitive |
| Can two twins share a folder without the internet? | 3/5 | ascii_only, on_topic |
| Why does LEVI say it is not alive? | 2/5 | ascii_only, non_repetitive, on_topic |
| How do I check that no data left my laptop? | 3/5 | ascii_only, on_topic |
| What happens if the network drops mid-answer? | 3/5 | ascii_only, on_topic |
| Explain a checksum without jargon. | 5/5 | none |
| Can LEVI set a reminder while offline? | 5/5 | none |

## Sample generations (verbatim, fixed seeds)

**Q:** How do I back up my LEVI notes?
**A:** 
LEVI: The LEVI Builder register. Voice: Stes, you can't do. Grief is a goal in the national forever with her hands a humor of 

**Q:** What does local-first mean?
**A:**  Three the observation store records on here. SkillRegistoric a door. The machine remembers was her wouldn'ty-eves me. The rogated, and 

**Q:** Can two twins share a folder without the internet?
**A:** <eod>User: do you speak as
LEVI: The receipt asked is what Morn tiful height — every head. That's the whole gone. That's the cont

**Q:** Why does LEVI say it is not alive?
**A:** 
User: what is the LEVI Liter register
LEVI: Chauncey's termer — I don't run it, me — the story before you doing
LEVI: Nothing 

**Q:** How do I check that no data left my laptop?
**A:** 
User: do you set it when you will can only making doing it, when) and I won't pretending is receipts — no one and no one is 

**Q:** What happens if the network drops mid-answer?
**A:**  Give: brightling receipt an before the she vending of the place place beyond its risk ceiling a text, — the skill system — the first

**Q:** Explain a checksum without jargon.
**A:**  date. He built on his machines: I can build without fating consent before, or That's the whole worst of it and he loss that never t

**Q:** Can LEVI set a reminder while offline?
**A:** 
User: . Never: promise's than first?<eod>User: about a receipt on his machinesone- reset is an archive of a bridge exerts for the 

_eval took 165s · glyph 📊_
