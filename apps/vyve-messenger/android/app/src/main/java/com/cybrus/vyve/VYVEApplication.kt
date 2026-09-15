package com.cybrus.vyve

import android.app.Application
import dagger.hilt.android.HiltAndroidApp
import timber.log.Timber

/**
 * VYVE Application entry point.
 *
 * Initializes Hilt dependency injection and logging. Debug builds plant a
 * logcat tree; release builds plant a no-op-by-default tree that should be
 * wired to the crash-reporting provider of choice.
 */
@HiltAndroidApp
class VYVEApplication : Application() {
    override fun onCreate() {
        super.onCreate()
        
        if (BuildConfig.DEBUG) {
            Timber.plant(Timber.DebugTree())
            Timber.d("VYVE Messenger starting — DEBUG build")
        } else {
            // Production: plant a crash-reporting tree (replace with your provider)
            Timber.plant(object : Timber.Tree() {
                override fun log(priority: Int, tag: String?, message: String, t: Throwable?) {
                    // TODO: Send to crash reporting service
                    // Example: FirebaseCrashlytics.log(priority, tag, message)
                }
            })
            Timber.d("VYVE Messenger starting — PRODUCTION build")
        }
    }
}
