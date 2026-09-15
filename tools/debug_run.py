"""Debug helper: run main.py and dump the traceback after 15 s if hung."""
import faulthandler
import os
import sys

faulthandler.dump_traceback_later(15, exit=True)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, ROOT)

with open(os.path.join(ROOT, "main.py"), encoding="utf-8") as f:
    code = compile(f.read(), "main.py", "exec")
exec(code, {"__name__": "__main__", "__file__": os.path.join(ROOT, "main.py")})