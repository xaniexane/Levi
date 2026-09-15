// Root build file — plugin version declarations only (see gradle/libs.versions.toml).
// Module build logic lives in app/build.gradle.kts.

plugins {
    alias(libs.plugins.android.application) apply false
    // NOTE (AGP 9+): org.jetbrains.kotlin.android is intentionally absent —
    // AGP 9.0+ has built-in Kotlin support and fails the build if the plugin
    // is applied (see app/build.gradle.kts).
    alias(libs.plugins.kotlin.compose) apply false
    alias(libs.plugins.kotlin.serialization) apply false
    alias(libs.plugins.ksp) apply false
    alias(libs.plugins.hilt.android) apply false
}

// WORKAROUND (remove once Dagger ships a Kotlin 2.4-aware release):
// Hilt 2.59.2 bundles a kotlin-metadata-jvm that cannot read Kotlin 2.4
// class-file metadata ("Provided Metadata instance has version 2.4.0, while
// maximum supported version is 2.3.0"), which breaks Hilt's KSP processing
// with "error: ...". Forcing a 2.4-aware reader onto every module's
// dependency graph (including the KSP processor classpath) is the
// maintainer-endorsed workaround.
subprojects {
    configurations.all {
        resolutionStrategy {
            force("org.jetbrains.kotlin:kotlin-metadata-jvm:${libs.versions.kotlin.get()}")
        }
    }
}
