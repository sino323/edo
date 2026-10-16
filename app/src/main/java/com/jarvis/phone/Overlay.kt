package com.jarvis.phone

import android.content.Context
import android.graphics.PixelFormat
import android.view.Gravity
import android.view.WindowManager

/** Draws BubbleView over every app, at the bottom. Touches pass straight through to the app underneath. */
class Overlay(private val ctx: Context) {
    private val wm = ctx.getSystemService(Context.WINDOW_SERVICE) as WindowManager
    val view = BubbleView(ctx)
    private var shown = false

    fun show() {
        if (shown) return
        val type = WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY
        val lp = WindowManager.LayoutParams(
            WindowManager.LayoutParams.MATCH_PARENT,
            (170 * ctx.resources.displayMetrics.density).toInt(),
            type,
            WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE or
                WindowManager.LayoutParams.FLAG_NOT_TOUCHABLE or
                WindowManager.LayoutParams.FLAG_LAYOUT_IN_SCREEN,
            PixelFormat.TRANSLUCENT
        ).apply { gravity = Gravity.BOTTOM }
        wm.addView(view, lp)
        shown = true
    }

    fun hide() { if (shown) { runCatching { wm.removeView(view) }; shown = false } }
}
