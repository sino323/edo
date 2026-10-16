package com.jarvis.phone

import android.Manifest
import android.app.Activity
import android.content.Intent
import android.content.pm.PackageManager
import android.graphics.Color
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.provider.Settings
import android.text.InputType
import android.view.View
import android.widget.*
import kotlin.concurrent.thread

/** One plain settings screen: grant permissions, save numbers, pair with the PC, start Jarvis. */
class MainActivity : Activity() {
    private lateinit var prefs: Prefs
    private lateinit var status: TextView

    override fun onCreate(b: Bundle?) {
        super.onCreate(b)
        prefs = Prefs(this)
        val d = resources.displayMetrics.density
        val col = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding((20 * d).toInt(), (36 * d).toInt(), (20 * d).toInt(), (20 * d).toInt())
        }
        setContentView(ScrollView(this).apply { setBackgroundColor(Color.parseColor("#060E18")); addView(col) })

        fun title(t: String) = col.addView(TextView(this).apply {
            text = t; textSize = 17f; setPadding(0, (20 * d).toInt(), 0, (4 * d).toInt()); setTextColor(Color.parseColor("#00D8FF"))
        })
        fun field(hint: String, value: String, phone: Boolean = false): EditText = EditText(this).apply {
            this.hint = hint; setText(value); setSingleLine(); setTextColor(Color.WHITE); setHintTextColor(Color.parseColor("#5E7388"))
            if (phone) inputType = InputType.TYPE_CLASS_PHONE
            col.addView(this)
        }
        fun box(hint: String): EditText = EditText(this).apply {
            this.hint = hint; setTextColor(Color.WHITE); setHintTextColor(Color.parseColor("#5E7388"))
            setBackgroundColor(Color.parseColor("#0C1B2A")); setPadding((12 * d).toInt(), (10 * d).toInt(), (12 * d).toInt(), (10 * d).toInt())
            inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_FLAG_MULTI_LINE or InputType.TYPE_TEXT_FLAG_CAP_SENTENCES
            minLines = 2; maxLines = 5; gravity = android.view.Gravity.TOP
            col.addView(this)
        }
        fun button(t: String, f: () -> Unit) = col.addView(Button(this).apply { text = t; setOnClickListener { f() } })

        status = TextView(this).apply { textSize = 14f; setTextColor(Color.parseColor("#9FB3C8")) }
        col.addView(TextView(this).apply { text = "JARVIS · Phone"; textSize = 26f; setTextColor(Color.WHITE) })
        col.addView(status)

        title("📱 Phone Jarvis (type instead of speaking)")
        val phoneBox = box("e.g. text Baba · sleep · anything you'd say after “Hey bro”")
        button("Send to phone Jarvis") {
            val t = phoneBox.text.toString().trim()
            when {
                t.isBlank() -> {}
                checkSelfPermission(Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED ->
                    toast("Allow the microphone first (section 1)")
                !Settings.canDrawOverlays(this) -> toast("Allow display over other apps first (section 1)")
                else -> {
                    startForegroundService(Intent(this, JarvisService::class.java).setAction("TEXT").putExtra("text", t))
                    phoneBox.setText("")
                }
            }
        }

        title("💻 Computer (runs on your PC)")
        val pcBox = box("e.g. open Spotify · what's my CPU usage")
        val pcMsg = TextView(this).apply { setTextColor(Color.parseColor("#9FB3C8")) }
        button("Send to PC") {
            val t = pcBox.text.toString().trim()
            when {
                t.isBlank() -> {}
                !PcLink(prefs).isPaired -> pcMsg.text = "Not linked yet. Scroll down to section 4 and pair."
                else -> {
                    pcMsg.text = "Sending…"
                    thread {
                        val ok = PcLink(prefs).command(t)
                        runOnUiThread { pcMsg.text = if (ok) "Sent to PC ✓" else "Couldn't reach the PC. Same Wi-Fi? JARVIS running?"; if (ok) pcBox.setText("") }
                    }
                }
            }
        }
        col.addView(pcMsg)

        title("1 · Permissions")
        button("Microphone + notifications") {
            val p = mutableListOf(Manifest.permission.RECORD_AUDIO)
            if (Build.VERSION.SDK_INT >= 33) p += Manifest.permission.POST_NOTIFICATIONS
            requestPermissions(p.toTypedArray(), 1)
        }
        button("Allow display over other apps") {
            startActivity(Intent(Settings.ACTION_MANAGE_OVERLAY_PERMISSION, Uri.parse("package:$packageName")))
        }
        button("Turn on 'Send' helper (accessibility)") {
            startActivity(Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS))
        }

        title("2 · Contacts (digits only, with country code)")
        val baba = field("Baba — e.g. 201001234567", prefs.babaNumber, true)
        val mama = field("Mama — e.g. 201001234567", prefs.mamaNumber, true)

        title("3 · Voice")
        val lang = field("Speech language (ar-EG or en-US)", prefs.language)
        val wake = field("Extra wake phrases, comma separated", prefs.extraWake)

        title("4 · Your PC (optional)")
        val pairMsg0 = TextView(this).apply { setTextColor(Color.parseColor("#9FB3C8")) }
        val url = field("PC address, e.g. https://192.168.1.5:8000", prefs.pcUrl)
        button("Find my PC on this Wi-Fi") {
            pairMsg0.text = "Looking…"
            thread {
                val found = PcLink(prefs).discover()
                runOnUiThread {
                    if (found != null) { url.setText(found); prefs.pcUrl = found; pairMsg0.text = "Found $found" }
                    else pairMsg0.text = "No answer. Is JARVIS running on the PC, on the same Wi-Fi? Or type the address by hand."
                }
            }
        }
        val key = field("6-character key (say “pair my phone” to JARVIS, or press Remote Control)", "")
        col.addView(pairMsg0)
        val pairMsg = TextView(this).apply { setTextColor(Color.parseColor("#9FB3C8")) }; col.addView(pairMsg)

        fun save() {
            prefs.babaNumber = baba.text.toString(); prefs.mamaNumber = mama.text.toString()
            prefs.language = lang.text.toString().trim(); prefs.extraWake = wake.text.toString()
            prefs.pcUrl = url.text.toString()
        }

        button("Pair with PC") {
            save(); pairMsg.text = "Pairing…"
            thread {
                val err = PcLink(prefs).pair(key.text.toString())
                runOnUiThread { pairMsg.text = err ?: "Paired ✓"; refresh() }
            }
        }

        title("5 · Run")
        button("Save and start Jarvis") {
            save()
            when {
                checkSelfPermission(Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED ->
                    toast("Allow the microphone first")
                !Settings.canDrawOverlays(this) -> toast("Allow display over other apps first")
                else -> { startForegroundService(Intent(this, JarvisService::class.java)); toast("Say “Hey bro”"); finish() }
            }
        }
        button("Stop Jarvis") { startService(Intent(this, JarvisService::class.java).setAction("STOP")) }
        refresh()
    }

    override fun onResume() { super.onResume(); refresh() }

    private fun refresh() {
        val mic = checkSelfPermission(Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED
        val ov = Settings.canDrawOverlays(this)
        val a11y = Settings.Secure.getString(contentResolver, Settings.Secure.ENABLED_ACCESSIBILITY_SERVICES)
            ?.contains("$packageName/") == true
        fun m(ok: Boolean) = if (ok) "✓" else "✗"
        status.text = "Mic ${m(mic)}   Overlay ${m(ov)}   Send helper ${m(a11y)}   PC ${m(PcLink(prefs).isPaired)}"
    }

    private fun toast(s: String) = Toast.makeText(this, s, Toast.LENGTH_SHORT).show()
    @Deprecated("Deprecated in Java")
    override fun onRequestPermissionsResult(c: Int, p: Array<out String>, r: IntArray) { refresh() }
}
