"""Jarvis mobile (Kivy) - HUD interface. Android entry point for buildozer; also runs on desktop."""
import os, re, math, random, threading, time
from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import Color, Line, Ellipse, Rectangle, RoundedRectangle, Mesh
from kivy.metrics import dp
from kivy.properties import StringProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.widget import Widget
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.utils import escape_markup

try:  # Arabic shaping + right-to-left ordering (Kivy does neither by itself)
    import arabic_reshaper
    from bidi.algorithm import get_display
except Exception:
    arabic_reshaper = None

BG = (0.012, 0.027, 0.078, 1)
PANEL = (0.0, 0.065, 0.095, 1)
EDGE = (0.0, 0.33, 0.43, 1)
CYAN, YELLOW, GREEN, RED, ORANGE = (0, .9, 1), (1, .78, 0), (0, 1, .5), (1, .22, .32), (1, .55, 0)
Window.clearcolor = BG
EMO = re.compile("([\U0001F300-\U0001FAFF\u2600-\u27BF\u2B50\uFE0F\u200D]+)")
AR = re.compile("[\u0600-\u06FF\u0750-\u077F\uFB50-\uFDFF\uFE70-\uFEFF]")
EMOJI_FONT = "assets/NotoEmoji-Regular.ttf"  # optional; without it emojis are hidden
HERE = os.path.dirname(os.path.abspath(__file__))
FONT = os.path.join(HERE, "assets", "DejaVuSans.ttf")  # Latin + Arabic glyphs
if not os.path.exists(FONT):
    FONT = None

def fkw():
    return {"font_name": FONT} if FONT else {}

def hx(c):
    return "%02x%02x%02x" % tuple(int(v * 255) for v in c[:3])

def shape(s):
    if not arabic_reshaper or not AR.search(s):
        return s
    return "\n".join(get_display(arabic_reshaper.reshape(l)) if AR.search(l) else l
                     for l in s.split("\n"))

def mk(s):
    s = escape_markup(shape(s))
    return EMO.sub(r"[font=%s]\1[/font]" % EMOJI_FONT, s) if os.path.exists(EMOJI_FONT) else EMO.sub("", s)

# ---------------------------------------------------------------- HUD widgets
class Panel(BoxLayout):
    def __init__(self, border=EDGE, fill=PANEL, **kw):
        super().__init__(**kw)
        with self.canvas.before:
            Color(*fill); self._bg = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(5)])
            Color(*border); self._ln = Line(rounded_rectangle=(self.x, self.y, self.width, self.height, dp(5)), width=1)
        self.bind(pos=self._u, size=self._u)

    def _u(self, *_):
        self._bg.pos, self._bg.size = self.pos, self.size
        self._ln.rounded_rectangle = (self.x, self.y, self.width, self.height, dp(5))

class HudButton(Button):
    def __init__(self, tint=CYAN, **kw):
        super().__init__(background_normal="", background_down="", bold=True, color=(*tint, 1),
                         background_color=(tint[0] * .13, tint[1] * .13, tint[2] * .13, 1), **fkw(), **kw)
        with self.canvas.after:
            Color(*tint, .9); self._ln = Line(rounded_rectangle=(self.x, self.y, self.width, self.height, dp(5)), width=1.2)
        self.bind(pos=self._u, size=self._u)

    def _u(self, *_):
        self._ln.rounded_rectangle = (self.x, self.y, self.width, self.height, dp(5))

class Bar(Widget):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.frac, self.color = 0.0, CYAN
        self.bind(pos=self.draw, size=self.draw)

    def draw(self, *_):
        self.canvas.clear()
        with self.canvas:
            Color(1, 1, 1, .08); Rectangle(pos=self.pos, size=self.size)
            Color(*self.color, 1)
            Rectangle(pos=self.pos, size=(self.width * max(0, min(1, self.frac)), self.height))

class Tile(Panel):
    def __init__(self, name, **kw):
        super().__init__(orientation="vertical", padding=(dp(6), dp(3)), spacing=dp(2), **kw)
        self.name = name
        self.lab = Label(markup=True, font_size="11sp", halign="left", valign="middle", **fkw())
        self.lab.bind(size=lambda w, _: setattr(w, "text_size", w.size))
        self.bar = Bar(size_hint_y=None, height=dp(4))
        self.add_widget(self.lab); self.add_widget(self.bar)

    def set(self, text, frac, color):
        self.lab.text = "[color=7fb8c8]%s[/color]\n[b][color=%s]%s[/color][/b]" % (self.name, hx(color), text)
        self.bar.frac, self.bar.color = frac, color
        self.bar.draw()

# ---------------------------------------------------------------- holographic head
from core.headmesh import build_head, eye_points, mouth_points
V, TRIS, NRING, ORDER = build_head()
EYES, MOUTH = eye_points(), mouth_points()
NB = 8
LIGHT = (-0.35, 0.45, 0.82)
_ll = math.sqrt(sum(x * x for x in LIGHT)); LIGHT = tuple(x / _ll for x in LIGHT)
STATES = {"idle": ("IDLE", CYAN), "thinking": ("THINKING", YELLOW),
          "listening": ("LISTENING", GREEN), "speaking": ("SPEAKING", CYAN)}

def _mic_level():
    try:
        from core import phone
        return phone.mic_level
    except Exception:
        return 0.0

class Head(Widget):
    state = StringProperty("idle")

    def __init__(self, **kw):
        super().__init__(**kw)
        self.level, self.t = 0.0, 0.0
        Clock.schedule_interval(self.tick, 1 / 20)

    def tick(self, dt):
        self.t += dt
        t, st = self.t, self.state
        tg = {"speaking": .3 + .7 * abs(math.sin(t * 9) * math.sin(t * 2.3)) + random.random() * .15,
              "thinking": .35, "listening": .15 + .85 * max(_mic_level(), .15 * abs(math.sin(t * 5))),
              "idle": .06 + .04 * math.sin(t * 2)}.get(st, .1)
        self.level += (tg - self.level) * .25
        if self.width < 10 or self.height < 10:
            return
        cx, cy = self.center_x, self.center_y
        s = min(self.height * .36, self.width * .46)
        a = .45 * math.sin(t * .7)
        ca, sa = math.cos(a), math.sin(a)
        pv, zr, flat = [], [], []
        for x, y, z in V:
            X = cx + (x * ca + z * sa) * s
            Y = cy + (y + .14) * s + self.height * .03
            pv.append((X, Y)); zr.append(-x * sa + z * ca)
            flat += [X, Y, 0, 0]
        bins = [[] for _ in range(NB)]
        for ia, ib, ic, nx, ny, nz, jt in TRIS:
            nzr = -nx * sa + nz * ca
            if nzr <= 0:
                continue
            nxr = nx * ca + nz * sa
            d = nxr * LIGHT[0] + ny * LIGHT[1] + nzr * LIGHT[2]
            sh = .22 + .78 * (d if d > 0 else 0) + jt
            b = int(sh * NB)
            bins[0 if b < 0 else (NB - 1 if b >= NB else b)] += (ia, ib, ic)
        self.canvas.clear()
        with self.canvas:
            Color(0, .5, .7, .06)
            Ellipse(pos=(cx - s * 1.1, cy - s * 1.1), size=(s * 2.2, s * 2.2))
            for b in range(NB):
                if bins[b]:
                    f = (b + .5) / NB
                    Color(0, .2 + .55 * f, .28 + .55 * f, 1)
                    Mesh(vertices=flat, indices=bins[b], mode="triangles")
            # hologram contour lines
            Color(0, .9, 1, .22)
            for k in range(1, 15):
                pts = []
                for j in ORDER:
                    i = k * NRING + j
                    if zr[i] > .02:
                        pts += [pv[i][0], pv[i][1]]
                if len(pts) >= 4:
                    Line(points=pts, width=1)
            # eyes
            for (x, y, z) in EYES:
                if -x * sa + z * ca > .05:
                    X, Y = cx + (x * ca + z * sa) * s, cy + (y + .14) * s + self.height * .03
                    Color(*CYAN, .8); Line(ellipse=(X - s * .13, Y - s * .045, s * .26, s * .09), width=1.2)
                    Color(1, .75, 0, .25); Ellipse(pos=(X - s * .07, Y - s * .07), size=(s * .14, s * .14))
                    Color(1, .8, 0, 1); Ellipse(pos=(X - s * .03, Y - s * .03), size=(s * .06, s * .06))
            # mouth (opens with speech level)
            gap = self.level * s * .12 if st in ("speaking",) else s * .01
            Color(0, .1, .15, 1)
            up, lo = [], []
            for (x, y, z) in MOUTH:
                if -x * sa + z * ca > .05:
                    X, Y = cx + (x * ca + z * sa) * s, cy + (y + .14) * s + self.height * .03
                    up += [X, Y + gap * .5]; lo += [X, Y - gap * .5]
            if len(up) >= 4:
                Color(0, .05, .08, 1); Line(points=up + lo[::-1], width=1.2, close=True)
                Color(*CYAN, .9); Line(points=up, width=1.1); Line(points=lo, width=1.1)
            # waveform
            n = 46; bw = self.width * .8 / n; x0 = cx - n * bw / 2
            Color(0, .55, .72, .9)
            for i in range(n):
                amp = .05 + self.level * abs(math.sin(t * 6 + i * .5) * math.sin(i * .31 + t))
                Rectangle(pos=(x0 + i * bw, self.y + self.height * .02), size=(bw * .7, 2 + amp * self.height * .12))

# ---------------------------------------------------------------- app
class JarvisApp(App):
    title = "Jarvis"

    def build(self):
        os.environ["JARVIS_HOME"] = self.user_data_dir
        from core import config, memory, phone
        from core.engine import Jarvis
        self.cfg, self.ai, self.phone = config, Jarvis(), phone
        self.voice_chat, self.busy, self.req_id, self.mic_retry = False, False, 0, 0
        self.t0, self._net = time.time(), None
        phone.init_tts()
        memory.load()  # seeds long-term memory on first run

        root = BoxLayout(orientation="vertical", padding=dp(8), spacing=dp(6))

        # header: MARK LV + gear | JARVIS | clock
        head = BoxLayout(size_hint_y=None, height=dp(54), spacing=dp(4))
        left = BoxLayout(spacing=dp(4), size_hint_x=.34)
        left.add_widget(Label(text="MARK LV", font_size="10sp", color=(.2, .55, .65, 1), **fkw()))
        left.add_widget(HudButton(text="SET", size_hint_x=None, width=dp(42), font_size="11sp",
                                  on_release=lambda *_: self.ask_key()))
        mid = BoxLayout(orientation="vertical", size_hint_x=.4)
        mid.add_widget(Label(text="JARVIS", bold=True, font_size="24sp", color=(*CYAN, 1), **fkw()))
        mid.add_widget(Label(text="A Friendly Assistant", font_size="9sp", color=(.2, .6, .7, 1),
                             size_hint_y=.5, **fkw()))
        self.clock = Label(font_size="11sp", color=(*CYAN, 1), halign="right", size_hint_x=.3,
                           markup=True, **fkw())
        self.clock.bind(size=lambda w, _: setattr(w, "text_size", w.size))
        head.add_widget(left); head.add_widget(mid); head.add_widget(self.clock)
        root.add_widget(head)

        # system monitor tiles
        row = BoxLayout(size_hint_y=None, height=dp(50), spacing=dp(5))
        self.t_bat, self.t_mem, self.t_net, self.t_up = Tile("BAT"), Tile("MEM"), Tile("NET"), Tile("UP")
        for t in (self.t_bat, self.t_mem, self.t_net, self.t_up):
            row.add_widget(t)
        root.add_widget(row)

        # head panel
        hp = Panel(orientation="vertical", size_hint_y=.46, padding=dp(2))
        self.ring = Head()
        self.ring.bind(state=self._on_state)
        hp.add_widget(self.ring)
        self.status = Label(markup=True, size_hint_y=None, height=dp(26), font_size="14sp", bold=True, **fkw())
        hp.add_widget(self.status)
        root.add_widget(hp)
        self._on_state(self.ring, "idle")

        # status chips
        chips = BoxLayout(size_hint_y=None, height=dp(24), spacing=dp(5))
        for txt, col in (("AI CORE ACTIVE", GREEN), ("SEC CLEARED", GREEN), ("PROTOCOL LV", (.3, .65, .75))):
            p = Panel(padding=(dp(2), 0))
            p.add_widget(Label(text=txt, font_size="9sp", bold=True, color=(*col, 1), **fkw()))
            chips.add_widget(p)
        root.add_widget(chips)

        # activity log
        lp = Panel(orientation="vertical", size_hint_y=.36, padding=dp(6), spacing=dp(2))
        lp.add_widget(Label(text="\u25b8 ACTIVITY LOG", font_size="10sp", color=(.35, .8, .9, 1), size_hint_y=None,
                            height=dp(16), halign="left", **fkw()))
        lp.children[0].bind(size=lambda w, _: setattr(w, "text_size", w.size))
        self.log = Label(markup=True, size_hint_y=None, halign="left", valign="top", font_size="13sp", **fkw())
        self.log.bind(width=lambda *_: setattr(self.log, "text_size", (self.log.width, None)),
                      texture_size=lambda *_: setattr(self.log, "height", self.log.texture_size[1]))
        self.sv = ScrollView(); self.sv.add_widget(self.log); lp.add_widget(self.sv)
        root.add_widget(lp)

        # command input
        inrow = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(5))
        self.inp = TextInput(hint_text="Type a command or question...", multiline=False, on_text_validate=self.send,
                             background_normal="", background_active="", background_color=PANEL,
                             foreground_color=(*CYAN, 1), hint_text_color=(.2, .5, .6, 1),
                             cursor_color=(*CYAN, 1), padding=(dp(8), dp(12)), **fkw())
        inrow.add_widget(self.inp)
        inrow.add_widget(HudButton(text="\u25ba", size_hint_x=None, width=dp(48), on_release=self.send))
        root.add_widget(inrow)

        # interrupt / microphone
        brow = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(6))
        brow.add_widget(HudButton(tint=RED, text="INTERRUPT", font_size="12sp", on_release=lambda *_: self.interrupt()))
        brow.add_widget(HudButton(tint=GREEN, text="MICROPHONE", font_size="12sp", on_release=lambda *_: self.mic()))
        root.add_widget(brow)

        # voice chat / language
        trow = BoxLayout(size_hint_y=None, height=dp(34), spacing=dp(6))
        self.vc_btn = HudButton(text="VOICE CHAT: OFF", font_size="10sp", on_release=lambda *_: self.set_vc(not self.voice_chat))
        self.lang_btn = HudButton(text=self._lang_label(), font_size="10sp", size_hint_x=.5, on_release=lambda *_: self.toggle_lang())
        trow.add_widget(self.vc_btn); trow.add_widget(self.lang_btn)
        root.add_widget(trow)

        Clock.schedule_interval(self.tick_clock, 1); self.tick_clock(0)
        Clock.schedule_interval(self.tick_stats, 2); Clock.schedule_once(self.tick_stats, .5)
        who = self.cfg.get_user_name() or "sir"
        self.add("Jarvis", f"Jarvis online. At your service, {who}.", "00e5ff")
        return root

    # ----- HUD updates
    def _on_state(self, w, st):
        name, col = STATES.get(st, STATES["idle"])
        self.status.text = "[color=%s]\u25c7  %s[/color]" % (hx(col), name)

    def tick_clock(self, dt):
        self.clock.text = "[b]%s[/b]\n[size=9sp]%s[/size]" % (time.strftime("%H:%M:%S"), time.strftime("%a %d %b %Y"))

    def tick_stats(self, dt):
        b = self.phone.battery()
        self.t_bat.set("N/A" if b is None else "%d%%" % b, (b or 0) / 100, GREEN if (b or 0) >= 30 else RED)
        try:
            m = {}
            for ln in open("/proc/meminfo"):
                k, v = ln.split(":")[:2]; m[k] = int(v.split()[0])
            used = 1 - m["MemAvailable"] / m["MemTotal"]
            self.t_mem.set("%d%%" % (used * 100), used, YELLOW)
        except Exception:
            self.t_mem.set("N/A", 0, YELLOW)
        nb, now = self.phone.net_bytes(), time.time()
        if nb is not None and self._net:
            kb = max(0, (nb - self._net[0]) / 1024 / max(now - self._net[1], .1))
            self.t_net.set("%dKB/s" % kb, min(kb / 1024, 1), GREEN)
        else:
            self.t_net.set("N/A" if nb is None else "0KB/s", 0, GREEN)
        if nb is not None:
            self._net = (nb, now)
        up = int(now - self.t0)
        self.t_up.set("%02d:%02d" % ((up // 3600, up // 60 % 60) if up >= 3600 else (up // 60, up % 60)),
                      (up % 60) / 60, ORANGE)

    # ----- chat
    def on_start(self):
        if not self.cfg.get_key():
            self.ask_key(first=True)

    def add(self, who, text, col):
        self.log.text += f"[color={col}][b]{who}[/b][/color]\n{mk(text)}\n\n"
        Clock.schedule_once(lambda dt: setattr(self.sv, "scroll_y", 0), .1)

    def ask_key(self, first=False):
        ki = TextInput(text="" if first else self.cfg.get_key(), password=True, multiline=False,
                       hint_text="Gemini API Key", size_hint_y=None, height=dp(48))
        ni = TextInput(text=self.cfg.get_user_name(), multiline=False,
                       hint_text="Your name (how Jarvis addresses you)", size_hint_y=None, height=dp(48), **fkw())
        mi = TextInput(text=self.cfg.get_model(), multiline=False,
                       hint_text="Model (leave empty = automatic)", size_hint_y=None, height=dp(48), **fkw())
        pi = TextInput(text=self.cfg.get_pc_mac(), multiline=False,
                       hint_text="PC MAC address (AA:BB:CC:DD:EE:FF) for 'open PC'", size_hint_y=None, height=dp(48))
        def ok(*_):
            if ki.text.strip():
                self.cfg.set_pc_mac(pi.text)
                self.cfg.set_key(ki.text)
                self.cfg.set_user_name(ni.text)
                self.cfg.set_model(mi.text)
                self.ai.dead.clear(); self.ai.good = None
                pop.dismiss()
        box = BoxLayout(orientation="vertical", spacing=dp(8), padding=dp(10))
        box.add_widget(ki); box.add_widget(ni); box.add_widget(mi); box.add_widget(pi)
        box.add_widget(Button(text="Save", size_hint_y=None, height=dp(48), on_release=ok))
        pop = Popup(title="Jarvis Setup" if first else "Settings", content=box,
                    size_hint=(.92, .75), auto_dismiss=not first)
        pop.open()

    # ----- voice
    def _lang_label(self):
        return "SPEECH: " + ("AR" if self.cfg.get_lang().startswith("ar") else "EN")

    def toggle_lang(self):
        self.cfg.set_lang("en-US" if self.cfg.get_lang().startswith("ar") else "ar-EG")
        self.lang_btn.text = self._lang_label()

    def set_vc(self, on):
        self.voice_chat = on
        self.vc_btn.text = "VOICE CHAT: ON" if on else "VOICE CHAT: OFF"
        if on and not self.busy:
            self.mic()

    def interrupt(self):
        self.req_id += 1; self.busy = False
        self.phone.stop(); Clock.unschedule(self._poll)
        self.ring.state = "idle"; self.set_vc(False)

    def mic(self):
        if self.busy:
            return
        self.phone.stop(); Clock.unschedule(self._poll)
        self.ring.state = "listening"
        if not self.phone.listen(self.cfg.get_lang(), self.heard):
            self.ring.state = "idle"; self.set_vc(False)
            self.add("Jarvis", "Voice input needs the Android app with Google speech services.", "00e5ff")

    def heard(self, text):
        if text:
            self.mic_retry = 0
            self.submit(text)
            return
        err = getattr(self.phone, "last_error", 0)
        self.ring.state = "idle"
        if self.voice_chat and err in (6, 7) and self.mic_retry < 4:  # silence: keep listening
            self.mic_retry += 1
            Clock.schedule_once(lambda dt: self.mic() if self.voice_chat and not self.busy else None, .6)
            return
        self.set_vc(False)
        if err == 9:
            self.add("Jarvis", "Microphone permission is off. Allow Microphone for Jarvis in Android settings.", "00e5ff")
        elif err not in (0, 6, 7):
            self.add("Jarvis", "Speech recognition error (%d). Check internet or install a speech language pack." % err, "00e5ff")

    def send(self, *_):
        t = self.inp.text.strip()
        if t:
            self.inp.text = ""
            self.submit(t)

    def submit(self, t):
        self.req_id += 1; rid = self.req_id
        self.add("You", t, "9d7bff"); self.ring.state = "thinking"; self.busy = True
        threading.Thread(target=self.work, args=(t, rid), daemon=True).start()

    def work(self, t, rid):
        try: r, ok = self.ai.ask(t), True
        except Exception as e: r, ok = str(e), False
        Clock.schedule_once(lambda dt: self.done(r, ok, rid))

    def done(self, r, ok, rid):
        if rid != self.req_id:  # interrupted
            return
        self.busy = False
        self.add("Jarvis", r, "00e5ff")
        if not ok:
            self.ring.state = "idle"; self.set_vc(False)
            return
        self.ring.state = "speaking"
        if self.phone.speak(r):  # native TTS (Arabic or English), poll until it finishes
            Clock.schedule_once(lambda dt: Clock.schedule_interval(self._poll, .4), 1.0)
            return
        try:
            from plyer import tts
            tts.speak(EMO.sub("", r))
        except Exception:
            pass
        Clock.schedule_once(lambda dt: self._finished(), min(len(r) / 14, 10))

    def _poll(self, dt):
        if self.phone.is_speaking():
            return True
        self._finished()
        return False

    def _finished(self):
        self.ring.state = "idle"
        if self.voice_chat and not self.busy:
            self.mic()

if __name__ == "__main__":
    try:
        JarvisApp().run()
    except Exception:
        import traceback
        err = traceback.format_exc()

        class ErrApp(App):
            def build(self):
                return Label(text=err, font_size="11sp", halign="left",
                             valign="top", text_size=(Window.width - 20, None))
        ErrApp().run()
