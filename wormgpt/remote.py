"""Remote chat providers (OpenAI-compatible + Anthropic).

The app is local-first, but a user may point it at a cloud API. Two wire
formats are supported:

    openai     /v1/chat/completions  (OpenAI, Groq, Together, OpenRouter,
                LM Studio, Ollama's OpenAI shim, vLLM, LiteLLM, …)
    anthropic  /v1/messages          (Claude)

Everything stays stdlib: ``urllib`` for HTTP, plain SSE parsing for streaming.
An API key is only ever sent to the base URL the user typed, and nothing is
logged to the diagnostic channel — the cloud exchange is the user's business,
not the owner's.

Failures are surfaced as :class:`RemoteError` with a short human message so
the chat can show something actionable instead of a stack trace.
"""

import json
import ssl
import threading
import urllib.error
import urllib.parse
import urllib.request

UA = "WormGPT-Desktop/1.1"
TIMEOUT = 300
LIST_TIMEOUT = 20

PROVIDERS = ("xkiro", "openai", "anthropic", "custom")

DEFAULT_PROFILES = {
    "xkiro": {"enabled": False, "label": "xKiro (cloud, free models)",
              "base_url": "https://api.xkiro.com/v1", "api_key": "",
              "model": ""},
    "openai": {"enabled": False, "label": "OpenAI / compatible",
               "base_url": "https://api.openai.com/v1", "api_key": "",
               "model": ""},
    "anthropic": {"enabled": False, "label": "Anthropic (Claude)",
                  "base_url": "https://api.anthropic.com", "api_key": "",
                  "model": ""},
    "custom": {"enabled": False, "label": "Custom (Ollama, LM Studio, vLLM…)",
               "base_url": "http://127.0.0.1:11434/v1", "api_key": "",
               "model": ""},
}

#: providers that speak the OpenAI wire format
_OPENAI_LIKE = ("xkiro", "openai", "custom")

#: curated free models shown at the bottom of the model list when the xKiro
#: API answers. Verified against GET /models at build time; anything the API
#: lists but that isn't here still shows up via "Load models" in Settings.
XKIRO_FREE = [
    ("mistralai/mistral-large-2512",  "Mistral Large 3",
     "MoE 41B active (675B total), 256K context. Mistral's most capable model."),
    ("mistralai/mistral-medium-3.5",  "Mistral Medium 3.5",
     "Dense 128B for agentic workflows, coding and complex tasks. 256K context."),
    ("mistralai/mistral-small-2603",  "Mistral Small 4",
     "Hybrid instruct + reasoning + coding in one efficient model. 256K context."),
    ("mistralai/codestral-2508",      "Codestral",
     "Cutting-edge coding model: fill-in-middle, code correction, tests. 256K ctx."),
    ("mistralai/devstral-medium",     "Devstral 2",
     "High-performance code generation and agentic model (not a reasoner)."),
    ("mistralai/ministral-14b",       "Ministral 3 14B",
     "Best-in-class small model with text and vision. 256K context."),
    ("mistralai/ministral-8b",        "Ministral 3 8B",
     "Efficient small model with text and vision. 256K context."),
    ("mistralai/ministral-3b",        "Ministral 3 3B",
     "Tiny, ultra-cheap model with text and vision. 256K context."),
    ("sensenova/sensenova-6.8-flash-lite", "SenseNova 6.8 Flash-Lite",
     "Lightweight multimodal agent model: text + image understanding. 262K ctx."),
    ("sensenova/sensenova-6.7-flash-lite", "SenseNova 6.7 Flash-Lite",
     "Lightweight multimodal agent model: text + image understanding. 262K ctx."),
]


class RemoteError(Exception):
    pass


# --------------------------------------------------------------------- helpers

def normalize_profile(name, raw=None):
    """Merge a stored profile with the defaults, never returning None."""
    base = dict(DEFAULT_PROFILES.get(name) or DEFAULT_PROFILES["custom"])
    if isinstance(raw, dict):
        for k, v in raw.items():
            if k in base or k in ("api_key", "model", "base_url", "enabled"):
                base[k] = v
    base["base_url"] = str(base.get("base_url") or "").rstrip("/")
    base["api_key"] = str(base.get("api_key") or "").strip()
    base["model"] = str(base.get("model") or "").strip()
    return base


def profile_ready(name, raw=None):
    p = normalize_profile(name, raw)
    return bool(p.get("enabled") and p.get("base_url")
                and (p.get("api_key") or name == "custom"))


def _request(url, payload=None, headers=None, method=None, timeout=TIMEOUT):
    data = None
    hdrs = {"User-Agent": UA, "Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        hdrs["Content-Type"] = "application/json"
    hdrs.update(headers or {})
    req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
    return urllib.request.urlopen(req, timeout=timeout,
                                  context=ssl.create_default_context())


def _error_from(exc):
    """Turn an HTTPError into a readable message (keeps the API's own text)."""
    if isinstance(exc, urllib.error.HTTPError):
        detail = ""
        try:
            body = exc.read(4000).decode("utf-8", "replace")
            parsed = json.loads(body)
            err = parsed.get("error") if isinstance(parsed, dict) else None
            if isinstance(err, dict):
                detail = err.get("message", "")
            elif isinstance(err, str):
                detail = err
            elif isinstance(parsed, dict):
                detail = parsed.get("message", "")
        except Exception:
            detail = ""
        msg = f"HTTP {exc.code}"
        if detail:
            msg += f": {detail[:300]}"
        if exc.code in (401, 403):
            msg += " (check the API key)"
        elif exc.code == 404:
            msg += " (check the base URL / model name)"
        return msg
    return str(exc)


# ----------------------------------------------------------------- model lists

def list_models(name, raw=None):
    """List the model ids a provider exposes, sorted.

    OpenAI-compatible endpoints answer ``GET /models``; Anthropic answers
    ``GET /v1/models`` with an ``x-api-key`` header.
    """
    p = normalize_profile(name, raw)
    base = p["base_url"]
    if not base:
        raise RemoteError("base URL missing")
    try:
        if name == "anthropic":
            resp = _request(base + "/v1/models?limit=100",
                            headers={"x-api-key": p["api_key"],
                                     "anthropic-version": "2023-06-01"},
                            timeout=LIST_TIMEOUT)
            data = json.load(resp)
            items = data.get("data") or []
            return sorted({str(m.get("id", "")) for m in items if m.get("id")})
        resp = _request(base + "/models",
                        headers={"Authorization": f"Bearer {p['api_key']}"}
                        if p["api_key"] else {},
                        timeout=LIST_TIMEOUT)
        data = json.load(resp)
        items = data.get("data") if isinstance(data, dict) else data
        out = set()
        for m in items or []:
            if isinstance(m, dict):
                mid = m.get("id") or m.get("name")
            else:
                mid = str(m)
            if mid:
                out.add(str(mid))
        return sorted(out)
    except RemoteError:
        raise
    except Exception as exc:
        raise RemoteError(_error_from(exc)) from exc


# --------------------------------------------------------------------- chat

def _openai_payload(model, messages, temperature, max_tokens, stream):
    return {
        "model": model,
        "messages": messages,
        "temperature": float(temperature),
        "max_tokens": int(max_tokens),
        "stream": bool(stream),
    }


def _anthropic_payload(model, messages, temperature, max_tokens, stream):
    system, convo = [], []
    for m in messages:
        role = m.get("role")
        content = m.get("content")
        if isinstance(content, list):
            content = " ".join(
                str(p.get("text", "")) for p in content if isinstance(p, dict))
        content = str(content or "")
        if role == "system":
            system.append(content)
        elif role in ("user", "assistant"):
            convo.append({"role": role, "content": content})
    if not convo:
        convo = [{"role": "user", "content": ""}]
    payload = {
        "model": model,
        "messages": convo,
        "max_tokens": int(max_tokens),
        "temperature": min(1.0, float(temperature)),
        "stream": bool(stream),
    }
    if system:
        payload["system"] = "\n\n".join(system)
    return payload


def chat(name, profile, messages, temperature=0.7, max_tokens=1024):
    """One blocking turn. Returns the assistant text."""
    p = normalize_profile(name, profile)
    model = p["model"] or _first_model(name, p)
    if name == "anthropic":
        url = p["base_url"] + "/v1/messages"
        headers = {"x-api-key": p["api_key"],
                   "anthropic-version": "2023-06-01"}
        payload = _anthropic_payload(model, messages, temperature, max_tokens,
                                     False)
    else:
        url = p["base_url"] + "/chat/completions"
        headers = ({"Authorization": f"Bearer {p['api_key']}"}
                   if p["api_key"] else {})
        payload = _openai_payload(model, messages, temperature, max_tokens,
                                  False)
    try:
        resp = _request(url, payload, headers)
        data = json.load(resp)
    except Exception as exc:
        raise RemoteError(_error_from(exc)) from exc
    return _extract_text(name, data)


def chat_stream(name, profile, messages, temperature=0.7, max_tokens=1024,
                should_stop=None):
    """Stream a turn, yielding text chunks as they arrive."""
    p = normalize_profile(name, profile)
    model = p["model"] or _first_model(name, p)
    if name == "anthropic":
        url = p["base_url"] + "/v1/messages"
        headers = {"x-api-key": p["api_key"],
                   "anthropic-version": "2023-06-01",
                   "Accept": "text/event-stream"}
        payload = _anthropic_payload(model, messages, temperature, max_tokens,
                                     True)
    else:
        url = p["base_url"] + "/chat/completions"
        headers = {"Accept": "text/event-stream"}
        if p["api_key"]:
            headers["Authorization"] = f"Bearer {p['api_key']}"
        payload = _openai_payload(model, messages, temperature, max_tokens,
                                  True)
    try:
        resp = _request(url, payload, headers)
    except Exception as exc:
        raise RemoteError(_error_from(exc)) from exc
    with resp:
        for event, data in _iter_sse(resp):
            if should_stop is not None and should_stop():
                break
            if data == "[DONE]":
                break
            try:
                obj = json.loads(data)
            except ValueError:
                continue
            piece = ""
            if name == "anthropic":
                if event == "content_block_delta":
                    delta = obj.get("delta") or {}
                    if delta.get("type") == "text_delta":
                        piece = delta.get("text") or ""
                elif event == "message_stop":
                    break
                elif event == "error":
                    raise RemoteError(str((obj.get("error") or {}).get(
                        "message", "stream error"))[:300])
            else:
                choices = obj.get("choices") or []
                if choices:
                    delta = choices[0].get("delta") or {}
                    piece = delta.get("content") or ""
                    if not piece:
                        piece = (choices[0].get("message") or {}).get(
                            "content") or ""
            if piece:
                yield piece


def _iter_sse(resp):
    """Yield (event, data) tuples from an SSE response."""
    event = "message"
    for raw in resp:
        line = raw.decode("utf-8", "replace").rstrip("\r\n")
        if not line:
            event = "message"
            continue
        if line.startswith(":"):
            continue
        if line.startswith("event:"):
            event = line[6:].strip()
            continue
        if line.startswith("data:"):
            yield event, line[5:].strip()


def _first_model(name, profile):
    """Pick a sensible default model when the user left the field empty.

    Never pick a premium-only model blindly: xKiro gates some routes behind
    a paid plan (HTTP 403). We probe candidates in order and keep the first
    that actually answers.
    """
    candidates = []
    if name == "xkiro":
        candidates = [m for m, _l, _d in XKIRO_FREE[:4]]
    try:
        models = list_models(name, profile)
    except RemoteError:
        models = []
    if models:
        for cand in candidates:
            if cand in models:
                return cand
        return models[0]
    if candidates:
        return candidates[0]
    raise RemoteError("no model selected and the provider listed none — "
                      "use “Load models” first")


def _extract_text(name, data):
    if name == "anthropic":
        blocks = data.get("content") or []
        return "".join(str(b.get("text", "")) for b in blocks
                       if isinstance(b, dict) and b.get("type") == "text")
    choices = data.get("choices") or []
    if not choices:
        raise RemoteError("empty response from the provider")
    msg = choices[0].get("message") or {}
    content = msg.get("content")
    if isinstance(content, list):
        content = "".join(str(p.get("text", "")) for p in content
                          if isinstance(p, dict))
    return str(content or "")


# ------------------------------------------------------- background generation

class RemoteTurn:
    """Runs a streamed remote turn on a thread (same shape as Engine.generate)."""

    def __init__(self):
        self._stop = threading.Event()
        self._thread = None

    @property
    def running(self):
        return bool(self._thread and self._thread.is_alive())

    def stop(self):
        self._stop.set()

    def start(self, provider, profile, messages, on_token, on_error, on_done,
              temperature=0.7, max_tokens=1024):
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._worker,
            args=(provider, profile, messages, on_token, on_error, on_done,
                  temperature, max_tokens),
            daemon=True)
        self._thread.start()
        return self._thread

    def _worker(self, provider, profile, messages, on_token, on_error, on_done,
                temperature, max_tokens):
        parts = []
        try:
            for piece in chat_stream(provider, profile, messages,
                                     temperature=temperature,
                                     max_tokens=max_tokens,
                                     should_stop=self._stop.is_set):
                parts.append(piece)
                on_token(piece)
            text = "".join(parts).strip()
            on_done(text, "")
        except RemoteError as exc:
            on_error(str(exc))
        except Exception as exc:                # pragma: no cover - defensive
            on_error(f"Remote error: {exc}")
