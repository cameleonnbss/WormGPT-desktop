"""Local performance & usage statistics for the Specs dashboard.

Everything is written to ``<app-data>/stats.json`` — nothing leaves the
machine. The store keeps aggregate counters (per model and overall) plus a
short rolling log so the dashboard can show averages, the most used model and
the last events without re-reading the whole application log.

Counters are intentionally simple so they survive partial writes: on a
corrupted file we start fresh instead of losing the app.
"""

import datetime
import json
import os
import threading
import time

from . import config as C

_LOCK = threading.Lock()
_LOG_MAX = 200
_FILENAME = "stats.json"


def _path():
    return os.path.join(C.data_dir(), _FILENAME)


def _blank():
    return {
        "turns": 0,
        "tokens": 0,
        "seconds": 0.0,
        "models": {},      # name -> {turns, tokens, seconds, last_used}
        "downloads": [],   # [{name, when, size_mb}]
        "log": [],         # rolling [{t, level, text}]
        "first_seen": time.time(),
        "last_turn": 0.0,
    }


def load():
    """Read the store (never raises)."""
    data = _blank()
    try:
        with open(_path(), "r", encoding="utf-8") as f:
            raw = json.load(f)
        if isinstance(raw, dict):
            for k, v in raw.items():
                if k == "models" and isinstance(v, dict):
                    data["models"] = v
                elif k in ("downloads", "log") and isinstance(v, list):
                    data[k] = v
                elif k in data:
                    data[k] = v
    except (OSError, ValueError):
        pass
    return data


def save(data):
    tmp = _path() + ".tmp"
    try:
        os.makedirs(os.path.dirname(tmp), exist_ok=True)
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
        os.replace(tmp, _path())
    except OSError:
        pass


def log(text, level="info"):
    """Append one line to the rolling log (also kept in debug.log)."""
    entry = {"t": time.time(), "level": level, "text": str(text)[:400]}
    with _LOCK:
        data = load()
        data["log"].append(entry)
        data["log"] = data["log"][-_LOG_MAX:]
        save(data)
    return entry


def record_turn(model, tokens=0, seconds=0.0, text_len=0):
    """Register one completed assistant turn."""
    model = str(model or "WormGPT")
    try:
        tokens = int(tokens or 0)
    except (TypeError, ValueError):
        tokens = 0
    try:
        seconds = float(seconds or 0.0)
    except (TypeError, ValueError):
        seconds = 0.0
    now = time.time()
    with _LOCK:
        data = load()
        data["turns"] = int(data.get("turns", 0)) + 1
        data["tokens"] = int(data.get("tokens", 0)) + tokens
        data["seconds"] = float(data.get("seconds", 0.0)) + seconds
        data["last_turn"] = now
        m = dict(data["models"].get(model) or {})
        m["turns"] = int(m.get("turns", 0)) + 1
        m["tokens"] = int(m.get("tokens", 0)) + tokens
        m["seconds"] = float(m.get("seconds", 0.0)) + seconds
        m["last_used"] = now
        if text_len:
            m["chars"] = int(m.get("chars", 0)) + int(text_len)
        data["models"][model] = m
        save(data)
    return data


def record_download(name, size_mb=0):
    with _LOCK:
        data = load()
        data["downloads"].append({"name": str(name), "when": time.time(),
                                  "size_mb": float(size_mb or 0)})
        data["downloads"] = data["downloads"][-50:]
        data["log"].append({"t": time.time(), "level": "ok",
                            "text": f"[MODEL INSTALLED] {name}"})
        data["log"] = data["log"][-_LOG_MAX:]
        save(data)


def reset():
    with _LOCK:
        save(_blank())


def _avg(total, count):
    return round(total / count, 2) if count else 0.0


def snapshot(extra_log=None, installed=None, active_model=""):
    """Aggregated view for the dashboard."""
    data = load()
    turns = int(data.get("turns", 0))
    tokens = int(data.get("tokens", 0))
    seconds = float(data.get("seconds", 0.0))
    models = []
    for name, m in (data.get("models") or {}).items():
        mt = int(m.get("turns", 0))
        mtok = int(m.get("tokens", 0))
        msec = float(m.get("seconds", 0.0))
        models.append({
            "name": name,
            "turns": mt,
            "tokens": mtok,
            "seconds": round(msec, 1),
            "avg_seconds": _avg(msec, mt),
            "avg_tps": _avg(mtok / msec if msec else 0, 1) if msec else 0.0,
            "last_used": float(m.get("last_used", 0) or 0),
        })
    models.sort(key=lambda x: x["turns"], reverse=True)
    most_used = models[0]["name"] if models else (active_model or "—")
    log = list(data.get("log") or [])
    if extra_log:
        log += list(extra_log)
    log = log[-40:]
    return {
        "turns": turns,
        "tokens": tokens,
        "seconds": round(seconds, 1),
        "avg_seconds": _avg(seconds, turns),
        "avg_tokens": _avg(tokens, turns),
        "avg_tps": _avg(tokens / seconds if seconds else 0, 1) if seconds else 0.0,
        "most_used": most_used,
        "models": models,
        "downloads": list(data.get("downloads") or [])[-12:],
        "installed": installed or [],
        "log": log,
        "since": data.get("first_seen", 0),
        "last_turn": data.get("last_turn", 0),
    }


def human_time(ts):
    try:
        return datetime.datetime.fromtimestamp(float(ts)).strftime("%H:%M:%S")
    except (TypeError, ValueError, OSError, OverflowError):
        return ""
