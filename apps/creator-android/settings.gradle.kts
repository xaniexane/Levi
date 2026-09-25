// Creator Android — the LEVI creator platform (dating + creator services),
// on-device via Chaquopy. AI track is the default surface; the SI track
// stays gate-locked behind the Plaiground adult gate (default OFF).
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

rootProject.name = "creator-android"
include(":creator")
