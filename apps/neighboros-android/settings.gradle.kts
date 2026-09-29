// NeighborOS Android — LEVI product line 01: local-services dispatch OS.
// Gig dispatch organ under LEVI. On-device via Chaquopy, local-only.
pluginManagement {
    repositories {
        google()
        mavenCentral()
        gradlePluginPortal()
        maven { url = uri("https://chaquo.com/maven") }
    }
}

dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        google()
        mavenCentral()
    }
}

rootProject.name = "neighboros-android"
include(":neighboros")
