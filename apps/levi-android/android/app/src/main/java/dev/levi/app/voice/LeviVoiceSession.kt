package dev.levi.app.voice

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.graphics.Typeface
import android.os.Bundle
import android.speech.RecognitionListener
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer
import android.service.voice.VoiceInteractionSession
import android.util.TypedValue
import android.view.Gravity
import android.view.View
import android.widget.ImageView
import android.widget.LinearLayout
import android.widget.TextView
import dev.levi.app.AssistActivity
import dev.levi.app.MainActivity
import dev.levi.app.R

/**
 * The assistant overlay shown when the user invokes the default assistant
 * (long-press home / assistant gesture) while LEVI is selected.
 *
 * Flow:
 *  1. Voice plate appears with a listening state.
 *  2. If RECORD_AUDIO is not granted, the plate explains why the mic is
 *     needed and offers a button that opens [AssistActivity] to request it.
 *     A session is not an Activity and cannot show the runtime permission
 *     dialog itself. Fail closed: no listening without the permission.
 *  3. If granted, a [SpeechRecognizer] (the device's own speech service —
 *     no cloud dependency of ours) transcribes one utterance.
 *  4. The transcript is handed to [MainActivity] via an explicit intent
 *     extra; the chat is LEVI's existing backend (WebView → configured
 *     LEVI server). The session then hides.
 *
 * Nothing is recorded, stored, or sent anywhere by the session itself.
 * App-lock still gates [MainActivity], so a locked phone stays locked.
 */
class LeviVoiceSession(context: android.content.Context) : VoiceInteractionSession(context) {

    private lateinit var statusText: TextView
    private lateinit var hintText: TextView
    private lateinit var actionButton: TextView
    private var recognizer: SpeechRecognizer? = null
    private var listening = false

    override fun onCreateContentView(): View {
        val ctx = context
        val pad = (16 * ctx.resources.displayMetrics.density).toInt()

        val root = LinearLayout(ctx).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.CENTER_HORIZONTAL
            setPadding(pad, pad * 2, pad, pad * 2)
            // The system draws the session over a scrim; keep our panel
            // opaque so text stays legible.
            setBackgroundColor(0xFF1A1A1A.toInt())
        }

        val mic = ImageView(ctx).apply {
            setImageResource(R.drawable.ic_mic)
            // Tint the mic amber like the rest of the app chrome.
            setColorFilter(0xFFB26A00.toInt())
            layoutParams = LinearLayout.LayoutParams(pad * 3, pad * 3).apply {
                gravity = Gravity.CENTER_HORIZONTAL
                bottomMargin = pad
            }
        }
        root.addView(mic)

        statusText = TextView(ctx).apply {
            setText(R.string.voice_listening)
            setTextColor(0xFFF4F1E8.toInt())
            setTextSize(TypedValue.COMPLEX_UNIT_SP, 18f)
            typeface = Typeface.DEFAULT_BOLD
            gravity = Gravity.CENTER
        }
        root.addView(statusText)

        hintText = TextView(ctx).apply {
            setText(R.string.voice_hint)
            setTextColor(0xFF8A867E.toInt())
            setTextSize(TypedValue.COMPLEX_UNIT_SP, 14f)
            gravity = Gravity.CENTER
            setPadding(0, pad / 2, 0, 0)
        }
        root.addView(hintText)

        // One contextual action button; its label/handler change by state.
        actionButton = TextView(ctx).apply {
            setTextSize(TypedValue.COMPLEX_UNIT_SP, 15f)
            typeface = Typeface.DEFAULT_BOLD
            setTextColor(0xFFB26A00.toInt())
            gravity = Gravity.CENTER
            setPadding(pad, pad, pad, pad)
            visibility = View.GONE
        }
        root.addView(actionButton)

        // Tapping anywhere outside the button dismisses.
        root.setOnClickListener { hide() }
        return root
    }

    override fun onShow(args: Bundle?, showFlags: Int) {
        super.onShow(args, showFlags)
        beginListening()
    }

    override fun onHide() {
        super.onHide()
        stopListening()
    }

    override fun onDestroy() {
        stopListening()
        recognizer?.destroy()
        recognizer = null
        super.onDestroy()
    }

    private fun beginListening() {
        val ctx = context
        actionButton.visibility = View.GONE
        if (ctx.checkSelfPermission(Manifest.permission.RECORD_AUDIO) !=
            PackageManager.PERMISSION_GRANTED
        ) {
            statusText.setText(R.string.voice_mic_needed)
            hintText.setText(R.string.voice_mic_why)
            actionButton.apply {
                setText(R.string.voice_grant_mic)
                visibility = View.VISIBLE
                setOnClickListener {
                    // Explicit internal intent: AssistActivity requests the
                    // runtime permission, then finishes. The user invokes
                    // the assistant again afterwards.
                    val i = Intent(ctx, AssistActivity::class.java)
                        .putExtra(AssistActivity.EXTRA_REQUEST_MIC, true)
                        .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                    ctx.startActivity(i)
                    hide()
                }
            }
            return
        }
        if (!SpeechRecognizer.isRecognitionAvailable(ctx)) {
            statusText.setText(R.string.voice_no_recognizer)
            hintText.setText(R.string.voice_no_recognizer_hint)
            actionButton.apply {
                setText(R.string.voice_open_chat)
                visibility = View.VISIBLE
                setOnClickListener { openChat(null) }
            }
            return
        }
        statusText.setText(R.string.voice_listening)
        hintText.setText(R.string.voice_hint)
        startRecognizer()
    }

    private fun startRecognizer() {
        stopListening()
        val ctx = context
        val sr = SpeechRecognizer.createSpeechRecognizer(ctx)
        recognizer = sr
        val intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
            putExtra(
                RecognizerIntent.EXTRA_LANGUAGE_MODEL,
                RecognizerIntent.LANGUAGE_MODEL_FREE_FORM,
            )
            putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, true)
        }
        sr.setRecognitionListener(object : RecognitionListener {
            override fun onReadyForSpeech(params: Bundle?) {
                listening = true
            }

            override fun onBeginningOfSpeech() = Unit
            override fun onRmsChanged(rmsdB: Float) = Unit
            override fun onBufferReceived(buffer: ByteArray?) = Unit
            override fun onEndOfSpeech() {
                listening = false
            }

            override fun onError(error: Int) {
                listening = false
                statusText.setText(R.string.voice_not_caught)
                hintText.text = errorMessage(error)
                actionButton.apply {
                    setText(R.string.voice_try_again)
                    visibility = View.VISIBLE
                    setOnClickListener { beginListening() }
                }
            }

            override fun onResults(results: Bundle?) {
                listening = false
                val heard = results
                    ?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
                    ?.firstOrNull { it.isNotBlank() }
                if (heard.isNullOrBlank()) {
                    onError(SpeechRecognizer.ERROR_NO_MATCH)
                    return
                }
                openChat(heard)
            }

            override fun onPartialResults(partialResults: Bundle?) {
                val partial = partialResults
                    ?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
                    ?.firstOrNull { it.isNotBlank() }
                if (!partial.isNullOrBlank()) {
                    statusText.text = getString(R.string.voice_hearing, partial)
                }
            }

            override fun onEvent(eventType: Int, params: Bundle?) = Unit
        })
        try {
            sr.startListening(intent)
        } catch (e: SecurityException) {
            // Permission revoked mid-flight: fail closed, explain, stop.
            stopListening()
            statusText.setText(R.string.voice_mic_needed)
            hintText.setText(R.string.voice_mic_why)
            actionButton.visibility = View.GONE
        }
    }

    private fun stopListening() {
        if (listening) {
            try {
                recognizer?.stopListening()
            } catch (e: Exception) {
                // Best effort; the recognizer may already be idle.
            }
            listening = false
        }
        recognizer?.cancel()
    }

    /** Hands the transcript to the chat and ends the session. */
    private fun openChat(query: String?) {
        val ctx = context
        val i = Intent(ctx, MainActivity::class.java)
            .setAction(Intent.ACTION_MAIN)
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        if (!query.isNullOrBlank()) {
            i.putExtra(MainActivity.EXTRA_VOICE_QUERY, query)
        }
        ctx.startActivity(i)
        hide()
    }

    private fun errorMessage(error: Int): String = when (error) {
        SpeechRecognizer.ERROR_NETWORK, SpeechRecognizer.ERROR_SERVER ->
            getString(R.string.voice_error_network)
        SpeechRecognizer.ERROR_NO_MATCH, SpeechRecognizer.ERROR_SPEECH_TIMEOUT ->
            getString(R.string.voice_error_no_match)
        SpeechRecognizer.ERROR_INSUFFICIENT_PERMISSIONS ->
            getString(R.string.voice_mic_why)
        else -> getString(R.string.voice_error_generic)
    }

    private fun getString(resId: Int, vararg args: Any): String =
        context.getString(resId, *args)
}
