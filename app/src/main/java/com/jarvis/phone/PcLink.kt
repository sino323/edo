package com.jarvis.phone

import okhttp3.*
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject
import java.net.URI
import java.security.SecureRandom
import java.security.cert.X509Certificate
import java.util.concurrent.TimeUnit
import javax.net.ssl.*

/**
 * Talks to the JARVIS PC edition through its existing dashboard (dashboard/server.py), no PC changes needed:
 *   pair()     one-time 6-character key from the PC's "Remote Control" button -> /auto-login
 *   command()  POST /api/command, same endpoint the browser dashboard uses
 *
 * The PC dashboard uses a self-signed certificate, so TLS checks are relaxed ONLY for the host
 * you typed in settings. Use it on your home Wi-Fi, or over a tunnel you control (Tailscale etc.).
 */
class PcLink(private val prefs: Prefs) {

    private fun client(): OkHttpClient {
        val host = runCatching { URI(prefs.pcUrl).host }.getOrNull()
        val b = OkHttpClient.Builder().connectTimeout(6, TimeUnit.SECONDS).readTimeout(10, TimeUnit.SECONDS)
        if (prefs.pcUrl.startsWith("https") && host != null) {
            val trustAll = object : X509TrustManager {
                override fun checkClientTrusted(c: Array<X509Certificate>, a: String) {}
                override fun checkServerTrusted(c: Array<X509Certificate>, a: String) {}
                override fun getAcceptedIssuers(): Array<X509Certificate> = emptyArray()
            }
            val ctx = SSLContext.getInstance("TLS").apply { init(null, arrayOf(trustAll), SecureRandom()) }
            b.sslSocketFactory(ctx.socketFactory, trustAll).hostnameVerifier { h, _ -> h == host }
        }
        return b.build()
    }

    /** Blocking. Shouts "JARVIS?" on the Wi-Fi; the PC plugin answers with its address. Null if nobody answers. */
    fun discover(): String? {
        repeat(2) {
            val found = runCatching {
                java.net.DatagramSocket().use { sock ->
                    sock.broadcast = true; sock.soTimeout = 2000
                    val q = "JARVIS?".toByteArray()
                    sock.send(java.net.DatagramPacket(q, q.size, java.net.InetAddress.getByName("255.255.255.255"), 8765))
                    val buf = ByteArray(256)
                    val pkt = java.net.DatagramPacket(buf, buf.size)
                    sock.receive(pkt)
                    String(pkt.data, 0, pkt.length).trim().removePrefix("JARVIS|").takeIf { it.startsWith("http") }
                }
            }.getOrNull()
            if (found != null) return found
        }
        return null
    }

    val isPaired get() = prefs.pcUrl.isNotBlank() && prefs.pcToken.isNotBlank()

    /** Blocking. Call from a background thread. Returns null on success, or an error message. */
    fun pair(key: String): String? = runCatching {
        val url = prefs.pcUrl.ifBlank { return "Set the PC address first" }
        val r = client().newCall(Request.Builder().url("$url/auto-login?key=${key.trim().uppercase()}").build()).execute()
        val html = r.body?.string().orEmpty()
        val tok = Regex("jarvis_token','([^']+)'").find(html)?.groupValues?.get(1)
            ?: return "Key expired or wrong. Press Remote Control on the PC for a new one."
        prefs.pcToken = tok
        prefs.pcDeviceToken = Regex("jarvis_device_token','([^']+)'").find(html)?.groupValues?.get(1) ?: ""
        null
    }.getOrElse { "Could not reach the PC: ${it.message}" }

    /** Blocking. Returns true if the PC accepted the command. Re-logs in once if the token went stale. */
    fun command(text: String): Boolean {
        if (!isPaired) return false
        return runCatching {
            var code = post(text)
            if (code == 401 && refresh()) code = post(text)
            code == 200
        }.getOrDefault(false)
    }

    private fun post(text: String): Int {
        val body = JSONObject().put("text", text).toString().toRequestBody("application/json".toMediaType())
        val req = Request.Builder().url("${prefs.pcUrl}/api/command")
            .header("Authorization", "Bearer ${prefs.pcToken}").post(body).build()
        return client().newCall(req).execute().use { it.code }
    }

    private fun refresh(): Boolean {
        val dev = prefs.pcDeviceToken.ifBlank { return false }
        val body = JSONObject().put("device_token", dev).toString().toRequestBody("application/json".toMediaType())
        val r = client().newCall(Request.Builder().url("${prefs.pcUrl}/api/device-login").post(body).build()).execute()
        val j = JSONObject(r.body?.string().orEmpty())
        if (!j.optBoolean("ok")) return false
        prefs.pcToken = j.getString("token")
        return true
    }
}
