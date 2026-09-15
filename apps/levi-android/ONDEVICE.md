# LEVI on-device inference — integration contract

How the LEVI Android app runs models on-device, PocketPal-style: the weights
live on the phone, inference happens locally through llama.cpp, no server
round-trip. This document is the contract between the `:inference` module
(`apps/levi-android/android/inference/`) and the app shell. The app module does
**not** depend on `:inference` yet; this doc describes the intended wiring.

All native/Kotlin code here is original to LEVI. llama.cpp (MIT) is used
purely as a compiled library dependency. No third-party app code was
referenced or copied.

## The LEVI family (product framing)

The on-device weights are the **LEVI family** — LEVI is always the headliner
and the default selected model:

| id | UI name | What it is | Base (labeled honestly) | Size | RAM |
|----|---------|-----------|------------------------|------|-----|
| `levi-tiny` | Levi Tiny | LEVI's own native brain — on-device build in progress | LEVI native | — | ~512 MB |
| `levi-0.6b` | Levi 0.6B | **Default.** Levi remix, LEVI-packaged | Qwen3-0.6B | ~640 MB | ~1.5 GB |
| `levi-4b` | Levi 4B | Levi remix, LEVI-packaged | Qwen3-4B | ~2.5 GB | ~4 GB |

`levi-tiny` is announced but not downloadable yet — `ModelManager.download()`
refuses it with a clear error instead of failing obscurely. When LEVI's native
brain (today a PyTorch proof-of-pipeline in `core/levi/brain/`) gets an
on-device export path, it slots into this family as the true first-party
weight.

Other providers (Ollama, OpenAI-compatible endpoints) appear in the model
picker as **selectable sources** — alternatives, never the headliner, never
the default. See `ModelCatalog.externalSources`.

## Module layout

```
inference/
  build.gradle.kts                  com.android.library, namespace dev.levi.inference
  native/build-android.sh           standalone CMake superbuild (NOT AGP externalNativeBuild)
  src/main/cpp/
    llama_jni.cpp                   original JNI bridge (load/unload/generate/stream/benchmark)
    CMakeLists.txt                  fetches llama.cpp at a pinned commit, builds liblevi_llama.so
    llama.cpp/                      fetched at build time, gitignored, never committed
  src/main/jniLibs/<abi>/           built .so files, gitignored, rebuilt by CI
  src/main/java/dev/levi/inference/
    LlamaBridge.kt                  JNI declarations + nativeAvailable guard
    InferenceEngine.kt              single-threaded high-level API (Result-based)
    ModelManager.kt                 HF download with resume + SHA-256, LEVI-family catalog
    PromptBuilder.kt                persona -> Qwen3 chat template
    InferenceModels.kt              ModelInfo/ModelCatalog/LeviPersona/params
  src/test/java/...                 JVM unit tests (no emulator needed)
```

## Integration flow (app side, to be wired)

```
1. Picker (default selection = Levi 0.6B)
     ModelCatalog.defaultModel()                       // always LEVI
     ModelCatalog.recommendedFor(totalRamMb)           // largest fitting LEVI model
     ModelCatalog.externalSources                      // "More sources…" section

2. Download (first run, Wi-Fi recommended)
     ModelManager(modelsDir).download(info, listener)
     // -> resume via Range, atomic publish, SHA-256 when advertised

3. Load
     engine.loadAsync(modelFile.absolutePath, GenerationParams(contextSize=2048))
     // first load: seconds (mmap + warmup); keep engine process-scoped

4. Chat (streaming)
     val prompt = PromptBuilder.build(persona, history, userMessage)
     engine.generateStreamAsync(prompt, params) { piece ->
         runOnUiThread { appendToken(piece) }; true
     }
     // cancel() stops at the next token boundary

5. Benchmark (optional, settings screen)
     engine.benchmark().tokensPerSecond
```

`LlamaBridge.nativeAvailable == false` (module built without
`native/build-android.sh`) must surface in the UI as "on-device engine not
included in this build" — never as a crash. Every `InferenceEngine` call
returns `EngineResult.Unavailable` in that state.

## LEVI concept mapping

| LEVI concept | On-device analogue | Status |
|---|---|---|
| Persona registers (Warm/Bold/Calm UI) | `LeviPersona` enum → system prompt in `PromptBuilder` | Done |
| Pals-style selectable personas | Model picker + persona picker in app settings | App UI to be built |
| Agent tool loop (`run_subtask`) | On-device tool calling (grammar-constrained JSON) | **Later stage** — needs constrained decoding + a tool schema bridge; not in this module |
| Cloud provider / MCP server | Phone as edge node: same MCP surface, local transport | Future |
| Growth loop / memory | On-device memory store (app-private, encrypted) | Future |

On-device tool calling is deliberately deferred: the current bridge does
free-form generation only. Constrained tool calling needs grammar sampling
(GBNF) wired through the sampler chain plus a strict JSON validator — a
separate, testable increment.

## Benchmark expectations (honest)

No emulator or device numbers have been measured yet — the native build is
wired to CI and the first real numbers will come from a physical device.
Expectations, not promises:

- **Levi 0.6B (Q8_0), modern mid-range phone (8 GB RAM):** prompt processing
  fast (GGUF Q8 prompt eval is cheap at 0.6B); generation roughly **15–40
  tok/s** on CPU depending on SoC and thread count. Usable for chat.
- **Levi 4B (Q4_K_M):** roughly **8–20 tok/s**; needs a 6–8 GB device and
  patience on first load.
- **First load:** seconds — model mmap plus KV allocation for the context
  size. `contextSize = 2048` keeps KV cache small (~tens of MB at 0.6B).
- **No NPU/GPU path yet:** `n_gpu_layers = 0`; pure CPU via llama.cpp's
  optimized kernels (ARM NEON dotprod/i8mm where the SoC supports them).

Measure with `engine.benchmark()` on-device and record real numbers here
before quoting them anywhere user-facing.

## Honest limits

1. **RAM is the ceiling.** Android will kill the app if the model + KV cache
   exceed available memory. `minRamMb` in the catalog is guidance, not a
   guarantee — OEM skins vary wildly.
2. **No NPU/GPU delegate.** CPU-only for now; NNAPI/GPU delegates are a
   future increment (and GGUF GPU offload on Android is still rough
   upstream).
3. **No tool calling yet.** Free-form chat only; see mapping table.
4. **levi-tiny is future.** The native brain exists as a training
   proof-of-pipeline (`core/levi/brain/`); its on-device export (execuTorch /
   LiteRT / custom) is a separate research track.
5. **Model provenance.** Remix bases are honest Qwen3 GGUFs from the
   publisher's official Hugging Face repos; SHA-256 is verified when the
   publisher advertises a digest, skipped openly otherwise.
6. **Battery/thermal.** Sustained generation throttles on most phones;
   streaming keeps UX acceptable but long generations will warm the device.
7. **What needs an emulator/device:** the JNI bridge, `.so` loading,
   actual generation, and benchmarks. Everything else (prompt building,
   download/resume/hash logic, catalog framing) is covered by JVM unit tests.

## Building

```bash
# Needs ANDROID_NDK_HOME (r26+). Fetches pinned llama.cpp, builds all ABIs:
./gradlew :inference:buildNativeLibs --no-daemon

# Single ABI (faster iteration):
cd inference && ./native/build-android.sh --abi arm64-v8a

# JVM unit tests (no NDK, no emulator):
./gradlew :inference:testDebugUnitTest --no-daemon
```
