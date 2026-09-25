# levi-bpe-v2 tokenizer

Byte-level BPE, vocab 8192, trained 2026-09-21 on the v3 curriculum corpus
(`train_corpus.jsonl` = `corpus_curriculum.jsonl` + `corpus_dialogue.jsonl`).

v2 vs v1 (`core/levi/brain/train/tokenizer.json`): adds explicit
`<bos>` (260) / `<eos>` (261) specials. The byte codec is unchanged
(format `levi-bpe-v1`), and v1 tokenizers still load/decode byte-identically
(the merge-id base follows the specials table in use).

Usage: `LEVI_TOKENIZER_PATH=core/levi/brain/tokenizers/levi-bpe-v2/tokenizer.json`.
Training sequences are wrapped `[bos] ... [eos]`; `<eod>` marks document
boundaries inside multi-document streams.
