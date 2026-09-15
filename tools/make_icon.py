"""Generate assets/wormgpt.ico — pure Python, no PIL.

Draws the WormGPT emblem (dark badge, red ring, serpent 'W') into an RGBA
buffer with supersampled anti-aliasing, encodes PNGs by hand (zlib) and
wraps them into a Windows .ico container.
"""

import os
import struct
import sys
import zlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

BG_BADGE   = (28, 13, 19, 255)
RED        = (230, 57, 70, 255)
RED_SOFT   = (58, 20, 27, 255)
EYE        = (28, 13, 19, 255)

W_POINTS = [(4.5, 17.0), (6.5, 7.5), (9.5, 15.5), (12.0, 8.5),
            (14.5, 15.5), (17.5, 7.5), (19.5, 17.0)]   # 24-grid serpent


def seg_dist(px, py, x1, y1, x2, y2):
    dx, dy = x2 - x1, y2 - y1
    if dx == dy == 0:
        return ((px - x1) ** 2 + (py - y1) ** 2) ** 0.5
    t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)))
    return ((px - (x1 + t * dx)) ** 2 + (py - (y1 + t * dy)) ** 2) ** 0.5


def draw(size, ss=4):
    """Render the emblem at ``size`` px with ``ss``x supersampling."""
    s = size * ss
    k = s / 24.0
    cx = cy = s / 2.0
    buf = bytearray([0, 0, 0, 0]) * (s * s)

    def put(x, y, col, a):
        i = (y * s + x) * 4
        buf[i] = int(buf[i] + (col[0] - buf[i]) * a)
        buf[i + 1] = int(buf[i + 1] + (col[1] - buf[i + 1]) * a)
        buf[i + 2] = int(buf[i + 2] + (col[2] - buf[i + 2]) * a)
        buf[i + 3] = int(buf[i + 3] + (col[3] - buf[i + 3]) * a)

    def disc(x, y, r, col):
        """Anti-aliased filled circle."""
        r2 = (r * k) ** 2
        lo_x, hi_x = max(0, int((x - r) * k)), min(s - 1, int((x + r) * k))
        lo_y, hi_y = max(0, int((y - r) * k)), min(s - 1, int((y + r) * k))
        for py in range(lo_y, hi_y + 1):
            for px in range(lo_x, hi_x + 1):
                d = (px - cx - (x - 12) * k) ** 2 + (py - cy - (y - 12) * k) ** 2
                if d <= r2:
                    put(px, py, col, 1.0)

    def ring(r, width):
        """Anti-aliased ring stroke."""
        r_outer, r_inner = (r + width / 2) * k, (r - width / 2) * k
        for py in range(s):
            for px in range(s):
                d = ((px - cx) ** 2 + (py - cy) ** 2) ** 0.5
                if r_inner <= d <= r_outer:
                    put(px, py, RED, 1.0)

    def polyline(width):
        """Thick round-capped polyline for the serpent body."""
        r = width / 2 * k
        pts = [(cx + (x - 12) * k, cy + (y - 12) * k) for x, y in W_POINTS]
        for py in range(s):
            for px in range(s):
                d = min(seg_dist(px, py, *a, *b) for a, b in zip(pts, pts[1:]))
                if d <= r:
                    put(px, py, RED, 1.0)

    disc(12, 12, 11.4, BG_BADGE)       # badge
    ring(11.4, 1.15)                   # ring
    polyline(2.6)                      # serpent W
    disc(4.7, 16.3, 1.5, RED)          # head
    disc(5.0, 15.8, 0.62, EYE)         # eye

    # downsample
    out = bytearray([0, 0, 0, 0]) * (size * size)
    for y in range(size):
        for x in range(size):
            r = g = b = a = 0
            for dy in range(ss):
                for dx in range(ss):
                    i = ((y * ss + dy) * s + (x * ss + dx)) * 4
                    r += buf[i]; g += buf[i + 1]; b += buf[i + 2]; a += buf[i + 3]
            n = ss * ss
            i = (y * size + x) * 4
            out[i] = r // n; out[i + 1] = g // n; out[i + 2] = b // n; out[i + 3] = a // n
    return bytes(out)


def png_encode(rgba, w, h):
    def chunk(tag, data):
        c = tag + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xffffffff)

    raw = b"".join(b"\x00" + rgba[y * w * 4:(y + 1) * w * 4] for y in range(h))
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) +
            chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


def build_ico(sizes=(16, 32, 48, 64, 128, 256)):
    entries, blobs = [], []
    for size in sizes:
        ss = 4 if size <= 64 else 2
        blob = png_encode(draw(size, ss), size, size)
        blobs.append(blob)
    offset = 6 + 16 * len(sizes)
    for size, blob in zip(sizes, blobs):
        entries.append(struct.pack("<BBBBHHII", size if size < 256 else 0, size if size < 256 else 0,
                                   0, 0, 1, 32, len(blob), offset))
        offset += len(blob)
    return struct.pack("<HHH", 0, 1, len(sizes)) + b"".join(entries) + b"".join(blobs)


def main():
    out_dir = os.path.join(ROOT, "assets")
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "wormgpt.ico")
    with open(path, "wb") as f:
        f.write(build_ico())
    print(f"OK: {path} ({os.path.getsize(path)} bytes)")


if __name__ == "__main__":
    sys.exit(main())