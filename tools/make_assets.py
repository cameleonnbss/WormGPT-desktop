"""Generate brand assets from assets/logo_source.png — pure Python, no PIL.

Produces:
    assets/wormgpt.ico      — multi-size Windows icon (16..256, PNG entries)
    assets/logo_<size>.png  — resized brand logos for the in-app UI

Includes a minimal PNG decoder (all colour types, 8/16-bit) and a
premultiplied-alpha bilinear resizer so the whole pipeline runs on the
standard library alone.
"""

import os
import struct
import sys
import zlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCE = os.path.join(ROOT, "assets", "logo_source.png")

ICO_SIZES = (16, 24, 32, 48, 64, 128, 256)
UI_SIZES = (16, 20, 24, 28, 32, 36, 40, 48, 64, 96, 128, 160, 256)


# ---------------------------------------------------------------------------
# PNG decode (stdlib only)
# ---------------------------------------------------------------------------

def _paeth(a, b, c):
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    return a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)


def decode_png(path):
    data = open(path, "rb").read()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("Not a PNG file")
    pos, idat = 8, b""
    w = h = bd = ct = 0
    plte, trns = b"", b""
    while pos < len(data):
        ln = struct.unpack(">I", data[pos:pos + 4])[0]
        typ = data[pos + 4:pos + 8]
        chunk = data[pos + 8:pos + 8 + ln]
        if typ == b"IHDR":
            w, h, bd, ct, _c, _f, inter = struct.unpack(">IIBBBBB", chunk)
            if inter:
                raise ValueError("Interlaced PNG not supported")
        elif typ == b"PLTE":
            plte = chunk
        elif typ == b"tRNS":
            trns = chunk
        elif typ == b"IDAT":
            idat += chunk
        elif typ == b"IEND":
            break
        pos += 12 + ln

    raw = zlib.decompress(idat)
    channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[ct]
    bpp = channels * (bd // 8 or 1)
    stride = w * bpp
    out = bytearray(h * stride)
    prev = bytearray(stride)
    for y in range(h):
        row = y * (stride + 1)
        f = raw[row]
        line = bytearray(raw[row + 1:row + 1 + stride])
        if bd == 16:  # keep high byte
            line = bytearray(line[i] for i in range(0, len(line), 2))
        if f == 1:
            for i in range(bpp, stride):
                line[i] = (line[i] + line[i - bpp]) & 255
        elif f == 2:
            for i in range(stride):
                line[i] = (line[i] + prev[i]) & 255
        elif f == 3:
            for i in range(stride):
                a = line[i - bpp] if i >= bpp else 0
                line[i] = (line[i] + ((a + prev[i]) >> 1)) & 255
        elif f == 4:
            for i in range(stride):
                a = line[i - bpp] if i >= bpp else 0
                c = prev[i - bpp] if i >= bpp else 0
                line[i] = (line[i] + _paeth(a, prev[i], c)) & 255
        out[y * stride:(y + 1) * stride] = line
        prev = line

    # convert to RGBA8
    rgba = bytearray(w * h * 4)
    if ct == 6:
        for i in range(w * h):
            rgba[4 * i:4 * i + 4] = out[4 * i:4 * i + 4]
    elif ct == 2:
        for i in range(w * h):
            rgba[4 * i:4 * i + 3] = out[3 * i:3 * i + 3]
            rgba[4 * i + 3] = 255
    elif ct == 4:
        for i in range(w * h):
            rgba[4 * i:4 * i + 2] = out[2 * i:2 * i + 2]
            rgba[4 * i + 3] = out[2 * i + 1]
    elif ct == 0:
        for i in range(w * h):
            rgba[4 * i] = rgba[4 * i + 1] = rgba[4 * i + 2] = out[i]
            rgba[4 * i + 3] = 255
    elif ct == 3:
        for i in range(w * h):
            idx = out[i]
            r, g, b = plte[3 * idx:3 * idx + 3]
            a = trns[idx] if idx < len(trns) else 255
            rgba[4 * i:4 * i + 4] = bytes((r, g, b, a))
    else:
        raise ValueError(f"Unsupported colour type {ct}")
    return w, h, bytes(rgba)


# ---------------------------------------------------------------------------
# Resize (premultiplied-alpha bilinear)
# ---------------------------------------------------------------------------

def resize_rgba(src, sw, sh, dw, dh):
    out = bytearray(dw * dh * 4)
    for y in range(dh):
        sy = (y + 0.5) * sh / dh - 0.5
        y0 = max(0, int(sy))
        y1 = min(sh - 1, y0 + 1)
        fy = sy - y0
        for x in range(dw):
            sx = (x + 0.5) * sw / dw - 0.5
            x0 = max(0, int(sx))
            x1 = min(sw - 1, x0 + 1)
            fx = sx - x0
            acc = [0.0] * 4
            for dyi, wy in ((y0, 1 - fy), (y1, fy)):
                for dxi, wx in ((x0, 1 - fx), (x1, fx)):
                    wgt = wx * wy
                    i = (dyi * sw + dxi) * 4
                    a = src[i + 3] / 255.0
                    acc[0] += src[i] * a * wgt
                    acc[1] += src[i + 1] * a * wgt
                    acc[2] += src[i + 2] * a * wgt
                    acc[3] += a * wgt
            a = acc[3]
            j = (y * dw + x) * 4
            if a > 0:
                out[j] = min(255, int(acc[0] / a))
                out[j + 1] = min(255, int(acc[1] / a))
                out[j + 2] = min(255, int(acc[2] / a))
            out[j + 3] = min(255, int(a * 255 + 0.5))
    return bytes(out)


# ---------------------------------------------------------------------------
# PNG encode + ICO container
# ---------------------------------------------------------------------------

def png_encode(rgba, w, h):
    def chunk(tag, data):
        c = tag + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xffffffff)

    raw = b"".join(b"\x00" + rgba[y * w * 4:(y + 1) * w * 4] for y in range(h))
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) +
            chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


def ico_bmp_entry(rgba, w, h):
    """Classic uncompressed BGRA + AND-mask ICO image (Tk/Explorer safe)."""
    header = struct.pack("<IiiHHIIiiII", 40, w, h * 2, 1, 32, 0, w * h * 4, 0, 0, 0, 0)
    xor = bytearray()
    for y in range(h - 1, -1, -1):  # bottom-up
        for x in range(w):
            i = (y * w + x) * 4
            xor += bytes((rgba[i + 2], rgba[i + 1], rgba[i], rgba[i + 3]))  # BGRA
    and_rows = ((w + 31) // 32) * 4
    return header + bytes(xor) + b"\x00" * (and_rows * h)


def build_ico(blobs_by_size):
    entries, blobs, offset = [], [], 6 + 16 * len(blobs_by_size)
    for size, blob in blobs_by_size:
        entries.append(struct.pack("<BBBBHHII", size if size < 256 else 0,
                                   size if size < 256 else 0, 0, 0, 1, 32,
                                   len(blob), offset))
        blobs.append(blob)
        offset += len(blob)
    return struct.pack("<HHH", 0, 1, len(entries)) + b"".join(entries) + b"".join(blobs)


# ---------------------------------------------------------------------------

def main():
    if not os.path.isfile(SOURCE):
        print(f"Missing source logo: {SOURCE}", file=sys.stderr)
        return 1
    sw, sh, rgba = decode_png(SOURCE)
    print(f"Source: {sw}x{sh} RGBA")

    ico_entries = []
    for size in ICO_SIZES:
        data = resize_rgba(rgba, sw, sh, size, size)
        # classic BMP entries for small sizes (Tk reads these), PNG for big ones
        blob = ico_bmp_entry(data, size, size) if size <= 64 else \
            png_encode(data, size, size)
        ico_entries.append((size, blob))
        print(f"  ico {size:3d}px  {len(blob)} bytes" + ("  (BMP)" if size <= 64 else "  (PNG)"))

    for size in UI_SIZES:
        data = png_encode(resize_rgba(rgba, sw, sh, size, size), size, size)
        with open(os.path.join(ROOT, "assets", f"logo_{size}.png"), "wb") as f:
            f.write(data)

    with open(os.path.join(ROOT, "assets", "wormgpt.ico"), "wb") as f:
        f.write(build_ico(ico_entries))
    print(f"OK: assets/wormgpt.ico + {len(UI_SIZES)} logo_<size>.png")
    return 0


if __name__ == "__main__":
    sys.exit(main())