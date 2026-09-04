package com.cybrus.vyve

import android.app.Application
import dagger.hilt.android.HiltAndroidApp
import timber.log.Timber

/**
 * VYVE Application entry point.
 * 
 * Initializes Hilt dependency injection and logging.
 * In production builds, Timber is only initialized if BuildConfig.DEBUG is false.
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
