import json
import os
import sys
import time

os.environ["APPDATA"] = r"C:\tmp\wgmodel"
sys.path.insert(0, ".")

from wormgpt import config as C

# config minimale dans l'APPDATA temporaire
cfg = C.load()
cfg["configured"] = True
cfg["model"] = {"tier": "WormGPT-1", "path": C.get_model_path(cfg)}
C.save(cfg)

from wormgpt.core import Core

events = []
core = Core(cfg, events.append)

# attendre que le moteur soit prêt (chargement ~1-2 min au pire)
t0 = time.time()
while time.time() - t0 < 180:
    if core.engine_state == "ready":
        print("ENGINE READY after", round(time.time() - t0, 1), "s", flush=True)
        break
    if core.engine_state == "error":
        print("ENGINE ERROR:", core.engine_status, flush=True)
        sys.exit(1)
    time.sleep(1)
else:
    print("ENGINE TIMEOUT, state =", core.engine_state, core.engine_status, flush=True)
    sys.exit(1)

# génération réelle
core.send("Dis bonjour en une phrase, en français.")
t0 = time.time()
reply = None
while time.time() - t0 < 120:
    evs = [e for e in events]
    events.clear()
    for e in evs:
        if e["type"] == "stream_end":
            reply = e["text"]
        if e["type"] == "error":
            print("GEN ERROR:", e["text"], flush=True)
            sys.exit(1)
    if reply is not None:
        break
    time.sleep(0.5)
print("REPLY:", (reply or "")[:300], flush=True)
core.shutdown()
print("TEST OK", flush=True)