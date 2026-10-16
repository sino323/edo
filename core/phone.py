"""Android-only helpers: voice input, spoken replies, and phone actions.
Everything fails soft (returns a message) when not running on Android."""
import os, re
from urllib.parse import quote

ANDROID = "ANDROID_ARGUMENT" in os.environ or "ANDROID_PRIVATE" in os.environ
_AR = re.compile("[\u0600-\u06FF]")
_RC = 7001
_cb = None
_bound = False
_tts = None
_tts_ready = False

def _act():
    from jnius import autoclass
    return autoclass("org.kivy.android.PythonActivity").mActivity

def _start(intent):
    from jnius import autoclass
    intent.addFlags(autoclass("android.content.Intent").FLAG_ACTIVITY_NEW_TASK)
    _act().startActivity(intent)

# ---------------- voice input (built-in recognizer, no popup) ----------------
_sr = None
_sr_keep = None
mic_level = 0.0      # live 0..1 loudness, drives the head animation
last_error = 0       # last recognizer error code (6/7 = silence / no match, 9 = no permission)

def _fire(callback, text, err=0):
    global last_error, mic_level
    last_error, mic_level = err, 0.0
    from kivy.clock import Clock
    Clock.schedule_once(lambda dt: callback(text))

def _make_listener(callback):
    from jnius import PythonJavaClass, java_method, autoclass

    class _L(PythonJavaClass):
        __javainterfaces__ = ["android/speech/RecognitionListener"]
        __javacontext__ = "app"

        @java_method("(Landroid/os/Bundle;)V")
        def onReadyForSpeech(self, b): pass
        @java_method("()V")
        def onBeginningOfSpeech(self): pass
        @java_method("(F)V")
        def onRmsChanged(self, rms):
            global mic_level
            mic_level = max(0.0, min(1.0, (rms + 2) / 12.0))
        @java_method("([B)V")
        def onBufferReceived(self, buf): pass
        @java_method("()V")
        def onEndOfSpeech(self): pass
        @java_method("(Landroid/os/Bundle;)V")
        def onPartialResults(self, b): pass
        @java_method("(ILandroid/os/Bundle;)V")
        def onEvent(self, t, b): pass
        @java_method("(I)V")
        def onError(self, code):
            _fire(callback, None, int(code))
        @java_method("(Landroid/os/Bundle;)V")
        def onResults(self, b):
            text = None
            try:
                SR = autoclass("android.speech.SpeechRecognizer")
                lst = b.getStringArrayList(SR.RESULTS_RECOGNITION)
                if lst is not None and lst.size() > 0:
                    text = str(lst.get(0))
            except Exception:
                text = None
            _fire(callback, text, 0 if text else 7)
    return _L()

def listen(lang, callback) -> bool:
    """Listen inside the app. callback(text or None) runs on the Kivy thread."""
    if not ANDROID:
        return False
    try:
        from android.permissions import request_permissions, check_permission, Permission
        if not check_permission(Permission.RECORD_AUDIO):
            def _granted(perms, grants):
                if grants and all(grants):
                    listen(lang, callback)
                else:
                    _fire(callback, None, 9)
            request_permissions([Permission.RECORD_AUDIO], _granted)
            return True
        return _listen_builtin(lang, callback)
    except Exception:
        return _listen_dialog(lang, callback)

def _listen_builtin(lang, callback) -> bool:
    from android.runnable import run_on_ui_thread

    @run_on_ui_thread
    def go():
        global _sr, _sr_keep
        try:
            from jnius import autoclass
            SR = autoclass("android.speech.SpeechRecognizer")
            RI = autoclass("android.speech.RecognizerIntent")
            Intent = autoclass("android.content.Intent")
            if not SR.isRecognitionAvailable(_act()):
                if not _listen_dialog(lang, callback):
                    _fire(callback, None, 12)
                return
            if _sr is not None:
                try: _sr.destroy()
                except Exception: pass
            _sr_keep = _make_listener(callback)
            _sr = SR.createSpeechRecognizer(_act())
            _sr.setRecognitionListener(_sr_keep)
            i = Intent(RI.ACTION_RECOGNIZE_SPEECH)
            i.putExtra(RI.EXTRA_LANGUAGE_MODEL, RI.LANGUAGE_MODEL_FREE_FORM)
            i.putExtra(RI.EXTRA_LANGUAGE, lang)
            i.putExtra(RI.EXTRA_PARTIAL_RESULTS, True)
            i.putExtra(RI.EXTRA_MAX_RESULTS, 1)
            _sr.startListening(i)
        except Exception:
            _fire(callback, None, 5)
    go()
    return True

# fallback only: the old system dialog, used if the in-app recognizer is missing
_RC = 7001
_cb = None
_bound = False

def _listen_dialog(lang, callback) -> bool:
    global _cb, _bound
    try:
        from jnius import autoclass
        from android import activity
        Intent = autoclass("android.content.Intent")
        RI = autoclass("android.speech.RecognizerIntent")
        _cb = callback
        if not _bound:
            activity.bind(on_activity_result=_result)
            _bound = True
        i = Intent(RI.ACTION_RECOGNIZE_SPEECH)
        i.putExtra(RI.EXTRA_LANGUAGE_MODEL, RI.LANGUAGE_MODEL_FREE_FORM)
        i.putExtra(RI.EXTRA_LANGUAGE, lang)
        i.putExtra(RI.EXTRA_PROMPT, "Jarvis is listening")
        _act().startActivityForResult(i, _RC)
        return True
    except Exception:
        return False

def _result(request, result, intent):
    global _cb
    if request != _RC:
        return
    text = None
    try:
        if result == -1 and intent is not None:
            from jnius import autoclass
            RI = autoclass("android.speech.RecognizerIntent")
            lst = intent.getStringArrayListExtra(RI.EXTRA_RESULTS)
            if lst is not None and lst.size() > 0:
                text = str(lst.get(0))
    except Exception:
        text = None
    cb, _cb = _cb, None
    if cb:
        _fire(cb, text, 0 if text else 7)

# ---------------- spoken replies (native TextToSpeech) ----------------
def init_tts():
    global _tts
    if not ANDROID or _tts is not None:
        return
    try:
        from jnius import autoclass, PythonJavaClass, java_method

        class _Init(PythonJavaClass):
            __javainterfaces__ = ["android/speech/tts/TextToSpeech$OnInitListener"]
            __javacontext__ = "app"

            @java_method("(I)V")
            def onInit(self, status):
                global _tts_ready
                _tts_ready = (status == 0)

        TTS = autoclass("android.speech.tts.TextToSpeech")
        init = _Init()
        _tts = TTS(_act(), init)
        _tts._keep = init  # keep the listener alive
    except Exception:
        _tts = None

def speak(text) -> bool:
    """Speak with the phone's TTS in Arabic or English. False = caller should fall back."""
    if not (ANDROID and _tts is not None and _tts_ready):
        return False
    try:
        from jnius import autoclass
        Locale = autoclass("java.util.Locale")
        _tts.setLanguage(Locale("ar", "EG") if _AR.search(text) else Locale.US)
        _tts.speak(text[:3500], 0, None, "jarvis")
        return True
    except Exception:
        return False

def is_speaking() -> bool:
    try:
        return bool(_tts.isSpeaking())
    except Exception:
        return False

def stop():
    try:
        _tts.stop()
    except Exception:
        pass
    if ANDROID and _sr is not None:
        try:
            from android.runnable import run_on_ui_thread
            @run_on_ui_thread
            def _c():
                try: _sr.cancel()
                except Exception: pass
            _c()
        except Exception:
            pass

# ---------------- phone actions (called by Gemini tools) ----------------
APPS = {"whatsapp": "com.whatsapp", "youtube": "com.google.android.youtube",
        "spotify": "com.spotify.music", "chrome": "com.android.chrome",
        "maps": "com.google.android.apps.maps", "gmail": "com.google.android.gm",
        "telegram": "org.telegram.messenger", "messenger": "com.facebook.orca",
        "facebook": "com.facebook.katana", "instagram": "com.instagram.android",
        "netflix": "com.netflix.mediaclient", "settings": "com.android.settings"}

def _launch_pkg(pm, pkg):
    it = pm.getLaunchIntentForPackage(pkg)
    if it is None:
        return False
    _start(it)
    return True

def open_app(name):
    from jnius import autoclass
    name = (name or "").strip().lower()
    pm = _act().getPackageManager()
    if name in APPS and _launch_pkg(pm, APPS[name]):
        return "opened " + name
    apps = pm.getInstalledApplications(0)
    for k in range(apps.size()):
        ai = apps.get(k)
        if name and name in str(pm.getApplicationLabel(ai)).lower():
            if _launch_pkg(pm, str(ai.packageName)):
                return "opened " + name
    return "could not find an app called " + name

def open_url(url):
    from jnius import autoclass
    Intent, Uri = autoclass("android.content.Intent"), autoclass("android.net.Uri")
    _start(Intent(Intent.ACTION_VIEW, Uri.parse(url)))
    return "opened"

def wake_pc() -> str:
    """Wake-on-LAN: send the magic packet straight from Jarvis (what Wolow's power button does)."""
    import socket, re as _re
    from . import config
    mac = _re.sub(r"[^0-9a-fA-F]", "", config.get_pc_mac())
    if len(mac) != 12:
        if ANDROID:
            try:
                return "No PC MAC address saved (Settings > PC MAC). " + open_app("wolow") + " - press the power button there."
            except Exception:
                pass
        return "No PC MAC address saved. Add it in Settings (PC MAC)."
    pkt = b"\xff" * 6 + bytes.fromhex(mac) * 16
    targets = {("255.255.255.255", 9), ("255.255.255.255", 7)}
    try:  # also the subnet broadcast (e.g. 192.168.1.255), which some routers need
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80)); ip = s.getsockname()[0]; s.close()
        b = ip.rsplit(".", 1)[0] + ".255"
        targets |= {(b, 9), (b, 7)}
    except Exception:
        pass
    sent = 0
    for host, port in targets:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            for _ in range(3):
                s.sendto(pkt, (host, port)); sent += 1
            s.close()
        except Exception:
            pass
    return "wake packet sent to your PC" if sent else "could not send the wake packet (check Wi-Fi)"

def run(name, a) -> str:
    if name == "wake_pc":
        return wake_pc()
    if not ANDROID:
        return "Phone actions only work in the Android app."
    from jnius import autoclass
    Intent, Uri = autoclass("android.content.Intent"), autoclass("android.net.Uri")
    try:
        if name == "open_app":
            return open_app(a.get("name"))
        if name == "open_url":
            return open_url(a.get("url", ""))
        if name == "web_search":
            return open_url("https://www.google.com/search?q=" + quote(a.get("query", "")))
        if name == "call_number":
            _start(Intent(Intent.ACTION_DIAL, Uri.parse("tel:" + str(a.get("number", "")))))
            return "dialer opened (user must press call)"
        if name == "set_timer":
            i = Intent("android.intent.action.SET_TIMER")
            i.putExtra("android.intent.extra.alarm.LENGTH", int(a.get("seconds", 60)))
            i.putExtra("android.intent.extra.alarm.MESSAGE", str(a.get("label", "Jarvis")))
            i.putExtra("android.intent.extra.alarm.SKIP_UI", True)
            _start(i)
            return "timer set"
        if name == "set_alarm":
            i = Intent("android.intent.action.SET_ALARM")
            i.putExtra("android.intent.extra.alarm.HOUR", int(a.get("hour", 0)))
            i.putExtra("android.intent.extra.alarm.MINUTES", int(a.get("minute", 0)))
            i.putExtra("android.intent.extra.alarm.MESSAGE", str(a.get("label", "Jarvis")))
            i.putExtra("android.intent.extra.alarm.SKIP_UI", True)
            _start(i)
            return "alarm set"
        if name == "open_settings":
            page = {"bluetooth": "android.settings.BLUETOOTH_SETTINGS",
                    "wifi": "android.settings.WIFI_SETTINGS"}.get(
                        str(a.get("page", "")).lower(), "android.settings.SETTINGS")
            _start(Intent(page))
            return "settings opened"
    except Exception as e:
        return "failed: %s" % e
    return "unknown action"

# ---------------- stats for the HUD ----------------
def battery():
    """Battery percent, or None."""
    if not ANDROID:
        return None
    try:
        from jnius import autoclass
        IF, It = autoclass("android.content.IntentFilter"), autoclass("android.content.Intent")
        i = _act().registerReceiver(None, IF(It.ACTION_BATTERY_CHANGED))
        lv, sc = i.getIntExtra("level", -1), i.getIntExtra("scale", 100)
        return int(100 * lv / sc) if lv >= 0 and sc > 0 else None
    except Exception:
        return None

def net_bytes():
    """Total rx+tx bytes since boot, or None."""
    if not ANDROID:
        return None
    try:
        from jnius import autoclass
        TS = autoclass("android.net.TrafficStats")
        a, b = TS.getTotalRxBytes(), TS.getTotalTxBytes()
        return a + b if a >= 0 and b >= 0 else None
    except Exception:
        return None
