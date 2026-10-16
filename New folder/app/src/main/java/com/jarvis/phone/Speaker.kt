package com.jarvis.phone

import android.content.Context
import android.speech.tts.TextToSpeech
import android.speech.tts.UtteranceProgressListener
import java.util.Locale

/** Text-to-speech. Picks Arabic or English by looking at the text itself. */
class Speaker(ctx: Context, private val whenStart: () -> Unit, private val whenDone: () -> Unit) {
    private var ready = false
    private val tts: TextToSpeech = TextToSpeech(ctx) { status ->
        ready = status == TextToSpeech.SUCCESS
    }.also { t ->
        t.setOnUtteranceProgressListener(object : UtteranceProgressListener() {
            override fun onStart(id: String?) = whenStart()
            override fun onDone(id: String?) = whenDone()
            @Deprecated("Deprecated in Java") override fun onError(id: String?) = whenDone()
        })
    }

    fun say(text: String) {
        if (!ready) { whenDone(); return }
        tts.language = if (Text.hasArabic(text)) Locale("ar") else Locale.US
        tts.speak(text, TextToSpeech.QUEUE_FLUSH, null, "j${System.nanoTime()}")
    }

    fun shutdown() { tts.stop(); tts.shutdown() }
}
