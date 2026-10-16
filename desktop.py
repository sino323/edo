"""Jarvis desktop (Windows/macOS/Linux) -- run: python desktop.py"""
import sys, math, random, re, threading, time, html
from PyQt6.QtCore import Qt, QTimer, QObject, pyqtSignal, QPropertyAnimation
from PyQt6.QtGui import QPainter, QColor, QPen, QRadialGradient, QBrush
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLineEdit,
    QPushButton, QTextBrowser, QInputDialog, QDialog, QFormLayout, QCheckBox, QLabel)
from core import config
from core.engine import MarkLV

QSS = """
QWidget{background:#070b14;color:#d8e6ff;font:14px 'Segoe UI'}
QTextBrowser,QLineEdit{background:#0d1424;border:1px solid #1c2c4d;border-radius:12px;padding:10px}
QLineEdit:focus{border:1px solid #00e5ff}
QPushButton{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #00b8ff,stop:1 #7c4dff);
 color:white;border:none;border-radius:12px;padding:10px 18px;font-weight:600}
QPushButton:hover{background:#00e5ff;color:#001018}
QLabel#title{font:700 20px 'Segoe UI';color:#00e5ff}
"""

class Visualizer(QWidget):
    """Core + rings + waveform bars. States: idle / thinking / speaking."""
    def __init__(self):
        super().__init__()
        self.setMinimumHeight(240)
        self.state, self.level, self.t = "idle", 0.0, 0.0
        tm = QTimer(self); tm.timeout.connect(self.tick); tm.start(16)

    def tick(self):
        self.t += 0.016
        tg = {"speaking": 0.3 + 0.7 * abs(math.sin(self.t * 9) * math.sin(self.t * 2.3)) + random.random() * 0.15,
              "thinking": 0.35, "idle": 0.1 + 0.05 * math.sin(self.t * 2)}[self.state]
        self.level += (tg - self.level) * 0.2
        self.update()

    def paintEvent(self, _):
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        c = self.rect().center(); R = min(self.width(), self.height()) * 0.3; L = self.level
        g = QRadialGradient(c.x(), c.y(), R * (1.3 + L))
        g.setColorAt(0, QColor(0, 229, 255, int(120 + 100 * L))); g.setColorAt(1, QColor(124, 77, 255, 0))
        p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(g))
        p.drawEllipse(c, int(R * (1.3 + L)), int(R * (1.3 + L)))
        p.setBrush(Qt.BrushStyle.NoBrush)
        for i in range(3):
            r = R * (1 + 0.18 * i) * (1 + 0.12 * L * (i + 1))
            col = QColor(0, 229, 255) if i % 2 == 0 else QColor(124, 77, 255); col.setAlpha(230 - i * 60)
            p.setPen(QPen(col, 2 + L * 3))
            if self.state == "thinking":
                a = int((self.t * (200 + 80 * i)) % 360 * 16)
                p.drawArc(int(c.x() - r), int(c.y() - r), int(2 * r), int(2 * r), a, 100 * 16)
            else:
                p.drawEllipse(c, int(r), int(r))
        p.setPen(QPen(QColor(0, 229, 255, 200), 2))
        for k in range(72):
            a = k * math.tau / 72; r0 = R * 0.8
            amp = 4 + 28 * L * abs(math.sin(a * 5 + self.t * 6))
            p.drawLine(int(c.x() + math.cos(a) * r0), int(c.y() + math.sin(a) * r0),
                       int(c.x() + math.cos(a) * (r0 - amp)), int(c.y() + math.sin(a) * (r0 - amp)))
        p.end()

class Bridge(QObject):
    reply = pyqtSignal(str, bool)
    speak = pyqtSignal(bool)

class Settings(QDialog):
    def __init__(self, parent):
        super().__init__(parent); self.setWindowTitle("Jarvis Settings")
        cfg = config.load(); f = QFormLayout(self)
        self.key = QLineEdit(cfg["gemini_api_key"]); self.key.setEchoMode(QLineEdit.EchoMode.Password)
        self.model = QLineEdit(cfg["model"])
        self.voice = QCheckBox("Speak replies"); self.voice.setChecked(bool(cfg["voice"]))
        ok = QPushButton("Save changes"); ok.clicked.connect(self.accept)
        f.addRow("Gemini API Key", self.key); f.addRow("Model", self.model); f.addRow(self.voice); f.addRow(ok)

    def apply(self):
        config.save(gemini_api_key=self.key.text().strip(),
                    model=self.model.text().strip() or config.DEFAULTS["model"],
                    voice=self.voice.isChecked())

class Main(QWidget):
    def __init__(self):
        super().__init__(); self.setWindowTitle("Jarvis"); self.resize(560, 840)
        self.ai, self.br = MarkLV(), Bridge()
        self.br.reply.connect(self.on_reply)
        self.br.speak.connect(lambda s: setattr(self.viz, "state", "speaking" if s else "idle"))
        top = QHBoxLayout(); t = QLabel("MARK-LV"); t.setObjectName("title")
        gear = QPushButton("Settings"); gear.clicked.connect(self.settings)
        top.addWidget(t); top.addStretch(); top.addWidget(gear)
        self.viz, self.chat, self.inp = Visualizer(), QTextBrowser(), QLineEdit()
        self.inp.setPlaceholderText("Ask Jarvis anything..."); self.inp.returnPressed.connect(self.send)
        go = QPushButton("Send"); go.clicked.connect(self.send)
        row = QHBoxLayout(); row.addWidget(self.inp); row.addWidget(go)
        lay = QVBoxLayout(self); lay.addLayout(top); lay.addWidget(self.viz, 2); lay.addWidget(self.chat, 3); lay.addLayout(row)
        self.add("Jarvis", "Hey, I'm Jarvis 🤖✨ Your AI companion is online. What are we building today? 🚀", "#00e5ff")

    def add(self, who, text, col):
        self.chat.append(f'<p><b style="color:{col}">{who}</b><br>{html.escape(text).replace(chr(10), "<br>")}</p>')

    def settings(self):
        d = Settings(self)
        if d.exec(): d.apply()

    def send(self):
        t = self.inp.text().strip()
        if not t: return
        self.inp.clear(); self.add("You", t, "#9d7bff"); self.viz.state = "thinking"
        threading.Thread(target=self.work, args=(t,), daemon=True).start()

    def work(self, t):
        try: self.br.reply.emit(self.ai.ask(t), True)
        except Exception as e: self.br.reply.emit(str(e), False)

    def on_reply(self, text, ok):
        self.add("Jarvis", text, "#00e5ff")
        if ok and config.load()["voice"]: self.say(text)
        else: self.viz.state = "idle"

    def say(self, text):
        def run():
            self.br.speak.emit(True)
            try:
                import pyttsx3
                e = pyttsx3.init(); e.say(re.sub(r"[^\w\s.,!?'-]", "", text)); e.runAndWait()
            except Exception:
                time.sleep(min(len(text) / 15, 8))
            self.br.speak.emit(False)
        threading.Thread(target=run, daemon=True).start()

def main():
    app = QApplication(sys.argv); app.setStyleSheet(QSS)
    while not config.get_key():  # first-run setup
        k, ok = QInputDialog.getText(None, "Jarvis Setup", "Please enter your Gemini API Key",
                                     QLineEdit.EchoMode.Password)
        if not ok: sys.exit(0)
        if k.strip(): config.set_key(k)
    w = Main(); w.setWindowOpacity(0); w.show()
    w.anim = QPropertyAnimation(w, b"windowOpacity"); w.anim.setDuration(700)
    w.anim.setStartValue(0.0); w.anim.setEndValue(1.0); w.anim.start()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
