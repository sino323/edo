package com.jarvis.phone

import android.content.Context

/** All settings live here. Phone numbers are digits only, international format (e.g. 201001234567). */
class Prefs(ctx: Context) {
    private val sp = ctx.getSharedPreferences("jarvis_phone", Context.MODE_PRIVATE)

    var babaNumber: String
        get() = sp.getString("baba", "") ?: ""
        set(v) = sp.edit().putString("baba", v.filter { it.isDigit() }).apply()

    var mamaNumber: String
        get() = sp.getString("mama", "") ?: ""
        set(v) = sp.edit().putString("mama", v.filter { it.isDigit() }).apply()

    /** Speech recognition language. ar-EG hears Arabic; set en-US if you mostly speak English. */
    var language: String
        get() = sp.getString("lang", "ar-EG") ?: "ar-EG"
        set(v) = sp.edit().putString("lang", v.ifBlank { "ar-EG" }).apply()

    /** Extra wake phrases, comma separated, added to the built-in "hey bro" list. */
    var extraWake: String
        get() = sp.getString("wake", "") ?: ""
        set(v) = sp.edit().putString("wake", v).apply()

    var pcUrl: String
        get() = sp.getString("pc_url", "") ?: ""
        set(v) = sp.edit().putString("pc_url", v.trim().trimEnd('/')).apply()

    var pcToken: String
        get() = sp.getString("pc_token", "") ?: ""
        set(v) = sp.edit().putString("pc_token", v).apply()

    var pcDeviceToken: String
        get() = sp.getString("pc_dev", "") ?: ""
        set(v) = sp.edit().putString("pc_dev", v).apply()
}
