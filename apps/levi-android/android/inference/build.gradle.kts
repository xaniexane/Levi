// LEVI on-device inference module.
//
// Standalone library module: Kotlin API + JNI bridge over llama.cpp.
// The app module does NOT depend on this yet (integration contract lives in
// apps/levi-android/ONDEVICE.md), so this module can never break :app's build.
//
// Native code is NOT built by AGP externalNativeBuild. Instead the standalone
// CMake superbuild in native/build-android.sh compiles llama.cpp + the JNI
// bridge per Android ABI and drops the .so files into src/main/jniLibs/<abi>/,
// which the AAR packages automatically. Without those .so files the Kotlin API
// still compiles and every call degrades honestly (isLoaded() == false).

plugins {
    // Version declared inline (not via the version catalog) so this module
    // touches no existing build files. MUST match the catalog's agp version.
    id("com.android.library") version "9.4.0"
    // NOTE (AGP 9+): org.jetbrains.kotlin.android must NOT be applied.
}

android {
    namespace = "dev.levi.inference"
    compileSdk = 36

    defaultConfig {
        minSdk = 26
        consumerProguardFiles("consumer-rules.pro")
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    // AGP 9's built-in Kotlin DSL (no kotlin-android plugin).
    kotlin {
        compilerOptions {
            jvmTarget.set(org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17)
        }
    }
}

dependencies {
    // Declared inline (not in the version catalog) so this module stays
    // self-contained and touches no existing build files.
    testImplementation("junit:junit:4.13.2")
}

// Builds llama.cpp + the JNI bridge for Android ABIs. Requires
// ANDROID_NDK_HOME to point at a usable NDK (r26+).
tasks.register<Exec>("buildNativeLibs") {
    group = "build"
    description = "Build llama.cpp JNI bridge for Android ABIs (needs ANDROID_NDK_HOME)."
    workingDir = file("native")
    commandLine("bash", "build-android.sh")
}
