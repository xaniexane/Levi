#!/usr/bin/env bash
# build-android.sh — compile llama.cpp + LEVI's JNI bridge for Android ABIs.
#
# Usage: ./build-android.sh [--abi arm64-v8a] [--clean]
#
# Requirements:
#   - ANDROID_NDK_HOME pointing at a usable NDK (r26+), or ANDROID_HOME/ndk/<ver>
#   - cmake >= 3.22, ninja, git, curl (network egress to github.com)
#
# Output: .so files in ../src/main/jniLibs/<abi>/ (gitignored; CI rebuilds them).
#
# This is deliberately NOT wired through AGP externalNativeBuild: the library
# module must configure and assemble even on machines without an NDK, degrading
# honestly at runtime (LlamaBridge.nativeAvailable == false).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
MODULE_DIR="$(dirname "$SCRIPT_DIR")"
CPP_DIR="$MODULE_DIR/src/main/cpp"
JNILIBS_DIR="$MODULE_DIR/src/main/jniLibs"
BUILD_ROOT="$SCRIPT_DIR/build"

# Pinned for reproducibility (ggml-org/llama.cpp @ 2026-09-15 HEAD).
LLAMA_CPP_REF="${LLAMA_CPP_REF:-38a5b42d9a3e82e0a586bcd1caed121f36c87a73}"
LLAMA_CPP_URL="${LLAMA_CPP_URL:-https://github.com/ggml-org/llama.cpp.git}"

ABIS=("arm64-v8a" "armeabi-v7a" "x86_64")
MIN_PLATFORM=26
CLEAN=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        --abi) ABIS=("$2"); shift 2 ;;
        --clean) CLEAN=1; shift ;;
        *) echo "unknown arg: $1" >&2; exit 1 ;;
    esac
done

# --- Resolve NDK -----------------------------------------------------------
if [[ -z "${ANDROID_NDK_HOME:-}" ]]; then
    if [[ -n "${ANDROID_HOME:-}" && -d "$ANDROID_HOME/ndk" ]]; then
        ANDROID_NDK_HOME="$(ls -d "$ANDROID_HOME"/ndk/* 2>/dev/null | sort -V | tail -1)"
    elif [[ -n "${ANDROID_SDK_ROOT:-}" && -d "$ANDROID_SDK_ROOT/ndk" ]]; then
        ANDROID_NDK_HOME="$(ls -d "$ANDROID_SDK_ROOT"/ndk/* 2>/dev/null | sort -V | tail -1)"
    fi
fi
if [[ -z "${ANDROID_NDK_HOME:-}" || ! -d "$ANDROID_NDK_HOME" ]]; then
    echo "ERROR: ANDROID_NDK_HOME is not set and no NDK found under ANDROID_HOME." >&2
    echo "Install one, e.g.: sdkmanager --sdk_root=\$ANDROID_HOME \"ndk;27.2.12479018\"" >&2
    exit 1
fi
TOOLCHAIN="$ANDROID_NDK_HOME/build/cmake/android.toolchain.cmake"
if [[ ! -f "$TOOLCHAIN" ]]; then
    echo "ERROR: toolchain file missing: $TOOLCHAIN" >&2
    exit 1
fi
echo "NDK: $ANDROID_NDK_HOME"

if [[ "$CLEAN" == "1" ]]; then
    rm -rf "$BUILD_ROOT" "$JNILIBS_DIR"
fi

command -v cmake >/dev/null || { echo "ERROR: cmake not found" >&2; exit 1; }
command -v ninja >/dev/null || { echo "ERROR: ninja not found" >&2; exit 1; }
command -v git >/dev/null || { echo "ERROR: git not found" >&2; exit 1; }

# --- Fetch llama.cpp (shallow, pinned commit) --------------------------------
LLAMA_SRC="$CPP_DIR/llama.cpp"
if [[ ! -d "$LLAMA_SRC/.git" ]]; then
    echo "Fetching llama.cpp @ $LLAMA_CPP_REF ..."
    rm -rf "$LLAMA_SRC"
    # Depth-1 clone then fetch the pinned commit explicitly (shallow clones
    # do not contain arbitrary SHAs).
    git init -q "$LLAMA_SRC"
    git -C "$LLAMA_SRC" remote add origin "$LLAMA_CPP_URL"
    git -C "$LLAMA_SRC" fetch --depth 1 origin "$LLAMA_CPP_REF"
    git -C "$LLAMA_SRC" checkout -q FETCH_HEAD
else
    echo "llama.cpp already present at $LLAMA_SRC"
fi
echo "$LLAMA_CPP_REF" > "$BUILD_ROOT-llama-ref.txt" 2>/dev/null || true

# --- Build per ABI ----------------------------------------------------------
NPROC="$(nproc 2>/dev/null || echo 4)"
for ABI in "${ABIS[@]}"; do
    echo "=== Building $ABI ==="
    BDIR="$BUILD_ROOT/$ABI"
    mkdir -p "$BDIR"
    # Upstream llama.cpp's llamafile sgemm uses fp16 NEON intrinsics that don't
    # exist on 32-bit ARM (FIXME in their source); disable it for that ABI.
    EXTRA_CMAKE_FLAGS=()
    if [ "$ABI" = "armeabi-v7a" ]; then
        EXTRA_CMAKE_FLAGS+=(-DGGML_LLAMAFILE=OFF)
    fi
    cmake -S "$CPP_DIR" -B "$BDIR" -G Ninja \
        -DCMAKE_TOOLCHAIN_FILE="$TOOLCHAIN" \
        -DANDROID_ABI="$ABI" \
        -DANDROID_PLATFORM="android-$MIN_PLATFORM" \
        -DCMAKE_BUILD_TYPE=Release \
        -DLLAMA_CPP_REF="$LLAMA_CPP_REF" \
        "${EXTRA_CMAKE_FLAGS[@]}"
    cmake --build "$BDIR" -- -j"$NPROC"

    OUT="$JNILIBS_DIR/$ABI"
    mkdir -p "$OUT"
    SO="$(find "$BDIR" -name "liblevi_llama.so" | head -1)"
    if [[ -z "$SO" ]]; then
        echo "ERROR: liblevi_llama.so not produced for $ABI" >&2
        exit 1
    fi
    cp "$SO" "$OUT/liblevi_llama.so"
    echo " -> $OUT/liblevi_llama.so ($(du -h "$OUT/liblevi_llama.so" | cut -f1))"
done

echo "Done. Native libs staged in $JNILIBS_DIR"
