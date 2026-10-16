package com.jarvis.phone

/** Arabic/English text helpers so "بابا", "baba", "أمي" etc. all match one way. */
object Text {
    private val tashkeel = Regex("[\\u064B-\\u0652\\u0640]")

    fun norm(s: String): String = s.lowercase()
        .replace(tashkeel, "")
        .replace(Regex("[أإآٱ]"), "ا")
        .replace('ى', 'ي')
        .replace('ة', 'ه')
        .replace(Regex("[\\p{Punct}،؟؛!]"), " ")
        .replace(Regex("\\s+"), " ")
        .trim()

    fun hasArabic(s: String) = s.any { it in '\u0600'..'\u06FF' }

    // Built-in wake phrases, normalised. Recognisers spell "hey bro" many ways.
    val defaultWake = listOf(
        "hey bro", "hay bro", "hi bro", "hey brother", "hey brow", "hey bra",
        "هاي برو", "هي برو", "هاى برو", "يا برو", "هاي بيرو", "هاي برا"
    )

    /** Returns the text AFTER the wake phrase, or null if the phrase is absent. Whole words only. */
    fun afterWake(text: String, extra: String): String? {
        val t = " " + norm(text) + " "
        val phrases = (defaultWake + extra.split(',')).map { norm(it) }.filter { it.isNotBlank() }.distinct()
        var bestStart = -1
        var bestEnd = -1
        for (p in phrases) {
            val needle = " $p "
            val i = t.indexOf(needle)
            if (i < 0) continue
            val e = i + needle.length
            if (bestStart < 0 || i < bestStart || (i == bestStart && e > bestEnd)) { bestStart = i; bestEnd = e }
        }
        if (bestStart < 0) return null
        return t.substring(bestEnd - 1).trim()
    }

    private val stopTail = Regex("(?:^|\\s)(?:stop|استوب|ستوب|ستوپ|استب)$")
    /** Returns the dictated text without the trailing stop word, or null if the user did not say stop. */
    fun stripStop(text: String): String? {
        val t = norm(text)
        val m = stopTail.find(t) ?: return null
        return t.substring(0, m.range.first).trim()
    }

    val yes = Regex("(?:^|\\s)(yes|yeah|yep|send|ok|okay|confirm|sure|ايوه|ايوا|ايوة|اه|نعم|ابعت|ارسل|ابعتها|تمام|اوكي|ماشي)(?:\\s|$)")
    val no = Regex("(?:^|\\s)(no|nope|cancel|dont|لا|الغاء|كانسل|بلاش|متبعتش|لاء)(?:\\s|$)")
    val cancel = Regex("^(cancel|الغاء|كانسل|بلاش)$")

    /** Whole-word match, allowing the Arabic prefixes ل / ب ("ابعت لبابا"). */
    private fun word(alts: String) = Regex("(?:^|\\s)(?:ل|ب)?(?:" + alts + ")(?:\\s|$)")

    val sleepCmd = Regex("(?:^|\\s)(go to sleep|sleep|نام|اسكت|روح نام)(?:\\s|$)")
    val babaWords = word("بابا|baba|dad|daddy|father|papa|ابويا|والدي")
    val mamaWords = word("ماما|mama|mom|mum|mother|امي|والدتي|مامي")
    val msgVerb = Regex("(text|message|msg|send|whatsapp|whats app|واتس|ابعت|ابعث|ارسل|رساله|رسالة|كلم|بعت)")
}
