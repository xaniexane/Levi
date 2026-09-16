plugins {
    alias(libs.plugins.android.application)
    // NOTE (AGP 9+): org.jetbrains.kotlin.android must NOT be applied.
}

android {
    namespace = "dev.levi.app"
    compileSdk = 36

    defaultConfig {
        applicationId = "dev.levi.app"
        minSdk = 26
        targetSdk = 36
        versionCode = 1
        versionName = "1.0.0"
        vectorDrawables {
            useSupportLibrary = true
        }
    }

    // Release keystore resolution (mirrors vyve-messenger):
    //   1. LEVI_KEYSTORE_PATH / LEVI_KEYSTORE_PASSWORD / LEVI_KEY_ALIAS /
    //      LEVI_KEY_PASSWORD env vars (CI)
    //   2. levi.keystore.path / levi.keystore.password / levi.key.alias /
    //      levi.key.password Gradle properties (local dev)
    // With no keystore configured the release build falls back to the debug
    // key LOUDLY — never upload a debug-signed artifact anywhere public.
    // NOTE: this must run before buildTypes so the release build type can
    // find the "leviRelease" signing config at configuration time.
    val keystorePath: String? =
        System.getenv("LEVI_KEYSTORE_PATH")
            ?: (project.findProperty("levi.keystore.path") as String?)?.ifBlank { null }
    val keystoreFile = keystorePath?.let { file(it) }?.takeIf { it.exists() }
    if (keystoreFile != null) {
        signingConfigs {
            create("leviRelease") {
                storeFile = keystoreFile
                storePassword = System.getenv("LEVI_KEYSTORE_PASSWORD")
                    ?: (project.findProperty("levi.keystore.password") as String?)
                keyAlias = System.getenv("LEVI_KEY_ALIAS")
                    ?: (project.findProperty("levi.key.alias") as String?) ?: "levi-upload"
                keyPassword = System.getenv("LEVI_KEY_PASSWORD")
                    ?: (project.findProperty("levi.key.password") as String?)
            }
        }
    } else {
        logger.warn(
            "No upload keystore configured (LEVI_KEYSTORE_PATH / levi.keystore.path). " +
                "Release builds will be signed with the debug key — do NOT distribute them.",
        )
    }

    buildTypes {
        debug {
            applicationIdSuffix = ".debug"
            versionNameSuffix = "-debug"
        }
        release {
            isMinifyEnabled = false
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro"
            )
            signingConfig =
                signingConfigs.findByName("leviRelease") ?: signingConfigs.getByName("debug")
        }
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

    buildFeatures {
        viewBinding = true
    }
}

dependencies {
    implementation(libs.core.ktx)
    implementation(libs.appcompat)
    implementation(libs.material)
    implementation(libs.activity)
}
