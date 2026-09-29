// NeighborOS — gig dispatch (Uber-for-gigs), on-device via Chaquopy.
// Bloodline distribution law (Chauncey, 2026-09-27): the founder build
// runs the ORIGINAL source at FULL capability; bloodline builds are
// derived and LIMITED (+metered). Flavors carry the NOS_FLAVOR flag
// into the Python bridge.
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
    namespace = "dev.neighboros.app"
    compileSdk = 36

    defaultConfig {
        applicationId = "dev.neighboros.app"
        minSdk = 24
        targetSdk = 36
        versionCode = 2
        versionName = "0.1.0"
        ndk {
            abiFilters += listOf("arm64-v8a")
        }
    }

    // Bloodline law: founder = original source, full capability;
    // bloodline = derived, limited + metered.
    flavorDimensions += "lineage"
    productFlavors {
        create("founder") {
            dimension = "lineage"
            buildConfigField("String", "NOS_FLAVOR", "\"founder\"")
        }
        create("bloodline") {
            dimension = "lineage"
            applicationIdSuffix = ".bloodline"
            buildConfigField("String", "NOS_FLAVOR", "\"bloodline\"")
        }
    }

    buildFeatures {
        buildConfig = true
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
tasks.register<Exec>("syncNeighborosPython") {
    workingDir = rootProject.projectDir
    commandLine("bash", "sync-python.sh")
}
tasks.named("preBuild") {
    dependsOn("syncNeighborosPython")
}

dependencies {
}
