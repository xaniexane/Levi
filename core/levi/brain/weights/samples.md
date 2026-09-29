# tiny-gpt samples

_held-out loss: 1.8570 | params: 3,271,168 | steps: 600 | corpus: 847,990 chars_

## prompt: 'Operating systems manage'

```
Operating systems manageributialate Compacted \Teling, Donytrot or Provethoprits Jonessorkead-yllial CSprof Scatif
Ruled JUsion Deaf
A Assivigns Sytawen
En . These sourgoriv ve, courscation we hotphill fo my boste, aquily he
```

## prompt: 'Register: LEVI'

```
Register: LEVI99 Wensorrs. : Wis ryl Compats
Scontading ( !), ased S(Unecity7), MADC. Stwø)
LAR)
# Krisomple colurplod ] hatep
IQuer-baphosss.ignignal
CRN-343pt
Nontemes HoI Stavexs : Eme oi Reassill kewn (11) to m
```

## prompt: 'Machine learning is'

```
Machine learning is in a sloorde
tecguation renis useand a the flome. DJayke course expating Lam
Sop': On 200
Thoor infor flineatines fost Uficed.
© (13: Coundinesom)
- you to have cuse worte
sions alters flith yneppect
```

---

## Tuning 2026-09-25: greedy vs temperature-0.8 (backlog item 8 — unblocked)

**Method** (no training, no weight changes — Brain V2 untouched): loaded
the committed `tiny-gpt.pt` through the committed `core/levi/brain/inference.py`
(`load_brain`), generated 160-char continuations for 5 held-out-style
prompts with `generate()` — greedy (`temperature=0`) vs sampling
(`temperature=0.8`), fixed seeds (1337, 4242), CPU torch 2.14.0+cpu.
Determinism proven: greedy ×2 byte-identical, temp-0.8 ×2 byte-identical.
Provenance: sha256 `7474e24f97c8df50904a26367a27e2e57dbaa050b0238cba1b1e79a46997e3b2`
matches the recorded expected hash; 3,271,168 params; 600 steps; 162-char vocab;
847,990 corpus chars. Script + full results:
`~/workspace/goals/levi-repo-modernization/hidden_files/round-the-clock/brain_voice_tuning.py`
and `brain_voice_tuning_results.json`.

**Measured unique-3-gram ratio** (1.0 = no repetition, over the continuation only):

| prompt | greedy | t=0.8 seed 1337 | t=0.8 seed 4242 |
|---|---|---|---|
| 'Operating systems manage' | 0.291 | 0.885 | 0.863 |
| 'Register: LEVI' | 0.390 | 0.936 | 0.872 |
| 'Machine learning is' | 0.260 | 0.870 | 0.881 |
| 'The future of work is' | 0.156 | 0.844 | 0.832 |
| 'A gentle rain fell on' | 0.140 | 0.894 | 0.827 |

**Verbatim samples** ('Machine learning is', first 120 continuation chars):

- greedy: ` and the the the the the the the the the to the the the seareare source the the the the sture the the the the the soure `
- t=0.8: ` strems, with for the bet with nowing and arvind exten of you mort here Moscest:\nThahad, on gor Fare toppe Thesat's buss`

**Verdict (honest):** neither mode produces usable text. Greedy collapses
into degenerate repetition loops — literal "the the the the…" on 3 of 5
prompts (3-gram ratio as low as 0.14). Temperature-0.8 trades repetition
for nonsense variety (3-gram ratio 0.83–0.94) but the output is still
non-language word-salad ("fseals allate conce conternodes"), matching the
garbled-output caveat this file already carried. This confirms the
standing law: the brain-voice is heard, never obeyed — the content is
noise in both modes. Practical consequence for `levi.alpha.reason`: the
brain-voice confidence cap stays where it is (below every rules stance),
and temperature-0.8 stays the only usable mode for the skeptical stance's
drift-word evidence (greedy would just echo "the the the"). The brain
remains a proof-of-learning: the loss curve proves the architecture
learns; the samples prove it cannot write.
