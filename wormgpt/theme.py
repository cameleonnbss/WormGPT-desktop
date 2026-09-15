"""WormGPT visual theme — dark hacker style, aligned with the DarkGPT / WormGPT
landing designs: near-black background, red accent (#ff3b5c), subtle borders,
Inter + Space Mono typography (bundled TTFs with graceful fallback)."""

import os
import tkinter as tk
import tkinter.font as tkfont

from . import __version__

APP_NAME = "WormGPT"
# une seule source de vérité : wormgpt/__init__.py
APP_VERSION = __version__

# ---------------------------------------------------------------------------
# Palette (from the reference site designs)
# ---------------------------------------------------------------------------
BG          = "#050506"   # main background (near black)
BG_SOFT     = "#0b0d13"   # soft panels / sidebar gradient base
CARD        = "#111111"   # card background
CARD_HOVER  = "#161616"   # card on hover
CARD_ACTIVE = "#1c0f14"   # selected card (red tint)
BORDER      = "#1e1e20"   # subtle borders (rgba(255,255,255,0.07) equivalent)
BORDER_LIGHT = "#3d3d42"

ACCENT        = "#ff3b5c"  # bright red (primary actions)
ACCENT_DARK   = "#c1123a"  # bordeaux
ACCENT_HOVER  = "#ff5b72"  # hover
ACCENT_SOFT   = "#2a0d14"  # soft red fill (rgba(255,59,92,0.12) equivalent)

TEXT        = "#f4f4f5"   # main text
TEXT_MUTED  = "#8f8f8f"   # secondary text
TEXT_DIM    = "#52525b"   # tertiary / hints

OK      = "#22c55e"
WARN    = "#f59e0b"
ERR     = ACCENT

SIDEBAR_BG = "#08080a"

# ---------------------------------------------------------------------------
# Fonts (bundled TTFs, registered with Tk; fallback to Segoe UI / Consolas)
# ---------------------------------------------------------------------------
FONT      = "Segoe UI"
FONT_MONO = "Consolas"
_FONTS_LOADED = False


def register_fonts(root=None):
    """Register the bundled Inter / Space Mono TTFs with Tk.

    Runs automatically on first UI creation; silently falls back to the
    system fonts when the files are missing or Tk refuses them.
    """
    global _FONTS_LOADED, FONT, FONT_MONO
    if _FONTS_LOADED:
        return
    _FONTS_LOADED = True
    try:
        from . import resource_path
        base = resource_path(os.path.join("assets", "fonts"))
        candidates = [
            (os.path.join(base, "Inter-Regular.ttf"), "Inter"),
            (os.path.join(base, "SpaceMono-Regular.ttf"), "Space Mono"),
        ]
        for path, family in candidates:
            if not os.path.isfile(path):
                continue
            ok = False
            # Windows: register with GDI (private to this process) so Tk can
            # resolve the family name; Tk itself has no -file option here.
            if os.name == "nt":
                try:
                    import ctypes
                    from ctypes import wintypes
                    gdi = ctypes.windll.gdi32
                    gdi.AddFontResourceExW.argtypes = [wintypes.LPCWSTR,
                                                       wintypes.DWORD,
                                                       ctypes.c_void_p]
                    gdi.AddFontResourceExW.restype = ctypes.c_int
                    ok = gdi.AddFontResourceExW(path, 0x10, 0) > 0  # FR_PRIVATE
                except Exception:
                    ok = False
            if not ok:
                # X11/macOS path: Tk can load a font file directly.
                try:
                    tkfont.Font(root=root, name=family, exists=False,
                                size=10, file=path)
                    ok = True
                except tk.TclError:
                    ok = False
            if ok:
                if family == "Inter":
                    FONT = "Inter"
                else:
                    FONT_MONO = "Space Mono"
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Sizes
# ---------------------------------------------------------------------------
SIZE_XS   = 9
SIZE_SM   = 10
SIZE_MD   = 11
SIZE_LG   = 13
SIZE_XL   = 16
SIZE_H1   = 30
SIZE_HERO = 40

NAV_H      = 44
HEADER_H   = 56
STATUS_H   = 26
WIN_W      = 1280
WIN_H      = 800
MIN_W      = 1024
MIN_H      = 680
RADIUS     = 14         # card rounding feel (borders remain squared)
SIDEBAR_W  = 224
CHAT_MAX   = 860        # max width of the message column