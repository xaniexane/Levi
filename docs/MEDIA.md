# LEVI Media — image generation

LEVI generates images through three backends, one dispatcher. The rule is
**local-first**: the zero-dependency core is always available, and the
network/hardware paths are opt-in.

## Backends

| Backend | Quality | Deps | Default? |
|---|---|---|---|
| `local` | Procedural generative art (gradients, glow, shapes, grain) — deterministic, **not** photoreal | None (stdlib) | **Yes** (`auto` → `local`) |
| `pollinations` | Photoreal via the free keyless Pollinations image API | Network | No (opt-in) |
| `sd` | Photoreal via local Stable Diffusion | `diffusers` + `torch` + weights + CUDA GPU | No (opt-in, fails closed) |

**Pollinations is a labeled external reference, never LEVI's identity.**
LEVI does not claim its models or outputs as its own; the client only
builds URLs and downloads bytes.

## Quality tier (Pollinations)

The free tier is squeezed with verified API parameters
(docs: `enter.pollinations.ai/AGENTS.md`):

- `model`: `flux` (documented default), `gptimage`, `turbo`, `kontext`, `seedream`
- `enhance=true`: Pollinations AI-enhances the prompt (default on)
- `quality=high`: `low|medium|high|hd` (default high)
- `nologo=true`: removes the Pollinations watermark (default on)
- `negative_prompt`: defaults to `worst quality, blurry, watermark, text, logo, deformed`
- `seed`: deterministic; derived from the prompt when omitted
- `safe` / `private`: opt-in flags, off by default

### Style presets (`--style`)

Append proven quality boosters to the prompt:

- `photo` — professional photograph, 85mm, sharp focus, natural light, 8k
- `anime` — anime key visual, cel shading, clean linework, studio quality
- `painting` — oil painting, rich brushwork, chiaroscuro
- `product` — commercial product shot, studio lighting, clean background
- `cinematic` — cinematic still, film grain, no text overlay

## Local Stable Diffusion scaffold (`--backend sd`)

Auto-detects `diffusers` + `torch` at runtime. When absent, fails closed
with a clear message naming what to install. Honest requirements: a CUDA
GPU and several GB of weights. **Not viable on CPU-only machines or
phones** — this backend is the quality ceiling for users with hardware,
not the default path. CPU renders are allowed but labeled slow.

Install: `pip install diffusers torch Pillow`, then
`levi image --backend sd --prompt "..." [--sd-model <hf-id>]`.

## CLI

```bash
levi image --prompt "a lighthouse at dusk"                 # local procedural (default)
levi image --prompt "a lighthouse at dusk" --backend pollinations --style photo
levi image --prompt "a lighthouse at dusk" --backend pollinations --model gptimage --seed 42
levi image --prompt "a lighthouse at dusk" --backend sd    # needs GPU + deps
levi image --prompt "a lighthouse at dusk" --url-only      # print the Pollinations URL only
levi image --story <id> --beat midpoint                    # L.W.P. story still (Pollinations)
```

Saves to `~/.levi/media/local/`, `~/.levi/media/`, or `~/.levi/media/sd/`.

## Agent tool

`image_generate` is registered in the agent tool registry
(`core/levi/agent/tools.py`): `prompt` (required), `backend`,
`style`, `width`, `height`, `seed`, `model`. The agent loop can call it
like any other tool; no confirmation gate (writes land in `~/.levi/media`
only — non-consequential).

## Tests

`tests/test_media_image.py` — local backend determinism (same prompt+seed
→ byte-identical PNG; different prompts differ), PNG validity, dimension
validation, Pollinations URL construction (enhance/quality/nologo/style —
no network), SD fail-closed path. Pollinations downloads are **never**
hit in tests.
