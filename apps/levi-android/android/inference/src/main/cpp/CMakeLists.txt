# LEVI on-device inference — native superbuild.
#
# Built by native/build-android.sh (NOT by AGP): it fetches llama.cpp at a
# pinned commit, builds libllama statically, and links it into liblevi_llama.so
# together with llama_jni.cpp. One .so per ABI, no other native deps.
#
# Invoked with an Android NDK toolchain file:
#   cmake -DCMAKE_TOOLCHAIN_FILE=$NDK/build/cmake/android.toolchain.cmake \
#         -DANDROID_ABI=arm64-v8a -DANDROID_PLATFORM=android-26 \
#         -DCMAKE_BUILD_TYPE=Release <this dir>

cmake_minimum_required(VERSION 3.22)
project(levi_llama_jni C CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# --- llama.cpp (MIT) as a compiled dependency; pinned for reproducibility. ---
set(LLAMA_CPP_REF "38a5b42d9a3e82e0a586bcd1caed121f36c87a73"
    CACHE STRING "llama.cpp commit to fetch")

include(FetchContent)
set(LLAMA_BUILD_TESTS OFF CACHE BOOL "" FORCE)
set(LLAMA_BUILD_EXAMPLES OFF CACHE BOOL "" FORCE)
set(LLAMA_BUILD_SERVER OFF CACHE BOOL "" FORCE)
set(LLAMA_BUILD_COMMON OFF CACHE BOOL "" FORCE)
set(LLAMA_CURL OFF CACHE BOOL "" FORCE)
set(BUILD_SHARED_LIBS OFF CACHE BOOL "" FORCE)   # static libllama -> one .so
set(GGML_NATIVE OFF CACHE BOOL "" FORCE)        # never use host CPU flags
set(GGML_CPU_ALL_VARIANTS OFF CACHE BOOL "" FORCE)

FetchContent_Declare(
    llamacpp
    GIT_REPOSITORY https://github.com/ggml-org/llama.cpp.git
    GIT_TAG ${LLAMA_CPP_REF}
    GIT_SHALLOW TRUE
)
FetchContent_MakeAvailable(llamacpp)

# --- LEVI's own JNI bridge (original code, see llama_jni.cpp). ---
add_library(levi_llama SHARED llama_jni.cpp)

target_link_libraries(levi_llama PRIVATE llama)
target_include_directories(levi_llama PRIVATE
    ${llamacpp_SOURCE_DIR}/include
)

find_library(LOG_LIB log)
if (LOG_LIB)
    target_link_libraries(levi_llama PRIVATE ${LOG_LIB})
endif ()

# Keep the .so lean.
if (CMAKE_CXX_COMPILER_ID MATCHES "Clang|GNU")
    target_compile_options(levi_llama PRIVATE -O3 -fvisibility=hidden)
endif ()
