// Dispatch Android — the LEVI truck-dispatch board, on-device.
// Thin vertical: dispatch automation, HOS-adjacent logs, checkcalls,
// time clock, fleet-admin coordination. Local-only: no network.
// Loop: dispatcher decides -> verifier twin countersigns -> receipt.
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

rootProject.name = "dispatch-android"
include(":dispatch")
