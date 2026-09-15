"""Model catalog and download manager.

The library is deliberately SHORT and every chat tier is genuinely
uncensored: an *abliterated* fine-tune (the refusal direction physically
removed from the weights) or a *heretic* fine-tune (trained to never
refuse). Nothing half-measured, nothing that only behaves because of a
system prompt, and the underlying model names are never shown — the user
only ever sees the WormGPT ladder:

    General   WormGPT-1..6    uncensored chat, from 0.5B up to the 70B titan
    Code      WormGPT Code-1  uncensored coding specialist
    Reasoning WormGPT Reason-1..2  chain-of-thought, shown live
    Vision    WormGPT Vision-1    reads screenshots, diagrams, photos
    Dolphin   WormGPT Dolphin-1..3 the legendary uncensored Dolphin line
    Image Gen WormGPT Draw-1..2   uncensored text-to-image (NSFW-capable)

All files are public GGUF models on Hugging Face, downloaded at runtime — the
exe itself ships no model. Vision tiers download two files (model + mmproj)
in a single tracked job.
"""

import os
import shutil
import threading
import time
import urllib.request

from . import config as C

_HF = "https://huggingface.co"


class Tier:
    def __init__(self, name, category, base, params, file, mmproj, size_mb,
                 ram_min, power, desc, url, mmproj_url=""):
        self.name = name                 # e.g. "WormGPT-3", "WormGPT Code-1"
        self.category = category         # "general" | "code" | "reason" | "image"
        self.base = base                 # real underlying model
        self.params = params
        self.file = file                 # gguf filename on disk
        self.mmproj = mmproj or ""       # vision projector filename ("" if none)
        self.size_mb = size_mb           # approx total download size
        self.ram_min = ram_min           # GB of system RAM recommended
        self.power = power               # short power label
        self.desc = desc
        self.url = url
        self.mmproj_url = mmproj_url or ""

    @property
    def is_vision(self):
        return bool(self.mmproj)

    @property
    def num(self):
        """Index of the tier inside its category (1-based)."""
        return [t for t in CATALOG if t.category == self.category].index(self) + 1

    @property
    def size_str(self):
        return _fmt_mb(self.size_mb)

    @property
    def ram_str(self):
        return f"{self.ram_min} GB RAM"


CATEGORIES = [
    ("general", "General", "chat"),
    ("code", "Code", "code"),
    ("reason", "Reasoning", "chip"),
    ("vision", "Vision", "image"),
    ("dolphin", "Dolphin", "zap"),
    ("genimg", "Image Gen", "spark"),
]


def _q(name, repo, file):
    return f"{_HF}/{repo}/resolve/main/{file}"


CATALOG = [
    # ------------------------------------------------------------ General --
    Tier("WormGPT-1", "general", "Uncensored", "0.5B",
         "Qwen2.5-0.5B-Instruct-abliterated.Q4_K_M.gguf", "", 398, 4,
         "Ultra-light",
         "Instant answers on any machine. Refusals physically removed from "
         "the weights — the fastest way to start.",
         _q("g0.5", "mradermacher/Qwen2.5-0.5B-Instruct-abliterated-GGUF",
            "Qwen2.5-0.5B-Instruct-abliterated.Q4_K_M.gguf")),
    Tier("WormGPT-2", "general", "Uncensored", "2B",
         "gemma-2-2b-it-abliterated.Q4_K_M.gguf", "", 1629, 6,
         "Crisp",
         "Clean prose and honest, direct answers — the safety layer has "
         "simply been cut out.",
         _q("g2", "mradermacher/gemma-2-2b-it-abliterated-GGUF",
            "gemma-2-2b-it-abliterated.Q4_K_M.gguf")),
    Tier("WormGPT-3", "general", "Uncensored", "3B",
         "Llama-3.2-3B-Instruct-abliterated.Q4_K_M.gguf", "", 2137, 8,
         "Balanced",
         "The sweet spot of the small ladder: strong reasoning, no refusals. "
         "Recommended for most machines.",
         _q("g3", "mradermacher/Llama-3.2-3B-Instruct-abliterated-GGUF",
            "Llama-3.2-3B-Instruct-abliterated.Q4_K_M.gguf")),
    Tier("WormGPT-4", "general", "Uncensored heretic", "4B (8B MoE)",
         "gemma-4-E4B-it-ultra-uncensored-heretic-Q4_K_M.gguf", "", 5088, 12,
         "Heretic",
         "Mixture-of-experts speed with an 8B-class brain: retrained to "
         "answer everything, trained to never refuse.",
         _q("g4e4", "llmfan46/gemma-4-E4B-it-ultra-uncensored-heretic-GGUF",
            "gemma-4-E4B-it-ultra-uncensored-heretic-Q4_K_M.gguf")),
    Tier("WormGPT-5", "general", "Uncensored", "8B",
         "Llama-3.1-8B-Instruct-abliterated.Q4_K_M.gguf", "", 4693, 12,
         "Powerful",
         "Deep technical reasoning with every refusal direction removed. "
         "The power pick if your machine can take it.",
         _q("g8", "mradermacher/Llama-3.1-8B-Instruct-abliterated-GGUF",
            "Llama-3.1-8B-Instruct-abliterated.Q4_K_M.gguf")),
    Tier("WormGPT-6", "general", "Uncensored", "70B",
         "Llama-3.3-70B-Instruct-abliterated.IQ4_XS.gguf", "", 36497, 48,
         "Titan",
         "The final word: a 70B monster with the alignment cut out, "
         "rivaling closed-source AIs. 48 GB of RAM.",
         _q("g70", "mradermacher/Llama-3.3-70B-Instruct-abliterated-GGUF",
            "Llama-3.3-70B-Instruct-abliterated.IQ4_XS.gguf")),

    # --------------------------------------------------------------- Code --
    Tier("WormGPT Code-1", "code", "Uncensored code", "7B",
         "Qwen2.5-Coder-7B-Instruct-abliterated.Q4_K_M.gguf", "", 4680, 12,
         "Powerful",
         "Uncensored code understanding across every major language: "
         "generation, review, debugging, exploits.",
         _q("c7", "mradermacher/Qwen2.5-Coder-7B-Instruct-abliterated-GGUF",
            "Qwen2.5-Coder-7B-Instruct-abliterated.Q4_K_M.gguf")),

    # --------------------------------------------------------- Reasoning --
    Tier("WormGPT Reason-1", "reason", "Uncensored reasoning", "1.5B",
         "DeepSeek-R1-Distill-Qwen-1.5B-abliterated.Q4_K_M.gguf", "", 1066, 8,
         "Light",
         "Thinks before it answers, and shows you the thinking live. "
         "Uncensored chain of thought.",
         _q("r1.5", "mradermacher/DeepSeek-R1-Distill-Qwen-1.5B-abliterated-GGUF",
            "DeepSeek-R1-Distill-Qwen-1.5B-abliterated.Q4_K_M.gguf")),
    Tier("WormGPT Reason-2", "reason", "Uncensored reasoning", "14B",
         "Qwen3-14B-abliterated.Q4_K_M.gguf", "", 8585, 16,
         "Deep",
         "Hybrid thinking mode: deep multi-step reasoning on maths, logic "
         "and hard technical analysis, with no moralising.",
         _q("r3-14", "mradermacher/Qwen3-14B-abliterated-GGUF",
            "Qwen3-14B-abliterated.Q4_K_M.gguf")),

    # ------------------------------------------------------------- Vision --
    Tier("WormGPT Vision-1", "vision", "Vision", "2B",
         "Qwen2-VL-2B-Instruct-Q4_K_M.gguf",
         "mmproj-Qwen2-VL-2B-Instruct-f16.gguf", 2700, 8,
         "Light",
         "Reads screenshots, diagrams, photos and documents. The one tier "
         "that is not abliterated — no uncensored vision model exists yet.",
         _q("v2", "bartowski/Qwen2-VL-2B-Instruct-GGUF",
            "Qwen2-VL-2B-Instruct-Q4_K_M.gguf"),
         _q("v2m", "bartowski/Qwen2-VL-2B-Instruct-GGUF",
            "mmproj-Qwen2-VL-2B-Instruct-f16.gguf")),

    # ------------------------------------------------------------ Dolphin --
    Tier("WormGPT Dolphin-1", "dolphin", "Dolphin uncensored", "1.1B",
         "TinyDolphin-2.8-1.1b.Q4_K_M.gguf", "", 637, 4,
         "Tiny",
         "The original tiny Dolphin: a 637 MB uncensored chat model that "
         "runs anywhere.",
         _q("d1", "mradermacher/TinyDolphin-2.8-1.1b-GGUF",
            "TinyDolphin-2.8-1.1b.Q4_K_M.gguf")),
    Tier("WormGPT Dolphin-2", "dolphin", "Dolphin uncensored", "8B",
         "dolphin-2.9-llama3-8b.Q4_K_M.gguf", "", 4980, 12,
         "Wild",
         "The legendary Dolphin line: creative, direct and completely "
         "uncensored. Trained to obey, not to lecture.",
         _q("d3", "QuantFactory/dolphin-2.9-llama3-8b-GGUF",
            "dolphin-2.9-llama3-8b.Q4_K_M.gguf")),
    Tier("WormGPT Dolphin-3", "dolphin", "Dolphin uncensored", "24B",
         "Dolphin3.0-Mistral-24B.Q4_K_M.gguf", "", 13670, 24,
         "Beast",
         "Massive 24B unaligned Dolphin: deep knowledge, obeys everything, "
         "never refuses. For strong machines.",
         _q("d4", "mradermacher/Dolphin3.0-Mistral-24B-GGUF",
            "Dolphin3.0-Mistral-24B.Q4_K_M.gguf")),

    # ---------------------------------------------------------- Image Gen --
    Tier("WormGPT Draw-1", "genimg", "Uncensored image", "SDXL",
         "pony-diffusion-v6-xl-Q4_K.gguf", "", 2668, 8,
         "Uncensored",
         "No filter, no refusal, extremely versatile: characters, scenes, "
         "any style. 100% offline.",
         _q("pony", "offgrid-ai/pony-diffusion-v6-xl-GGUF",
            "pony-diffusion-v6-xl-Q4_K.gguf")),
    Tier("WormGPT Draw-2", "genimg", "Uncensored image", "SDXL",
         "WAI-NSFW-illustrious-SDXL-v110-Q4_0.gguf", "", 1422, 8,
         "Raw",
         "Uncensored anime and illustration model: sharp line art, fast "
         "thanks to the light quant. 100% offline.",
         _q("wai", "kekusprod/WAI-NSFW-illustrious-SDXL-v110-GGUF",
            "WAI-NSFW-illustrious-SDXL-v110-Q4_0.gguf")),
]


def get_tier(name):
    for t in CATALOG:
        if t.name == name:
            return t
    return CATALOG[2]


def catalog_path(tier_name, for_mmproj=False):
    t = get_tier(tier_name)
    fname = t.mmproj if for_mmproj else t.file
    return os.path.join(C.models_dir(), fname)


def is_installed(tier_name):
    t = get_tier(tier_name)
    for fname in (t.file, t.mmproj) if t.is_vision else (t.file,):
        p = os.path.join(C.models_dir(), fname)
        if os.path.exists(p + ".part"):
            return False
        if not os.path.isfile(p):
            return False
    # sanity: main gguf roughly the right size (mmproj not size-checked)
    p = os.path.join(C.models_dir(), t.file)
    return os.path.getsize(p) >= t.size_mb * 0.85 * 1024 * 1024


def installed_size_mb():
    total = 0
    for t in CATALOG:
        if not is_installed(t.name):
            continue
        for fname in (t.file, t.mmproj) if t.is_vision else (t.file,):
            p = os.path.join(C.models_dir(), fname)
            if os.path.isfile(p):
                total += os.path.getsize(p)
    return total / (1024 * 1024)


def free_space_mb():
    try:
        return shutil.disk_usage(C.models_dir()).free / (1024 * 1024)
    except OSError:
        return 0.0


def cleanup_partials():
    """Remove interrupted download leftovers at startup."""
    for t in CATALOG:
        for fname in (t.file, t.mmproj) if t.is_vision else (t.file,):
            p = os.path.join(C.models_dir(), fname) + ".part"
            try:
                if os.path.exists(p):
                    os.remove(p)
            except OSError:
                pass


def _fmt_mb(mb):
    if mb >= 1024:
        return f"{mb / 1024:.1f} GB"
    return f"{mb:.0f} MB"


# ---------------------------------------------------------------------------
# Download manager (stdlib only: urllib + threads)
# ---------------------------------------------------------------------------

class DownloadJob:
    """Streams one or two GGUF files (model + optional mmproj) to disk.

    Big files are fetched with several parallel HTTP range requests
    (segmented download) — a single connection caps at a fraction of what
    the CDN allows. Each segment is written to its own ``.segN`` file so an
    interrupted download resumes where it stopped, then the segments are
    concatenated and the final size is verified before install.
    """

    CHUNK = 1024 * 1024
    MIN_SEG_SIZE = 16 * 1024 * 1024      # below this, one stream is enough
    MAX_STREAMS = 16

    def __init__(self, tier, on_progress=None, on_done=None, on_error=None):
        self.tier = tier
        self.on_progress = on_progress      # (received, total)
        self.on_done = on_done              # ()
        self.on_error = on_error            # (message)
        self._cancel = threading.Event()
        self._thread = None

    @property
    def running(self):
        return self._thread is not None and self._thread.is_alive()

    def start(self):
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def cancel(self):
        self._cancel.set()

    def _drop_partials(self):
        for fname in (self.tier.file, self.tier.mmproj) if self.tier.is_vision else (self.tier.file,):
            for suffix in (".part",):
                try:
                    p = os.path.join(C.models_dir(), fname) + suffix
                    if os.path.exists(p):
                        os.remove(p)
                except OSError:
                    pass
            # segments d'un téléchargement segmenté
            for i in range(self.MAX_STREAMS):
                try:
                    p = f"{os.path.join(C.models_dir(), fname)}.seg{i}"
                    if os.path.exists(p):
                        os.remove(p)
                except OSError:
                    pass

    # ------------------------------------------------------------------
    # Segmented download engine
    # ------------------------------------------------------------------

    def _run(self):
        steps = [(self.tier.url, self.tier.file)]
        if self.tier.is_vision:
            steps.append((self.tier.mmproj_url, self.tier.mmproj))
        total = self.tier.size_mb * 1024 * 1024
        received = 0
        try:
            for url, fname in steps:
                received = self._download(url, fname, received, total)
                if self._cancel.is_set():
                    raise _Cancelled()
            if self.on_done:
                self.on_done()
        except _Cancelled:
            self._drop_partials()
        except Exception as exc:
            self._drop_partials()
            if self.on_error:
                self.on_error(f"Download failed: {exc}")

    def _download(self, url, fname, received, total):
        """Fetch one file with parallel range streams, then assemble it."""
        dest = os.path.join(C.models_dir(), fname)
        final_part = dest + ".part"
        expected = self._expected_size(url, total)
        if not expected:
            raise RuntimeError(f"{fname}: server gave no size")

        # How many streams? Small files don't need segmentation.
        n_streams = 1 if expected < self.MIN_SEG_SIZE else self.MAX_STREAMS
        seg_size = expected // n_streams
        bounds = []
        for i in range(n_streams):
            lo = i * seg_size
            hi = (i + 1) * seg_size - 1 if i < n_streams - 1 else expected - 1
            bounds.append((lo, hi))

        # Segment files on disk: .segN (already on disk from a previous
        # attempt) keeps its bytes; each stream resumes its own segment.
        seg_paths = [f"{dest}.seg{i}" for i in range(n_streams)]
        done_bytes = [0] * n_streams        # per-stream progress counters
        errors = []
        lock = threading.Lock()

        def stream(i, lo, hi):
            path = seg_paths[i]
            have = os.path.getsize(path) if os.path.isfile(path) else 0
            seg_len = hi - lo + 1
            if have >= seg_len:                 # segment already complete
                done_bytes[i] = seg_len
                return
            done_bytes[i] = have
            headers = {"User-Agent": "WormGPT-Desktop/1.0", "Accept": "*/*"}
            if have:
                headers["Range"] = f"bytes={lo + have}-{hi}"
            else:
                headers["Range"] = f"bytes={lo}-{hi}"
            last_err = None
            for attempt in range(6):
                if self._cancel.is_set():
                    raise _Cancelled()
                try:
                    req = urllib.request.Request(url, headers=headers)
                    with urllib.request.urlopen(req, timeout=90) as resp:
                        mode = "ab" if resp.status == 206 and have else "wb"
                        if mode == "wb":
                            have = 0
                            done_bytes[i] = 0
                        with open(path, mode) as f:
                            while True:
                                if self._cancel.is_set():
                                    raise _Cancelled()
                                chunk = resp.read(self.CHUNK)
                                if not chunk:
                                    break
                                f.write(chunk)
                                have += len(chunk)
                                done_bytes[i] = have
                                if self.on_progress:
                                    self.on_progress(
                                        received + sum(done_bytes), total)
                    if os.path.getsize(path) >= seg_len:
                        done_bytes[i] = seg_len
                        return
                    last_err = RuntimeError(f"segment {i} short")
                except _Cancelled:
                    raise
                except Exception as exc:
                    last_err = exc
                    time.sleep(1 + attempt)
                have = os.path.getsize(path) if os.path.isfile(path) else 0
                done_bytes[i] = have
                if have:
                    headers["Range"] = f"bytes={lo + have}-{hi}"
            raise RuntimeError(f"{fname} segment {i}: {last_err}")

        def guarded(i, lo, hi):
            try:
                stream(i, lo, hi)
            except BaseException as exc:       # threads swallow raises
                with lock:
                    errors.append(exc)

        threads = [threading.Thread(target=guarded, args=(i, lo, hi), daemon=True)
                   for i, (lo, hi) in enumerate(bounds)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        if self._cancel.is_set():
            raise _Cancelled()
        if errors:
            raise errors[0]

        # All segments complete: concatenate into .part then install.
        with open(final_part, "wb") as out:
            for path in seg_paths:
                with open(path, "rb") as f:
                    shutil.copyfileobj(f, out, length=4 * 1024 * 1024)
        size_now = os.path.getsize(final_part)
        if size_now < expected * 0.98:
            raise RuntimeError(
                f"{fname}: incomplete download "
                f"({size_now // (1024*1024)} MB / {expected // (1024*1024)} MB) "
                "— try again")
        os.replace(final_part, dest)
        for path in seg_paths:
            try:
                os.remove(path)
            except OSError:
                pass
        return received + expected

    def _expected_size(self, url, total):
        """Real Content-Length when the catalogue estimate is off."""
        try:
            req = urllib.request.Request(url, method="HEAD", headers={
                "User-Agent": "WormGPT-Desktop/1.0"})
            with urllib.request.urlopen(req, timeout=30) as r:
                return int(r.headers.get("Content-Length") or 0) or total
        except Exception:
            return total


class _Cancelled(Exception):
    pass