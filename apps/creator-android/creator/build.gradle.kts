// LEVI Platform — Chauncey's entire project in one mega APK, on-device
// via Chaquopy. One stable application ID; updates install over it in place.
// AI track is the default surface; the SI track stays gate-locked behind the
// Plaiground adult gate (default OFF).
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
    namespace = "dev.creator.app"
    compileSdk = 36

    defaultConfig {
        applicationId = "dev.creator.app"
        minSdk = 24
        targetSdk = 36
        versionCode = 2
        versionName = "0.2.0-mega"
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
            // No minification on the M1 creator app: Chaquopy + reflection stay intact.
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
tasks.register<Exec>("syncCreatorPython") {
    workingDir = rootProject.projectDir
    commandLine("bash", "sync-python.sh")
}
tasks.named("preBuild") {
    dependsOn("syncCreatorPython")
}

dependencies {
}
