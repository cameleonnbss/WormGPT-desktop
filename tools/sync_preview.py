"""Regenerate the browser-only preview harness from the real web UI.

The packaged app renders ``wormgpt/ui_web/static/index.html`` inside a WebView2
window and talks to Python through ``window.pywebview.api``. To eyeball the UI
in a plain browser (no WebView, no llama-cpp) this script copies the *real*
``index.html`` / ``app.js`` / ``style.css`` into ``preview-web/`` and rewrites
the absolute ``/assets/…`` URLs to the relative ``assets/…`` used there.
``preview-web/mock.js`` provides a fake bridge.

Run it after any change to the real static files::

    python tools/sync_preview.py
"""

import json
import os
import re
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
SRC = os.path.join(ROOT, "wormgpt", "ui_web", "static")
DST = os.path.join(ROOT, "preview-web")

FILES = {"index.html": "preview.html", "app.js": "app.js", "style.css": "style.css"}


def write_strings():
    """Regenerate strings.js from the real i18n tables + presets (French)."""
    from wormgpt import config as C
    from wormgpt import i18n as _
    _.set_lang("fr")
    strings = dict(_.get_table())
    presets = [{"key": k, "name": n, "text": t}
               for k, n, t in C.localized_presets("fr")]
    blob = {"strings": strings, "presets": presets}
    out = "window.__PREVIEW__ = " + json.dumps(blob, ensure_ascii=False) + ";\n"
    with open(os.path.join(DST, "strings.js"), "w", encoding="utf-8",
              newline="") as fh:
        fh.write(out)
    print("synced i18n -> strings.js (%d keys, %d presets)"
          % (len(strings), len(presets)))


def copy_assets():
    """Mirror the icons/fonts the preview needs (skip the huge sdengine)."""
    src = os.path.join(ROOT, "assets")
    dst = os.path.join(DST, "assets")
    copied = 0
    for root, dirs, files in os.walk(src):
        if "sdengine" in dirs:
            dirs.remove("sdengine")
        rel = os.path.relpath(root, src)
        out_dir = os.path.join(dst, rel) if rel != "." else dst
        os.makedirs(out_dir, exist_ok=True)
        for fn in files:
            shutil.copy2(os.path.join(root, fn), os.path.join(out_dir, fn))
            copied += 1
    print("synced assets -> preview-web/assets (%d files)" % copied)


def write_catalog():
    """Regenerate catalog.js from the real model catalogue."""
    from wormgpt import models as M
    from wormgpt import systeminfo as SI
    out = []
    for t in M.CATALOG:
        out.append({
            "name": t.name, "category": t.category, "power": t.power,
            "params": t.params, "size": t.size_str, "ram": t.ram_str,
            "desc": t.desc, "vision": t.is_vision,
            "installed": False, "active": t.name == M.CATALOG[0].name,
            "downloading": False,
            "recommended": t.name == SI.best_tier(t.category),
            "remote": False,
        })
    out[0]["installed"] = True
    blob = "window.__PREVIEW__ = window.__PREVIEW__ || {};\n" \
           "window.__PREVIEW__.catalog = " \
           + json.dumps(out, ensure_ascii=False) + ";\n"
    with open(os.path.join(DST, "catalog.js"), "w", encoding="utf-8",
              newline="") as fh:
        fh.write(blob)
    print("synced catalogue -> catalog.js (%d tiers)" % len(out))


def main():
    if not os.path.isdir(SRC):
        print("missing source dir:", SRC)
        return 1
    os.makedirs(DST, exist_ok=True)
    for src_name, dst_name in FILES.items():
        with open(os.path.join(SRC, src_name), encoding="utf-8") as fh:
            text = fh.read()
        # absolute asset URLs → relative (the preview is served at its own root)
        text = re.sub(r'(["\'(])/assets/', r"\1assets/", text)
        if src_name == "index.html":
            # inject the browser-only mocks *before* app.js
            text = text.replace(
                '<script src="app.js"></script>',
                '<script src="strings.js"></script>\n'
                '<script src="catalog.js"></script>\n'
                '<script src="mock.js"></script>\n'
                '<script src="app.js"></script>',
            )
        with open(os.path.join(DST, dst_name), "w", encoding="utf-8",
                  newline="") as fh:
            fh.write(text)
        print("synced", src_name, "->", dst_name)
    write_strings()
    write_catalog()
    copy_assets()
    return 0


if __name__ == "__main__":
    sys.exit(main())
