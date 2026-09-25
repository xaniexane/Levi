package com.cybrus.vyve.net

import android.app.Service
import android.content.Intent
import android.os.IBinder
import timber.log.Timber

/**
 * Background sync entry point declared in the manifest.
 *
 * Minimal real implementation: the service exists so the manifest component
 * resolves and the OS can deliver start requests (e.g. from a future
 * BOOT_COMPLETED receiver). The actual sync work belongs in a WorkManager
 * worker — this service just acknowledges the request and stops, so it never
 * lingers as a zombie foreground service.
 */
class MessageSyncService : Service() {

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        Timber.d("MessageSyncService start requested (action=%s)", intent?.action)
        // TODO: enqueue the WorkManager SyncWorker that drains GET /queue
        //       and flushes pending uploads when network is available.
        stopSelf(startId)
        return START_NOT_STICKY
    }
}
