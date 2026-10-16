package com.jarvis.phone

import android.content.Context
import android.graphics.*
import android.text.Layout
import android.text.StaticLayout
import android.text.TextPaint
import android.view.View
import kotlin.math.abs
import kotlin.math.sin

/**
 * The thing from the sketch: a thin line across the bottom with a small "JARVIS" ring on it.
 *   asleep -> small ring, dim line          (SLEEP)
 *   awake  -> medium ring                   (AWAKE)
 *   talking (you or Jarvis) -> ring grows with the voice level
 */
class BubbleView(ctx: Context) : View(ctx) {
    enum class Mode { SLEEP, AWAKE }

    private val d = resources.displayMetrics.density
    private val accent = Color.parseColor("#00D8FF")
    private val line = Paint(Paint.ANTI_ALIAS_FLAG).apply { color = accent; strokeWidth = 1.5f * d }
    private val ring = Paint(Paint.ANTI_ALIAS_FLAG).apply { color = accent; style = Paint.Style.STROKE; strokeWidth = 2f * d }
    private val fill = Paint(Paint.ANTI_ALIAS_FLAG).apply { color = Color.argb(200, 6, 14, 24) }
    private val label = TextPaint(Paint.ANTI_ALIAS_FLAG).apply {
        color = accent; textAlign = Paint.Align.CENTER; textSize = 9f * d; typeface = Typeface.DEFAULT_BOLD
    }
    private val captionPaint = TextPaint(Paint.ANTI_ALIAS_FLAG).apply { color = Color.WHITE; textSize = 13f * d }

    private var mode = Mode.SLEEP
    private var level = 0f            // 0..1 voice level, set from mic RMS or TTS pulse
    private var radius = 14f * d
    private var caption = ""
    private var speakingPulse = false

    fun setMode(m: Mode) { mode = m; if (m == Mode.SLEEP) { caption = ""; level = 0f }; invalidate() }
    fun setLevel(l: Float) { level = l.coerceIn(0f, 1f) }
    fun setCaption(s: String) { caption = s; invalidate() }
    /** While Jarvis speaks we have no audio level, so fake a natural pulse. */
    fun setSpeaking(on: Boolean) { speakingPulse = on; if (!on) level = 0f }

    override fun onDraw(c: Canvas) {
        if (speakingPulse) level = 0.35f + 0.65f * abs(sin(System.nanoTime() / 1.6e8)).toFloat()

        val target = when (mode) {
            Mode.SLEEP -> 14f * d
            Mode.AWAKE -> (24f + 16f * level) * d
        }
        radius += (target - radius) * 0.18f                    // ease toward target

        val cx = width / 2f
        val cy = height - 34f * d
        line.alpha = if (mode == Mode.SLEEP) 70 else 190
        c.drawLine(0f, cy, width.toFloat(), cy, line)
        c.drawCircle(cx, cy, radius, fill)
        ring.alpha = if (mode == Mode.SLEEP) 120 else 255
        c.drawCircle(cx, cy, radius, ring)
        if (mode == Mode.AWAKE && level > 0.05f)               // soft halo while talking
            c.drawCircle(cx, cy, radius + 6f * d * level, ring.apply { alpha = 90 })
        if (radius > 18f * d) c.drawText("JARVIS", cx, cy + label.textSize / 3f, label)

        if (caption.isNotBlank() && mode == Mode.AWAKE) {
            val w = (width - 48 * d).toInt()
            val sl = StaticLayout.Builder.obtain(caption, 0, caption.length, captionPaint, w)
                .setAlignment(Layout.Alignment.ALIGN_CENTER).setMaxLines(3)
                .setEllipsize(android.text.TextUtils.TruncateAt.END).build()
            c.save()
            val top = cy - radius - 12f * d - sl.height
            c.drawRoundRect(RectF(12 * d, top - 8 * d, width - 12 * d, top + sl.height + 8 * d), 14 * d, 14 * d, fill)
            c.translate(24 * d, top)
            sl.draw(c)
            c.restore()
        }
        val settled = abs(radius - target) < 0.5f * d
        if (mode == Mode.AWAKE || speakingPulse || !settled) postInvalidateOnAnimation()
    }
}
