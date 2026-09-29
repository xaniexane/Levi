// BuzzTunes — Chauncey's music player, on-device via Chaquopy.
// Bloome listening threads + native media surface in one product.
// YouTube playback seam (never fakes audio); dark-first void theme.
plugins {
    id("com.android.application")
    id("com.chaquo.python")
}

// Release key lives OUTSIDE the repo (~/.keystores). Never committed.
// NOTE: parsed with kotlin-stdlib only — a qualified `java.*` reference does
// not resolve in this project's Kotlin DSL scripts (sandbox quirk, 2026-09-22).
val releaseKeyProps: Map<String, String> = buildMap {
    val keyFile = file("/home/hatch/.keystores/release.properties")
    if (keyFile.exists()) {
        keyFile.forEachLine { line ->
            val t = line.trim()
            if (t.isNotEmpty() && !t.startsWith("#")) {
                val i = t.indexOf('=')
                if (i > 0) put(t.substring(0, i).trim(), t.substring(i + 1).trim())
            }
        }
    }
}
val hasReleaseKey = releaseKeyProps.isNotEmpty()

android {
    namespace = "dev.buzztunes.app"
    compileSdk = 36

    defaultConfig {
        applicationId = "dev.buzztunes.app"
        minSdk = 24
        targetSdk = 36
        versionCode = 2
        versionName = "0.2.0"
        ndk {
            abiFilters += listOf("arm64-v8a")
        }
    }

    signingConfigs {
        create("release") {
            if (hasReleaseKey) {
                storeFile = file(releaseKeyProps.getValue("storeFile"))
                storePassword = releaseKeyProps.getValue("storePassword")
                keyAlias = releaseKeyProps.getValue("keyAlias")
                keyPassword = releaseKeyProps.getValue("keyPassword")
            }
        }
    }

    buildTypes {
        debug {
            applicationIdSuffix = ".debug"
            isDebuggable = true
        }
        release {
            // No minification: Chaquopy + reflection stay intact.
            isMinifyEnabled = false
            signingConfig = signingConfigs.getByName("release")
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
        // NewPipeExtractor needs core-library desugaring below API 33.
        isCoreLibraryDesugaringEnabled = true
    }
}

// Chaquopy: Kotlin DSL must use the top-level chaquopy block (not the
// Groovy-only `python {}` inside android.defaultConfig).
chaquopy {
    defaultConfig {
        version = "3.12"
        buildPython("/usr/bin/python3")
    }
}

// The repo is the single source of truth for the Python engine — sync it
// into the Chaquopy python dir before every build.
tasks.register<Exec>("syncBuzzTunesPython") {
    workingDir = rootProject.projectDir
    commandLine("bash", "sync-python.sh")
}
tasks.named("preBuild") {
    dependsOn("syncBuzzTunesPython")
}

dependencies {
    // YouTube-to-ringtone (2026-09-29, flagship): audio stream extraction
    // for user-pasted YouTube links. JitPack repo declared in
    // settings.gradle.kts with a TeamNewPipe-only content filter.
    // NOTE: extraction/download run only after the user taps "Get audio"
    // (Law L3); nothing here phones home on its own.
    implementation("com.github.teamnewpipe:NewPipeExtractor:0.24.8")
    // Required by NewPipeExtractor on minSdk < 33.
    coreLibraryDesugaring("com.android.tools:desugar_jdk_libs:2.1.4")
}
