"""Web UI (Edge WebView2) — DarkGPT-style interface in French.

The UI is a plain HTML/CSS/JS page rendered by pywebview; the Python side
exposes the Bridge object as `window.pywebview.api`.
"""

from .bridge import Bridge  # noqa: F401