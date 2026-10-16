package com.jarvis.phone

import android.app.*
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Build
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import android.content.pm.ServiceInfo
import kotlin.concurrent.thread

/**
 * Foreground service = Jarvis keeps running after you leave the app.
 *
 *   SLEEP       listening only for "Hey bro"; small ring at the bottom
 *   AWAKE       ring grows; listens for a command; goes back to sleep after 25 s of silence
 *   DICTATING   "text baba / mama": WhatsApp chat is open, everything you say is the message until you say "stop"
 *   CONFIRMING  Jarvis reads the message back, you say yes (send) or no (cancel)
 */
class JarvisService : Service() {
    private enum class S { SLEEP, AWAKE, DICTATING, CONFIRMING }

    private lateinit var prefs: Prefs
    private lateinit var overlay: Overlay
    private lateinit var voice: VoiceEngine
    private lateinit var speaker: Speaker
    private lateinit var pc: PcLink
    private val main = Handler(Looper.getMainLooper())

    private var state = S.SLEEP
    private var target = ""                       // "baba" | "mama"
    private val parts = mutableListOf<String>()
    private var pending = ""
    private var retried = false
    private var started = false

    private val idleToSleep = Runnable { if (state == S.AWAKE) sleep("") }
    private val dictationTimeout = Runnable { if (state == S.DICTATING) cancel("Message cancelled.") }

    override fun onBind(i: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        prefs = Prefs(this); pc = PcLink(prefs)
        overlay = Overlay(this)
        speaker = Speaker(this,
            whenStart = { main.post { overlay.view.setSpeaking(true); voice.pause() } },
            whenDone = { main.post { overlay.view.setSpeaking(false); voice.resume() } })
        voice = VoiceEngine(this, prefs,
            onPartial = ::onPartial, onFinal = ::onFinal,
            onLevel = { if (state != S.SLEEP) overlay.view.setLevel(it) })
    }

    override fun onStartCommand(i: Intent?, flags: Int, id: Int): Int {
        if (i?.action == "STOP") { stopSelf(); return START_NOT_STICKY }
        startForegroundCompat()
        if (!started) {
            started = true
            overlay.show()
            overlay.view.setMode(BubbleView.Mode.SLEEP)
            voice.start()
        }
        // Typed in the app's "Phone Jarvis" box: same as saying it after "Hey bro".
        if (i?.action == "TEXT") i.getStringExtra("text")?.trim()?.takeIf { it.isNotBlank() }?.let { typed(it) }
        return START_STICKY
    }

    override fun onDestroy() {
        voice.stop(); speaker.shutdown(); overlay.hide(); main.removeCallbacksAndMessages(null)
        super.onDestroy()
    }

    // ── voice events ────────────────────────────────────────────────────────

    private fun onPartial(text: String) {
        // Light the ring as soon as the wake phrase is heard, before the sentence ends.
        if (state == S.SLEEP && Text.afterWake(text, prefs.extraWake) != null) wake()
    }

    private fun onFinal(text: String) {
        when (state) {
            S.SLEEP -> Text.afterWake(text, prefs.extraWake)?.let { rest ->
                wake()
                if (rest.isNotBlank()) handleCommand(rest)
            }
            S.AWAKE -> {
                val t = Text.afterWake(text, prefs.extraWake) ?: Text.norm(text)
                if (t.isNotBlank()) handleCommand(t)
            }
            S.DICTATING -> handleDictation(text)
            S.CONFIRMING -> handleConfirm(Text.norm(text))
        }
    }

    /** Typed text behaves exactly like speech, whatever state Jarvis is in. */
    private fun typed(text: String) {
        when (state) {
            S.SLEEP -> { wake(); handleCommand(text, false) }
            S.AWAKE -> handleCommand(text, false)
            S.DICTATING -> handleDictation(text)
            S.CONFIRMING -> handleConfirm(Text.norm(text))
        }
    }

    // ── state helpers ───────────────────────────────────────────────────────

    private fun wake() {
        if (state != S.SLEEP) return
        state = S.AWAKE
        overlay.view.setMode(BubbleView.Mode.AWAKE)
        armIdle()
    }

    private fun sleep(say: String) {
        state = S.SLEEP; parts.clear(); pending = ""
        main.removeCallbacks(idleToSleep); main.removeCallbacks(dictationTimeout)
        overlay.view.setMode(BubbleView.Mode.SLEEP)
        if (say.isNotBlank()) speaker.say(say)
    }

    private fun armIdle() { main.removeCallbacks(idleToSleep); main.postDelayed(idleToSleep, 25_000) }

    // ── commands ────────────────────────────────────────────────────────────

    private fun handleCommand(raw: String, toPc: Boolean = true) {
        armIdle()
        val t = Text.norm(raw)
        overlay.view.setCaption(raw)
        when {
            Text.sleepCmd.containsMatchIn(t) -> sleep("Going to sleep.")
            Text.msgVerb.containsMatchIn(t) && Text.babaWords.containsMatchIn(t) -> startMessage("baba")
            Text.msgVerb.containsMatchIn(t) && Text.mamaWords.containsMatchIn(t) -> startMessage("mama")
            toPc -> forwardToPc(raw)
            else -> speaker.say("That one is for your computer. Use the Computer box.")
        }
    }

    private fun forwardToPc(raw: String) {
        if (!pc.isPaired) { speaker.say("I'm not linked to your computer yet. Pair it in the app."); return }
        thread {
            val ok = pc.command(raw)
            main.post { speaker.say(if (ok) "Sent to your computer." else "I couldn't reach your computer.") }
        }
    }

    // ── "text baba / mama" ──────────────────────────────────────────────────

    private fun startMessage(who: String) {
        val number = if (who == "baba") prefs.babaNumber else prefs.mamaNumber
        val name = if (who == "baba") "Baba" else "Mama"
        if (number.isBlank()) { speaker.say("There is no number saved for $name. Add it in the app."); return }
        target = who; parts.clear(); pending = ""
        openChat(number, null)                                  // 1. open WhatsApp on that chat
        state = S.DICTATING                                     // 2. everything you say is the message
        overlay.view.setCaption("Message for $name… say stop when done")
        speaker.say("Go ahead. Say stop when you're done.")
        main.removeCallbacks(idleToSleep)
        main.postDelayed(dictationTimeout, 180_000)
    }

    private fun handleDictation(raw: String) {
        val t = Text.norm(raw)
        if (Text.cancel.matches(t)) { cancel("Cancelled."); return }
        val stripped = Text.stripStop(raw)
        // Keep the user's own spelling (not the normalised form) in the message.
        val chunk = if (stripped != null) raw.trim().replace(Regex("(?i)[\\s,.!؟?،]*(stop|استوب|إستوب|ستوب)[\\s.!؟?]*$"), "") else raw.trim()
        if (chunk.isNotBlank()) parts += chunk
        overlay.view.setCaption(parts.joinToString(" "))
        if (stripped == null) return                            // keep listening until "stop"

        main.removeCallbacks(dictationTimeout)
        pending = parts.joinToString(" ").trim()
        if (pending.isBlank()) { cancel("I didn't hear a message."); return }
        state = S.CONFIRMING; retried = false
        val name = if (target == "baba") "Baba" else "Mama"
        overlay.view.setCaption("To $name: $pending")
        speaker.say("Send to $name: $pending. Say yes to send, or no to cancel.")
    }

    private fun handleConfirm(t: String) {
        when {
            Text.no.containsMatchIn(t) -> cancel("Okay, cancelled.")
            Text.yes.containsMatchIn(t) -> send()
            !retried -> { retried = true; speaker.say("Say yes to send or no to cancel.") }
            else -> cancel("Cancelled.")
        }
    }

    private fun send() {
        val number = if (target == "baba") prefs.babaNumber else prefs.mamaNumber
        val msg = pending
        state = S.AWAKE; pending = ""; parts.clear(); armIdle()
        // Re-open the chat with the text pre-filled, then let the accessibility service press Send.
        SendBridge.arm(12_000) { ok ->
            main.post {
                overlay.view.setCaption(if (ok) "Sent ✓" else "")
                speaker.say(if (ok) "Sent." else "I filled the message but couldn't press send. Tap it yourself.")
            }
        }
        main.postDelayed({
            if (SendBridge.armedUntil != 0L && System.currentTimeMillis() >= SendBridge.armedUntil) SendBridge.finish(false)
        }, 12_500)
        openChat(number, msg)
    }

    private fun cancel(say: String) {
        state = S.AWAKE; parts.clear(); pending = ""
        main.removeCallbacks(dictationTimeout); armIdle()
        overlay.view.setCaption("")
        speaker.say(say)
    }

    private fun openChat(number: String, text: String?) {
        val uri = Uri.parse("https://wa.me/$number" + (text?.let { "?text=" + Uri.encode(it) } ?: ""))
        val i = Intent(Intent.ACTION_VIEW, uri).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        // Prefer regular WhatsApp, fall back to Business, then to whatever handles wa.me.
        for (pkg in listOf("com.whatsapp", "com.whatsapp.w4b", null)) {
            try { startActivity(if (pkg != null) Intent(i).setPackage(pkg) else i); return } catch (_: Exception) {}
        }
        speaker.say("I couldn't open WhatsApp.")
    }

    // ── notification ────────────────────────────────────────────────────────

    private fun startForegroundCompat() {
        val ch = "jarvis"
        val nm = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        nm.createNotificationChannel(NotificationChannel(ch, "Jarvis", NotificationManager.IMPORTANCE_LOW))
        val stop = PendingIntent.getService(this, 0, Intent(this, JarvisService::class.java).setAction("STOP"),
            PendingIntent.FLAG_IMMUTABLE)
        val open = PendingIntent.getActivity(this, 1, Intent(this, MainActivity::class.java), PendingIntent.FLAG_IMMUTABLE)
        val n = Notification.Builder(this, ch)
            .setContentTitle("Jarvis is listening for \"Hey bro\"")
            .setSmallIcon(R.drawable.ic_stat_jarvis)
            .setContentIntent(open)
            .addAction(Notification.Action.Builder(android.R.drawable.ic_menu_close_clear_cancel, "Stop", stop).build())
            .setOngoing(true).build()
        if (Build.VERSION.SDK_INT >= 29)
            startForeground(1, n, ServiceInfo.FOREGROUND_SERVICE_TYPE_MICROPHONE)
        else startForeground(1, n)
    }
}
