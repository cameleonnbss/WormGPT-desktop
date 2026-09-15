"""Image generation for WormGPT.

Two backends:

1. Local GGUF engine (default) — stable-diffusion.cpp is downloaded once
   into the app data directory and runs a quantized Stable Diffusion model
   (also downloaded once) entirely offline. No server, no account.
2. External Stable Diffusion WebUI (``http://127.0.0.1:7860``) — the legacy
   HTTP backend, still available in Settings.
"""

import os
import re
import shutil
import subprocess
import threading
import time
import urllib.request

from . import config as C


class ImageGenError(Exception):
    pass

SIZES = ["512x512", "768x768", "1024x1024"]

SD_CPP_DIR = "sd.cpp"
SD_CPP_URL = ("https://github.com/leejet/stable-diffusion.cpp/releases/download/"
              "master-849-d04e895/sd-master-d04e895-bin-win-cpu-x64.zip")


def _bundled_dir():
    """Engine shipped NEXT TO the exe (assets/sdengine folder in the zip).

    Deliberately NOT packed inside the exe: PyInstaller extracts every
    binary at the root of its runtime folder, and sd.cpp's ggml*.dll would
    shadow llama_cpp's own (incompatible) versions — breaking all model
    loads. A sibling folder keeps both engines isolated.
    """
    import sys
    # frozen exe : dossier de l'exe ; dev : dossier parent du paquet
    if getattr(sys, "frozen", False):
        base = os.path.dirname(os.path.abspath(sys.executable))
    else:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    p = os.path.join(base, "assets", "sdengine")
    return p if os.path.isdir(p) else ""


def engine_dir():
    d = os.path.join(C.data_dir(), SD_CPP_DIR)
    os.makedirs(d, exist_ok=True)
    return d


def engine_exe():
    """Prefer the engine bundled in the exe; fall back to the downloaded one."""
    bundled = _bundled_dir()
    if bundled and os.path.isfile(os.path.join(bundled, "sd.exe")):
        return os.path.join(bundled, "sd.exe")
    return os.path.join(engine_dir(), "sd.exe")


def model_path(name=""):
    """Path of a downloaded generation model; "" if none.

    ``name`` can be a file name ("dreamshaper-xl-v2-turbo-Q4_K.gguf") or
    empty — then the first model found is returned.
    """
    d = C.models_dir()
    if not os.path.isdir(d):
        return ""
    models = _all_models()
    if name:
        for fn, path in models:
            if fn == name or os.path.basename(path) == name:
                return path
    return models[0][1] if models else ""


# ---------------------------------------------------------------------------
# Registre des modèles de génération d'images (format GGUF de
# stable-diffusion.cpp). Uniquement des modèles communautaires
# « uncensored » qui n'appliquent AUCUN filtre : Pony V6 XL (généraliste)
# et WAI-NSFW Illustrious (anime/illustration).
# Les fichiers d'anciens modèles déjà téléchargés restent utilisables via
# _LEGACY_PREFIXES ci-dessous.
# ---------------------------------------------------------------------------
IMAGE_MODELS = [
    {"file": "pony-diffusion-v6-xl-Q4_K.gguf", "label": "WormGPT Draw-1",
     "repo": "offgrid-ai/pony-diffusion-v6-xl-GGUF",
     "size_mb": 2668, "base": 1024, "steps": 28},
    {"file": "WAI-NSFW-illustrious-SDXL-v110-Q4_0.gguf",
     "label": "WormGPT Draw-2",
     "repo": "kekusprod/WAI-NSFW-illustrious-SDXL-v110-GGUF",
     "size_mb": 1422, "base": 1024, "steps": 28},
]

#: préfixes historiques encore acceptés lors du scan du dossier de modèles
_LEGACY_PREFIXES = ("stable-diffusion-", "dreamshaper", "realvisxl",
                    "juggernaut", "pony-diffusion", "wai-")

IMAGE_FILES = {m["file"] for m in IMAGE_MODELS}


def model_info(file_name):
    """Registry entry for a file name (or None)."""
    for m in IMAGE_MODELS:
        if m["file"] == file_name:
            return m
    return None


def _all_models():
    """[(file_name, full_path)] of every downloaded txt2img model."""
    d = C.models_dir()
    out = []
    if not os.path.isdir(d):
        return out
    for fn in sorted(os.listdir(d)):
        low = fn.lower()
        if not fn.endswith(".gguf"):
            continue
        if fn in IMAGE_FILES or low.startswith(_LEGACY_PREFIXES):
            out.append((fn, os.path.join(d, fn)))
    return out


def is_ready():
    return os.path.isfile(engine_exe()) and bool(_all_models())


def _ascii_model_path(src):
    """stable-diffusion.cpp cannot open GGUF files whose path contains
    non-ASCII characters (e.g. C:\\Users\\caméléon\\...). When needed, the
    model is hard-linked/copied once into an ASCII-safe location."""
    try:
        src.encode("ascii")
        return src                      # déjà ASCII : rien à faire
    except UnicodeEncodeError:
        pass
    d = os.path.join(os.environ.get("PROGRAMDATA", r"C:\ProgramData"),
                     "WormGPT", "models")
    try:
        os.makedirs(d, exist_ok=True)
        dst = os.path.join(d, os.path.basename(src))
        if not os.path.exists(dst) or os.path.getsize(dst) != os.path.getsize(src):
            try:
                os.link(src, dst)       # gratuit : même disque, pas de copie
            except OSError:
                shutil.copyfile(src, dst)
        return dst
    except OSError:
        return src                      # on tentera quand même


def _ascii_output_path(path):
    """Same constraint for the output PNG (the exe writes it itself)."""
    try:
        path.encode("ascii")
        return path, False
    except UnicodeEncodeError:
        d = os.path.join(os.environ.get("PROGRAMDATA", r"C:\ProgramData"),
                         "WormGPT", "generated")
        try:
            os.makedirs(d, exist_ok=True)
            return os.path.join(d, os.path.basename(path)), True
        except OSError:
            return path, False


def engine_bundled():
    """True when the image engine ships inside the app (no download needed)."""
    bundled = _bundled_dir()
    return bool(bundled and os.path.isfile(os.path.join(bundled, "sd.exe")))


def engine_ready():
    return os.path.isfile(engine_exe())


def install_state():
    """(engine_installed, model_installed)"""
    return engine_ready(), bool(model_path())


def download_engine(on_progress=None):
    """Download stable-diffusion.cpp (win-cpu) and extract it."""
    import zipfile
    import io

    dest = engine_dir()
    os.makedirs(dest, exist_ok=True)
    req = urllib.request.Request(SD_CPP_URL, headers={"User-Agent": "WormGPT/1.0"})
    with urllib.request.urlopen(req, timeout=120) as r:
        total = int(r.headers.get("Content-Length") or 0)
        buf, last = bytearray(), 0
        while True:
            chunk = r.read(256 * 1024)
            if not chunk:
                break
            buf += chunk
            if on_progress and total:
                if len(buf) - last > 2 * 1024 * 1024 or len(buf) == total:
                    last = len(buf)
                    on_progress(len(buf) / total, "engine")
    with zipfile.ZipFile(io.BytesIO(bytes(buf))) as z:
        for name in z.namelist():
            if name.lower().endswith(".exe") or name.lower().endswith(".dll"):
                z.extract(name, dest)
    # the zip may nest the binaries one level deep
    for root, _dirs, files in os.walk(dest):
        for fn in files:
            if fn.lower() == "sd.exe" and os.path.abspath(
                    os.path.join(root, fn)) != os.path.abspath(engine_exe()):
                shutil.move(os.path.join(root, fn), engine_exe())
    if not os.path.isfile(engine_exe()):
        raise RuntimeError("sd.exe introuvable après extraction")


def download_model(on_progress=None, file_name=""):
    """Download a quantized txt2img GGUF into the models directory.

    ``file_name`` defaults to SD 1.5 (the lightest, ~1.7 GB). The other
    entries of :data:`IMAGE_MODELS` (SDXL finetunes, uncensored community
    models) are normally fetched from the Models page, but this keeps the
    "install engine + model" button working for any of them.
    """
    info = model_info(file_name) or IMAGE_MODELS[0]
    url = (f"https://huggingface.co/{info['repo']}/resolve/main/{info['file']}")
    dest = os.path.join(C.models_dir(), info["file"])
    partial = dest + ".part"
    req = urllib.request.Request(url, headers={"User-Agent": "WormGPT/1.0"})
    with urllib.request.urlopen(req, timeout=120) as r, open(partial, "wb") as f:
        total = int(r.headers.get("Content-Length") or 0)
        got, last = 0, 0
        while True:
            chunk = r.read(1024 * 1024)
            if not chunk:
                break
            f.write(chunk)
            got += len(chunk)
            if on_progress and total and got - last > 8 * 1024 * 1024:
                last = got
                on_progress(got / total, "model")
    if on_progress and total:
        on_progress(1.0, "model")
    os.replace(partial, dest)
    return dest


class SDClient:
    """Legacy HTTP backend (Stable Diffusion WebUI)."""

    def __init__(self, url="http://127.0.0.1:7860", timeout=600):
        self.url = (url or "").rstrip("/")
        self.timeout = timeout

    def ping(self):
        try:
            req = urllib.request.Request(self.url + "/sdapi/v1/sd-models")
            with urllib.request.urlopen(req, timeout=10) as r:
                return r.status < 300
        except (urllib.error.URLError, OSError) as exc:
            raise ImageGenError(
                f"Serveur d'images injoignable ({self.url}) : {exc}") from exc

    def generate(self, prompt, size="512x512", steps=24, out_dir=None):
        import base64
        import json

        w, h = (size.split("x") + ["512", "512"])[:2]
        payload = {
            "prompt": prompt, "negative_prompt": "",
            "width": int(w), "height": int(h), "steps": int(steps),
            "cfg_scale": 7, "sampler_name": "Euler a",
        }
        req = urllib.request.Request(
            self.url + "/sdapi/v1/txt2img",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                data = json.loads(r.read().decode("utf-8"))
        except (urllib.error.URLError, OSError) as exc:
            raise ImageGenError(
                f"Erreur du serveur d'images : {exc}") from exc
        img_b64 = (data.get("images") or [""])[0]
        if not img_b64:
            raise ImageGenError("The image server returned no image.")
        out_dir = out_dir or os.path.join(C.data_dir(), "generated")
        os.makedirs(out_dir, exist_ok=True)
        path = os.path.join(out_dir, time.strftime("img-%Y%m%d-%H%M%S.png"))
        with open(path, "wb") as f:
            f.write(base64.b64decode(img_b64))
        return path


class LocalGen:
    """Runs stable-diffusion.cpp on a downloaded GGUF model."""

    def __init__(self, progress_cb=None):
        self.progress_cb = progress_cb or (lambda step, total, stage: None)
        self._proc = None
        self._stop = threading.Event()

    @staticmethod
    def defaults_for(model_file):
        """(steps, cfg) — turbo models need ~4 steps and cfg 1.0."""
        low = (model_file or "").lower()
        if "turbo" in low or "lcm" in low or "lightning" in low or "schnell" in low:
            return 6, 1.0
        return 24, 7.0

    def generate(self, prompt, size="512x512", steps=0, out_dir=None,
                 model="", negative="", cfg_scale=0.0):
        if not is_ready():
            raise RuntimeError("local image engine not installed")
        w, h = (size.split("x") + ["512", "512"])[:2]
        mfile = os.path.basename(model_path(model))
        def_steps, def_cfg = self.defaults_for(mfile)
        steps = int(steps) if steps else def_steps
        cfg_scale = float(cfg_scale) if cfg_scale else def_cfg
        out_dir = out_dir or os.path.join(C.data_dir(), "generated")
        os.makedirs(out_dir, exist_ok=True)
        path = os.path.join(out_dir, time.strftime("img-%Y%m%d-%H%M%S") + ".png")
        out_real, out_moved = _ascii_output_path(path)
        cmd = [engine_exe(), "-m", _ascii_model_path(model_path(model)),
               "-p", prompt, "-W", str(int(w)), "-H", str(int(h)),
               "--steps", str(steps), "--cfg-scale", str(cfg_scale),
               "--rng", "cpu",
               "-o", out_real, "-t", str(max(4, (os.cpu_count() or 8) - 2))]
        if negative:
            cmd += ["-n", negative]
        creation = 0x08000000 if os.name == "nt" else 0  # CREATE_NO_WINDOW
        self._proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, errors="replace", creationflags=creation)
        pat = re.compile(r"(\d+)\s*/\s*(\d+)")
        tail = []
        for line in self._proc.stdout:
            if self._stop.is_set():
                self._proc.kill()
                raise RuntimeError("cancelled")
            tail.append(line.strip())
            tail = tail[-8:]
            m = pat.search(line)
            if m:
                self.progress_cb(int(m.group(1)), int(m.group(2)), "sampling")
        rc = self._proc.wait()
        self._proc = None
        if rc != 0:
            # message clair quand le fichier modèle est tronqué/corrompu
            detail = " ".join(tail)[-300:]
            if "read tensor" in detail or "load tensor" in detail or \
                    "sd version from file failed" in detail:
                raise RuntimeError(
                    "The image model file is damaged or incomplete — delete "
                    "it in the Models page and download it again.")
            raise RuntimeError(f"stable-diffusion.cpp exited (code {rc}) {detail}")
        if out_moved and os.path.isfile(out_real):
            shutil.move(out_real, path)      # ramène l'image dans le dossier app
        if not os.path.isfile(path):
            raise RuntimeError("aucune image produite")
        return path

    def stop(self):
        self._stop.set()
        if self._proc:
            try:
                self._proc.kill()
            except OSError:
                pass