"""SUPERSEDED — LoRA fine-tune of third-party Qwen weights on the course corpus.

STATUS: SUPERSEDED BY USER DIRECTIVE (2026-09-15). LEVI does not build
on LLaMA-family weights — the native brain (``levi-brain``,
``core/levi/agent/brain_provider.py``) is the supported path. This stub
is kept for the record only; it was never run here and is not LEVI's
future. The native scaling roadmap lives in docs/BRAIN_TRAINING.md §4:
bigger native transformers trained from scratch on LEVI's own corpus.
"""

raise SystemExit(
    "finetune_lora.py is superseded (2026-09-15): LEVI builds its own "
    "native brain instead of fine-tuning third-party weights. See "
    "docs/BRAIN_TRAINING.md §4."
)
