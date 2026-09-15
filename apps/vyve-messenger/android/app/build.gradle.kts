import java.util.Properties

plugins {
    alias(libs.plugins.android.application)
    // NOTE (AGP 9+): org.jetbrains.kotlin.android must NOT be applied — AGP 9
    // has built-in Kotlin support and fails the build if it is present.
    // Kotlin compiler plugins that are still required (Compose, serialization)
    // keep their org.jetbrains.kotlin.plugin.* aliases below.
    alias(libs.plugins.kotlin.compose)
    alias(libs.plugins.kotlin.serialization)
    alias(libs.plugins.ksp)
    alias(libs.plugins.hilt.android)
}

android {
    namespace = "com.cybrus.vyve"
    // compileSdk/targetSdk 36. Newer androidx releases (Compose 1.12.0 via BOM
    // 2026.08.00+, androidx.core 1.19.0) declare minCompileSdk 37 in their AAR
    // metadata, which AGP 9 enforces as a hard gate — but Google has not
    // published a platforms;android-37 SDK package, so we pin the catalog to
    // versions whose metadata tops out at 36 (see libs.versions.toml notes).
    compileSdk = 36

    defaultConfig {
        applicationId = "com.cybrus.vyve"
        minSdk = 24
        targetSdk = 36
        versionCode = 1
        versionName = "1.0.0"

        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
        vectorDrawables {
            useSupportLibrary = true
        }
    }

    // ---- Release signing (Play App Signing) ----
    // The upload keystore lives OUTSIDE the repo. Resolution order:
    //   1. VYVE_KEYSTORE_PATH / VYVE_KEYSTORE_PASSWORD / VYVE_KEY_ALIAS /
    //      VYVE_KEY_PASSWORD env vars (CI)
    //   2. vyve.keystore.path / vyve.keystore.password / vyve.key.alias /
    //      vyve.key.password Gradle properties (local dev, see gradle.properties)
    // If no keystore is configured the release build falls back to the debug
    // key so `./gradlew assembleRelease` still assembles locally — NEVER
    // upload a debug-signed artifact to Play. See RUNBOOK.md.
    val keystorePath: String? =
        System.getenv("VYVE_KEYSTORE_PATH")
            ?: (project.findProperty("vyve.keystore.path") as String?)?.ifBlank { null }
    val keystoreFile = keystorePath?.let { file(it) }?.takeIf { it.exists() }
    if (keystoreFile != null) {
        signingConfigs {
            create("vyveRelease") {
                storeFile = keystoreFile
                storePassword = System.getenv("VYVE_KEYSTORE_PASSWORD")
                    ?: (project.findProperty("vyve.keystore.password") as String?)
                keyAlias = System.getenv("VYVE_KEY_ALIAS")
                    ?: (project.findProperty("vyve.key.alias") as String?) ?: "vyve-upload"
                keyPassword = System.getenv("VYVE_KEY_PASSWORD")
                    ?: (project.findProperty("vyve.key.password") as String?)
            }
        }
    } else {
        logger.warn(
            "No upload keystore configured (VYVE_KEYSTORE_PATH / vyve.keystore.path). " +
                "Release builds will be signed with the debug key — do NOT ship to Play.",
        )
    }

    buildTypes {
        release {
            isMinifyEnabled = true
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro",
            )
            signingConfig =
                signingConfigs.findByName("vyveRelease") ?: signingConfigs.getByName("debug")
        }
        debug {
            applicationIdSuffix = ".debug"
            isDebuggable = true
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    kotlin {
        compilerOptions {
            jvmTarget.set(org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17)
        }
    }

    buildFeatures {
        compose = true
        buildConfig = true
    }

    packaging {
        resources {
            excludes += setOf(
                "META-INF/AL2.0",
                "META-INF/LGPL2.1",
                "META-INF/LICENSE.md",
                "META-INF/LICENSE-notice.md",
            )
        }
        // SQLCipher ships native libs for several ABIs; keep the 64-bit ones.
        jniLibs {
            excludes += setOf("**/x86/libsqlcipher.so")
        }
    }
}

dependencies {
    // Core Android
    implementation(libs.core.ktx)
    implementation(libs.appcompat)
    implementation(libs.material)
    implementation(libs.activity.compose)

    // Compose (Compose Compiler comes from the org.jetbrains.kotlin.plugin.compose plugin)
    implementation(platform(libs.compose.bom))
    implementation(libs.compose.ui)
    implementation(libs.compose.ui.graphics)
    implementation(libs.compose.ui.tooling.preview)
    implementation(libs.compose.material3)
    debugImplementation(libs.compose.ui.tooling)
    debugImplementation(libs.compose.ui.test.manifest)

    // Navigation + Lifecycle
    implementation(libs.navigation.compose)
    implementation(libs.hilt.navigation.compose)
    implementation(libs.lifecycle.viewmodel)
    implementation(libs.lifecycle.runtime.compose)
    implementation(libs.lifecycle.service)

    // Hilt DI
    implementation(libs.hilt.android)
    ksp(libs.hilt.compiler)

    // Coroutines / Serialization / DateTime
    implementation(libs.coroutines.android)
    implementation(libs.serialization.json)
    implementation(libs.datetime)

    // Networking (OkHttp 5.x + Retrofit 3.x; kotlinx-serialization is the
    // ONE JSON converter used throughout — see net/ApiService.kt)
    implementation(libs.okhttp)
    implementation(libs.okhttp.logging)
    implementation(libs.retrofit)
    implementation(libs.retrofit.serialization)

    // Encrypted database (SQLCipher) + encrypted prefs + DataStore
    implementation(libs.sqlcipher)
    // sqlite-android: the androidx.sqlite.db.* supertypes sqlcipher's classes
    // extend (the transitive sqlite artifact ships no classes jar at 2.5.0).
    implementation(libs.sqlite.android)
    implementation(libs.security.crypto)
    implementation(libs.datastore.preferences)

    // Biometric
    implementation(libs.biometric)

    // WorkManager (background sync)
    implementation(libs.work.runtime)
    implementation(libs.hilt.work)

    // Logging
    implementation(libs.timber)

    // Tests
    testImplementation(libs.junit)
    testImplementation(libs.coroutines.test)
    testImplementation(libs.mockito.core)
    testImplementation(libs.mockito.kotlin)
    androidTestImplementation(libs.test.ext.junit)
    androidTestImplementation(libs.espresso.core)
    androidTestImplementation(platform(libs.compose.bom))
    androidTestImplementation(libs.compose.ui.test.junit4)
}
