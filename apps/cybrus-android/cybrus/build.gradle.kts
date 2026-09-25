// Cybrus — local-only WebView shell over the self-contained UI preview.
// Zero library dependencies by design: the asset needs nothing but WebView.
plugins {
    id("com.android.application")
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
    namespace = "dev.cybrus.app"
    compileSdk = 36

    defaultConfig {
        applicationId = "dev.cybrus.app"
        minSdk = 24
        targetSdk = 36
        versionCode = 1
        versionName = "0.1.0-preview"
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
            // Signed release (proper key, not the debug key). Still a UI-preview
            // shell until the platform-sync / Veil work lands and gets wired in.
            isMinifyEnabled = false
            signingConfig = signingConfigs.getByName("release")
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
}
