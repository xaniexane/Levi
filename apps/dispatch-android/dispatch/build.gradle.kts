// Dispatch — the LEVI truck-dispatch board, on-device via Chaquopy.
// Dispatcher decides, verifier twin countersigns, every move receipted.
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
    namespace = "dev.dispatch.app"
    compileSdk = 36

    defaultConfig {
        applicationId = "dev.dispatch.app"
        minSdk = 24
        targetSdk = 36
        versionCode = 1
        versionName = "0.1.0"
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
            // No minification on v1: Chaquopy + reflection stay intact.
            isMinifyEnabled = false
            signingConfig = signingConfigs.getByName("release")
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
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

// The repo is the single source of truth for the Python engines — sync them
// into the Chaquopy python dir before every build.
tasks.register<Exec>("syncDispatchPython") {
    workingDir = rootProject.projectDir
    commandLine("bash", "sync-python.sh")
}
tasks.named("preBuild") {
    dependsOn("syncDispatchPython")
}

dependencies {
}
