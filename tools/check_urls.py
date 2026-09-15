"""Check that every model URL in the catalog resolves (read-only network check).

Uses a ranged GET (Hugging Face CDN responds 206) so nothing is downloaded.
"""

import sys
import urllib.request

import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from wormgpt import models as M  # noqa: E402

BAD = []


def check(url, label):
    req = urllib.request.Request(url, headers={
        "User-Agent": "WormGPT-Desktop/1.0",
        "Range": "bytes=0-0",
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            status = resp.status
            ok = status in (200, 206) or (300 <= status < 400 and resp.geturl() != url)
            ok = status in (200, 206)
            print(f"{'OK  ' if ok else 'FAIL'} {status}  {label}")
            if not ok:
                BAD.append(url)
    except Exception as exc:
        print(f"FAIL --  {label}  ({exc})")
        BAD.append(url)


def main():
    for tier in M.CATALOG:
        check(tier.url, f"{tier.name}  {tier.file}")
        if tier.mmproj_url:
            check(tier.mmproj_url, f"{tier.name}  {tier.mmproj}")
    print()
    if BAD:
        print(f"{len(BAD)} URL(s) failed")
        return 1
    print("All catalog URLs resolve.")
    return 0


if __name__ == "__main__":
    sys.exit(main())