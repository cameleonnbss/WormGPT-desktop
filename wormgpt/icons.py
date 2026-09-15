"""Vector icons drawn on tkinter Canvas — no images, no emoji, all procedural.

Each draw_* function paints a 24x24-unit icon centred on (cx, cy) scaled to
``s`` pixels. Coordinates follow a 24-unit grid so icons are crisp at any
size.
"""

from tkinter import Canvas

from . import theme as T


def _pts(pts, cx, cy, s):
    """Scale normalised 24-grid points to canvas coordinates."""
    k = s / 24.0
    out = []
    for x, y in pts:
        out.extend((cx + (x - 12) * k, cy + (y - 12) * k))
    return out


def _line(c: Canvas, pts, cx, cy, s, color, width=2.0, smooth=False):
    c.create_line(*_pts(pts, cx, cy, s), fill=color, width=max(1.0, width * s / 24.0),
                  capstyle="round", joinstyle="round", smooth=smooth)


def _poly(c: Canvas, pts, cx, cy, s, color, outline="", width=1.0):
    c.create_polygon(*_pts(pts, cx, cy, s), fill=color, outline=outline, width=width, smooth=True)


def _circle(c: Canvas, cx, cy, s, x, y, r, color, width=2.0, fill=""):
    k = s / 24.0
    c.create_oval(cx + (x - r) * k, cy + (y - r) * k, cx + (x + r) * k, cy + (y + r) * k,
                  outline=color, width=max(1.0, width * k), fill=fill)


# ---------------------------------------------------------------------------
# Brand logo
# ---------------------------------------------------------------------------

def worm_logo(c: Canvas, cx, cy, s, ring=True, glow=True):
    """WormGPT emblem: dark badge, red ring, serpent forming a 'W'."""
    if glow:
        c.create_oval(cx - s * 0.62, cy - s * 0.62, cx + s * 0.62, cy + s * 0.62,
                      fill=T.ACCENT_SOFT, outline="")
    c.create_oval(cx - s * 0.52, cy - s * 0.52, cx + s * 0.52, cy + s * 0.52,
                  fill="#1c0d13", outline="")
    if ring:
        c.create_oval(cx - s * 0.5, cy - s * 0.5, cx + s * 0.5, cy + s * 0.5,
                      outline=T.ACCENT, width=max(1.5, s * 0.045))
    # serpentine "W"
    pts = [(4.5, 17), (6.5, 7.5), (9.5, 15.5), (12, 8.5), (14.5, 15.5), (17.5, 7.5), (19.5, 17)]
    _line(c, pts, cx, cy, s, T.ACCENT, width=2.6, smooth=True)
    # head
    _circle(c, cx, cy, s, 4.6, 16.4, 1.35, T.ACCENT, width=0, fill=T.ACCENT)
    _circle(c, cx, cy, s, 4.9, 15.9, 0.5, "#1c0d13", width=0, fill="#1c0d13")


# ---------------------------------------------------------------------------
# Line icons (24-grid)
# ---------------------------------------------------------------------------

def shield(c, cx, cy, s, color=T.TEXT, width=2.0):
    _line(c, [(12, 2.5), (20, 5.5), (20, 12), (20, 12), (12, 21.5), (4, 12), (4, 5.5), (12, 2.5)], cx, cy, s, color, width)
    _line(c, [(8.5, 11.5), (11, 14), (15.8, 8.8)], cx, cy, s, color, width)


def lock(c, cx, cy, s, color=T.TEXT, width=2.0):
    _line(c, [(6.5, 11), (6.5, 11), (6.5, 21.5), (17.5, 21.5), (17.5, 11), (6.5, 11)], cx, cy, s, color, width)
    c.create_arc(cx - 4.2 * s / 24, cy - 5.2 * s / 24, cx + 4.2 * s / 24, cy + 4.4 * s / 24,
                 start=0, extent=180, style="arc", outline=color, width=max(1.0, 2.0 * s / 24))
    _circle(c, cx, cy, s, 12, 16, 1.6, color, width)
    _line(c, [(12, 17.6), (12, 19.4)], cx, cy, s, color, width)


def chip(c, cx, cy, s, color=T.TEXT, width=2.0):
    """Circuit / neural chip — stands for technical depth."""
    c.create_rectangle(cx - 5.4 * s / 24, cy - 5.4 * s / 24, cx + 5.4 * s / 24, cy + 5.4 * s / 24,
                       outline=color, width=max(1.0, 2.0 * s / 24))
    _line(c, [(12, 4.5), (12, 7)], cx, cy, s, color, width)
    _line(c, [(12, 17), (12, 19.5)], cx, cy, s, color, width)
    _line(c, [(4.5, 12), (7, 12)], cx, cy, s, color, width)
    _line(c, [(17, 12), (19.5, 12)], cx, cy, s, color, width)
    _line(c, [(9, 9), (15, 9), (15, 15), (9, 15), (9, 9)], cx, cy, s, color, width)


def code(c, cx, cy, s, color=T.TEXT, width=2.0):
    _line(c, [(8.5, 6.5), (3.5, 12), (8.5, 17.5)], cx, cy, s, color, width)
    _line(c, [(15.5, 6.5), (20.5, 12), (15.5, 17.5)], cx, cy, s, color, width)


def zap(c, cx, cy, s, color=T.TEXT, width=2.0):
    _poly(c, [(13.5, 2.5), (5.5, 13.5), (11, 13.5), (10.5, 21.5), (18.5, 10.5), (13, 10.5), (13.5, 2.5)], cx, cy, s, color)


def folder(c, cx, cy, s, color=T.TEXT, width=2.0):
    _line(c, [(3.5, 6), (9.5, 6), (12, 8.5), (20.5, 8.5), (20.5, 19), (3.5, 19), (3.5, 6)], cx, cy, s, color, width)


def target(c, cx, cy, s, color=T.TEXT, width=2.0):
    _circle(c, cx, cy, s, 12, 12, 9, color, width)
    _circle(c, cx, cy, s, 12, 12, 5.2, color, width)
    _circle(c, cx, cy, s, 12, 12, 1.4, color, width=0, fill=color)


def download(c, cx, cy, s, color=T.TEXT, width=2.0):
    _line(c, [(12, 4), (12, 14.5)], cx, cy, s, color, width)
    _line(c, [(7.8, 10.2), (12, 14.6), (16.2, 10.2)], cx, cy, s, color, width)
    _line(c, [(4.5, 18.5), (19.5, 18.5)], cx, cy, s, color, width)


def chat(c, cx, cy, s, color=T.TEXT, width=2.0):
    _line(c, [(3.5, 4.5), (20.5, 4.5), (20.5, 15.5), (12.5, 15.5), (8, 19.5), (9, 15.5), (3.5, 15.5), (3.5, 4.5)], cx, cy, s, color, width)


def gear(c, cx, cy, s, color=T.TEXT, width=2.0):
    for a in range(0, 360, 45):
        import math
        r1, r2 = 7.4, 10.0
        c.create_line(cx + r1 * math.cos(math.radians(a)) * s / 24,
                      cy + r1 * math.sin(math.radians(a)) * s / 24,
                      cx + r2 * math.cos(math.radians(a)) * s / 24,
                      cy + r2 * math.sin(math.radians(a)) * s / 24,
                      fill=color, width=max(1.0, 2.4 * s / 24), capstyle="round")
    _circle(c, cx, cy, s, 12, 12, 4.6, color, width)
    _circle(c, cx, cy, s, 12, 12, 1.8, color, width=0, fill=color)


def send(c, cx, cy, s, color=T.TEXT, width=2.0):
    _poly(c, [(3, 3.5), (21, 12), (3, 20.5), (7, 12), (3, 3.5)], cx, cy, s, color)


def check(c, cx, cy, s, color=T.TEXT, width=3.0):
    _line(c, [(4.5, 12.5), (10, 18), (19.5, 6.5)], cx, cy, s, color, width)


def chevron(c, cx, cy, s, color=T.TEXT, width=2.0):
    _line(c, [(6.5, 9.5), (12, 15), (17.5, 9.5)], cx, cy, s, color, width)


def trash(c, cx, cy, s, color=T.TEXT, width=2.0):
    _line(c, [(4.5, 6.5), (19.5, 6.5)], cx, cy, s, color, width)
    _line(c, [(8, 6.5), (8.6, 3.5), (15.4, 3.5), (16, 6.5)], cx, cy, s, color, width)
    _line(c, [(6.5, 6.5), (7.5, 20.5), (16.5, 20.5), (17.5, 6.5)], cx, cy, s, color, width)


def cpu(c, cx, cy, s, color=T.TEXT, width=2.0):
    c.create_rectangle(cx - 6 * s / 24, cy - 6 * s / 24, cx + 6 * s / 24, cy + 6 * s / 24,
                       outline=color, width=max(1.0, 2.0 * s / 24))
    for dx, dy in [(-8.5, -8.5), (0, -9.5), (8.5, -8.5), (-8.5, 8.5), (0, 9.5), (8.5, 8.5), (-9.5, 0), (9.5, 0)]:
        c.create_line(cx + dx * s / 24, cy + dy * s / 24, cx + dx * s / 24 * 0.55, cy + dy * s / 24 * 0.55,
                      fill=color, width=max(1.0, 2.0 * s / 24), capstyle="round")
    _line(c, [(10, 10), (14, 10), (14, 14), (10, 14), (10, 10)], cx, cy, s, color, width)


def stop(c, cx, cy, s, color=T.TEXT, width=2.0):
    c.create_rectangle(cx - 4.5 * s / 24, cy - 4.5 * s / 24, cx + 4.5 * s / 24, cy + 4.5 * s / 24,
                       outline=color, width=max(1.0, 2.0 * s / 24))


def refresh(c, cx, cy, s, color=T.TEXT, width=2.0):
    c.create_arc(cx - 8 * s / 24, cy - 8 * s / 24, cx + 8 * s / 24, cy + 8 * s / 24,
                 start=30, extent=270, style="arc", outline=color, width=max(1.0, 2.2 * s / 24))
    _line(c, [(17.5, 4.5), (17.5, 9.5), (12.5, 9.5)], cx, cy, s, color, width)


def info(c, cx, cy, s, color=T.TEXT, width=2.0):
    _circle(c, cx, cy, s, 12, 12, 9.2, color, width)
    _line(c, [(12, 11), (12, 17)], cx, cy, s, color, width)
    _circle(c, cx, cy, s, 12, 7.3, 1.1, color, width=0, fill=color)


def folder_open(c, cx, cy, s, color=T.TEXT, width=2.0):
    _line(c, [(3.5, 6), (9.5, 6), (12, 8.5), (16, 8.5), (14.5, 14), (3.5, 19.5), (3.5, 6)], cx, cy, s, color, width)
    _line(c, [(14.5, 14), (19.5, 12.5), (18.5, 19), (3.5, 19)], cx, cy, s, color, width)


def magnifier(c, cx, cy, s, color=T.TEXT, width=2.0):
    """Search magnifier."""
    _circle(c, cx, cy, s, 10, 10, 6.2, color, width)
    _line(c, [(14.6, 14.6), (21, 21)], cx, cy, s, color, width)


def plug(c, cx, cy, s, color=T.TEXT, width=2.0):
    """Power / model plug."""
    _line(c, [(9, 15), (12, 12), (19, 5)], cx, cy, s, color, width)
    _line(c, [(16.5, 3), (21, 7.5)], cx, cy, s, color, width)
    _line(c, [(12, 12), (12, 15.5)], cx, cy, s, color, width)
    _line(c, [(9, 15), (6.5, 17.5), (8.5, 19.5), (6, 22)], cx, cy, s, color, width)


ICON_DRAWERS = {
    "shield": shield, "lock": lock, "chip": chip, "code": code, "zap": zap,
    "folder": folder, "target": target, "download": download, "chat": chat,
    "gear": gear, "send": send, "check": check, "chevron": chevron,
    "trash": trash, "cpu": cpu, "stop": stop, "refresh": refresh,
    "info": info, "folder_open": folder_open, "plug": plug, "search": magnifier,
}


def draw_icon(c: Canvas, name, cx, cy, s, color=T.TEXT, width=2.0):
    fn = ICON_DRAWERS.get(name)
    if fn:
        fn(c, cx, cy, s, color, width)


def icon_canvas(parent, name, size, color=T.TEXT, bg=None, width=2.0, highlightthickness=0):
    """Standalone canvas containing one icon, for use in widgets."""
    c = Canvas(parent, width=size, height=size, bg=bg if bg else T.BG,
               highlightthickness=highlightthickness, bd=0)
    draw_icon(c, name, size / 2, size / 2, size, color, width)
    return c