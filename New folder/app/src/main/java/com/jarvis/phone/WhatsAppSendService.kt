package com.jarvis.phone

import android.accessibilityservice.AccessibilityService
import android.view.accessibility.AccessibilityEvent
import android.view.accessibility.AccessibilityNodeInfo

/** Shared flag between JarvisService and the accessibility service (same process). */
object SendBridge {
    @Volatile var armedUntil = 0L
    @Volatile var onResult: ((Boolean) -> Unit)? = null
    fun arm(ms: Long, cb: (Boolean) -> Unit) { onResult = cb; armedUntil = System.currentTimeMillis() + ms }
    fun finish(ok: Boolean) { armedUntil = 0L; onResult?.invoke(ok); onResult = null }
}

/**
 * Android has no API to press "Send" in another app. An accessibility service is the one supported way.
 * It does NOTHING unless JarvisService armed it after you said yes, and it only looks at WhatsApp windows.
 */
class WhatsAppSendService : AccessibilityService() {

    override fun onAccessibilityEvent(e: AccessibilityEvent?) {
        if (System.currentTimeMillis() > SendBridge.armedUntil) return
        val root = rootInActiveWindow ?: return
        val pkg = root.packageName?.toString() ?: return
        if (pkg != "com.whatsapp" && pkg != "com.whatsapp.w4b") return

        val btn = root.findAccessibilityNodeInfosByViewId("$pkg:id/send").firstOrNull()
            ?: findByDescription(root, listOf("send", "إرسال", "ارسال"))
        var n: AccessibilityNodeInfo? = btn
        while (n != null && !n.isClickable) n = n.parent
        if (n != null && n.performAction(AccessibilityNodeInfo.ACTION_CLICK)) SendBridge.finish(true)
    }

    private fun findByDescription(node: AccessibilityNodeInfo, words: List<String>): AccessibilityNodeInfo? {
        val d = node.contentDescription?.toString()?.lowercase()
        if (d != null && words.any { d == it }) return node
        for (i in 0 until node.childCount) {
            val c = node.getChild(i) ?: continue
            findByDescription(c, words)?.let { return it }
        }
        return null
    }

    override fun onInterrupt() {}
}
