package com.jarvis.phone

import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.speech.RecognitionListener
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer

/**
 * Always-on listening loop on top of Android's SpeechRecognizer.
 * It restarts itself after every result or error, so it keeps listening while the app is in the background.
 * Must be created and used on the main thread (the foreground service does that).
 */
class VoiceEngine(
    private val ctx: Context,
    private val prefs: Prefs,
    private val onPartial: (String) -> Unit,
    private val onFinal: (String) -> Unit,
    private val onLevel: (Float) -> Unit,
) {
    private val main = Handler(Looper.getMainLooper())
    private var rec: SpeechRecognizer? = null
    private var running = false
    private var paused = false
    private var busy = false

    fun start() { running = true; paused = false; listen() }
    fun stop() { running = false; main.removeCallbacksAndMessages(null); destroy() }
    /** Pause while Jarvis speaks, so it never answers its own voice. */
    fun pause() { paused = true; main.removeCallbacksAndMessages(null); rec?.cancel(); busy = false }
    fun resume() { if (!running) return; paused = false; main.postDelayed({ listen() }, 350) }

    private fun destroy() { rec?.destroy(); rec = null; busy = false }

    private fun listen() {
        if (!running || paused || busy) return
        if (!SpeechRecognizer.isRecognitionAvailable(ctx)) return
        if (rec == null) {
            rec = SpeechRecognizer.createSpeechRecognizer(ctx).apply { setRecognitionListener(listener) }
        }
        val i = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
            putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
            putExtra(RecognizerIntent.EXTRA_LANGUAGE, prefs.language)
            putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, true)
            putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 1)
            putExtra(RecognizerIntent.EXTRA_CALLING_PACKAGE, ctx.packageName)
            // Let the user pause mid-sentence while dictating without the session closing.
            putExtra(RecognizerIntent.EXTRA_SPEECH_INPUT_COMPLETE_SILENCE_LENGTH_MILLIS, 1800L)
            putExtra(RecognizerIntent.EXTRA_SPEECH_INPUT_POSSIBLY_COMPLETE_SILENCE_LENGTH_MILLIS, 1500L)
        }
        busy = true
        rec?.startListening(i)
    }

    private fun again(delay: Long) {
        busy = false
        if (running && !paused) main.postDelayed({ listen() }, delay)
    }

    private val listener = object : RecognitionListener {
        override fun onReadyForSpeech(p: Bundle?) {}
        override fun onBeginningOfSpeech() {}
        override fun onRmsChanged(rmsdB: Float) { onLevel(((rmsdB + 2f) / 12f).coerceIn(0f, 1f)) }
        override fun onBufferReceived(b: ByteArray?) {}
        override fun onEndOfSpeech() { onLevel(0f) }
        override fun onEvent(t: Int, p: Bundle?) {}
        override fun onPartialResults(b: Bundle?) {
            b?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)?.firstOrNull()?.let(onPartial)
        }
        override fun onResults(b: Bundle?) {
            busy = false
            val t = b?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)?.firstOrNull()
            if (!t.isNullOrBlank()) onFinal(t)
            again(150)
        }
        override fun onError(error: Int) {
            // Silence/no-match are normal for an always-on loop. Busy/too-many-requests need a longer breather.
            val wait = when (error) {
                SpeechRecognizer.ERROR_RECOGNIZER_BUSY, SpeechRecognizer.ERROR_TOO_MANY_REQUESTS -> 1500L
                SpeechRecognizer.ERROR_INSUFFICIENT_PERMISSIONS -> { stop(); return }
                else -> 250L
            }
            if (error == SpeechRecognizer.ERROR_RECOGNIZER_BUSY) { rec?.cancel() }
            again(wait)
        }
    }
}
