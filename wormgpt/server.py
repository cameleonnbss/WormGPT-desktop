"""Local HTTP server — OpenAI- and Anthropic-compatible chat API.

Lets external tools (Claude Code, Continue, open-webui, custom scripts…)
talk to the locally loaded model:

    GET  /v1/models              list available tiers
    POST /v1/chat/completions    OpenAI format (stream + SSE supported)
    POST /v1/messages            Anthropic format (stream + SSE supported)

Everything stays on the loopback interface by default and every request is
serialised on the engine lock shared with the chat UI.
"""

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import __version__
from . import models as M


class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = f"WormGPT/{__version__}"

    # -- plumbing -----------------------------------------------------------

    def log_message(self, *args):
        pass

    def _json(self, code, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            return json.loads(self.rfile.read(length) or b"{}")
        except (ValueError, json.JSONDecodeError):
            self._json(400, {"error": {"message": "Invalid JSON body"}})
            return None

    # -- GET ----------------------------------------------------------------

    def do_GET(self):
        if self.path in ("/", "/health"):
            self._json(200, {
                "status": "ok",
                "name": "WormGPT",
                "version": __version__,
                "models": [t.name for t in M.CATALOG],
            })
        elif self.path == "/v1/models":
            self._json(200, {
                "object": "list",
                "data": [{"id": t.name, "object": "model",
                          "owned_by": "wormgpt"} for t in M.CATALOG],
            })
        else:
            self._json(404, {"error": {"message": "Not found"}})

    # -- POST ---------------------------------------------------------------

    def do_POST(self):
        body = self._read_json()
        if body is None:
            return
        try:
            if self.path == "/v1/chat/completions":
                self._chat_completions(body)
            elif self.path == "/v1/messages":
                self._anthropic_messages(body)
            else:
                self._json(404, {"error": {"message": "Not found"}})
        except Exception as exc:
            self._json(500, {"error": {"message": str(exc)}})

    # -- OpenAI -------------------------------------------------------------

    def _chat_completions(self, body):
        messages = body.get("messages") or []
        temperature = float(body.get("temperature", 0.7))
        max_tokens = int(body.get("max_tokens", 1024))
        stream = bool(body.get("stream"))
        model = body.get("model", self.server.app.active_tier_name())

        def to_sse(payload):
            return b"data: " + json.dumps(payload).encode() + b"\n\n"

        if stream:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            for piece in self.server.app.server_generate(messages, temperature,
                                                         max_tokens, stream=True,
                                                         model=model):
                self.wfile.write(to_sse({"choices": [{"delta": {"content": piece}}]}))
                self.wfile.flush()
            self.wfile.write(b"data: [DONE]\n\n")
            self.wfile.flush()
        else:
            text = self.server.app.server_generate(messages, temperature,
                                                   max_tokens, stream=False,
                                                   model=model)
            self._json(200, {
                "id": "chatcmpl-wormgpt",
                "object": "chat.completion",
                "model": model,
                "choices": [{"index": 0, "message": {"role": "assistant",
                                                     "content": text},
                             "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 0, "completion_tokens": 0,
                          "total_tokens": 0},
            })

    # -- Anthropic ----------------------------------------------------------

    def _anthropic_messages(self, body):
        messages = []
        system = body.get("system", "")
        if isinstance(system, list):
            system = " ".join(p.get("text", "") for p in system if isinstance(p, dict))
        for msg in body.get("messages") or []:
            content = msg.get("content")
            if isinstance(content, str):
                text = content
            else:
                text = " ".join(p.get("text", "") for p in content
                                if isinstance(p, dict) and p.get("type") == "text")
            if msg.get("role") == "system":
                system = (system + "\n" + text).strip()
            else:
                messages.append({"role": msg.get("role", "user"), "content": text})
        temperature = float(body.get("temperature", 0.7))
        max_tokens = int(body.get("max_tokens", 1024))
        stream = bool(body.get("stream"))
        model = body.get("model", self.server.app.active_tier_name())

        def event(payload):
            return b"event: " + payload.get("type", "").encode() + b"\ndata: " + \
                json.dumps(payload).encode() + b"\n\n"

        if stream:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(event({"type": "message_start",
                                    "message": {"id": "msg_wormgpt", "type": "message",
                                                "role": "assistant", "model": model,
                                                "content": [], "stop_reason": None}}))
            self.wfile.write(event({"type": "content_block_start",
                                    "index": 0, "content_block": {"type": "text",
                                                                  "text": ""}}))
            for piece in self.server.app.server_generate(messages, temperature,
                                                         max_tokens, stream=True,
                                                         model=model):
                self.wfile.write(event({"type": "content_block_delta", "index": 0,
                                        "delta": {"type": "text_delta", "text": piece}}))
                self.wfile.flush()
            self.wfile.write(event({"type": "content_block_stop", "index": 0}))
            self.wfile.write(event({"type": "message_delta",
                                    "delta": {"stop_reason": "end_turn"}}))
            self.wfile.write(event({"type": "message_stop"}))
            self.wfile.flush()
        else:
            text = self.server.app.server_generate(messages, temperature,
                                                   max_tokens, stream=False,
                                                   model=model)
            self._json(200, {
                "id": "msg_wormgpt",
                "type": "message",
                "role": "assistant",
                "model": model,
                "content": [{"type": "text", "text": text}],
                "stop_reason": "end_turn",
                "stop_sequence": None,
                "usage": {"input_tokens": 0, "output_tokens": 0},
            })


class LocalServer:
    """Lifecycle wrapper around the threaded HTTP server."""

    def __init__(self, app, host="127.0.0.1", port=1234):
        self.app = app
        self.host = host
        self.port = port
        self._httpd = None
        self._thread = None

    @property
    def running(self):
        return self._httpd is not None

    def start(self):
        if self.running:
            return
        self._httpd = ThreadingHTTPServer((self.host, self.port), _Handler)
        self._httpd.daemon_threads = True
        self._httpd.app = self.app
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._thread.start()
        self.port = self._httpd.server_address[1]

    def stop(self):
        if self._httpd:
            self._httpd.shutdown()
            self._httpd.server_close()
            self._httpd = None
            self._thread = None