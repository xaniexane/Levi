package dev.levi.app

import android.app.Application
import dev.levi.app.settings.LeviChannels
import dev.levi.app.settings.SettingsStore

/** Applies the saved appearance theme before any activity is created. */
class LeviApp : Application() {
    override fun onCreate() {
        super.onCreate()
        SettingsStore.applyTheme(this)
        LeviChannels.ensure(this)
    }
}
