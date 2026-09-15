"""WormGPT Desktop — entry point.

Usage:
    python main.py          # web UI (WebView2, style DarkGPT)
    WormGPT.exe             # packaged build (single file)
"""

import os
import sys


def _log_crash(lines):
    """Write an exception traceback to %APPDATA%/WormGPT/crash.log."""
    try:
        from wormgpt import config as C
        with open(os.path.join(C.data_dir(), "crash.log"), "a",
                  encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
    except OSError:
        pass


def _log(msg):
    """Diagnostic file log (engine load issues are silent by design in
    daemon threads — this makes them visible)."""
    try:
        from wormgpt import config as C
        import datetime
        with open(os.path.join(C.data_dir(), "debug.log"), "a",
                  encoding="utf-8") as f:
            f.write(datetime.datetime.now().strftime("%m-%d %H:%M:%S")
                    + " " + msg + "\n")
    except OSError:
        pass


def _thread_hook(args):
    """Log exceptions dying inside threads (never surfaced otherwise)."""
    import traceback
    _log("THREAD-EXC " + "".join(
        traceback.format_exception(args.exc_type, args.exc_value,
                                   args.exc_traceback))[-1500:])


def _crash_hook(exc_type, exc, tb):
    """Never die silently: log unhandled exceptions and show a dialog."""
    import traceback
    lines = traceback.format_exception(exc_type, exc, tb)
    _log_crash(lines)
    try:
        import tkinter.messagebox as mb
        mb.showerror("WormGPT — error", "".join(lines[-6:]))
    except Exception:
        pass


def _serve_ui():
    """Serve the bundled UI over 127.0.0.1 (random port).

    The server root is the resource root (project dir in dev, _MEIPASS in the
    exe), so the absolute asset URLs (/assets/...) and the UI files resolve
    identically in both environments.
    """
    import functools
    from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

    from wormgpt import resource_path

    root = resource_path("")
    handler = functools.partial(SimpleHTTPRequestHandler, directory=root)
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    port = httpd.server_address[1]
    import threading
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{port}/wormgpt/ui_web/static/index.html"
    return httpd, url


def _run_web():
    """Web UI rendered in a WebView2 window (Edge Chromium)."""
    import webview

    from wormgpt import config as C
    from wormgpt.ui_web.bridge import Bridge

    cfg = C.load()
    bridge = Bridge(cfg)
    _httpd, url = _serve_ui()
    webview.create_window(
        "WormGPT",
        url=url,
        js_api=bridge,
        width=1280,
        height=800,
        min_size=(1024, 680),
        background_color="#050506",
    )
    webview.start(debug=False)


def main():
    # never die silently: log unhandled exceptions to %APPDATA% and show them
    sys.excepthook = _crash_hook
    import threading
    threading.excepthook = _thread_hook

    from wormgpt import models as M
    M.cleanup_partials()

    _run_web()


if __name__ == "__main__":
    main()