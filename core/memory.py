"""Long-term memory, same shape as the desktop JARVIS long_term.json
(identity / preferences / notes, each entry {value, updated})."""
import json, os
from datetime import date

CATEGORIES = ("identity", "preferences", "notes")

SEED = {
    "identity": {
        "name": {"value": "Yassin"},
        "nickname": {"value": "Konda"},
        "language": {"value": "Arabic"},
        "dialect": {"value": "Egyptian Arabic"},
    },
    "preferences": {}, "notes": {},
}

def _path():
    return os.path.join(os.environ.get("JARVIS_HOME", "."), "long_term.json")

def load() -> dict:
    try:
        with open(_path(), "r", encoding="utf-8") as f:
            d = json.load(f)
        if isinstance(d, dict):
            return d
    except Exception:
        pass
    d = json.loads(json.dumps(SEED))
    for cat in d.values():
        for e in cat.values():
            e["updated"] = str(date.today())
    save(d)
    return d

def save(d: dict):
    os.makedirs(os.path.dirname(_path()) or ".", exist_ok=True)
    with open(_path(), "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)

def remember(category: str, key: str, value: str) -> str:
    category = category if category in CATEGORIES else "notes"
    key, value = (key or "").strip(), (value or "").strip()
    if not key or not value:
        return "nothing to save"
    d = load()
    if value.upper() == "DELETE":
        d.get(category, {}).pop(key, None)
    else:
        d.setdefault(category, {})[key] = {"value": value, "updated": str(date.today())}
    save(d)
    return "saved"

def for_prompt(d: dict) -> str:
    lines = []
    for cat, items in d.items():
        if isinstance(items, dict):
            for k, e in items.items():
                if isinstance(e, dict) and "value" in e:
                    lines.append(f"- {cat}/{k}: {e['value']}")
    return "[LONG-TERM MEMORY]\n" + "\n".join(lines) + "\n" if lines else ""
