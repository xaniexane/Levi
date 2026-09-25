package dev.levi.app.voice

import android.Manifest
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.content.pm.ServiceInfo
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import android.os.SystemClock
import android.speech.RecognitionListener
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer
import androidx.core.app.NotificationCompat
import dev.levi.app.MainActivity
import dev.levi.app.R

/**
 * Best-effort "Hey LEVI" hotword listener.
 *
 * A third-party app cannot register a DSP-level hotword like the system
 * assistant does, so this is the honest version: a user-toggled
 * foreground service that keeps the device's own speech recognizer warm
 * and matches transcripts with [HeyLeviMatcher]. Saying "Hey LEVI" raises
 * a high-priority notification whose full-screen intent opens LEVI's
 * voice input (background activity launches are restricted, so the
 * notification is the sanctioned path — on most devices it pops the
 * voice prompt immediately, otherwise it's one tap away).
 *
 * Honest costs, stated in the Settings toggle before the user opts in:
 * - The microphone stays warm: Android shows the mic indicator the whole
 *   time, and battery use goes up.
 * - Detection is only as good as the on-device recognizer; in noise it
 *   misses, and lookalike phrases can false-trigger.
 * - The listener stops on reboot / process death; re-enable it in
 *   Settings (no boot receiver — starting a mic foreground service from
 *   the background is restricted on current Android).
 *
 * Fail-closed everywhere: no RECORD_AUDIO, no recognizer on the device,
 * or a revoked permission mid-listen all stop the service instead of
 * pretending to listen. Nothing is recorded or stored — transcripts are
 * matched in memory and dropped.
 */
class HeyLeviService : Service() {

    companion object {
        private const val ACTION_LISTEN = "dev.levi.app.action.LISTEN"
        private const val CHANNEL_LISTEN = "hey_levi_listen"
        private const val CHANNEL_TRIGGER = "hey_levi_trigger"
        private const val NOTIF_LISTEN_ID = 41
        private const val NOTIF_TRIGGER_ID = 42

        /** Quiet period after a trigger so one utterance can't loop. */
        private const val COOLDOWN_MS = 20_000L
        private const val MAX_RESTART_DELAY_MS = 10_000L

        @Volatile
        var running = false
            private set

        fun start(context: Context) {
            val intent = Intent(context, HeyLeviService::class.java)
                .setAction(ACTION_LISTEN)
            androidx.core.content.ContextCompat.startForegroundService(context, intent)
        }

        fun stop(context: Context) {
            context.stopService(Intent(context, HeyLeviService::class.java))
        }
    }

    private val handler = Handler(Looper.getMainLooper())
    private var recognizer: SpeechRecognizer? = null
    private var listening = false
    private var lastTriggerAt = 0L
    private var restartDelayMs = 1_000L
    private var restartTask: Runnable? = null

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        createChannels()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent?.action != ACTION_LISTEN) {
            stopSelf()
            return START_NOT_STICKY
        }
        if (checkSelfPermission(Manifest.permission.RECORD_AUDIO) !=
            PackageManager.PERMISSION_GRANTED ||
            !SpeechRecognizer.isRecognitionAvailable(this)
        ) {
            // Fail closed: don't pretend to listen.
            VoicePrefs.setHeyLeviEnabled(this, false)
            stopSelf()
            return START_NOT_STICKY
        }
        running = true
        val notification = listenNotification()
        if (Build.VERSION.SDK_INT >= 29) {
            startForeground(
                NOTIF_LISTEN_ID,
                notification,
                ServiceInfo.FOREGROUND_SERVICE_TYPE_MICROPHONE,
            )
        } else {
            @Suppress("DEPRECATION")
            startForeground(NOTIF_LISTEN_ID, notification)
        }
        beginLoop()
        return START_STICKY
    }

    override fun onDestroy() {
        running = false
        restartTask?.let { handler.removeCallbacks(it) }
        restartTask = null
        handler.removeCallbacksAndMessages(null)
        tearDownRecognizer()
        super.onDestroy()
    }

    // ---- recognition loop ----

    private fun beginLoop() {
        tearDownRecognizer()
        val sr = SpeechRecognizer.createSpeechRecognizer(this)
        recognizer = sr
        sr.setRecognitionListener(
            object : RecognitionListener {
                override fun onReadyForSpeech(params: Bundle?) {
                    listening = true
                    restartDelayMs = 1_000L
                }

                override fun onBeginningOfSpeech() = Unit
                override fun onRmsChanged(rmsdB: Float) = Unit
                override fun onBufferReceived(buffer: ByteArray?) = Unit

                override fun onEndOfSpeech() {
                    listening = false
                    scheduleRestart(500L)
                }

                override fun onError(error: Int) {
                    listening = false
                    // Back off: the recognizer is often briefly busy.
                    scheduleRestart(restartDelayMs)
                    restartDelayMs =
                        minOf(restartDelayMs * 2, MAX_RESTART_DELAY_MS)
                }

                override fun onResults(results: Bundle?) {
                    listening = false
                    handleResults(results)
                    scheduleRestart(500L)
                }

                override fun onPartialResults(partialResults: Bundle?) {
                    handleResults(partialResults)
                }

                override fun onEvent(eventType: Int, params: Bundle?) = Unit
            },
        )
        val intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
            putExtra(
                RecognizerIntent.EXTRA_LANGUAGE_MODEL,
                RecognizerIntent.LANGUAGE_MODEL_FREE_FORM,
            )
            putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, true)
            putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 3)
        }
        try {
            sr.startListening(intent)
        } catch (e: SecurityException) {
            // Permission revoked mid-flight: fail closed.
            VoicePrefs.setHeyLeviEnabled(this, false)
            stopSelf()
        }
    }

    private fun handleResults(results: Bundle?) {
        val heard =
            results?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
                ?: return
        if (heard.any { HeyLeviMatcher.isTrigger(it) }) onTrigger()
    }

    private fun onTrigger() {
        val now = SystemClock.elapsedRealtime()
        if (now - lastTriggerAt < COOLDOWN_MS) return
        lastTriggerAt = now
        tearDownRecognizer()
        notifyTrigger()
        scheduleRestart(COOLDOWN_MS)
    }

    private fun scheduleRestart(delayMs: Long) {
        restartTask?.let { handler.removeCallbacks(it) }
        val task = Runnable {
            restartTask = null
            if (running) beginLoop()
        }
        restartTask = task
        handler.postDelayed(task, delayMs)
    }

    private fun tearDownRecognizer() {
        listening = false
        try {
            recognizer?.cancel()
        } catch (e: Exception) {
            // Best effort; the recognizer may already be idle.
        }
        try {
            recognizer?.destroy()
        } catch (e: Exception) {
            // Best effort.
        }
        recognizer = null
    }

    // ---- notifications ----

    private fun createChannels() {
        if (Build.VERSION.SDK_INT < 26) return
        val manager = getSystemService(NotificationManager::class.java)
        manager.createNotificationChannel(
            NotificationChannel(
                CHANNEL_LISTEN,
                getString(R.string.hey_levi_channel_listen),
                NotificationManager.IMPORTANCE_LOW,
            ),
        )
        manager.createNotificationChannel(
            NotificationChannel(
                CHANNEL_TRIGGER,
                getString(R.string.hey_levi_channel_trigger),
                NotificationManager.IMPORTANCE_HIGH,
            ),
        )
    }

    private fun chatPendingIntent(): PendingIntent {
        val intent = Intent(this, MainActivity::class.java)
            .setAction(Intent.ACTION_MAIN)
            .putExtra(MainActivity.EXTRA_START_VOICE, true)
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP)
        return PendingIntent.getActivity(
            this,
            0,
            intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
    }

    private fun listenNotification(): android.app.Notification =
        NotificationCompat.Builder(this, CHANNEL_LISTEN)
            .setSmallIcon(R.drawable.ic_mic)
            .setContentTitle(getString(R.string.hey_levi_notif_title))
            .setContentText(getString(R.string.hey_levi_notif_text))
            .setContentIntent(chatPendingIntent())
            .setOngoing(true)
            .build()

    /**
     * The trigger alert. Background activity launches are restricted, so
     * this goes through a high-priority notification with a full-screen
     * intent — the sanctioned way to surface immediately. Needs
     * POST_NOTIFICATIONS on Android 13+ to be seen; without it the
     * listener keeps listening but can't pop the prompt.
     */
    private fun notifyTrigger() {
        val notification = NotificationCompat.Builder(this, CHANNEL_TRIGGER)
            .setSmallIcon(R.drawable.ic_mic)
            .setContentTitle(getString(R.string.hey_levi_trigger_title))
            .setContentText(getString(R.string.hey_levi_trigger_text))
            .setContentIntent(chatPendingIntent())
            .setFullScreenIntent(chatPendingIntent(), true)
            .setAutoCancel(true)
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .build()
        val manager = getSystemService(NotificationManager::class.java)
        manager.notify(NOTIF_TRIGGER_ID, notification)
    }
}
