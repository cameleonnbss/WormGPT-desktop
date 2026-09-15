"""WormGPT Desktop — local-first AI chat application."""

import os
import sys

# Source unique de vérité pour la version affichée (sidebar, réglages, API
# locale, métadonnées de l'exe). À incrémenter de 0.1 à chaque nouveau lot de
# changements : 1.9.0 -> 1.10.0 -> 1.11.0 ...
__version__ = "1.9.0"


def resource_path(name):
    """Resolve a bundled asset, in dev mode or inside a PyInstaller exe."""
    if hasattr(sys, "_MEIPASS"):
        base = sys._MEIPASS
    else:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, name)