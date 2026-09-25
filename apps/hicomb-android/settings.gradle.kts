// Hicomb Android — the from-scratch code editor, on-device.
// Quetta-Pan is front and center in the UI; Surgeon repairs beside it.
// Loop: Alpha builds -> Surgeon repairs -> Quetta-Pan improves.
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

rootProject.name = "hicomb-android"
include(":hicomb")
