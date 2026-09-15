// llama_jni.cpp — LEVI on-device inference JNI bridge.
//
// ORIGINAL implementation written for LEVI. It drives llama.cpp (MIT) purely
// as a compiled library dependency through its public C API (llama.h).
// No third-party app code was referenced or copied.
//
// JNI surface (mirrors dev.levi.inference.LlamaBridge):
//   nativeLoad(modelPath, nCtx, nThreads) -> boolean
//   nativeUnload()
//   nativeIsLoaded() -> boolean
//   nativeGenerate(prompt, maxTokens, temperature, seed) -> String | null
//   nativeGenerateStream(prompt, maxTokens, temperature, seed, callback) -> boolean
//   nativeBenchmark(prompt, nTokens) -> float (tokens/sec, generation only)
//   nativeContextSize() -> int
//
// Threading: all entry points serialize on one mutex; Kotlin additionally
// funnels calls through a single-thread executor. The streaming callback is
// invoked on the calling thread; returning false cancels generation.

#include <jni.h>

#include <atomic>
#include <chrono>
#include <cstring>
#include <mutex>
#include <string>
#include <vector>

#include "llama.h"

namespace {

struct EngineState {
    llama_model* model = nullptr;
    const llama_vocab* vocab = nullptr;  // owned by the model; valid while model lives
    llama_context* ctx = nullptr;
    int n_ctx = 0;
    std::mutex mutex;
};

EngineState& engine_state() {
    static EngineState s;
    return s;
}

void backend_init_once() {
    static std::once_flag flag;
    std::call_once(flag, [] { llama_backend_init(); });
}

std::string jstring_to_utf8(JNIEnv* env, jstring jstr) {
    if (!jstr) return {};
    const char* chars = env->GetStringUTFChars(jstr, nullptr);
    std::string out(chars ? chars : "");
    if (chars) env->ReleaseStringUTFChars(jstr, chars);
    return out;
}

jstring utf8_to_jstring(JNIEnv* env, const std::string& s) {
    // NewStringUTF expects modified UTF-8; llama.cpp emits plain UTF-8 which
    // is compatible except for embedded NULs (impossible in token pieces).
    return env->NewStringUTF(s.c_str());
}

void unload_locked(EngineState& st) {
    if (st.ctx) {
        llama_free(st.ctx);
        st.ctx = nullptr;
    }
    if (st.model) {
        llama_model_free(st.model);
        st.model = nullptr;
        st.vocab = nullptr;
    }
    st.n_ctx = 0;
}

// Decode `n` tokens starting at KV position `n_past`; logits on the last one.
bool eval_tokens(llama_context* ctx, const llama_token* tokens, int n, int n_past) {
    llama_batch batch = llama_batch_init(n, 0, 1);
    for (int i = 0; i < n; i++) {
        batch.token[i] = tokens[i];
        batch.pos[i] = n_past + i;
        batch.n_seq_id[i] = 1;
        batch.seq_id[i][0] = 0;
        batch.logits[i] = (i == n - 1) ? 1 : 0;
    }
    const bool ok = llama_decode(ctx, batch) == 0;
    llama_batch_free(batch);
    return ok;
}

std::string token_piece(const llama_vocab* vocab, llama_token tok) {
    char buf[256];
    int n = llama_token_to_piece(vocab, tok, buf, sizeof(buf), 0, true);
    if (n < 0) {
        std::vector<char> big(static_cast<size_t>(-n));
        n = llama_token_to_piece(vocab, tok, big.data(), static_cast<int32_t>(big.size()), 0, true);
        if (n <= 0) return {};
        return std::string(big.data(), static_cast<size_t>(n));
    }
    if (n == 0) return {};
    return std::string(buf, static_cast<size_t>(n));
}

struct Sampler {
    llama_sampler* s = nullptr;
    explicit Sampler(float temperature, int32_t seed) {
        llama_sampler_chain_params scp = llama_sampler_chain_default_params();
        s = llama_sampler_chain_init(scp);
        if (temperature <= 0.0f) {
            llama_sampler_chain_add(s, llama_sampler_init_greedy());
        } else {
            llama_sampler_chain_add(s, llama_sampler_init_temp(temperature));
            const uint32_t useed =
                seed < 0 ? LLAMA_DEFAULT_SEED : static_cast<uint32_t>(seed);
            llama_sampler_chain_add(s, llama_sampler_init_dist(useed));
        }
    }
    ~Sampler() {
        if (s) llama_sampler_free(s);
    }
    Sampler(const Sampler&) = delete;
    Sampler& operator=(const Sampler&) = delete;
};

// Core generation loop. Returns the generated text; empty string is a valid
// (if boring) result, so callers use the boolean for success/failure.
bool generate_locked(JNIEnv* env, EngineState& st, const std::string& prompt,
                     int max_tokens, float temperature, int32_t seed,
                     jobject token_callback, std::string& out_text) {
    if (!st.ctx || !st.model || max_tokens <= 0) return false;

    // Tokenize the prompt; keep a slice that fits with room for output.
    std::vector<llama_token> toks(static_cast<size_t>(st.n_ctx));
    int n_prompt = llama_tokenize(st.vocab, prompt.c_str(),
                                  static_cast<int32_t>(prompt.size()), toks.data(),
                                  static_cast<int32_t>(toks.size()), true, true);
    if (n_prompt <= 0) return false;

    int prompt_budget = st.n_ctx - max_tokens - 8;
    if (prompt_budget < 1) prompt_budget = 1;
    std::vector<llama_token> prompt_toks;
    if (n_prompt > prompt_budget) {
        // Truncate from the LEFT (keep the tail: latest user message matters).
        prompt_toks.assign(toks.begin() + (n_prompt - prompt_budget), toks.begin() + n_prompt);
    } else {
        prompt_toks.assign(toks.begin(), toks.begin() + n_prompt);
    }

    llama_memory_clear(llama_get_memory(st.ctx), true);

    int n_past = 0;
    if (!eval_tokens(st.ctx, prompt_toks.data(),
                     static_cast<int>(prompt_toks.size()), n_past)) {
        return false;
    }
    n_past += static_cast<int>(prompt_toks.size());

    Sampler sampler(temperature, seed);

    jmethodID on_token = nullptr;
    if (token_callback) {
        jclass cb_class = env->GetObjectClass(token_callback);
        on_token = env->GetMethodID(cb_class, "onToken", "(Ljava/lang/String;)Z");
        if (!on_token) return false;
    }

    out_text.clear();
    out_text.reserve(1024);
    for (int i = 0; i < max_tokens; i++) {
        const llama_token tok = llama_sampler_sample(sampler.s, st.ctx, -1);
        if (llama_vocab_is_eog(st.vocab, tok)) break;
        llama_sampler_accept(sampler.s, tok);

        const std::string piece = token_piece(st.vocab, tok);
        out_text += piece;

        if (on_token) {
            jstring jpiece = utf8_to_jstring(env, piece);
            const jboolean keep_going =
                env->CallBooleanMethod(token_callback, on_token, jpiece);
            env->DeleteLocalRef(jpiece);
            if (env->ExceptionCheck() || keep_going == JNI_FALSE) {
                env->ExceptionClear();
                break;  // cancelled by the app (or callback threw)
            }
        }

        if (!eval_tokens(st.ctx, &tok, 1, n_past)) break;
        n_past += 1;
    }
    return true;
}

}  // namespace

extern "C" {

JNIEXPORT jboolean JNICALL
Java_dev_levi_inference_LlamaBridge_nativeLoad(JNIEnv* env, jobject /*thiz*/,
                                               jstring model_path, jint n_ctx,
                                               jint n_threads) {
    EngineState& st = engine_state();
    std::lock_guard<std::mutex> lock(st.mutex);
    unload_locked(st);
    backend_init_once();

    llama_model_params mp = llama_model_default_params();
    mp.n_gpu_layers = 0;  // CPU-only path; no NPU/GPU delegate yet (see ONDEVICE.md)

    const std::string path = jstring_to_utf8(env, model_path);
    st.model = llama_model_load_from_file(path.c_str(), mp);
    if (!st.model) return JNI_FALSE;

    llama_context_params cp = llama_context_default_params();
    cp.n_ctx = n_ctx > 0 ? n_ctx : 2048;
    const int threads = n_threads > 0 ? n_threads : 4;
    cp.n_threads = threads;
    cp.n_threads_batch = threads;

    st.ctx = llama_init_from_model(st.model, cp);
    if (!st.ctx) {
        unload_locked(st);
        return JNI_FALSE;
    }
    st.vocab = llama_model_get_vocab(st.model);
    st.n_ctx = llama_n_ctx(st.ctx);
    return JNI_TRUE;
}

JNIEXPORT void JNICALL
Java_dev_levi_inference_LlamaBridge_nativeUnload(JNIEnv* /*env*/, jobject /*thiz*/) {
    EngineState& st = engine_state();
    std::lock_guard<std::mutex> lock(st.mutex);
    unload_locked(st);
}

JNIEXPORT jboolean JNICALL
Java_dev_levi_inference_LlamaBridge_nativeIsLoaded(JNIEnv* /*env*/, jobject /*thiz*/) {
    EngineState& st = engine_state();
    std::lock_guard<std::mutex> lock(st.mutex);
    return (st.ctx && st.model) ? JNI_TRUE : JNI_FALSE;
}

JNIEXPORT jstring JNICALL
Java_dev_levi_inference_LlamaBridge_nativeGenerate(JNIEnv* env, jobject /*thiz*/,
                                                   jstring prompt, jint max_tokens,
                                                   jfloat temperature, jint seed) {
    EngineState& st = engine_state();
    std::lock_guard<std::mutex> lock(st.mutex);
    const std::string prompt_s = jstring_to_utf8(env, prompt);
    std::string out;
    if (!generate_locked(env, st, prompt_s, max_tokens, temperature, seed,
                         nullptr, out)) {
        return nullptr;
    }
    return utf8_to_jstring(env, out);
}

JNIEXPORT jboolean JNICALL
Java_dev_levi_inference_LlamaBridge_nativeGenerateStream(
    JNIEnv* env, jobject /*thiz*/, jstring prompt, jint max_tokens,
    jfloat temperature, jint seed, jobject callback) {
    if (!callback) return JNI_FALSE;
    EngineState& st = engine_state();
    std::lock_guard<std::mutex> lock(st.mutex);
    const std::string prompt_s = jstring_to_utf8(env, prompt);
    std::string out;
    return generate_locked(env, st, prompt_s, max_tokens, temperature, seed,
                           callback, out)
               ? JNI_TRUE
               : JNI_FALSE;
}

JNIEXPORT jfloat JNICALL
Java_dev_levi_inference_LlamaBridge_nativeBenchmark(JNIEnv* env, jobject /*thiz*/,
                                                    jstring prompt, jint n_tokens) {
    EngineState& st = engine_state();
    std::lock_guard<std::mutex> lock(st.mutex);
    if (!st.ctx || !st.model || n_tokens <= 0) return -1.0f;

    const std::string prompt_s = jstring_to_utf8(env, prompt);
    std::vector<llama_token> toks(static_cast<size_t>(st.n_ctx));
    int n_prompt = llama_tokenize(st.vocab, prompt_s.c_str(),
                                  static_cast<int32_t>(prompt_s.size()), toks.data(),
                                  static_cast<int32_t>(toks.size()), true, true);
    if (n_prompt <= 0) return -1.0f;
    if (n_prompt > st.n_ctx - n_tokens - 8) {
        n_prompt = st.n_ctx - n_tokens - 8;
        if (n_prompt < 1) return -1.0f;
    }

    llama_memory_clear(llama_get_memory(st.ctx), true);
    if (!eval_tokens(st.ctx, toks.data(), n_prompt, 0)) return -1.0f;

    Sampler sampler(0.0f, 0);  // greedy: deterministic throughput measurement
    const auto t0 = std::chrono::steady_clock::now();
    int produced = 0;
    for (int i = 0; i < n_tokens; i++) {
        const llama_token tok = llama_sampler_sample(sampler.s, st.ctx, -1);
        if (llama_vocab_is_eog(st.vocab, tok)) break;
        llama_sampler_accept(sampler.s, tok);
        if (!eval_tokens(st.ctx, &tok, 1, n_prompt + produced)) break;
        produced++;
    }
    const auto t1 = std::chrono::steady_clock::now();
    const double secs =
        std::chrono::duration<double>(t1 - t0).count();
    if (secs <= 0.0 || produced == 0) return -1.0f;
    return static_cast<jfloat>(produced / secs);
}

JNIEXPORT jint JNICALL
Java_dev_levi_inference_LlamaBridge_nativeContextSize(JNIEnv* /*env*/,
                                                     jobject /*thiz*/) {
    EngineState& st = engine_state();
    std::lock_guard<std::mutex> lock(st.mutex);
    return st.n_ctx;
}

}  // extern "C"
