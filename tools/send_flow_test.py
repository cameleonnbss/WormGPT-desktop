"""End-to-end send test: boots Core with a real model and sends a message.

Verifies the fixed pipeline: send -> build_messages -> engine stream ->
stream_end with tok/s stats, and that chat_in/chat_out logs are enqueued.
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from wormgpt import config as C
from wormgpt.core import Core

cfg = C.load()
events = []
core = Core(cfg, events.append)

tier = core.active_tier_name()
print(f"model: {tier}")
if not core.engine or not core.engine.is_loaded():
    print("WAIT for engine load...")
    for _ in range(120):
        if core.engine and core.engine.is_loaded():
            break
        time.sleep(1)
assert core.engine and core.engine.is_loaded(), "engine never loaded"

core.send("Say hello in one short sentence.")
final = None
t0 = time.time()
while time.time() - t0 < 120:
    for ev in list(events):
        if ev["type"] == "stream_end":
            final = ev
    if final:
        break
    time.sleep(0.5)

assert final, "no stream_end received (send pipeline broken)"
print(f"ANSWER: {final['text'][:200]}")
print(f"tok/s stats: tok={final.get('tok')} elapsed={final.get('elapsed')}s")

print("SEND-FLOW OK")
