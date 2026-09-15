"""Local inference engine (llama.cpp via llama-cpp-python).

The engine runs fully offline — no cloud, no account, no telemetry. Models
are loaded from the user's model directory and generation is streamed token
by token so the UI can render text as it arrives. Vision models load an
additional mmproj projector and accept images inside chat messages.
"""

import base64
import os
import re
import shutil
import sys
import tempfile
import threading

from . import theme as T


# ---------------------------------------------------------------------------
# Chemin ASCII : certains backends C (llama.cpp/sd.cpp selon le build) échouent
# silencieusement sur des chemins non-ASCII (ex. profil Windows "caméléon").
# On copie le modèle (hard link si possible : zéro espace disque en plus)
# vers un chemin 100% ASCII avant de le charger.
# ---------------------------------------------------------------------------
_ASCII_TMP = None

_LLAMA_PRELOADED = False


def _preload_llama_dlls():
    """Load the ggml/llama DLLs from llama_cpp/lib with ABSOLUTE paths.

    PyInstaller also copies ggml*.dll to the bundle root (dependency walk);
    if Windows resolves those first, llama.dll gets mismatched ggml versions
    and every model load fails with "no backends are loaded". Loading the
    correct DLLs by absolute path first pins the right versions in the
    process (already-loaded modules always win by name).
    """
    global _LLAMA_PRELOADED
    if _LLAMA_PRELOADED or sys.platform != "win32":
        return
    _LLAMA_PRELOADED = True
    try:
        import ctypes
        import llama_cpp
        lib = os.path.join(os.path.dirname(llama_cpp.__file__), "lib")
        if not os.path.isdir(lib):
            return
        # ordre des dépendances : base -> core -> cpu -> mtmd -> llama
        for name in ("ggml-base.dll", "ggml.dll", "ggml-cpu.dll",
                     "mtmd.dll", "llama.dll"):
            p = os.path.join(lib, name)
            if os.path.isfile(p):
                try:
                    ctypes.WinDLL(p)
                except OSError:
                    pass
    except Exception:
        pass


def ascii_safe_path(path):
    """Return a path guaranteed free of non-ASCII characters.

    Uses a hard link when the source and the staging dir are on the same
    volume, else a real copy. The staged file lives in %TEMP%/WormGPT-models
    and is reused across loads (same size ⇒ same file).
    """
    global _ASCII_TMP
    try:
        path.encode("ascii")
        return path                      # déjà ASCII : rien à faire
    except UnicodeEncodeError:
        pass
    if not _ASCII_TMP:
        _ASCII_TMP = os.path.join(tempfile.gettempdir(), "WormGPT-models")
        try:
            os.makedirs(_ASCII_TMP, exist_ok=True)
        except OSError:
            _ASCII_TMP = None
            return path
    base = "".join(c if c.isascii() and (c.isalnum() or c in "._-")
                   else "_" for c in os.path.basename(path))
    if not base or base.startswith("."):
        base = "model.gguf"
    dest = os.path.join(_ASCII_TMP, base)
    try:
        if os.path.isfile(dest) and \
                os.path.getsize(dest) == os.path.getsize(path):
            return dest                  # déjà sur place (même taille)
        try:
            os.remove(dest)
        except OSError:
            pass
        try:
            os.link(path, dest)          # hard link : pas de copie réelle
        except OSError:
            shutil.copy2(path, dest)
        return dest
    except OSError:
        return path                      # on tentera quand même l'original

# ---------------------------------------------------------------------------
# Token cleanup — strip chat-template special tokens the backend may leak
# ---------------------------------------------------------------------------
_SPECIAL = re.compile(r"<\|?(?:im_start|im_end|s|/s|endoftext)\|?>")

ALLOWED_STOPS = {"</s>", "<|im_end|>"}

# Reasoning markers. Every common local-model style is covered so the
# chain of thought never leaks into the answer:
#   Qwen3 / R1-distill  <think>…</think>
#   DeepSeek-R1 (raw)   …
#   Hermes / others     <thinking>…</thinking>, <reasoning>…</reasoning>
#   gpt-oss             <|channel|>analysis…<|channel|>final
# Kept internal: the UI renders them as a collapsible "Reasoning" block.
_THINK_OPEN = re.compile(
    r"<think\s*>|<thinking\s*>|<\|\s*thinking\s*\|>|<reasoning\s*>|"
    r"<thought\s*>|<\|\s*reasoning\s*\|>|<\|\s*begin_of_thought\s*\|>|"
    r"<\|channel\|>\s*analysis", re.I)
_THINK_CLOSE = re.compile(
    r"</think\s*>|</thinking\s*>|<\|\s*/thinking\s*\|>|</reasoning\s*>|"
    r"</thought\s*>|<\|\s*/reasoning\s*\|>|<\|\s*end_of_thought\s*\|>|"
    r"<\|channel\|>\s*final", re.I)

#: littéraux utilisés pour retenir un fragment de balise coupé entre deux
#: chunks ("<thi" + "nk>")
_TAGS = ("<think>", "<thinking>", "<|thinking|>", "<reasoning>",
         "<thought>", "<|reasoning|>", "<|begin_of_thought|>",
         "<|channel|>analysis", "</think>", "</thinking>",
         "<|/thinking|>", "</reasoning>", "</thought>",
         "<|/reasoning|>", "<|end_of_thought|>", "<|channel|>final")


def split_think(text):
    """Split a full text into (reasoning, final) extracting thinking blocks."""
    reason, final = [], []
    state, pos = "text", 0
    while True:
        if state == "text":
            m = _THINK_OPEN.search(text, pos)
            if not m:
                final.append(text[pos:])
                break
            final.append(text[pos:m.start()])
            pos, state = m.end(), "reason"
        else:
            m = _THINK_CLOSE.search(text, pos)
            if not m:
                reason.append(text[pos:])
                break
            reason.append(text[pos:m.start()])
            pos, state = m.end(), "text"
    return "".join(reason).strip(), "".join(final).strip()


def _partial_tag_len(buf):
    """Length of the trailing fragment that might be an incomplete think tag.

    Streaming chunks can split '<think>' between two pieces ('<thi' + 'nk>');
    the caller must hold such a fragment back instead of emitting it as text.
    """
    i = buf.rfind("<")
    if i == -1:
        return 0
    frag = buf[i:].lower()
    for cand in _TAGS:
        if cand.startswith(frag):
            return len(frag)
    return 0


class _ThinkSplitter:
    """État persistant du découpage texte/raisonnement d'un flux.

    Une instance est conservée pendant TOUT le stream : c'est ce qui permet
    de retenir un fragment de balise coupé entre deux chunks sans jamais
    l'afficher comme du texte.
    """

    def __init__(self):
        self.buf = ""
        self.state = "text"

    def feed(self, piece):
        out = []
        self.buf += piece
        while True:
            if self.state == "text":
                m = _THINK_OPEN.search(self.buf)
                if not m:
                    hold = _partial_tag_len(self.buf)
                    emit = self.buf[:-hold] if hold else self.buf
                    if emit:
                        out.append(("text", emit))
                    self.buf = self.buf[-hold:] if hold else ""
                    break
                if m.start() > 0:
                    out.append(("text", self.buf[:m.start()]))
                self.buf, self.state = self.buf[m.end():], "reason"
            else:
                m = _THINK_CLOSE.search(self.buf)
                if not m:
                    hold = _partial_tag_len(self.buf)
                    emit = self.buf[:-hold] if hold else self.buf
                    if emit:
                        out.append(("reason", emit))
                    self.buf = self.buf[-hold:] if hold else ""
                    break
                if m.start() > 0:
                    out.append(("reason", self.buf[:m.start()]))
                self.buf, self.state = self.buf[m.end():], "text"
        return out

    def flush(self):
        if not self.buf:
            return []
        kind, part = self.state, self.buf
        self.buf = ""
        return [(kind, part)]


def _iter_split(chunks):
    """Yield ("text"|"reason", piece) tuples from a chunk stream."""
    sp = _ThinkSplitter()
    for piece in chunks:
        for kind, part in sp.feed(piece):
            yield (kind, part)
    for kind, part in sp.flush():
        yield (kind, part)


class EngineError(Exception):
    pass


class Engine:
    """Wraps one loaded GGUF model with a chat-completion interface."""

    def __init__(self, model_path, n_ctx=4096, n_threads=0, temperature=0.7,
                 max_tokens=1024, system_prompt="", clip_model_path=None,
                 status_cb=None):
        self.model_path = model_path
        self.clip_model_path = clip_model_path
        self.n_ctx = n_ctx
        self.n_threads = n_threads
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.system_prompt = system_prompt
        self.status_cb = status_cb or (lambda s: None)
        self._llm = None
        self._lock = threading.Lock()
        self._stop = threading.Event()

    # -- lifecycle ----------------------------------------------------------

    def is_loaded(self):
        return self._llm is not None

    @property
    def is_vision(self):
        return bool(self.clip_model_path)

    def load(self):
        """Import llama_cpp lazily and load the model. Raises EngineError."""
        _preload_llama_dlls()
        try:
            from llama_cpp import Llama
        except Exception as exc:  # missing or broken install
            raise EngineError(
                "The local inference engine (llama-cpp-python) is not "
                f"available: {exc}\n\nRebuild the exe with the bundled "
                "engine, or install it with:\n"
                "  python -m pip install llama-cpp-python"
            ) from exc

        if not os.path.isfile(self.model_path):
            raise EngineError(f"Model file not found:\n{self.model_path}")

        # Garde-fou bon marché : un GGUF commence toujours par la magie
        # "GGUF". Un fichier tronqué/corrompu au point de ne même plus avoir
        # l'entête est détecté ici avec un message clair (sans toucher au
        # fichier : c'est à l'utilisateur de le supprimer).
        try:
            with open(self.model_path, "rb") as fh:
                magic = fh.read(4)
            if magic != b"GGUF":
                raise EngineError(
                    "This model file is not a valid GGUF (bad header) — "
                    "delete it in the Models page and download it again.\n"
                    f"File: {self.model_path}")
        except EngineError:
            raise
        except OSError:
            pass

        # Toujours avoir une fenêtre de contexte valide, quel que soit le
        # modèle : un n_ctx supérieur à l'entraînement dégrade les réponses,
        # et un fichier GGUF corrompu/tronqué doit produire un message clair.
        file_gb = 0.0
        try:
            file_gb = os.path.getsize(self.model_path) / (1024 ** 3)
        except OSError:
            pass
        n_ctx = self.n_ctx
        if file_gb and n_ctx > 8192 and file_gb < 1.2:
            n_ctx = 8192          # petits modèles : au-delà, ça délire

        kwargs = dict(
            model_path=self.model_path,
            n_ctx=n_ctx,
            n_threads=self.n_threads or None,
            n_batch=min(512, max(64, (self.n_threads or 8) * 64)),
            # verbeux si un marqueur debug est présent (sinon silencieux)
            verbose=os.path.isfile(os.path.join(tempfile.gettempdir(),
                                                "WormGPT-verbose")),
        )
        if self.clip_model_path:
            if not os.path.isfile(self.clip_model_path):
                raise EngineError(f"Vision projector not found:\n{self.clip_model_path}")
            kwargs["clip_model_path"] = self.clip_model_path
            self.status_cb("Loading vision model…")
        else:
            self.status_cb("Loading model…")
        try:
            self._llm = Llama(**kwargs)
        except Exception as exc:
            self._llm = None
            msg = str(exc)
            if len(msg) > 300:
                msg = msg[:300] + "…"
            # diagnostic complet quelque part (le thread est daemon :
            # sans ça, une erreur interne ne laisse aucune trace)
            try:
                import traceback as _tb
                from . import config as _C
                with open(os.path.join(_C.data_dir(), "debug.log"), "a",
                          encoding="utf-8") as _f:
                    _f.write("ENGINE-LOAD-FAIL " + self.model_path + "\n" +
                             "".join(_tb.format_exception(exc))[-2000:] + "\n")
            except OSError:
                pass
            if "gguf" in msg.lower() or "magic" in msg.lower() or \
                    "format" in msg.lower() or "invalid" in msg.lower():
                msg = ("The model file appears damaged or incomplete — try "
                       "downloading it again from the Models page. (" + msg + ")")
            raise EngineError(f"Failed to load model: {msg}") from exc
        self.status_cb("Model ready")

    def unload(self):
        with self._lock:
            self._llm = None

    # -- generation ---------------------------------------------------------

    def generate(self, messages, on_token, on_error, on_done, on_reasoning=None):
        """Run generation on a background thread.

        ``messages``  list of {role, content} dicts (system already merged).
        ``on_token``  called with each text chunk (UI thread safe via queue).
        ``on_reasoning`` optional — called with reasoning chunks as they stream.
        ``on_done(text, reasoning)`` called on completion.
        """
        self._stop.clear()
        t = threading.Thread(target=self._generate_worker,
                             args=(list(messages), on_token, on_error, on_done,
                                   on_reasoning),
                             daemon=True)
        t.start()
        return t

    def stop(self):
        self._stop.set()

    def _generate_worker(self, messages, on_token, on_error, on_done,
                         on_reasoning=None):
        try:
            kwargs = dict(messages=list(messages), temperature=self.temperature,
                          max_tokens=self.max_tokens)
            with self._lock:
                if self._llm is None:
                    raise EngineError("No model loaded.")
                text_parts, reason_parts = [], []
                for kind, piece in self._iter_events(kwargs):
                    if not piece:
                        continue
                    if kind == "reason":
                        reason_parts.append(piece)
                        if on_reasoning:
                            on_reasoning(piece)
                    else:
                        text_parts.append(piece)
                        on_token(piece)
            # Le texte a DÉJÀ été poussé au fil de l'eau par `on_token`
            # ci-dessus (`_iter_split` émet aussi son dernier tampon). Ne
            # jamais repousser `text` ici : le chat l'afficherait en double.
            text = "".join(text_parts).strip()
            reason = "".join(reason_parts).strip()
            on_done(text, reason)
        except EngineError as exc:
            on_error(str(exc))
        except Exception as exc:
            on_error(f"Generation failed: {exc}")

    # -- synchronous API (bot, local server, agent loop) -------------------

    def complete(self, messages, tools=None, temperature=None, max_tokens=None):
        """Run a full non-streamed turn. Returns (text, raw_tool_calls, reasoning).

        Runs in the calling thread; serialised on the engine lock so it never
        races with the chat UI. ``raw_tool_calls`` is the list of tool_call
        dicts as returned by the backend (empty when the model produced no
        tool calls).
        """
        with self._lock:
            if self._llm is None:
                raise EngineError("No model loaded.")
            kwargs = dict(
                messages=list(messages),
                temperature=temperature if temperature is not None else self.temperature,
                max_tokens=max_tokens if max_tokens is not None else self.max_tokens,
                stream=False,
            )
            if tools:
                kwargs["tools"] = tools
                try:
                    resp = self._invoke(kwargs)
                except Exception:
                    kwargs.pop("tools")
                    resp = self._invoke(kwargs)
            else:
                resp = self._invoke(kwargs)
        msg = (resp.get("choices") or [{}])[0].get("message") or {}
        text = _SPECIAL.sub("", msg.get("content") or "").strip()
        native = _SPECIAL.sub("", msg.get("reasoning_content") or "").strip()
        reason, text = split_think(text)
        if native:
            reason = (native + ("\n\n" + reason if reason else "")).strip()
        return text, list(msg.get("tool_calls") or []), reason

    def complete_stream(self, messages, temperature=None, max_tokens=None):
        """Stream a full turn synchronously; yields cleaned text chunks
        (thinking blocks are stripped, so API consumers only see the answer)."""
        with self._lock:
            if self._llm is None:
                raise EngineError("No model loaded.")
            kwargs = dict(
                messages=list(messages),
                temperature=temperature if temperature is not None else self.temperature,
                max_tokens=max_tokens if max_tokens is not None else self.max_tokens,
            )
            for kind, piece in _iter_split(self._iter_chunks(kwargs)):
                if kind == "text" and piece:
                    yield piece

    # -- internals ----------------------------------------------------------

    def _invoke(self, kwargs):
        """Call the backend, adapting to llama-cpp-python versions."""
        try:
            return self._llm.create_chat_completion(**kwargs)
        except (AttributeError, TypeError):
            return self._llm(**kwargs)

    def _iter_raw(self, kwargs):
        """Yield each streamed choice object."""
        stream = self._invoke(dict(kwargs, stream=True))
        for chunk in stream:
            if self._stop.is_set():
                break
            choices = chunk.get("choices") or []
            if choices:
                yield choices[0]

    def _iter_chunks(self, kwargs):
        """Yield cleaned text chunks (thinking blocks are NOT stripped)."""
        for choice in self._iter_raw(kwargs):
            piece = (choice.get("delta") or {}).get("content")
            if piece is None:
                piece = choice.get("text")
            if not piece:
                continue
            piece = _SPECIAL.sub("", piece)
            if piece:
                yield piece

    def _iter_events(self, kwargs):
        """Yield ("text"|"reason", piece) with a PERSISTENT splitter.

        Handles both the native ``reasoning_content`` field exposed by some
        backends and every ``<think>``/``<thinking>``/```` style, even when a
        tag is split across two stream chunks.
        """
        sp = _ThinkSplitter()
        for choice in self._iter_raw(kwargs):
            delta = choice.get("delta") or {}
            rc = delta.get("reasoning_content")
            if rc:
                piece = _SPECIAL.sub("", rc)
                if piece:
                    yield ("reason", piece)
            piece = delta.get("content")
            if piece is None:
                piece = choice.get("text")
            if not piece:
                continue
            piece = _SPECIAL.sub("", piece)
            if not piece:
                continue
            for kind, part in sp.feed(piece):
                yield (kind, part)
        for kind, part in sp.flush():
            yield (kind, part)

    # -- helpers ------------------------------------------------------------

    @staticmethod
    def trim_history(messages, max_turns=12, ctx_tokens=4096):
        """Keep the system prompt + the most recent turns within context.

        ``ctx_tokens`` is an approximate character budget (≈4 chars/token):
        long answers get dropped from history first, otherwise the context
        silently overflows and the model produces garbage.
        """
        sys_msgs = [m for m in messages if m.get("role") == "system"]
        rest = [m for m in messages if m.get("role") != "system"]
        if len(rest) > max_turns * 2:
            rest = rest[-(max_turns * 2):]
        budget = max(1000, ctx_tokens) * 4
        def size(m):
            c = m.get("content")
            if isinstance(c, list):
                c = " ".join(str(p.get("text", "")) for p in c if isinstance(p, dict))
            return len(c or "")
        while rest and sum(size(m) for m in rest) > budget:
            rest = rest[1:]   # jette le plus vieux
        return sys_msgs + rest


def image_data_uri(path):
    """Encode a local image as a data: URI for multimodal messages."""
    ext = os.path.splitext(path)[1].lower().lstrip(".")
    if ext == "jpg":
        ext = "jpeg"
    mime = f"image/{ext}" if ext else "image/jpeg"
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("ascii")
    return f"data:{mime};base64,{b64}"


def _content(role, text, image, vision):
    if image and vision:
        return {"role": role, "content": [
            {"type": "image_url", "image_url": {"url": image_data_uri(image)}},
            {"type": "text", "text": text},
        ]}
    return {"role": role, "content": text}


def build_messages(system_prompt, history, user_text, user_image=None, vision=False):
    """Assemble the message list sent to the model.

    ``history`` entries are dicts: {role, text, image?}. Images are embedded
    as data URIs only when the engine is vision-capable.
    """
    msgs = [{"role": "system", "content": system_prompt}]
    for entry in history:
        msgs.append(_content(entry["role"], entry.get("text", ""),
                             entry.get("image"), vision))
    msgs.append(_content("user", user_text, user_image, vision))
    return Engine.trim_history(msgs, ctx_tokens=4096)