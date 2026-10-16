"""Jarvis settings (API key, names). Stored as JSON in the app's private data dir."""
import json
import os

DEFAULT_MODEL = "gemini-3.8-flash"

def _path():
    return os.path.join(os.environ.get("JARVIS_HOME", "."), "config.json")

def _load():
    try:
        with open(_path(), "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def _patch(**kw):
    d = _load()
    d.update(kw)
    os.makedirs(os.path.dirname(_path()) or ".", exist_ok=True)
    with open(_path(), "w", encoding="utf-8") as f:
        json.dump(d, f, indent=2)

def get_key() -> str:
    return (_load().get("gemini_api_key") or "").strip()

def set_key(k: str):
    _patch(gemini_api_key=k.strip())

def get_user_name() -> str:
    return (_load().get("user_name") or "").strip()

def set_user_name(n: str):
    _patch(user_name=n.strip())

def get_assistant_name() -> str:
    return (_load().get("assistant_name") or "Jarvis").strip() or "Jarvis"

def get_lang() -> str:
    """Speech-recognition language: 'ar-EG' (Egyptian Arabic) or 'en-US'."""
    return _load().get("voice_lang") or "ar-EG"

def set_lang(l: str):
    _patch(voice_lang=l)

# ---- Gemini model -------------------------------------------------------
def get_model() -> str:
    """Manual model chosen in Settings. Empty = automatic (engine tries 3.8, 3.5, then what Google lists)."""
    d = _load()
    return (d.get("model_name") or d.get("model") or "").strip()

def set_model(m: str):
    _patch(model_name=m.strip())

def get_model_name() -> str:
    """Active Gemini model name, defaulting to gemini-3.8-flash."""
    return get_model() or DEFAULT_MODEL

def set_model_name(m: str):
    set_model(m)

# ---- PC wake (Wake-on-LAN) ----------------------------------------------
def get_pc_mac() -> str:
    return (_load().get("pc_mac") or "").strip()

def set_pc_mac(m: str):
    _patch(pc_mac=m.strip())
