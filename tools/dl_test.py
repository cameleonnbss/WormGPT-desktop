import os
import sys
import time

os.environ["APPDATA"] = "/tmp/wgmodel"
sys.path.insert(0, ".")

from wormgpt import models as M

t = M.get_tier("WormGPT-1")
print("start", t.name, t.url, flush=True)
job = M.DownloadJob(
    t,
    on_progress=lambda r, tot: print(f"{100 * r / tot:.1f}%", flush=True)
    if r % (150 * 1024 * 1024) < 1024 * 1024 else None,
    on_done=lambda: print("DONE", flush=True),
    on_error=lambda e: print("ERR", e, flush=True),
)
job.start()
while job.running:
    time.sleep(2)
print("finished", flush=True)