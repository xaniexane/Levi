"""STUB — LoRA fine-tune of the levi-local Qwen weights on the course corpus.

STATUS: NOT RUN HERE. This is a documented starting point, not a working
pipeline. Fine-tuning a 0.6B-4B model needs a GPU with 8GB+ VRAM (or
Apple Silicon with MLX); this VM is CPU-only, so this script has never
executed. Do not present it as done.

Honest path to a genuinely smarter LEVI brain:
  1. On a GPU machine: pip install torch transformers peft datasets
  2. Convert core/levi/brain/train/corpus.jsonl into instruction pairs
     (the raw chunks are continuations, not instructions — wrap them:
     {"instruction": "Explain this topic:", "input": <chunk>, ...}
     or better, generate Q/A pairs from chunks with a teacher model).
  3. LoRA (r=16, alpha=32, target q_proj/v_proj) on Qwen3-0.6B for 1-3 epochs.
  4. Merge LoRA into the base model, quantize to Q4_K_M GGUF with llama.cpp,
     drop into ~/.levi/models — levi-local picks it up automatically.

Skeleton (fill in on real hardware):

    from peft import LoraConfig, get_peft_model
    from transformers import AutoModelForCausalLM, AutoTokenizer, TrainingArguments

    MODEL = "Qwen/Qwen3-0.6B"
    tok = AutoTokenizer.from_pretrained(MODEL)
    base = AutoModelForCausalLM.from_pretrained(MODEL)
    peft_cfg = LoraConfig(r=16, lora_alpha=32,
                          target_modules=["q_proj", "v_proj"],
                          lora_dropout=0.05, task_type="CAUSAL_LM")
    model = get_peft_model(base, peft_cfg)
    # ... load corpus.jsonl as a datasets.Dataset, tokenize, Trainer ...

After merging + GGUF conversion, the result is a drop-in replacement for the
weights that `levi agent model pull` installs — same provider, smarter brain.
"""
raise SystemExit(
    "finetune_lora.py is a documented stub, not a runnable pipeline. "
    "It needs a GPU machine; see the module docstring."
)
