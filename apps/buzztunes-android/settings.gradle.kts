// BuzzTunes Android — Chauncey's music player, on-device.
// Bloome (agent-messaging listening threads) + Metrolist (native media)
// MIX in one product. YouTube playback seam; never fakes audio.
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
        // NewPipeExtractor ships via JitPack only (not Maven Central).
        // Content filter keeps JitPack from being consulted for anything
        // but TeamNewPipe artifacts — supply-chain hygiene.
        maven("https://jitpack.io") {
            content {
                includeGroup("com.github.teamnewpipe")
            }
        }
    }
}

rootProject.name = "buzztunes-android"
include(":buzztunes")
