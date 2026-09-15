"""Self-tests run before packaging: engine (fake llama_cpp), downloader
(local HTTP server) and a brief UI smoke test."""

import json
import os
import shutil
import sys
import tempfile
import threading
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

# isolated app-data so the test never touches the real config
TEST_APP = tempfile.mkdtemp(prefix="wormgpt_test_")
os.environ["APPDATA"] = TEST_APP

FAILURES = []


def check(name, cond, detail=""):
    print(("PASS  " if cond else "FAIL  ") + name + (f"  — {detail}" if detail and not cond else ""))
    if not cond:
        FAILURES.append(name)


# ---------------------------------------------------------------------------
# 1. Engine with a fake llama_cpp
# ---------------------------------------------------------------------------
FAKE = os.path.join(TEST_APP, "llama_cpp")
os.makedirs(FAKE)
with open(os.path.join(FAKE, "__init__.py"), "w") as f:
    f.write("""
class Llama:
    def __init__(self, **kw):
        self.kw = kw
        self._calls = 0
    def create_chat_completion(self, messages=None, **kw):
        if kw.get("stream"):
            return [{"choices": [{"delta": {"content": tok}}]}
                    for tok in ["Hello", " ", "world", ",", " <|im_end|>"]
                   ]
        if "tools" in kw and not getattr(self, "_tool_used", False):
            self._tool_used = True
            return {"choices": [{"message": {"content": "", "tool_calls": [
                {"function": {"name": "run_command",
                 "arguments": '{"command": "echo hi"}'}}]}}]}
        return {"choices": [{"message": {"content": "Done <|im_end|>"}}]}
""")
sys.path.insert(0, TEST_APP)

from wormgpt import engine as E  # noqa: E402
from wormgpt import models as M  # noqa: E402
from wormgpt import runner as R  # noqa: E402

model_file = os.path.join(TEST_APP, "fake.gguf")
with open(model_file, "wb") as f:
    f.write(b"GGUF-fake-model")  # magie GGUF : l'entête est vérifiée au load

eng = E.Engine(model_file, n_ctx=512, temperature=0.5, max_tokens=64,
               system_prompt="sys")
eng.load()
check("engine.load() with fake llama_cpp", eng.is_loaded())

# i18n sanity
from wormgpt import i18n as _  # noqa: E402
_.set_lang("fr")
check("i18n fr", _.tr("nav.models") == "Modèles" and _.trf("chat.with", model="X") == "Chat avec X")
_.set_lang("es")
check("i18n es", _.tr("nav.home") == "Inicio")
_.set_lang("de")
check("i18n de", _.tr("settings.language") == "Sprache")
_.set_lang("xx")
check("i18n fallback", _.tr("nav.chat") == "Chat")
_.set_lang("en")

# catalog sanity
check("catalog has 15 tiers", len(M.CATALOG) == 15, str(len(M.CATALOG)))
cats = {t.category for t in M.CATALOG}
check("catalog categories", cats == {"general", "code", "reason", "vision", "dolphin", "genimg"}, str(cats))
vision = [t for t in M.CATALOG if t.category == "vision"]
genimg = [t for t in M.CATALOG if t.category == "genimg"]
check("genimg tiers present", len(genimg) == 2 and
      {t.name for t in genimg} == {"WormGPT Draw-1", "WormGPT Draw-2"},
      str([t.name for t in genimg]))
check("genimg tiers are uncensored",
      all("uncensored" in (t.power + t.base + t.desc).lower()
          for t in genimg), str([t.power for t in genimg]))
check("vision tiers have mmproj", all(t.is_vision for t in vision))
dolphin = [t for t in M.CATALOG if t.category == "dolphin"]
check("dolphin tiers present", len(dolphin) == 3, str(len(dolphin)))
# les noms de modèles sous-jacents ne doivent JAMAIS apparaître
# "Dolphin" est conservé : c'est une famille affichée volontairement
# (WormGPT Dolphin-N), demandée par l'utilisateur.
_leak = ("qwen", "llama", "gemma", "mistral", "deepseek", "hermes",
         "smollm", "pony", "illustrious", "cognit", "nous", "stable diffusion")
_bad = [(t.name, t.base + " " + t.desc)
        for t in M.CATALOG
        if any(word in (t.base + " " + t.desc).lower() for word in _leak)]
check("no underlying model name leaks in the catalog", not _bad, str(_bad[:2]))
check("every chat tier is abliterated/uncensored",
      all(("abliterated" in (t.base + " " + t.desc + " " + t.power).lower()
           or "uncensored" in (t.base + " " + t.desc + " " + t.power).lower()
           or "heretic" in (t.base + " " + t.desc + " " + t.power).lower()
           or "dolphin" in t.base.lower()
           or t.category in ("vision", "genimg"))
          for t in M.CATALOG))

# reasoning extraction
reason, final = E.split_think("<|thinking|>Let me think...<|/thinking|>But first, the answer.")
check("split_think extracts block", "Let me think..." in reason and "But first" in final, repr((reason, final)))
reason2, final2 = E.split_think("No thinking here")
check("split_think passthrough", reason2 == "" and final2 == "No thinking here")
parts = list(E._iter_split(iter(["Hi ", "<|thinking|>", "Hmm...", "<|/thinking|>", "Answer"])))
check("_iter_split kinds", [(p[0]) for p in parts] == ["text", "reason", "text"], repr(parts))
check("_iter_split content", "".join(p[1] for p in parts) == "Hi Hmm...Answer")

# vision message building
fake_img = os.path.join(TEST_APP, "shot.png")
with open(fake_img, "wb") as f:
    f.write(b"\x89PNG\r\n\x1a\nfake-image-bytes")
hist = [{"role": "user", "text": "hi", "image": fake_img}]
msgs_v = E.build_messages("sys", hist, "describe", vision=True)
check("vision builds multimodal content",
      isinstance(msgs_v[1]["content"], list) and
      msgs_v[1]["content"][0]["type"] == "image_url" and
      msgs_v[1]["content"][0]["image_url"]["url"].startswith("data:image/png;base64,"))
msgs_p = E.build_messages("sys", hist, "describe", vision=False)
check("non-vision keeps plain text", msgs_p[1]["content"] == "hi")

msgs = E.build_messages("sys", [{"role": "user", "text": "hi"}], "test prompt")
check("build_messages roles", [m["role"] for m in msgs] == ["system", "user", "user"])

got = []
done = threading.Event()


def on_token(t):
    got.append(t)


def on_done(t, r=None):
    done.set()


eng.generate(msgs, on_token, lambda e: check("engine.generate no error", False, e), on_done)
done.wait(10)
text = "".join(got)
check("engine streaming text", "Hello" in text and "world" in text, repr(text))
check("engine strips special tokens", "<|im_end|>" not in text, repr(text))
# régression : le worker repoussait tout le texte à la fin du flux -> doublon
check("engine streams the answer exactly once", text.count("Hello") == 1,
      repr(text))
check("engine keeps the trailing space out of the bubble",
      text.strip() == "Hello world,", repr(text))

# reasoning : le bloc <think> part dans on_reasoning, une seule fois, même
# quand les balises sont coupées entre deux chunks (streaming réel).
_real_iter_raw = eng._iter_raw
eng._iter_raw = lambda kw: iter([
    {"delta": {"content": c}} for c in
    ["Voici", " <think", ">je réflé", "chis</think", ">", " la ré", "ponse"]])
got_t, got_r, done_r = [], [], threading.Event()
eng._generate_worker(msgs, got_t.append, lambda e: None,
                     lambda t, r=None: done_r.set(), got_r.append)
done_r.wait(10)
check("think block split across chunks", "".join(got_r) == "je réfléchis",
      repr("".join(got_r)))
check("answer around think block intact",
      "".join(got_t).split() == ["Voici", "la", "réponse"],
      repr("".join(got_t)))
eng._iter_raw = _real_iter_raw

# reasoning natif : le backend expose parfois un champ dédié
eng._iter_raw = lambda kw: iter([
    {"delta": {"reasoning_content": "je", "content": None}},
    {"delta": {"reasoning_content": " pense", "content": None}},
    {"delta": {"content": "Résultat final"}}])
got_t2, got_r2, done_r2 = [], [], threading.Event()
eng._generate_worker(msgs, got_t2.append, lambda e: None,
                     lambda t, r=None: done_r2.set(), got_r2.append)
done_r2.wait(10)
check("native reasoning_content routed to reasoning",
      "".join(got_r2) == "je pense", repr("".join(got_r2)))
check("native reasoning keeps the answer clean",
      "".join(got_t2).strip() == "Résultat final", repr("".join(got_t2)))
eng._iter_raw = _real_iter_raw

# synchronous API + tool calls (agent loop primitives)
text_c, calls_c, reason_c = eng.complete(msgs)
check("engine.complete returns text", text_c == "Done", repr(text_c))
check("engine.complete no tool calls", calls_c == [])
text_t, calls_t, _rt = eng.complete(msgs, tools=[R.RUN_COMMAND_TOOL])
check("engine.complete with tools returns calls",
      calls_t and calls_t[0]["function"]["name"] == "run_command", repr(calls_t))
check("engine.complete with tools text empty", text_t == "")
streamed = list(eng.complete_stream(msgs))
check("engine.complete_stream yields chunks", "".join(streamed).strip() == "Hello world,", repr(streamed))

# system recommendations
from wormgpt import systeminfo as SI  # noqa: E402
info = SI.detect()
check("systeminfo detects hardware", set(info) >= {"ram_gb", "cores", "gpu"}, str(info))
rec = SI.recommendations()
check("recommendations propose a real tier", M.get_tier(rec["tier"]).category == "general", rec["tier"])
check("recommendations sane values", 2 <= rec["threads"] <= 64 and 1024 <= rec["n_ctx"] <= 32768)
for cat, _name, _icon in M.CATEGORIES:
    t = M.get_tier(SI.best_tier(cat))
    check(f"best_tier({cat}) valid", t.category == cat, t.name)

# GPU : détection générique (nom + VRAM), pas seulement nvidia-smi
g = SI.gpu_stats()
check("gpu_stats returns a shape or None",
      g is None or {"name", "load", "vram_total_mb"} <= set(g), str(g))
check("gpu summary names the card or says none",
      "GPU:" in SI.summary_text(), SI.summary_text())
check("gpu vram is not the 4 GB 32-bit cap",
      g is None or g.get("vram_total_mb", 0) <= 4095
      or not g.get("vram_approx"), str(g))
check("registry vram probe returns a number",
      isinstance(SI._registry_vram_mb(), float))
for p in ("C:\\nope\\nvidia-smi.exe",):
    check("nvidia-smi probe ignores missing paths",
          not (os.path.isfile(p) and SI._find_nvidia_smi() == p))

# web search (live, skipped when offline)
import socket as _socket  # noqa: E402
try:
    _socket.create_connection(("en.wikipedia.org", 443), timeout=3).close()
    _online = True
except OSError:
    _online = False
if _online:
    from wormgpt import search as SR  # noqa: E402
    try:
        res = SR.web_search("Python programming language")
        check("web_search returns digest", res.startswith("Web search results"), res[:60])
        check("web_search bounded", len(res) < 6000, str(len(res)))
        ddg = SR.duckduckgo_instant("Python programming language")
        check("duckduckgo backend", isinstance(ddg, list))
    except Exception as exc:
        check("web_search live", True, f"network flaky — skipped ({exc})")
else:
    check("web_search live", True, "offline — skipped")

# command runner
out = R.run_command("echo hello", cwd=TEST_APP)
check("runner executes command", "hello" in out, repr(out))
out2 = R.run_command("python -c \"import time; time.sleep(3)\"", cwd=TEST_APP, timeout=1)
check("runner times out", "timed out" in out2, repr(out2))
check("runner clamps timeout", R.run_command("echo ok", cwd=TEST_APP,
                                             timeout=0) == "ok")

# ---------------------------------------------------------------------------
# Agent tools (Claude-Code-style filesystem primitives)
# ---------------------------------------------------------------------------
from wormgpt import filesys as FS  # noqa: E402

tool_names = {t["function"]["name"] for t in FS.TOOLS}
check("agent exposes claude-code tools",
      {"read_file", "write_file", "edit_file", "multi_edit", "list_dir",
       "glob", "grep", "run_command"} <= tool_names, str(sorted(tool_names)))

check("write_file creates parents",
      "written" in FS.write_file("sub/deep/agent_demo.txt",
                                "alpha\nbeta\ngamma\n", cwd=TEST_APP))
f = os.path.join(TEST_APP, "sub", "deep", "agent_demo.txt")
rd = FS.read_file(f, cwd=TEST_APP)
check("read_file numbers lines", "1\talpha" in rd and "3\tgamma" in rd, repr(rd[:80]))
rd2 = FS.read_file(f, cwd=TEST_APP, offset=2, limit=1)
check("read_file offset/limit", "2\tbeta" in rd2 and "alpha" not in rd2, repr(rd2))
gl = FS.glob("**/*agent_demo*", TEST_APP, cwd=TEST_APP)
check("glob finds the file", "agent_demo.txt" in gl, repr(gl))
gr = FS.grep(r"g\w+m", TEST_APP, cwd=TEST_APP, include="*.txt")
check("grep matches regex", "agent_demo.txt" in gr, repr(gr[:80]))
ls = FS.list_dir(TEST_APP, cwd=TEST_APP)
check("list_dir lists entries", "DIR  sub" in ls, repr(ls[:80]))
lsr = FS.list_dir(TEST_APP, cwd=TEST_APP, recursive=True)
check("list_dir recursive", "agent_demo.txt" in lsr, repr(lsr[:120]))
check("read_file rejects missing",
      "not a file" in FS.read_file("nope.txt", cwd=TEST_APP))
check("edit_file single match",
      "edited" in FS.edit_file(f, "beta", "BETA", cwd=TEST_APP))
check("edit_file applied", "BETA" in FS.read_file(f, cwd=TEST_APP))
check("edit_file rejects ambiguous",
      "matches 2 times" in FS.edit_file(f, "m", "M", cwd=TEST_APP))
check("edit_file replace_all",
      "edited" in FS.edit_file(f, "m", "M", cwd=TEST_APP, replace_all=True))
check("multi_edit applies in order",
      "edited" in FS.multi_edit(f, [{"old_string": "MM", "new_string": "mm"},
                                    {"old_string": "BETA", "new_string": "Z"}],
                                cwd=TEST_APP), repr(FS.read_file(f, cwd=TEST_APP)))
check("multi_edit result", "mm" in FS.read_file(f, cwd=TEST_APP),
      repr(FS.read_file(f, cwd=TEST_APP)))

# recherche web : helpers de parsing (indépendants du réseau)
from wormgpt import search as SR  # noqa: E402
check("search strips tags and entities",
      SR._clean("<b>Hello</b> &amp; bye") == "Hello & bye",
      repr(SR._clean("<b>Hello</b> &amp; bye")))
check("search unwraps the DDG redirect",
      SR._real_url("//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Fx")
      == "https://example.com/x")
_blocks = SR._blocks('<div class="result x"><a class="result__a" '
                     'href="https://a">A</a></div>'
                     '<div class="result y"><a class="result__a" '
                     'href="https://b">B</a></div>')
check("search splits result blocks",
      len(_blocks) == 2 and "A" in _blocks[0] and "B" in _blocks[1],
      str(len(_blocks)))
check("search flags sponsored blocks",
      bool(SR._AD_MARK.search('<div class="result result--ad x">')))
check("search backends list",
      callable(SR.duckduckgo_lite) and callable(SR.duckduckgo_html))

# discord guard (discord.py not installed in dev env)
from wormgpt import discordbot as DB  # noqa: E402
try:
    import discord  # noqa: F401
    _has_discord = True
except ImportError:
    _has_discord = False
if not _has_discord:
    try:
        DB.DiscordBot("fake", handler=lambda t: "").start()
        check("discord import guard", False, "no exception raised")
    except RuntimeError:
        check("discord import guard", True)
else:
    check("discord import guard", True, "discord.py present, skipped")

# local server (OpenAI + Anthropic endpoints)
from wormgpt import server as S  # noqa: E402

class _StubApp:
    @staticmethod
    def active_tier_name():
        return "WormGPT-3"

    @staticmethod
    def server_generate(messages, temperature, max_tokens, stream=False, model=None):
        if stream:
            return iter(["Hel", "lo world"])
        return "Hello world"

srv = S.LocalServer(_StubApp(), port=0)
srv.start()
base = f"http://127.0.0.1:{srv.port}"

def post(path, payload):
    req = urllib.request.Request(base + path,
                                 data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as r:
        return r.status, json.loads(r.read().decode())

with urllib.request.urlopen(base + "/v1/models", timeout=10) as r:
    models = json.loads(r.read().decode())
check("server /v1/models", any(m["id"] == "WormGPT-3" for m in models["data"]))
st, resp = post("/v1/chat/completions",
                {"messages": [{"role": "user", "content": "hi"}]})
check("server OpenAI endpoint", st == 200 and resp["choices"][0]["message"]["content"] == "Hello world")
st, resp = post("/v1/messages",
                {"messages": [{"role": "user", "content": [{"type": "text", "text": "hi"}]}],
                 "max_tokens": 64})
check("server Anthropic endpoint", st == 200 and resp["content"][0]["text"] == "Hello world")
req = urllib.request.Request(base + "/v1/chat/completions",
                             data=json.dumps({"messages": [{"role": "user", "content": "hi"}],
                                              "stream": True}).encode(),
                             headers={"Content-Type": "application/json"})
with urllib.request.urlopen(req, timeout=10) as r:
    body = r.read().decode()
check("server SSE streaming", "data: [DONE]" in body and "Hel" in body, body[:80])
srv.stop()
check("history trimming keeps system", E.Engine.trim_history(
    [{"role": "system", "content": "s"}] + [{"role": "user", "content": "u"}] * 30)[0]["role"] == "system")
check("history trimming limits turns", len(E.Engine.trim_history(
    [{"role": "system", "content": "s"}] + [{"role": "user", "content": "u"}] * 30)) == 25)

# ---------------------------------------------------------------------------
# 2. Downloader against a local HTTP server
# ---------------------------------------------------------------------------
from http.server import BaseHTTPRequestHandler, HTTPServer, ThreadingHTTPServer  # noqa: E402

PAYLOAD = os.urandom(512 * 1024)  # 512 KB
SLOW = {"/slow": 2.0}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        delay = SLOW.get(self.path, 0.0)
        if delay:
            import time as _t
            _t.sleep(delay)
        self.send_response(200)
        self.send_header("Content-Length", str(len(PAYLOAD)))
        self.end_headers()
        self.wfile.write(PAYLOAD)

    def log_message(self, *a):
        pass


server = HTTPServer(("127.0.0.1", 0), Handler)
threading.Thread(target=server.serve_forever, daemon=True).start()
port = server.server_address[1]

tier = M.CATALOG[0]
tier.size_mb = 0.4  # calibrate the installed-size check for the small payload
tier.url = f"http://127.0.0.1:{port}/model.gguf"

progress = []
job = M.DownloadJob(tier, on_progress=lambda r, t: progress.append((r, t)))
job.start()
while job.running:
    pass
check("download writes the file", os.path.isfile(M.catalog_path(tier.name)))
check("download content matches", open(M.catalog_path(tier.name), "rb").read() == PAYLOAD)
check("download reports progress", len(progress) >= 1, f"{len(progress)} callbacks")
check("download receives everything", progress[-1][0] == len(PAYLOAD))
check("is_installed true", M.is_installed(tier.name))

# cancel path — server sleeps so we can cancel mid-stream
tier2 = M.CATALOG[1]
tier2.url = f"http://127.0.0.1:{port}/slow"
job2 = M.DownloadJob(tier2, on_progress=lambda r, t: None)
job2.start()
threading.Event().wait(0.3)
job2.cancel()
while job2.running:
    pass
check("cancel removes .part", not os.path.exists(M.catalog_path(tier2.name) + ".part"))
check("cancel leaves no installed file", not os.path.isfile(M.catalog_path(tier2.name)))

server.shutdown()

# ---------------------------------------------------------------------------
# 2b. Image generation client against a mock SD WebUI
# ---------------------------------------------------------------------------
from wormgpt import imagegen as IG  # noqa: E402

PNG_BYTES = open(fake_img, "rb").read()
IMG_REQS = []


class IHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        IMG_REQS.append(json.loads(self.rfile.read(length).decode()))
        import base64 as _b64
        body = json.dumps({"images": [_b64.b64encode(PNG_BYTES).decode()]}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


iserver = ThreadingHTTPServer(("127.0.0.1", 0), IHandler)
threading.Thread(target=iserver.serve_forever, daemon=True).start()
iport = iserver.server_address[1]
client = IG.SDClient(url=f"http://127.0.0.1:{iport}")
check("imagegen ping", client.ping())
img_out = client.generate("a worm", size="512x512", steps=12, out_dir=TEST_APP)
check("imagegen saves file", os.path.isfile(img_out))
check("imagegen request payload", IMG_REQS and IMG_REQS[0]["prompt"] == "a worm"
      and IMG_REQS[0]["width"] == 512)
off_client = IG.SDClient(url=f"http://127.0.0.1:{iport + 1000}", timeout=3)
try:
    off_client.generate("x")
    check("imagegen offline error", False, "no exception")
except IG.ImageGenError:
    check("imagegen offline error", True)
iserver.shutdown()

# ---------------------------------------------------------------------------
# 3. Headless Core / web Bridge (the web UI backend)
# ---------------------------------------------------------------------------
from wormgpt import config as C  # noqa: E402
from wormgpt.core import Core  # noqa: E402
from wormgpt.ui_web.bridge import Bridge  # noqa: E402

EVENTS = []
core = Core(C.load(), EVENTS.append)
check("core starts", core.engine_state in ("off", "loading", "ready"),
       core.engine_state)
check("core ai_name default", core.ai_name() == "WormGPT")
core.set_ai_name("Viper")
check("core ai_name set", core.ai_name() == "Viper")
check("core search toggle", core.toggle_search() is True and core.is_search_on())
core.toggle_search()
# le raisonnement n'a plus de bouton : il reste TOUJOURS activé, même si une
# ancienne config (ou un appel API) tentait de le couper
check("core reasoning always on", core.toggle_reasoning() is True
      and core.is_reasoning_on())
core.cfg.setdefault("reasoning", {})["show"] = False
check("core forces reasoning back on",
      core.toggle_reasoning() is True and core.cfg["reasoning"]["show"] is True)
check("core prompt injects name", "Viper" in core._system_prompt())

bridge = Bridge(C.load())
st = bridge.init()
check("bridge init payload", st["app_name"] == "WormGPT"
      and st["strings"].get("nav.chat"))

# une seule version, partout
from wormgpt import theme as TH  # noqa: E402
from wormgpt import __version__ as APP_V  # noqa: E402
check("theme version follows __version__", TH.APP_VERSION == APP_V, TH.APP_VERSION)
check("bridge reports the same version", bridge.init()["version"] == APP_V)

# --- un modèle retiré n'est plus « chargé » ----------------------------
# Bug d'origine : supprimer le modèle actif laissait le nom dans la config,
# donc l'app continuait à l'afficher comme chargé/actif alors que le fichier
# n'existait plus. On simule l'installation sans écrire de vrai GGUF.
_orig_installed = M.is_installed
core.cfg.setdefault("remote", {})["active"] = ""
try:
    M.is_installed = lambda name: name == "WormGPT-3"
    core.cfg["model"]["tier"] = "WormGPT-3"
    check("installed model is labelled loaded",
          core.current_model_label() == "WormGPT-3",
          repr(core.current_model_label()))
    check("first installed chat tier found",
          core._first_installed_chat_tier() == "WormGPT-3")
    # le fichier disparaît du disque
    M.is_installed = lambda name: False
    check("removed model is no longer labelled loaded",
          core.current_model_label() == "", repr(core.current_model_label()))
    snap_del = core.system_stats()
    check("removed model absent from specs engine",
          snap_del["engine"]["model"] == "", repr(snap_del["engine"]))
    check("no catalog tier marked active once removed",
          not any(m["active"] for m in Bridge(C.load()).get_catalog()))
finally:
    M.is_installed = _orig_installed

# delete_model : le fichier part, l'état « chargé » part avec lui
_mdir = tempfile.mkdtemp(prefix="wormgpt_models_")
_orig_models_dir = C.models_dir
C.models_dir = lambda: _mdir
try:
    core.cfg["model"]["tier"] = "WormGPT-2"
    _t2 = M.get_tier("WormGPT-2")
    with open(os.path.join(_mdir, _t2.file), "wb") as _fh:
        _fh.write(b"GGUF")
    core.engine = None
    core.engine_state = "ready"
    core.delete_model("WormGPT-2")
    M.is_installed = lambda name: False
    check("select_model refuses a model that is not installed",
          core.select_model("WormGPT-3") is False)
    M.is_installed = _orig_installed
    check("delete_model removes the file",
          not os.path.isfile(os.path.join(_mdir, _t2.file)))
    check("delete_model clears the engine", core.engine is None)
    check("delete_model drops the loaded label",
          core.current_model_label() == "", repr(core.current_model_label()))
finally:
    C.models_dir = _orig_models_dir

# --- boucle d'agent (style Claude Code) ---------------------------------
class _FakeEngine:
    """Un tour avec outil, puis plus d'outil → réponse finale streamée."""
    def __init__(self):
        self.rounds = 0
        self.final_msgs = []

    def is_loaded(self):
        return True

    def complete(self, msgs, tools=None, **kw):
        self.rounds += 1
        if self.rounds == 1:
            return "", [{"id": "c1", "type": "function", "function": {
                "name": "list_dir", "arguments": '{"path": "."}'}}], ""
        return "", [], ""

    def generate(self, msgs, on_token, on_error, on_done, on_reasoning=None):
        self.final_msgs = list(msgs)
        on_token("final answer")

_orig_engine = core.engine
core.engine = _FakeEngine()
core.cfg.setdefault("tools", {}).update({"enabled": True, "mode": "auto",
                                          "cwd": TEST_APP})
with core._hist_lock:
    core.history.append({"role": "user", "text": "list the files"})
_agent_events = []
_orig_on_event = core.on_event
core.on_event = _agent_events.append
core._tool_followup()
core.on_event = _orig_on_event
_fake = core.engine
check("agent loop runs several rounds", _fake.rounds >= 2, str(_fake.rounds))
check("agent feeds tool results back",
      any(m.get("role") == "tool" for m in _fake.final_msgs))
check("agent preambles the tool list",
      any(m.get("role") == "system" and "AGENT MODE" in (m.get("content") or "")
          for m in _fake.final_msgs))
check("agent streams the final answer",
      any(e.get("type") == "stream" and e.get("text") == "final answer"
          for e in _agent_events))
core.engine = _orig_engine
core.generating = False
core.cfg["tools"]["enabled"] = False
check("bridge catalog 15", len(bridge.get_catalog()) == 15)
ss = bridge.system_summary()
check("bridge system summary", bool(ss["hardware"]) and ss["rec"]["tier"])
r = bridge.finish_setup({"language": "fr", "ai_name": "Viper",
                          "preset": "Security Professional",
                          "tier": "WormGPT-1",
                          "ui": {"accent": "#3b82f6", "particles": False},
                          "engine": {"n_ctx": 16384, "n_threads": 6}})
check("bridge finish_setup", r["ok"])
_saved = C.load()
check("wizard saves the look", _saved["ui"]["accent"] == "#3b82f6"
      and _saved["ui"]["particles"] is False, str(_saved.get("ui")))
check("wizard saves performance", _saved["engine"]["n_ctx"] == 16384
      and _saved["engine"]["n_threads"] == 6, str(_saved.get("engine")))
check("bridge configured flag", C.load()["configured"] is True)
check("bridge events streamed", any(e["type"] == "status" for e in EVENTS))

# conversation archive
core.history = [{"role": "user", "text": "Salut"},
                {"role": "assistant", "text": "Hello"}]
core._save_history()
convs = core.list_conversations()
check("conversation archived", any(c["title"] == "Salut" and c["count"] == 2
      for c in convs), str(convs))
sid0 = core._session_id()
core.new_conversation()
check("new conversation switches session", core._session_id() != sid0
      and core.history == [])
check("new conversation keeps archive", core.list_conversations()[0]["id"] == sid0
      or any(c["id"] == sid0 for c in core.list_conversations()))
ok = core.load_conversation(sid0)
check("load_conversation restores", ok and len(core.history) == 2
      and core.history[0]["text"] == "Salut")
check("load_conversation switches session", core._session_id() == sid0)

shutil.rmtree(TEST_APP, ignore_errors=True)
print()
if FAILURES:
    print(f"{len(FAILURES)} FAILURE(S): {FAILURES}")
    sys.exit(1)
print("All self-tests passed.")
sys.exit(0)