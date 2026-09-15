# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec — builds dist/WormGPT.exe (single file, no console)."""

from PyInstaller.utils.hooks import collect_all
from PyInstaller.utils.win32.versioninfo import (
    FixedFileInfo, StringFileInfo, StringStruct, StringTable, VarFileInfo,
    VarStruct, VSVersionInfo,
)

datas, binaries, hiddenimports = [], [], []
for pkg in ("llama_cpp", "aiohttp", "webview"):
    try:
        d, b, h = collect_all(pkg)
    except Exception:
        continue
    datas += d
    binaries += b
    hiddenimports += h

hiddenimports += ["webview.platforms.edgechromium"]

# le dossier assets entier SAUF sdengine (les DLL de sd.cpp ne doivent JAMAIS
# être reclassifiées binaries : elles écraseraient llama_cpp à la racine)
import os as _os
for _root, _dirs, _files in _os.walk("assets"):
    if "sdengine" in _root:
        continue
    for _fn in _files:
        _fp = _os.path.join(_root, _fn)
        datas.append((_fp, _root))
datas += [("wormgpt/ui_web/static", "wormgpt/ui_web/static")]

# moteur de génération d'images (stable-diffusion.cpp) : PAS embarqué dans
# l'exe — PyInstaller v6 reclassifie les .dll en binaries et les extrait à la
# racine du runtime, où les ggml*.dll de sd.cpp masquent ceux de llama_cpp
# (« no backends are loaded » à chaque chargement de modèle). Le dossier
# assets/sdengine est livré À CÔTÉ de l'exe dans le zip (voir imagegen.py).

# version lue depuis la source unique de vérité (wormgpt/__init__.py) : plus
# de numéro à mettre à jour à la main dans le spec.
import sys as _sys
_sys.path.insert(0, SPECPATH)
from wormgpt import __version__ as _APP_VERSION  # noqa: E402

_parts = [int(p) for p in _APP_VERSION.split(".") if p.isdigit()][:4]
while len(_parts) < 4:
    _parts.append(0)
_version_tuple = tuple(_parts)

version_info = VSVersionInfo(
    ffi=FixedFileInfo(
        filevers=_version_tuple,
        prodvers=_version_tuple,
        mask=0x3F,
        flags=0x0,
        OS=0x40004,
        fileType=0x1,
        subtype=0x0,
        date=(0, 0),
    ),
    kids=[
        StringFileInfo([
            StringTable("040904B0", [
                StringStruct("CompanyName", "WormGPT"),
                StringStruct("FileDescription", "WormGPT Desktop — local AI chat"),
                StringStruct("FileVersion", _APP_VERSION),
                StringStruct("InternalName", "WormGPT"),
                StringStruct("LegalCopyright", "(c) 2026 WormGPT"),
                StringStruct("OriginalFilename", "WormGPT.exe"),
                StringStruct("ProductName", "WormGPT"),
                StringStruct("ProductVersion", _APP_VERSION),
            ]),
        ]),
        VarFileInfo([VarStruct("Translation", [1033, 1200])]),
    ],
)

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=["PyQt5", "PyQt6", "PySide2", "PySide6", "IPython", "pytest",
              "matplotlib", "numpy.distutils"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="WormGPT",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,  # shrinks the exe ~2x when upx is on PATH; ignored otherwise
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="assets/wormgpt.ico",
    version=version_info,
)