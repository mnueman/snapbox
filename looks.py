"""The CLASSIC CAMERA look: everything on the main screen around the strip, and the
countdown, drawn with Pillow. No app state in here: photobooth.py passes in what to show (a plain
dict) and gets back pictures and tap areas, so this can be rendered and looked at on its own:

    python3 looks.py out.png          # a few states, side by side

Sizes are in "design pixels" on a 640x480 screen and scale with the real one. Everything is drawn
at twice the size and shrunk, so curves and small type come out smooth; the result is cached by
the app and only redrawn when something on it changes.
"""
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

SS = 2  # drawn this many times bigger, then shrunk
FONT_DIR = Path(__file__).resolve().parent / "ui" / "fonts"
LOOKS = ("classic",)
BRAND = "Snapshot"  # the name on the classic look's plate and the boot splash
STAGE_BG = {"classic": (6, 6, 6)}

# Menu and review-screen colours for each look (same keys as THEMES in photobooth.py).
THEMES = {
    "classic": dict(bg=(23, 23, 23), row=(52, 52, 52), text=(241, 241, 238), dim=(185, 186, 184),
                    accent=(217, 218, 216), done=(92, 94, 96), danger=(200, 30, 37),
                    off=(34, 34, 34), busy=(96, 97, 98), key=(74, 75, 76), field=(8, 8, 8),
                    inset=(38, 38, 38), good=(225, 226, 224), bad=(255, 110, 114),
                    disc=(10, 10, 10), main=(23, 23, 23)),
}

# What each look's main screen doesn't draw from the app's state (photobooth.py: _look_state), so
# a change to it (swiping to another design, say) doesn't mean redrawing everything.
NOT_DRAWN = {
    "classic": {"title", "chip", "switch_text", "plate_text", "design", "designs", "saved", "wifi",
                "battery", "cta", "cta_narrow", "cta_seconds", "cta_frac", "count_side", "segments",
                "phone", "printer_title", "printer_sub"},
}

_fonts = {}


def font(name, size, weight=None):
    """A font from ui/fonts at `size` screen px (drawn SS times bigger). `weight` for the variable
    Plus Jakarta Sans (200-800)."""
    key = (name, round(size * SS), weight)
    if key not in _fonts:
        try:
            f = ImageFont.truetype(str(FONT_DIR / name), key[1])
            if weight:
                f.set_variation_by_axes([weight])
        except Exception:
            f = ImageFont.load_default(size=key[1])
        _fonts[key] = f
    return _fonts[key]


def menu_font_file(look, bold):
    """(file, weight, size factor) for the app's menus in this look."""
    return ("BarlowCondensed-Bold.ttf" if bold else "BarlowCondensed-Medium.ttf"), None, 1.22


class Pen:
    """Drawing in screen px on a canvas SS times bigger."""

    def __init__(self, w, h):
        self.w, self.h = w, h
        self.img = Image.new("RGBA", (w * SS, h * SS), (0, 0, 0, 0))
        self.d = ImageDraw.Draw(self.img, "RGBA")

    @staticmethod
    def s(v):
        return round(v * SS)

    def b(self, r):
        return tuple(round(v * SS) for v in r)

    def rect(self, r, fill=None, outline=None, width=1):
        self.d.rectangle(self.b(r), fill=fill, outline=outline, width=max(1, self.s(width)))

    def rrect(self, r, rad, fill=None, outline=None, width=1):
        self.d.rounded_rectangle(self.b(r), radius=self.s(rad), fill=fill, outline=outline,
                                 width=max(1, self.s(width)))

    def oval(self, r, fill=None, outline=None, width=1):
        self.d.ellipse(self.b(r), fill=fill, outline=outline, width=max(1, self.s(width)))

    def circle(self, cx, cy, rad, fill=None, outline=None, width=1):
        self.oval((cx - rad, cy - rad, cx + rad, cy + rad), fill, outline, width)

    def line(self, pts, fill, width=1, joint="curve"):
        self.d.line([(x * SS, y * SS) for x, y in pts], fill=fill, width=max(1, self.s(width)),
                    joint=joint)

    def cap_line(self, pts, fill, width):
        """A line with round ends."""
        self.line(pts, fill, width)
        for x, y in (pts[0], pts[-1]):
            self.circle(x, y, width / 2, fill)

    def poly(self, pts, fill=None, outline=None):
        self.d.polygon([(x * SS, y * SS) for x, y in pts], fill=fill, outline=outline)

    def arc(self, r, start, end, fill, width=1):
        self.d.arc(self.b(r), start, end, fill=fill, width=max(1, self.s(width)))

    def text(self, xy, s, f, fill, anchor="la", spacing=0.0):
        """`spacing`: extra space between letters, in screen px (drawn letter by letter)."""
        x, y = xy[0] * SS, xy[1] * SS
        if not spacing:
            self.d.text((x, y), s, font=f, fill=fill, anchor=anchor)
            return
        widths = [self.d.textlength(ch, font=f) for ch in s]
        total = sum(widths) + spacing * SS * (len(s) - 1)
        if anchor[0] == "m":
            x -= total / 2
        elif anchor[0] == "r":
            x -= total
        for ch, cw in zip(s, widths):
            self.d.text((x, y), ch, font=f, fill=fill, anchor="l" + anchor[1])
            x += cw + spacing * SS

    def text_w(self, s, f, spacing=0.0):
        return (self.d.textlength(s, font=f) + spacing * SS * max(0, len(s) - 1)) / SS

    def fit(self, s, name, size, max_w, weight=None, spacing=0.0):
        while size > 7:
            f = font(name, size, weight)
            if self.text_w(s, f, spacing) <= max_w:
                return f
            size -= 0.5
        return font(name, size, weight)

    def shadows(self, items):
        """Soft drop shadows: items = [(rect, radius, blur, dy, strength)]. Each is a small blurred
        patch, kept by size: the same cards and keys are drawn again and again."""
        for r, rad, blur, dy, strength in items:
            x0, y0, x1, y1 = (round(v * SS) for v in (r[0], r[1] + dy, r[2], r[3] + dy))
            m = math.ceil((blur * 3 + 2) * SS)
            w, h = x1 - x0 + 2 * m, y1 - y0 + 2 * m
            if x1 <= x0 or y1 <= y0:
                continue
            key = ("shadow", w, h, self.s(rad), round(blur * SS, 1), round(strength, 2))
            patch = _tex.get(key)
            if patch is None:
                if len(_tex) > 600:
                    _tex.clear()
                mask = Image.new("L", (w, h), 0)
                ImageDraw.Draw(mask).rounded_rectangle((m, m, w - m, h - m), radius=self.s(rad),
                                                       fill=round(255 * strength))
                mask = mask.filter(ImageFilter.GaussianBlur(blur * SS))
                patch = Image.new("RGBA", (w, h), (0, 0, 0, 255))
                patch.putalpha(mask)
                _tex[key] = patch
            self.blend(patch, x0 - m, y0 - m)

    def blend(self, patch, x, y):
        """Lays an RGBA patch (SS scale, canvas px) over the picture, clipped to it."""
        cx0, cy0 = max(0, x), max(0, y)
        cx1, cy1 = min(self.img.width, x + patch.width), min(self.img.height, y + patch.height)
        if cx1 <= cx0 or cy1 <= cy0:
            return
        self.img.alpha_composite(patch.crop((cx0 - x, cy0 - y, cx1 - x, cy1 - y)), (cx0, cy0))

    def paste(self, im, xy):
        """An RGBA picture already at SS scale, top-left at xy (screen px)."""
        self.blend(im, self.s(xy[0]), self.s(xy[1]))

    def hole(self, r, rad=0):
        """Makes this area see-through (the strip shows there)."""
        x0, y0, x1, y1 = self.b(r)
        x0, y0 = max(0, x0), max(0, y0)
        x1, y1 = min(self.img.width, x1), min(self.img.height, y1)
        if x1 <= x0 or y1 <= y0:
            return
        mask = Image.new("L", (x1 - x0, y1 - y0), 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, x1 - x0 - 1, y1 - y0 - 1), radius=self.s(rad), fill=255)
        self.img.paste(Image.new("RGBA", mask.size, (0, 0, 0, 0)), (x0, y0), mask)

    def done(self):
        return self.img.reduce(SS)  # an exact shrink: each screen pixel is the average of SS x SS


# ---------------------------------------------------------------------------------- geometry

def geometry(look, w, h):
    """Where things are, in screen px. The screen is tiny (2.8 inches), so the strip gets almost
    all of it: "rail" = the four main buttons down the left, "stage" = everything else, where the
    strip goes. Status pieces sit in the corners the strip leaves empty (free_areas)."""
    k = h / 480.0
    g = {"k": k}
    col = 96 * k
    cell = h / 4
    # Big keys, and the whole cell around each one answers a tap.
    g["rail"] = [(0, i * cell, col, (i + 1) * cell) for i in range(4)]
    g["keys"] = [(col / 2 - 1 * k, i * cell + 47 * k, 37 * k) for i in range(4)]
    g["stage"] = (col, 0, w, h)
    g["pad"] = 10 * k  # room for each window's chrome bezel
    return g


def free_areas(stage, rects, gap):
    """The two empty areas the strip leaves on the stage, as (A, B): a strip folded in two hangs
    its left half from the top and sits its right half on the bottom, so A is above the right
    half and B below the left one; a sheet leaves bands above and below it (or beside it)."""
    if not rects:
        return None, None
    sx0, sy0, sx1, sy1 = stage
    if len(rects) >= 2:
        left, right = min(rects, key=lambda r: r[0]), max(rects, key=lambda r: r[0])
        return (right[0], sy0, right[2], right[1] - gap), (left[0], left[3] + gap, left[2], sy1)
    x0, y0, x1, y1 = rects[0]
    if y0 - sy0 >= x0 - sx0:
        return (x0, sy0, x1, y0 - gap), (x0, y1 + gap, x1, sy1)
    return (x1 + gap, sy0, sx1, sy1), (sx0, sy0, x0 - gap, sy1)


def _fit_card(area, max_w, max_h, min_w, min_h, m, corner, v_h=150):
    """A card inside a free area, hugging `corner` ("tr" or "bl"); None if it's too small. Returns
    (rect, "h" or "v"): wide cards lay their contents out in a row, narrow ones in a column."""
    if area is None:
        return None, None
    x0, y0, x1, y1 = area
    aw, ah = x1 - x0 - 2 * m, y1 - y0 - 2 * m
    if aw >= min_w and ah >= min_h:
        cw, ch, mode = min(aw, max_w), min(ah, max_h), "h"
    elif aw >= min_h * 1.3 and ah >= min_w * 0.9:
        cw, ch, mode = min(aw, max_h * 1.35), min(ah, v_h), "v"
    else:
        return None, None
    if corner == "tr":
        return (x1 - m - cw, y0 + m, x1 - m, y0 + m + ch), mode
    return (x0 + m, y1 - m - ch, x0 + m + cw, y1 - m), mode


# ----------------------------------------------------------------------------------- classic

WHITE = (255, 255, 255, 255)
BC_B, BC_S, BC_M = "BarlowCondensed-Bold.ttf", "BarlowCondensed-SemiBold.ttf", "BarlowCondensed-Medium.ttf"
ENGRAVE = (27, 27, 27, 255)
RED = (200, 30, 37, 255)
_tex = {}


def _vgrad(w, h, stops):
    """A vertical gradient (w x h px, already at SS scale): stops = [(pos 0..1, (r, g, b))]."""
    ys = np.linspace(0, 1, max(2, h))
    pos = [s[0] for s in stops]
    out = np.stack([np.interp(ys, pos, [s[1][c] for s in stops]) for c in range(3)], axis=1)
    arr = np.repeat(out[:, None, :], w, axis=1).astype(np.uint8)
    return Image.fromarray(arr, "RGB").convert("RGBA")


CHROME = [(0, (247, 247, 245)), (0.28, (221, 222, 220)), (0.6, (182, 184, 184)), (0.84, (212, 213, 211)), (1, (143, 145, 146))]
KEY = [(0, (255, 255, 255)), (0.55, (196, 198, 198)), (1, (150, 152, 153))]
KEY_IN = [(0, (140, 142, 143)), (0.6, (188, 190, 190)), (1, (204, 205, 203))]


def _metal(p, r, stops, rad=0.0):
    """A brushed-metal panel with rounded corners (kept by size and finish)."""
    x0, y0, x1, y1 = p.b(r)
    w, h = max(2, x1 - x0), max(2, y1 - y0)
    key = ("metal", w, h, tuple(stops), p.s(rad))
    made = _tex.get(key)
    if made is None:
        if len(_tex) > 600:
            _tex.clear()
        arr = np.asarray(_vgrad(w, h, stops)).copy()
        rng = np.random.default_rng(7)
        grain = rng.integers(-5, 6, size=(h, 1, 1))  # fine horizontal brushing
        arr[..., :3] = np.clip(arr[..., :3].astype(int) + grain, 0, 255)
        im = Image.fromarray(arr, "RGBA")
        mask = Image.new("L", (w, h), 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, w - 1, h - 1), radius=p.s(rad), fill=255)
        made = _tex[key] = (im, mask)
    p.img.paste(made[0], (x0, y0), made[1])


def _disc(d, light=(255, 255, 255), mid=(214, 215, 213), dark=(150, 152, 153), hx=0.35, hy=0.28):
    """A domed metal disc d px across (SS scale): bright off-centre, darker at the rim."""
    key = ("disc", d, light, mid, dark, hx, hy)
    if key not in _tex:
        y, x = np.mgrid[0:d, 0:d]
        dist = np.hypot(x - d * hx, y - d * hy) / (d * 0.82)
        t = np.clip(dist, 0, 1)[..., None]
        a, b, c = np.array(light), np.array(mid), np.array(dark)
        col = np.where(t < 0.4, a + (b - a) * (t / 0.4), b + (c - b) * ((t - 0.4) / 0.6))
        rr = np.hypot(x - d / 2 + 0.5, y - d / 2 + 0.5)
        alpha = np.clip((d / 2 - rr) * 1.0, 0, 1) * 255
        _tex[key] = Image.fromarray(np.dstack([col, alpha]).astype(np.uint8), "RGBA")
    return _tex[key]


def _knurl(d, teeth=60):
    """A knurled ring d px across (SS scale): alternating dark and bright teeth."""
    key = ("knurl", d, teeth)
    if key not in _tex:
        im = Image.new("RGBA", (d, d), (0, 0, 0, 0))
        dr = ImageDraw.Draw(im)
        step = 360 / (teeth * 2)
        for i in range(teeth * 2):
            dr.pieslice((0, 0, d - 1, d - 1), i * step, (i + 1) * step,
                        fill=(108, 110, 112, 255) if i % 2 == 0 else (236, 236, 234, 255))
        # light from the top left: brighten that side, darken the other
        y, x = np.mgrid[0:d, 0:d]
        shade = ((x + y) / (2 * d) - 0.5) * -70
        arr = np.asarray(im).astype(int)
        arr[..., :3] = np.clip(arr[..., :3] + shade[..., None], 0, 255)
        _tex[key] = Image.fromarray(arr.astype(np.uint8), "RGBA")
    return _tex[key]


def _leather(w, h, k):
    """Leatherette: a fine pebbled grain."""
    key = ("leather", w, h)
    if key not in _tex:
        rng = np.random.default_rng(3)
        t = max(4, round(5 * k * SS))
        base = np.full((h, w, 3), 23, dtype=np.int16)
        # pebbles: a regular bump every t px, jittered, each a lighter top-left and darker bottom-right
        yy, xx = np.mgrid[0:h, 0:w]
        ox = (xx + (yy // t % 2) * (t // 2)) % t
        oy = yy % t
        bump = np.cos((ox - t * 0.35) / t * 2 * np.pi) + np.cos((oy - t * 0.35) / t * 2 * np.pi)
        base += (bump * 6)[..., None].astype(np.int16)
        base += rng.integers(-4, 5, size=(h, w, 1), dtype=np.int16)
        arr = np.dstack([np.clip(base, 0, 255), np.full((h, w), 255)]).astype(np.uint8)
        _tex[key] = Image.fromarray(arr, "RGBA")
    return _tex[key]


def _jewel(p, cx, cy, r, lit=True):
    """A small red lamp."""
    if lit:
        gs = p.s(r * 8)
        glow = Image.new("RGBA", (gs, gs), (0, 0, 0, 0))
        ImageDraw.Draw(glow).ellipse((gs * 0.22, gs * 0.22, gs * 0.78, gs * 0.78), fill=(224, 42, 49, 150))
        p.blend(glow.filter(ImageFilter.GaussianBlur(r * SS)), p.s(cx) - gs // 2, p.s(cy) - gs // 2)
    d = p.s(r * 2)
    disc = _disc(d, (255, 150, 150), (224, 42, 49), (120, 14, 20)) if lit else _disc(d, (150, 90, 90), (90, 28, 30), (48, 14, 16))
    p.paste(disc, (cx - r, cy - r))


def _screw(p, cx, cy, r, angle):
    p.paste(_disc(p.s(r * 2), (250, 250, 248), (190, 192, 192), (110, 112, 113)), (cx - r, cy - r))
    a = math.radians(angle)
    p.line([(cx - r * 0.7 * math.cos(a), cy - r * 0.7 * math.sin(a)), (cx + r * 0.7 * math.cos(a), cy + r * 0.7 * math.sin(a))], (60, 61, 62, 255), r * 0.28)


def _engraved(p, xy, s, f, anchor="mm", spacing=0.0, col=ENGRAVE, k=1.0):
    """Type cut into metal: a light edge just below it."""
    p.text((xy[0], xy[1] + 0.9 * k), s, f, (255, 255, 255, 190), anchor, spacing)
    p.text(xy, s, f, col, anchor, spacing)


def _knob(p, cx, cy, r, k):
    """A knurled knob with a domed top."""
    p.shadows([((cx - r, cy - r, cx + r, cy + r), r, 3 * k, 2.5 * k, 0.55)])
    p.paste(_knurl(p.s(r * 2)), (cx - r, cy - r))
    p.circle(cx, cy, r, outline=(70, 71, 72, 255), width=0.8 * k)
    ir = r * 0.76
    p.paste(_disc(p.s(ir * 2)), (cx - ir, cy - ir))
    p.circle(cx, cy, ir, outline=(120, 122, 123, 255), width=0.7 * k)
    return ir


def _window(p, cx, cy, r, k):
    """A round glass window in a chrome bezel; returns the glass radius."""
    p.shadows([((cx - r, cy - r, cx + r, cy + r), r, 3 * k, 2.5 * k, 0.5)])
    p.paste(_disc(p.s(r * 2), (255, 255, 255), (200, 202, 202), (120, 122, 123)), (cx - r, cy - r))
    gr = r - 4.5 * k
    p.circle(cx, cy, gr + 1 * k, fill=(60, 61, 62, 255))
    p.circle(cx, cy, gr, fill=(13, 13, 13, 255))
    return gr


def _glass(p, r):
    """A faint reflection across a window."""
    x0, y0, x1, y1 = p.b(r)
    w, h = x1 - x0, y1 - y0
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(layer).polygon([(w * 0.10, 0), (w * 0.34, 0), (w * 0.14, h), (w * 0.02, h)],
                                  fill=(255, 255, 255, 30))
    p.blend(layer, x0, y0)


def _gauge(p, r, k, state):
    """A needle meter for the printer, any size: red zone = off, middle = busy, right = ready."""
    x0, y0, x1, y1 = r
    gw, gh = x1 - x0, y1 - y0
    u = min(gw / 144.0, gh / 86.0) / k  # how big next to its full size
    p.shadows([(r, 5 * k, 4 * k, 3 * k, 0.55)])
    _metal(p, r, [(0, (244, 244, 242)), (0.55, (138, 140, 141)), (1, (217, 218, 216))], 5 * k)
    face = (x0 + 3 * k, y0 + 3 * k, x1 - 3 * k, y1 - 3 * k)
    p.rrect(face, 3.5 * k, fill=(238, 232, 216, 255))
    cx, cy = (x0 + x1) / 2, y1 - gh * 0.27
    R = min(gw / 2 - 22 * k * u, gh * 0.5)
    box = (cx - R, cy - R, cx + R, cy + R)
    p.arc(box, 205, 335, ENGRAVE, 1.3 * k)
    p.arc((cx - R + 3 * k * u, cy - R + 3 * k * u, cx + R - 3 * k * u, cy + R - 3 * k * u), 205, 245, RED, 4.5 * k * u)
    for i in range(14):
        a = math.radians(205 + i * 10)
        long = i % 3 == 1
        r0, r1 = R + 2 * k * u, R + (8 if long else 5) * k * u
        p.line([(cx + r0 * math.cos(a), cy + r0 * math.sin(a)), (cx + r1 * math.cos(a), cy + r1 * math.sin(a))], ENGRAVE, (1.4 if long else 0.9) * k)
    a = math.radians({"off": 218, "alert": 228, "printing": 270, "ready": 318}.get(state, 218))
    p.cap_line([(cx - 6 * k * u * math.cos(a), cy - 6 * k * u * math.sin(a)), (cx + (R + 4 * k * u) * math.cos(a), cy + (R + 4 * k * u) * math.sin(a))], RED, 2.0 * k)
    p.circle(cx, cy, 5 * k * u, fill=ENGRAVE)
    p.circle(cx - 1.2 * k * u, cy - 1.2 * k * u, 1.6 * k * u, fill=(120, 122, 123, 255))
    f = font(BC_B, max(7.5 * k, 9 * k * u))
    p.text((x0 + 8 * k, y0 + 3 * k + 8 * k * u), "OFF", f, (176, 26, 32, 255), "lm", 0.8 * k)
    p.text((x1 - 8 * k, y0 + 3 * k + 8 * k * u), "READY", f, ENGRAVE, "rm", 0.8 * k)
    p.text((cx, y1 - 3 * k - 6 * k * u), "PRINTER", font(BC_B, max(7 * k, 8.5 * k * u)), ENGRAVE, "mm", 2.0 * k * u)
    _glass(p, face)


def _tape(p, r, s, k, col=RED, tilt=-1.0):
    """Embossed label tape."""
    x0, y0, x1, y1 = r
    f = p.fit(s, BC_S, 15.5 * k, x1 - x0 - 20 * k, spacing=2.6 * k)
    wdt = p.text_w(s, f, 2.6 * k) + 24 * k
    tw, th = p.s(wdt), p.s(y1 - y0)
    im = Image.new("RGBA", (tw, th), col)
    d = ImageDraw.Draw(im, "RGBA")
    d.rectangle((0, 0, tw, p.s(1.2 * k)), fill=(255, 255, 255, 70))
    d.rectangle((0, th - p.s(1.6 * k), tw, th), fill=(0, 0, 0, 70))
    tp = Pen(1, 1)
    tp.img, tp.d = im, d
    tp.text((wdt / 2, (y1 - y0) / 2 + 1 * k), s, f, (0, 0, 0, 90), "mm", 2.6 * k)
    tp.text((wdt / 2, (y1 - y0) / 2), s, f, (255, 255, 255, 255), "mm", 2.6 * k)
    im = im.rotate(tilt, expand=True, resample=Image.BICUBIC)
    p.shadows([((x0 + 1 * k, y0 + 1 * k, x0 + wdt - 1 * k, y1), 1 * k, 2.5 * k, 2 * k, 0.6)])
    p.paste(im, (x0, y0 - 2 * k))


def _date_wheels(p, r, k, parts):
    p.shadows([(r, 4 * k, 3 * k, 2.5 * k, 0.6)])
    _metal(p, r, [(0, (242, 242, 240)), (1, (142, 144, 145))], 4 * k)
    cw = (r[2] - r[0] - 8 * k - 6 * k) / 3
    for i, part in enumerate(parts):
        wx = r[0] + 4 * k + i * (cw + 3 * k)
        win = (wx, r[1] + 4 * k, wx + cw, r[3] - 4 * k)
        p.rrect(win, 2 * k, fill=(14, 14, 14, 255))
        p.text(((win[0] + win[2]) / 2, (win[1] + win[3]) / 2), part, font(BC_S, min(19 * k, (win[3] - win[1]) * 0.7)), (244, 242, 234, 255), "mm")
        p.rect((win[0], win[1], win[2], win[1] + 2.5 * k), fill=(0, 0, 0, 150))
        p.rect((win[0], win[3] - 2.5 * k, win[2], win[3]), fill=(0, 0, 0, 120))


def _counter(p, cx, cy, rad, k, cur, of):
    """The exposure counter: a round window with the next photo's number under a red mark."""
    gr = _window(p, cx, cy, rad, k)
    cream, dim = (244, 242, 234, 255), (140, 139, 134, 255)
    p.text((cx, cy + 1 * k), str(cur), font(BC_B, rad * 1.06), cream, "mm")
    if cur - 1 >= 1:
        p.text((cx - rad * 0.58, cy + 2 * k), str(cur - 1), font(BC_S, rad * 0.5), dim, "mm")
    if cur + 1 <= of:
        p.text((cx + rad * 0.58, cy + 2 * k), str(cur + 1), font(BC_S, rad * 0.5), dim, "mm")
    p.poly([(cx - 5 * k, cy - gr), (cx + 5 * k, cy - gr), (cx, cy - gr + 8 * k)], fill=(224, 42, 49, 255))
    p.arc((cx - gr + 3 * k, cy - gr + 3 * k, cx + gr - 3 * k, cy + gr - 3 * k), 200, 250, (255, 255, 255, 60), 2 * k)


def _classic(w, h, st):
    g = geometry("classic", w, h)
    k = g["k"]
    p = Pen(w, h)
    p.img.paste(_leather(w * SS, h * SS, k), (0, 0))
    p.d = ImageDraw.Draw(p.img, "RGBA")
    stage = g["stage"]
    rects = st.get("strip_rects", [])
    area_a, area_b = free_areas(stage, rects, 9 * k)
    card_a, mode_a = _fit_card(area_a, 260 * k, 96 * k, 150 * k, 40 * k, 3 * k, "tr", 170 * k)
    card_b, mode_b = _fit_card(area_b, 250 * k, 88 * k, 150 * k, 40 * k, 3 * k, "bl", 190 * k)
    g["status"] = card_b

    # ---------------- the key column: a chrome edge, then four keys on the leather
    col = stage[0]
    p.rect((col - 3 * k, 0, col - 1.6 * k, h), fill=(8, 8, 8, 255))
    p.rect((col - 1.6 * k, 0, col - 0.6 * k, h), fill=(150, 152, 153, 255))
    kinds = st["kinds"]
    names = {"menu": "MENU", "gallery": "ROLL", "fx": "EFFECTS", "layout": "FORMAT", "camera": "CAMERA"}
    for i, kind in enumerate(kinds):
        cx, cy, rad = g["keys"][i]
        r = (cx - rad, cy - rad, cx + rad, cy + rad)
        pressed = (kind == "fx" and st["effects_on"]) or kind == "camera"
        p.shadows([((cx - rad - 5 * k, cy - rad - 5 * k, cx + rad + 5 * k, cy + rad + 5 * k), rad + 5 * k, 4 * k, 4 * k, 0.7)])
        p.circle(cx, cy, rad + 5.5 * k, fill=(172, 174, 174, 255))
        p.circle(cx, cy, rad + 4.6 * k, outline=(240, 240, 238, 255), width=1 * k)
        p.circle(cx, cy, rad + 3 * k, fill=(10, 10, 10, 255))
        if pressed:
            p.paste(_disc(p.s(rad * 2), (255, 255, 255), (200, 201, 200), (126, 128, 129), 0.62, 0.7), (cx - rad, cy - rad))
            p.circle(cx, cy, rad, outline=(60, 61, 62, 200), width=2.2 * k)
        else:
            p.paste(_disc(p.s(rad * 2), (255, 255, 255), (217, 218, 216), (142, 144, 145)), (cx - rad, cy - rad))
        for rr, al in ((rad * 0.74, 70), (rad * 0.5, 45)):
            p.circle(cx, cy, rr, outline=(0, 0, 0, al), width=0.8 * k)
            p.arc((cx - rr - 0.8 * k, cy - rr - 0.8 * k, cx + rr + 0.8 * k, cy + rr + 0.8 * k), 20, 110, (255, 255, 255, 150), 0.8 * k)
        if kind == "fx":
            _jewel(p, r[2] - 3 * k, r[1] + 3 * k, 6 * k, lit=st["effects_on"])
        p.text((cx, r[3] + 18 * k), names[kind], font(BC_B, 14 * k), (236, 236, 233, 255), "mm", 2.0 * k)

    # ---------------- each piece of the strip in its own chrome-rimmed window
    for r in rects:
        b = (r[0] - 5 * k, r[1] - 5 * k, r[2] + 5 * k, r[3] + 5 * k)
        p.shadows([(b, 5 * k, 5 * k, 4 * k, 0.75)])
        _metal(p, b, [(0, (246, 246, 244)), (0.5, (150, 152, 153)), (1, (220, 221, 219))], 5 * k)
        p.rrect((b[0] + 0.8 * k, b[1] + 0.8 * k, b[2] - 0.8 * k, b[3] - 0.8 * k), 4.5 * k, outline=(255, 255, 255, 150), width=0.8 * k)
        p.rect((r[0] - 1.6 * k, r[1] - 1.6 * k, r[2] + 1.6 * k, r[3] + 1.6 * k), fill=(34, 35, 36, 255))

    # ---------------- A: the name plate with the exposure counter
    if card_a:
        x0, y0, x1, y1 = card_a
        cw, ch = x1 - x0, y1 - y0
        p.shadows([(card_a, 5 * k, 4 * k, 3 * k, 0.6)])
        _metal(p, card_a, CHROME, 5 * k)
        p.rrect(card_a, 5 * k, outline=(96, 98, 99, 255), width=0.8 * k)
        p.rect((x0 + 5 * k, y0 + 0.8 * k, x1 - 5 * k, y0 + 1.8 * k), fill=(255, 255, 255, 230))
        fmt = "STRIP" if st["layout"] == "strip" else "SHEET"
        if mode_a == "h":
            rad = min(ch / 2 - (7 if ch >= 64 * k else 4) * k, 30 * k)
            ccx, ccy = x1 - 10 * k - rad, y0 + ch / 2
            _counter(p, ccx, ccy, rad, k, st["count"], st["count_of"])
            for sx_, sy_, ang in ((x0 + 7 * k, y0 + 7 * k, 30), (x0 + 7 * k, y1 - 7 * k, 110)):
                _screw(p, sx_, sy_, 2.8 * k, ang)
            tw = ccx - rad - 10 * k - (x0 + 16 * k)
            size = min(52 * k, ch * 0.66)
            script = font("Yellowtail.ttf", size)
            while p.text_w(BRAND, script) > tw - size * 0.5 and size > 12 * k:
                size -= 1 * k
                script = font("Yellowtail.ttf", size)
            ty = y0 + ch * (0.43 if ch >= 72 * k else 0.5)
            p.text((x0 + 16 * k, ty + 1 * k), BRAND, script, (255, 255, 255, 200), "lm")
            p.text((x0 + 16 * k, ty), BRAND, script, ENGRAVE, "lm")
            bw = p.text_w(BRAND, script)
            dr = size * 0.24
            p.paste(_disc(p.s(dr * 2), (255, 140, 140), (216, 35, 42), (130, 16, 22)), (x0 + 16 * k + bw + 5 * k, ty - dr - 4 * k))
            if ch >= 72 * k:
                sub = f"{st['count_label']} {st['count']} OF {st['count_of']} · {fmt}"
                _engraved(p, (x0 + 17 * k, y1 - 11 * k), sub, p.fit(sub, BC_B, 9.5 * k, tw, spacing=1.5 * k), "lm", 1.5 * k, k=k)
        else:
            cx = (x0 + x1) / 2
            rad = min(cw / 2 - 8 * k, 32 * k)
            _counter(p, cx, y0 + 12 * k + rad, rad, k, st["count"], st["count_of"])
            sub = f"OF {st['count_of']} · {fmt}"
            _engraved(p, (cx, y0 + 24 * k + 2 * rad), sub, p.fit(sub, BC_B, 10.5 * k, cw - 12 * k, spacing=1.4 * k), "mm", 1.4 * k, k=k)
            size = 34 * k
            script = font("Yellowtail.ttf", size)
            while p.text_w(BRAND, script) > cw - 10 * k and size > 11 * k:
                size -= 1 * k
                script = font("Yellowtail.ttf", size)
            if y0 + 46 * k + 2 * rad + size <= y1:
                p.text((cx, y0 + 46 * k + 2 * rad + 1 * k), BRAND, script, (255, 255, 255, 200), "mm")
                p.text((cx, y0 + 46 * k + 2 * rad), BRAND, script, ENGRAVE, "mm")

    # ---------------- B: label tape, the printer's needle gauge, the date wheels
    if card_b:
        x0, y0, x1, y1 = card_b
        cw, ch = x1 - x0, y1 - y0
        has_gauge = st["printer"] is not None
        tape = st.get("tape") or ""
        if mode_b == "h" and not tape:
            gw = min(ch * 1.62, cw * 0.56) if has_gauge else 0
            if has_gauge:
                _gauge(p, (x0, y0, x0 + gw, y1), k, st["printer"])
            dw, dh = min(108 * k, cw - gw - 10 * k), min(40 * k, ch)
            if dw >= 70 * k:
                _date_wheels(p, (x1 - dw, y0 + (ch - dh) / 2, x1, y0 + (ch + dh) / 2), k, st["date"])
        elif mode_b == "h":
            if ch >= 78 * k:
                _tape(p, (x0, y0 + 2 * k, x1, y0 + 28 * k), st["tape"], k)
                row = (x0, y0 + 36 * k, x1, y1)
                gw = min(104 * k, cw * 0.48)
                if has_gauge:
                    _gauge(p, (row[0], row[1], row[0] + gw, row[3]), k, st["printer"])
                dw = min(100 * k, cw - gw - 10 * k)
                dh = min(38 * k, row[3] - row[1])
                if dw >= 70 * k:
                    _date_wheels(p, (x1 - dw, row[3] - dh, x1, row[3]), k, st["date"])
            else:
                gw = min(ch * 1.6, cw * 0.4) if has_gauge else 0
                if has_gauge:
                    _gauge(p, (x0, y0, x0 + gw, y1), k, st["printer"])
                _tape(p, (x0 + gw + 8 * k, y0 + ch / 2 - 13 * k, x1, y0 + ch / 2 + 13 * k), st["tape"], k)
        else:
            y = y1
            if has_gauge:
                gh = min(cw * 0.62, 80 * k)
                _gauge(p, (x0, y - gh, x1, y), k, st["printer"])
                y -= gh + 10 * k
            if y - 36 * k >= y0:
                _date_wheels(p, (x0, y - 36 * k, x1, y), k, st["date"])
                y -= 46 * k
            if st.get("tape_narrow") and y - 28 * k >= y0:
                _tape(p, (x0, y - 28 * k, x1, y - 2 * k), st["tape_narrow"], k)

    # ---------------- the strip shows through its windows
    for r in rects:
        p.hole(r, 0)
    return p.done(), g


# ------------------------------------------------------- menus and the review screen: the skin

_plates = {}
GUNMETAL = [(0, (98, 100, 102)), (0.08, (70, 72, 74)), (0.6, (48, 49, 51)), (1, (30, 31, 32))]
ENAMEL = [(0, (246, 96, 100)), (0.12, (226, 50, 57)), (0.6, (200, 30, 37)), (1, (140, 18, 24))]
STEEL = [(0, (150, 152, 154)), (0.1, (112, 114, 116)), (0.6, (88, 90, 92)), (1, (62, 63, 65))]


def plate(look, w, h, name, radius=8):
    """A button or row background, w x h screen px (RGBA), for this look. `name`: row, key, accent,
    done, danger, off, busy, field or inset. Cached: menus redraw many times a second."""
    key = (look, w, h, name, radius)
    if key in _plates:
        return _plates[key]
    if len(_plates) > 400:
        _plates.clear()
    p = Pen(w, h)
    full = (0, 0, w, h)
    rad = min(max(radius, 5), 8, h / 2)
    if name == "accent":      # the chosen thing: polished chrome, dark type on it
        _metal(p, full, CHROME, rad)
        p.rrect(full, rad, outline=(70, 71, 72, 255), width=1)
        p.rect((rad, 1, w - rad, 2), fill=(255, 255, 255, 235))
    elif name == "danger":    # red enamel
        _metal(p, full, ENAMEL, rad)
        p.rrect(full, rad, outline=(70, 10, 14, 255), width=1)
        p.rrect((1.5, 1.5, w - 1.5, h - 1.5), rad - 1, outline=(255, 255, 255, 60), width=0.8)
    elif name in ("done", "busy"):
        _metal(p, full, STEEL, rad)
        p.rrect(full, rad, outline=(20, 20, 20, 255), width=1)
        p.rect((rad, 1, w - rad, 2), fill=(255, 255, 255, 110))
    elif name == "key":
        _metal(p, full, GUNMETAL, rad)
        p.rrect(full, rad, outline=(12, 12, 12, 255), width=1)
        p.rect((rad, 1, w - rad, 2), fill=(255, 255, 255, 70))
    elif name == "row":       # a black panel in a thin chrome rim
        _metal(p, full, [(0, (236, 236, 234)), (0.5, (120, 122, 123)), (1, (200, 201, 199))], rad)
        p.rrect((1.6, 1.6, w - 1.6, h - 1.6), max(1, rad - 1.2), fill=(20, 20, 20, 255))
        p.rect((rad, 2.2, w - rad, 3.4), fill=(0, 0, 0, 255))
    elif name == "field":     # a window: black glass, shadowed at the top
        _metal(p, full, [(0, (150, 152, 153)), (1, (236, 236, 234))], rad)
        p.rrect((1.6, 1.6, w - 1.6, h - 1.6), max(1, rad - 1.2), fill=(8, 8, 8, 255))
        p.rect((rad, 1.6, w - rad, 5), fill=(0, 0, 0, 255))
    else:                     # off, inset: dull, pressed into the body
        p.rrect(full, rad, fill=(14, 14, 14, 255))
        p.rrect((1, 1, w - 1, h - 1), max(1, rad - 1), fill=(34, 34, 34, 255) if name == "off" else (40, 40, 41, 255))
    _plates[key] = p.done()
    return _plates[key]


def menu_ground(look, w, h):
    """What's behind the menus and the review screen (RGB)."""
    key = ("ground", look, w, h)
    if key not in _plates:
        if look == "classic":
            _plates[key] = _leather(w * SS, h * SS, h / 480.0).resize((w, h), Image.LANCZOS).convert("RGB")
        else:
            _plates[key] = Image.new("RGB", (w, h), THEMES[look]["bg"])
    return _plates[key]


def film_edge(w, h):
    """A band of film edge with sprocket holes, w x h px (RGBA), for the classic review screen."""
    key = ("film", w, h)
    if key not in _plates:
        p = Pen(w, h)
        p.rect((0, 0, w, h), fill=(28, 23, 20, 255))
        hole_w, hole_h, step = h * 0.62, h * 0.52, h * 1.5
        x = step * 0.3
        while x + hole_w < w:
            p.rrect((x, (h - hole_h) / 2, x + hole_w, (h + hole_h) / 2), hole_h * 0.22, fill=(236, 232, 220, 255))
            x += step
        _plates[key] = p.done()
    return _plates[key]


def render_main(look, w, h, st):
    """(RGBA picture of everything around the strip, geometry). See photobooth.py for `st`."""
    return _classic(w, h, st)


# --------------------------------------------------------------------------------- countdown

def render_countdown(look, w, h, value, count, count_of, frac=1.0):
    """What goes over the full-screen camera while it counts down (RGBA)."""
    k = h / 480.0
    p = Pen(w, h)
    cx, cy = w / 2, h / 2
    # the dark corners of a viewfinder
    q = 8  # built small and stretched: it is only a soft shadow
    vw, vh = max(2, p.img.width // q), max(2, p.img.height // q)
    vig = Image.new("L", (vw, vh), 120)
    ImageDraw.Draw(vig).rounded_rectangle((46 * k * SS / q, 40 * k * SS / q, vw - 46 * k * SS / q, vh - 40 * k * SS / q),
                                          radius=60 * k * SS / q, fill=0)
    vig = vig.filter(ImageFilter.GaussianBlur(34 * k * SS / q)).resize(p.img.size, Image.BILINEAR)
    dark = Image.new("RGBA", p.img.size, (0, 0, 0, 255))
    dark.putalpha(vig)
    p.img = dark
    p.d = ImageDraw.Draw(p.img, "RGBA")
    white = (255, 255, 255, 240)
    # bright-line frame
    x0, y0, x1, y1 = 70 * k, 58 * k, w - 70 * k, h - 58 * k
    for (ax, ay), (bx, by), (cx_, cy_) in (((x0, y0 + 46 * k), (x0, y0), (x0 + 58 * k, y0)), ((x1 - 58 * k, y0), (x1, y0), (x1, y0 + 46 * k)),
                                         ((x1, y1 - 46 * k), (x1, y1), (x1 - 58 * k, y1)), ((x0 + 58 * k, y1), (x0, y1), (x0, y1 - 46 * k))):
        p.cap_line([(ax, ay), (bx, by), (cx_, cy_)], white, 2.6 * k)
    for (ax, ay, bx, by) in ((cx, y0 - 14 * k, cx, y0), (cx, y1, cx, y1 + 14 * k), (x0 - 14 * k, cy, x0, cy), (x1, cy, x1 + 14 * k, cy)):
        p.line([(ax, ay), (bx, by)], (255, 255, 255, 200), 1.6 * k)
    # the self-timer's clockwork ring: sixty ticks, the part still to run in red
    R = 124 * k
    for i in range(60):
        a = math.radians(i * 6 - 90)
        long = i % 5 == 0
        r0, r1 = R - (9 if long else 5) * k, R
        p.line([(cx + r0 * math.cos(a), cy + r0 * math.sin(a)), (cx + r1 * math.cos(a), cy + r1 * math.sin(a))], white, (2.2 if long else 1.2) * k)
    p.circle(cx, cy, R - 15 * k, outline=(255, 255, 255, 110), width=1 * k)
    p.arc((cx - R - 7 * k, cy - R - 7 * k, cx + R + 7 * k, cy + R + 7 * k), -90, -90 + 360 * max(0.02, min(1.0, frac)), (224, 42, 49, 255), 5 * k)
    p.poly([(cx - 8 * k, cy - R - 24 * k), (cx + 8 * k, cy - R - 24 * k), (cx, cy - R - 10 * k)], fill=(224, 42, 49, 255))
    numf = font(BC_B, 214 * k)
    p.text((cx + 2 * k, cy - 6 * k + 4 * k), str(value), numf, (0, 0, 0, 150), "mm")
    p.text((cx, cy - 6 * k), str(value), numf, WHITE, "mm")
    _tape(p, (22 * k, 20 * k, 180 * k, 50 * k), "SELF-TIMER", k, tilt=-1.5)
    gr = _window(p, w - 22 * k - 32 * k, 16 * k + 32 * k, 32 * k, k)
    ex, ey = w - 22 * k - 32 * k, 16 * k + 32 * k
    p.text((ex, ey + 1 * k), str(count), font(BC_B, 34 * k), (244, 242, 234, 255), "mm")
    if count > 1:
        p.text((ex - 19 * k, ey + 2 * k), str(count - 1), font(BC_S, 16 * k), (140, 139, 134, 255), "mm")
    if count < count_of:
        p.text((ex + 19 * k, ey + 2 * k), str(count + 1), font(BC_S, 16 * k), (140, 139, 134, 255), "mm")
    p.poly([(ex - 5 * k, ey - gr), (ex + 5 * k, ey - gr), (ex, ey - gr + 8 * k)], fill=(224, 42, 49, 255))
    _jewel(p, 34 * k, h - 32 * k, 11 * k, lit=True)
    p.text((54 * k, h - 32 * k + 1 * k), "LAMP ON · THEN CLICK", font(BC_S, 14 * k), (0, 0, 0, 200), "lm", 3.2 * k)
    p.text((54 * k, h - 32 * k), "LAMP ON · THEN CLICK", font(BC_S, 14 * k), WHITE, "lm", 3.2 * k)
    _tape(p, (cx - 78 * k, h - 96 * k, cx + 78 * k, h - 62 * k), "HOLD STILL", k, col=(17, 17, 17, 255), tilt=1.0)
    return p.done()


if __name__ == "__main__":
    import sys
    W, H = 629, 480
    base = dict(kinds=["menu", "gallery", "fx", "layout"], effects_on=True, saved=57, wifi=True,
                battery=None, title="Frame 16", chip="2x6 strip · 4 photos", design=11, designs=37,
                switch_text="", count_label="PHOTO", count=2, count_of=4,
                count_side="2 left", segments=["done", "now", "todo", "todo"], printer="ready",
                printer_title="Printer ready", printer_sub="Nothing waiting", phone=True,
                cta=["Press the big button", "for photo 2"], cta_narrow=["Press", "the big", "button"],
                layout="strip", tape="", tape_narrow="",
                plate_text="", date=("11", "14", "26"))
    tiles = []
    for look in LOOKS:
        g = geometry(look, W, H)
        sx0, sy0, sx1, sy1 = g["stage"]
        pad = g["pad"]
        cell = (sx1 - sx0) / 2
        sc = min((cell - 2 * pad) / 1200, (sy1 - sy0 - 2 * pad) / 1800)
        hw, hh = 1200 * sc, 1800 * sc
        halves = [(sx0 + (cell - hw) / 2, sy0 + pad, sx0 + (cell - hw) / 2 + hw, sy0 + pad + hh),
                  (sx0 + cell + (cell - hw) / 2, sy1 - pad - hh, sx0 + cell + (cell - hw) / 2 + hw, sy1 - pad)]
        sc = min((sx1 - sx0 - 2 * pad) / 1800, (sy1 - sy0 - 2 * pad) / 1200)
        sheet_r = [((sx0 + sx1) / 2 - 900 * sc, (sy0 + sy1) / 2 - 600 * sc, (sx0 + sx1) / 2 + 900 * sc, (sy0 + sy1) / 2 + 600 * sc)]
        sc = min((sx1 - sx0 - 2 * pad) / 1200, (sy1 - sy0 - 2 * pad) / 1800)
        psheet_r = [((sx0 + sx1) / 2 - 600 * sc, (sy0 + sy1) / 2 - 900 * sc, (sx0 + sx1) / 2 + 600 * sc, (sy0 + sy1) / 2 + 900 * sc)]
        for rects, extra in ((halves, {}), (sheet_r, {"layout": "sheet", "printer": "printing", "printer_title": "Printing"}),
                             (psheet_r, {"layout": "sheet", "cta_seconds": 12, "cta_frac": 0.6, "tape": "1 KEEP · 2 RETAKE · 12s"})):
            im, _ = render_main(look, W, H, dict(base, strip_rects=[tuple(round(v) for v in r) for r in rects], **extra))
            bg = Image.new("RGBA", (W, H), (120, 150, 190, 255))
            bg.alpha_composite(im)
            tiles.append(bg)
    sheet = Image.new("RGB", (W * 3 + 20, (H + 10) * len(LOOKS) - 10), "white")
    for i, t in enumerate(tiles):
        sheet.paste(t.convert("RGB"), ((i % 3) * (W + 10), (i // 3) * (H + 10)))
    sheet.save(sys.argv[1] if len(sys.argv) > 1 else "looks.png")
