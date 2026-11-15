"""The MODERN and CLASSIC CAMERA looks: everything on the main screen around the strip, and the
countdown, drawn with Pillow. No app state in here: photobooth.py passes in what to show (a plain
dict) and gets back pictures and tap areas, so this can be rendered and looked at on its own:

    python3 looks.py out.png          # both looks, a few states, side by side

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
LOOKS = ("modern", "classic")
STAGE_BG = {"modern": (244, 245, 248), "classic": (6, 6, 6)}

# Menu and review-screen colours for each look (same keys as THEMES in photobooth.py).
THEMES = {
    "modern": dict(bg=(238, 240, 244), row=(255, 255, 255), text=(13, 16, 23), dim=(75, 85, 101),
                   accent=(91, 134, 255), done=(60, 196, 120), danger=(240, 100, 88),
                   off=(226, 229, 235), busy=(200, 205, 214), key=(222, 226, 233),
                   field=(255, 255, 255), inset=(226, 229, 235), good=(11, 122, 64),
                   bad=(197, 40, 28), disc=(13, 16, 23), main=(238, 240, 244)),
    "classic": dict(bg=(23, 23, 23), row=(52, 52, 52), text=(241, 241, 238), dim=(185, 186, 184),
                    accent=(217, 218, 216), done=(92, 94, 96), danger=(200, 30, 37),
                    off=(34, 34, 34), busy=(96, 97, 98), key=(74, 75, 76), field=(8, 8, 8),
                    inset=(38, 38, 38), good=(225, 226, 224), bad=(255, 110, 114),
                    disc=(10, 10, 10), main=(23, 23, 23)),
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
    if look == "modern":
        return "PlusJakartaSans.ttf", 800 if bold else 600, 1.0
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
        """Soft drop shadows: items = [(rect, radius, blur, dy, strength)]. Each is blurred in its
        own small patch (a blur of the whole screen per shadow is far too slow)."""
        for r, rad, blur, dy, strength in items:
            x0, y0, x1, y1 = r
            m = blur * 3 + 2
            bx0, by0 = math.floor((x0 - m) * SS), math.floor((y0 + dy - m) * SS)
            bx1, by1 = math.ceil((x1 + m) * SS), math.ceil((y1 + dy + m) * SS)
            w, h = bx1 - bx0, by1 - by0
            if w <= 0 or h <= 0:
                continue
            mask = Image.new("L", (w, h), 0)
            ImageDraw.Draw(mask).rounded_rectangle(
                (x0 * SS - bx0, (y0 + dy) * SS - by0, x1 * SS - bx0, (y1 + dy) * SS - by0),
                radius=self.s(rad), fill=round(255 * strength))
            mask = mask.filter(ImageFilter.GaussianBlur(blur * SS))
            patch = Image.new("RGBA", (w, h), (0, 0, 0, 255))
            patch.putalpha(mask)
            self.blend(patch, bx0, by0)

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
        return self.img.resize((self.w, self.h), Image.LANCZOS)


# ---------------------------------------------------------------------------------- geometry

def geometry(look, w, h):
    """Where things are, in screen px: "stage" (the strip goes here), "buttons" (the four main
    ones, in order), and other tap areas by name."""
    k = h / 480.0
    g = {"k": k}
    if look == "modern":
        pad, gap, rail, aside = 14 * k, 12 * k, 68 * k, 158 * k
        g["rail"] = [(pad, pad + i * 80 * k, pad + rail, pad + i * 80 * k + 72 * k) for i in range(4)]
        g["status"] = (pad, pad + 4 * 80 * k, pad + rail, h - pad)
        card = (pad + rail + gap, pad, w - pad - aside - gap, h - pad)
        g["card"] = card
        inner = 14 * k
        g["stage"] = (card[0] + inner, card[1] + inner + 34 * k, card[2] - inner, card[3] - inner - 58 * k)
        sy = card[3] - inner - 46 * k
        g["prev"] = (card[0] + inner, sy, card[0] + inner + 46 * k, sy + 46 * k)
        g["next"] = (card[2] - inner - 46 * k, sy, card[2] - inner, sy + 46 * k)
        ax = w - pad - aside
        g["photo_card"] = (ax, pad, w - pad, pad + 132 * k)
        g["printer"] = (ax, pad + 142 * k, w - pad, pad + 202 * k)
        g["phone"] = (ax, pad + 212 * k, w - pad, pad + 272 * k)
        g["cta"] = (ax, pad + 282 * k, w - pad, h - pad)
    else:
        plate, foot, col, pad = 84 * k, 62 * k, 150 * k, 16 * k
        g["plate"] = (0, 0, w, plate)
        vf = (pad, plate + 12 * k, w - pad - col - 14 * k, h - foot)
        g["viewfinder"] = vf
        g["stage"] = (vf[0] + 5 * k, vf[1] + 5 * k, vf[2] - 5 * k, vf[3] - 5 * k)
        cx0 = w - pad - col
        g["rail"] = []
        for i in range(4):
            bx = cx0 + (i % 2) * 82 * k + 3 * k
            by = plate + 14 * k + (i // 2) * 92 * k
            g["rail"].append((bx, by, bx + 62 * k, by + 62 * k))
        g["printer"] = (cx0, h - foot - 90 * k, w - pad, h - foot - 4 * k)
        fy = h - foot + 10 * k
        g["tape"] = (pad, fy + 4 * k, pad + 196 * k, fy + 34 * k)
        g["plate_name"] = (pad + 208 * k, fy, w - pad - 108 * k, fy + 38 * k)
        g["prev"] = (g["plate_name"][0], fy - 3 * k, g["plate_name"][0] + 46 * k, fy + 41 * k)
        g["next"] = (g["plate_name"][2] - 46 * k, fy - 3 * k, g["plate_name"][2], fy + 41 * k)
        g["date"] = (w - pad - 96 * k, fy, w - pad, fy + 38 * k)
    return g


# ------------------------------------------------------------------------------------ modern

INK, MUTED, BLUE = (13, 16, 23, 255), (75, 85, 101, 255), (43, 91, 255, 255)
WHITE = (255, 255, 255, 255)
PJS = "PlusJakartaSans.ttf"


def _icon(p, kind, cx, cy, s, col, bg=WHITE):
    """Line icons, about s px across, centred on (cx, cy)."""
    u = s / 24.0
    w = 2.0 * u

    def L(pts, width=w):
        p.cap_line([(cx + (x - 12) * u, cy + (y - 12) * u) for x, y in pts], col, width)

    def C(x, y, r, fill=None, outline=None):
        p.circle(cx + (x - 12) * u, cy + (y - 12) * u, r * u, fill, outline, w)

    def R(x0, y0, x1, y1, rad, fill=None, outline=None):
        p.rrect((cx + (x0 - 12) * u, cy + (y0 - 12) * u, cx + (x1 - 12) * u, cy + (y1 - 12) * u),
                rad * u, fill, outline, w)

    if kind == "menu":
        for y, kx in ((6, 15), (12, 9), (18, 17)):
            L([(4, y), (20, y)])
            C(kx, y, 3.2, fill=bg)
            C(kx, y, 2.6, outline=col)
    elif kind == "gallery":
        R(7, 4, 21, 17, 2.5, outline=col)
        R(3, 7, 17, 20, 2.5, fill=bg, outline=col)
        L([(5, 18), (9, 14), (12, 17), (14, 15), (16.5, 18)], w * 0.9)
        C(8, 11.3, 1.3, fill=col)
    elif kind == "fx":
        def star(x, y, r):
            pts = []
            for i in range(8):
                a = math.pi / 4 * i - math.pi / 2
                rr = r if i % 2 == 0 else r * 0.32
                pts.append((cx + (x - 12) * u + rr * u * math.cos(a), cy + (y - 12) * u + rr * u * math.sin(a)))
            p.poly(pts, fill=col)
        star(10.5, 12.5, 9.5)
        star(19, 5.5, 4)
    elif kind == "layout":
        R(3, 3, 9, 21, 1.8, outline=col)
        R(12, 7, 21, 17, 1.8, outline=col)
    elif kind == "camera":
        R(3, 8, 21, 19.5, 2.5, outline=col)
        R(8.5, 4.5, 15.5, 9, 1.5, fill=bg, outline=col)
        C(12, 13.5, 3.6, outline=col)
    elif kind == "printer":
        R(7, 3, 17, 10, 0.6, outline=col)
        R(3, 9, 21, 17, 2, fill=bg, outline=col)
        R(7, 14, 17, 21, 0.6, fill=bg, outline=col)
    elif kind == "phone":
        R(6.5, 2, 17.5, 22, 3, outline=col)
        L([(10.5, 18.5), (13.5, 18.5)])
    elif kind == "wifi":
        for r in (10.5, 6.8, 3.2):
            p.arc((cx - r * u, cy + 7.5 * u - r * u, cx + r * u, cy + 7.5 * u + r * u), 225, 315, col, w * 1.1)
        C(12, 19.5, 1.3, fill=col)
    elif kind in ("left", "right"):
        sgn = 1 if kind == "left" else -1
        L([(12 + 3.5 * sgn, 5), (12 - 3.5 * sgn, 12), (12 + 3.5 * sgn, 19)], w * 1.3)
    elif kind == "down":
        L([(12, 4), (12, 19)], w * 1.2)
        L([(6, 13), (12, 19), (18, 13)], w * 1.2)
    elif kind == "check":
        L([(5, 12.5), (9.5, 17), (19, 7.5)], w * 1.3)


def _modern(w, h, st):
    g = geometry("modern", w, h)
    k = g["k"]
    p = Pen(w, h)
    p.rect((0, 0, w, h), fill=(238, 240, 244, 255))

    kinds = st["kinds"]
    soft = [(r, 18 * k, 8 * k, 4 * k, 0.07) for i, r in enumerate(g["rail"]) if i < len(kinds)]
    soft += [(g["card"], 22 * k, 12 * k, 8 * k, 0.09), (g["photo_card"], 20 * k, 8 * k, 4 * k, 0.07)]
    if st["printer"] is not None:
        soft += [(g["printer"], 18 * k, 8 * k, 4 * k, 0.07)]
        if st.get("phone"):
            soft += [(g["phone"], 18 * k, 8 * k, 4 * k, 0.07)]
    p.shadows(soft)

    # --- the rail
    labels = {"menu": "Settings", "gallery": "Photos", "fx": "Effects", "layout": "Layout",
              "camera": "Camera"}
    for i, kind in enumerate(kinds):
        r = g["rail"][i]
        on = (kind == "fx" and st["effects_on"]) or kind == "camera"
        fill = BLUE if on else WHITE
        fg = WHITE if on else INK
        p.rrect(r, 18 * k, fill=fill)
        cx, cy = (r[0] + r[2]) / 2, r[1] + 29 * k
        _icon(p, kind, cx, cy, 27 * k, fg, fill)
        text = "Effects on" if kind == "fx" and st["effects_on"] else labels[kind]
        p.text((cx, r[3] - 15 * k), text, font(PJS, 10 * k, 700), fg, "mm")
        if kind == "gallery" and st.get("saved"):
            n = str(st["saved"]) if st["saved"] < 1000 else "999+"
            f = font(PJS, 9.5 * k, 800)
            bw = max(20 * k, p.text_w(n, f) + 10 * k)
            p.rrect((r[2] - 6 * k - bw, r[1] + 6 * k, r[2] - 6 * k, r[1] + 26 * k), 10 * k, fill=INK)
            p.text((r[2] - 6 * k - bw / 2, r[1] + 16 * k), n, f, WHITE, "mm")
    s = g["status"]
    if s[3] - s[1] > 40 * k:
        p.rrect(s, 18 * k, fill=(226, 229, 235, 255))
        cx = (s[0] + s[2]) / 2
        has_batt = st.get("battery") is not None
        cy = (s[1] + s[3]) / 2 - (9 * k if has_batt else 0)
        col = (58, 67, 83, 255) if st.get("wifi") else (170, 176, 188, 255)
        _icon(p, "wifi", cx, cy - 3 * k, 26 * k, col)
        if not st.get("wifi"):
            p.cap_line([(cx - 10 * k, cy + 9 * k), (cx + 10 * k, cy - 11 * k)], (197, 40, 28, 255), 2.4 * k)
        if has_batt:
            by = cy + 22 * k
            p.rrect((cx - 24 * k, by - 6 * k, cx - 6 * k, by + 6 * k), 3 * k, outline=(58, 67, 83, 255), width=1.6 * k)
            p.rrect((cx - 5 * k, by - 2.5 * k, cx - 3 * k, by + 2.5 * k), 1 * k, fill=(58, 67, 83, 255))
            fw = 14 * k * max(0.08, min(1.0, st["battery"] / 100.0))
            low = st["battery"] <= 20
            p.rrect((cx - 22 * k, by - 4 * k, cx - 22 * k + fw, by + 4 * k), 1.5 * k,
                    fill=(197, 40, 28, 255) if low else (58, 67, 83, 255))
            p.text((cx + 1 * k, by), f"{st['battery']:.0f}%", font(PJS, 10.5 * k, 800), (58, 67, 83, 255), "lm")

    # --- the strip's card
    card = g["card"]
    p.rrect(card, 22 * k, fill=WHITE)
    tx, ty = card[0] + 14 * k, card[1] + 14 * k
    chip_f = font(PJS, 10.5 * k, 700)
    chip = st["chip"]
    chip_w = p.text_w(chip, chip_f) + 16 * k
    title_f = p.fit(st["title"], PJS, 17 * k, card[2] - card[0] - 28 * k - chip_w - 10 * k, 800)
    p.text((tx, ty + 12 * k), st["title"], title_f, INK, "lm")
    cx0 = card[2] - 14 * k - chip_w
    p.rrect((cx0, ty + 2 * k, card[2] - 14 * k, ty + 22 * k), 10 * k, fill=(231, 237, 255, 255))
    p.text((cx0 + chip_w / 2, ty + 12 * k), chip, chip_f, (27, 63, 196, 255), "mm")
    p.rrect(g["stage"], 16 * k, fill=STAGE_BG["modern"] + (255,))

    for name, kind in (("prev", "left"), ("next", "right")):
        r = g[name]
        p.rrect(r, 14 * k, fill=(238, 240, 244, 255))
        _icon(p, kind, (r[0] + r[2]) / 2, (r[1] + r[3]) / 2, 22 * k, INK)
    mid = (g["prev"][2] + g["next"][0]) / 2
    my = (g["prev"][1] + g["prev"][3]) / 2
    n, total = st["design"], max(1, st["designs"])
    dots = min(total, 7)
    at = 0 if total <= 1 else round((n - 1) / (total - 1) * (dots - 1))
    dw = 9 * k
    x = mid - (dots - 1) * dw / 2
    for i in range(dots):
        on = i == at
        p.circle(x + i * dw, my - 8 * k, (3.6 if on else 2.4) * k, fill=BLUE if on else (201, 206, 216, 255))
    p.text((mid, my + 9 * k), st["switch_text"], p.fit(st["switch_text"], PJS, 11 * k, g["next"][0] - g["prev"][2] - 12 * k, 700), MUTED, "mm")

    # --- photo counter
    c = g["photo_card"]
    p.rrect(c, 20 * k, fill=WHITE)
    x0, y0 = c[0] + 14 * k, c[1] + 14 * k
    p.text((x0, y0 + 6 * k), st["count_label"], font(PJS, 10.5 * k, 800), MUTED, "lm", spacing=0.9 * k)
    side = st.get("count_side", "")
    if side:
        p.text((c[2] - 14 * k, y0 + 6 * k), side, p.fit(side, PJS, 10.5 * k, 74 * k, 700), MUTED, "rm")
    big = font(PJS, 54 * k, 800)
    num = str(st["count"])
    p.text((x0 - 2 * k, y0 + 50 * k), num, big, INK, "lm")
    p.text((x0 + p.text_w(num, big) + 5 * k, y0 + 61 * k), f"of {st['count_of']}", font(PJS, 18 * k, 700), MUTED, "lm")
    seg = st.get("segments") or []
    if seg:
        sw = (c[2] - c[0] - 28 * k - (len(seg) - 1) * 5 * k) / len(seg)
        for i, state in enumerate(seg):
            col = {"done": INK, "now": BLUE}.get(state, (217, 221, 229, 255))
            sx = x0 + i * (sw + 5 * k)
            p.rrect((sx, c[3] - 22 * k, sx + sw, c[3] - 14 * k), 4 * k, fill=col)

    # --- printer and phone
    if st["printer"] is not None:
        tile = {"ready": ((227, 245, 234, 255), (11, 122, 64, 255)),
                "printing": ((255, 241, 214, 255), (138, 82, 0, 255)),
                "alert": ((255, 233, 228, 255), (181, 50, 31, 255)),
                "off": ((232, 234, 239, 255), (75, 85, 101, 255))}[st["printer"]]
        cards = [("printer", "printer", st["printer_title"], st["printer_sub"], tile)]
        if st.get("phone"):
            cards.append(("phone", "phone", "Print from phone", "Show me how",
                          ((231, 237, 255, 255), (27, 63, 196, 255))))
        for name, icon, title, sub, (tbg, tfg) in cards:
            r = g[name]
            p.rrect(r, 18 * k, fill=WHITE)
            cy = (r[1] + r[3]) / 2
            p.rrect((r[0] + 12 * k, cy - 18 * k, r[0] + 48 * k, cy + 18 * k), 11 * k, fill=tbg)
            _icon(p, icon, r[0] + 30 * k, cy, 21 * k, tfg, tbg)
            tw = r[2] - r[0] - 68 * k
            p.text((r[0] + 58 * k, cy - 8 * k), title, p.fit(title, PJS, 13 * k, tw, 800), INK, "lm")
            p.text((r[0] + 58 * k, cy + 9 * k), sub, p.fit(sub, PJS, 11 * k, tw, 600), MUTED, "lm")
        cta_top = g["phone"][3] + 10 * k if st.get("phone") else g["printer"][3] + 10 * k
    else:
        cta_top = g["photo_card"][3] + 10 * k

    # --- what to do next
    c = (g["cta"][0], cta_top, g["cta"][2], g["cta"][3])
    p.rrect(c, 20 * k, fill=INK)
    x0 = c[0] + 14 * k
    cy = c[1] + 37 * k
    if st.get("cta_seconds") is not None:
        ring = (x0, cy - 23 * k, x0 + 46 * k, cy + 23 * k)
        p.oval(ring, outline=(74, 84, 100, 255), width=4 * k)
        frac = max(0.0, min(1.0, st["cta_frac"]))
        p.arc(ring, -90, -90 + 360 * frac, BLUE, 4 * k)
        p.text((x0 + 23 * k, cy), str(st["cta_seconds"]), font(PJS, 17 * k, 800), WHITE, "mm")
    else:
        p.circle(x0 + 23 * k, cy, 33 * k, fill=(22, 34, 78, 255))
        p.circle(x0 + 23 * k, cy, 28 * k, fill=(28, 50, 128, 255))
        p.circle(x0 + 23 * k, cy, 23 * k, fill=BLUE)
        _icon(p, "down", c[2] - 26 * k, cy, 26 * k, WHITE)
    lines = st["cta"]
    f = None
    for size in (16, 15, 14, 13, 12, 11):
        f = font(PJS, size * k, 800)
        if all(p.text_w(line, f) <= c[2] - c[0] - 28 * k for line in lines):
            break
    lh = f.size / SS * 1.22
    y = c[3] - 14 * k - lh * len(lines) + lh / 2
    for line in lines:
        p.text((x0, y), line, f, WHITE, "lm")
        y += lh

    # --- the strip shows through here, lifted off the panel by a shadow
    p.hole(g["stage"], 16 * k)
    p.shadows([(r, 2 * k, 9 * k, 7 * k, 0.26) for r in st.get("strip_rects", [])])
    for r in st.get("strip_rects", []):
        p.hole(r, 0)
    return p.done(), g


# ----------------------------------------------------------------------------------- classic

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
    """A brushed-metal panel with rounded corners."""
    x0, y0, x1, y1 = p.b(r)
    w, h = max(2, x1 - x0), max(2, y1 - y0)
    im = _vgrad(w, h, stops)
    arr = np.asarray(im).copy()
    rng = np.random.default_rng(7)
    grain = rng.integers(-5, 6, size=(h, 1, 1))  # fine horizontal brushing
    arr[..., :3] = np.clip(arr[..., :3].astype(int) + grain, 0, 255)
    im = Image.fromarray(arr, "RGBA")
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, w - 1, h - 1), radius=p.s(rad), fill=255)
    p.img.paste(im, (x0, y0), mask)


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
    """A needle meter for the printer: red zone = off, middle = busy, right = ready."""
    x0, y0, x1, y1 = r
    p.shadows([(r, 6 * k, 4 * k, 3 * k, 0.55)])
    _metal(p, r, [(0, (244, 244, 242)), (0.55, (138, 140, 141)), (1, (217, 218, 216))], 6 * k)
    face = (x0 + 3.5 * k, y0 + 3.5 * k, x1 - 3.5 * k, y1 - 3.5 * k)
    p.rrect(face, 4 * k, fill=(238, 232, 216, 255))
    cx, cy = (x0 + x1) / 2, y1 - 24 * k
    R = min((x1 - x0) / 2 - 22 * k, y1 - y0 - 44 * k)
    box = (cx - R, cy - R, cx + R, cy + R)
    p.arc(box, 205, 335, ENGRAVE, 1.4 * k)
    p.arc((cx - R + 3 * k, cy - R + 3 * k, cx + R - 3 * k, cy + R - 3 * k), 205, 245, RED, 5 * k)
    for i in range(14):
        a = math.radians(205 + i * 10)
        long = i % 3 == 1
        r0, r1 = R + 2 * k, R + (9 if long else 5.5) * k
        p.line([(cx + r0 * math.cos(a), cy + r0 * math.sin(a)), (cx + r1 * math.cos(a), cy + r1 * math.sin(a))], ENGRAVE, (1.5 if long else 1.0) * k)
    ang = {"off": 218, "alert": 228, "printing": 270, "ready": 318}.get(state, 218)
    a = math.radians(ang)
    p.cap_line([(cx - 7 * k * math.cos(a), cy - 7 * k * math.sin(a)), (cx + (R + 5 * k) * math.cos(a), cy + (R + 5 * k) * math.sin(a))], RED, 2.2 * k)
    p.circle(cx, cy, 6 * k, fill=ENGRAVE)
    p.circle(cx - 1.5 * k, cy - 1.5 * k, 2 * k, fill=(120, 122, 123, 255))
    f = font(BC_B, 9 * k)
    p.text((x0 + 10 * k, y0 + 12 * k), "OFF", f, (176, 26, 32, 255), "lm", 1.0 * k)
    p.text((x1 - 10 * k, y0 + 12 * k), "READY", f, ENGRAVE, "rm", 1.0 * k)
    p.text((cx, y1 - 8.5 * k), "PRINTER", font(BC_B, 8.5 * k), ENGRAVE, "mm", 2.4 * k)
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


def _classic(w, h, st):
    g = geometry("classic", w, h)
    k = g["k"]
    p = Pen(w, h)
    p.img.paste(_leather(w * SS, h * SS, k), (0, 0))
    p.d = ImageDraw.Draw(p.img, "RGBA")

    # ---------------- top plate
    plate = g["plate"]
    p.shadows([((0, plate[3] - 6 * k, w, plate[3]), 0, 4 * k, 4 * k, 0.7)])
    _metal(p, plate, CHROME)
    p.rect((0, 0, w, 1.2 * k), fill=(255, 255, 255, 255))
    p.rect((0, plate[3] - 2 * k, w, plate[3]), fill=(74, 75, 76, 255))
    p.rect((0, plate[3] - 3.2 * k, w, plate[3] - 2 * k), fill=(236, 236, 234, 255))
    for sx, ang in ((7 * k, 35), (w - 7 * k, -20)):
        _screw(p, sx, 9 * k, 3.4 * k, ang)
        _screw(p, sx, plate[3] - 11 * k, 3.4 * k, ang + 70)
    pc = plate[3] / 2

    # rewind knob with its fold-out crank
    kx = 16 * k + 31 * k
    ir = _knob(p, kx, pc, 29 * k, k)
    a = math.radians(-28)
    p.cap_line([(kx - ir * 0.78 * math.cos(a), pc - ir * 0.78 * math.sin(a)), (kx + ir * 0.78 * math.cos(a), pc + ir * 0.78 * math.sin(a))], (95, 97, 98, 255), 8.5 * k)
    p.cap_line([(kx - ir * 0.78 * math.cos(a), pc - ir * 0.78 * math.sin(a) - 1 * k), (kx + ir * 0.78 * math.cos(a), pc + ir * 0.78 * math.sin(a) - 1 * k)], (228, 229, 227, 255), 6 * k)
    p.circle(kx + ir * 0.78 * math.cos(a), pc + ir * 0.78 * math.sin(a), 4.6 * k, fill=(70, 71, 72, 255))
    p.circle(kx + ir * 0.78 * math.cos(a) - 0.8 * k, pc + ir * 0.78 * math.sin(a) - 0.8 * k, 3.2 * k, fill=(214, 215, 213, 255))

    # the name, engraved, and the red dot
    bx = kx + 44 * k
    script = font("Yellowtail.ttf", 35 * k)
    p.text((bx, pc - 7 * k + 1 * k), "Snapbox", script, (255, 255, 255, 200), "lm")
    p.text((bx, pc - 7 * k), "Snapbox", script, ENGRAVE, "lm")
    bw = p.text_w("Snapbox", script)
    _engraved(p, (bx + 2 * k, pc + 20 * k), "AUTOMATIC · 35", font(BC_S, 11 * k), "lm", 3.3 * k, k=k)
    p.shadows([((bx + bw + 6 * k, pc - 16 * k, bx + bw + 24 * k, pc + 2 * k), 9 * k, 1.5 * k, 1.2 * k, 0.5)])
    p.paste(_disc(p.s(18 * k), (255, 140, 140), (216, 35, 42), (130, 16, 22)), (bx + bw + 6 * k, pc - 16 * k))

    # accessory shoe
    right_block = w - 16 * k - 58 * k - 16 * k - 64 * k
    sx0 = bx + bw + 40 * k
    if right_block - sx0 > 70 * k:
        scx = (sx0 + right_block) / 2
        sw = min(104 * k, right_block - sx0 - 16 * k)
        shoe = (scx - sw / 2, pc - 13 * k, scx + sw / 2, pc + 13 * k)
        p.rrect((shoe[0] - 1 * k, shoe[1] - 1 * k, shoe[2] + 1 * k, shoe[3] + 1 * k), 2.5 * k, fill=(96, 98, 99, 255))
        _metal(p, shoe, [(0, (150, 152, 153)), (0.45, (232, 232, 230)), (1, (160, 162, 162))], 2 * k)
        for yy in (shoe[1] + 3 * k, shoe[3] - 7 * k):
            p.rrect((shoe[0] + 5 * k, yy, shoe[2] - 5 * k, yy + 4 * k), 1 * k, fill=(74, 76, 78, 255))
            p.rect((shoe[0] + 5 * k, yy + 3.2 * k, shoe[2] - 5 * k, yy + 4 * k), fill=(240, 240, 238, 255))
        p.circle(scx, pc, 3 * k, fill=(60, 61, 62, 255))
        p.circle(scx - 0.6 * k, pc - 0.6 * k, 1.8 * k, fill=(200, 201, 200, 255))

    # exposure counter: which photo is next
    ecx = w - 16 * k - 58 * k - 22 * k - 31 * k
    gr = _window(p, ecx, pc - 6 * k, 29 * k, k)
    ey = pc - 6 * k
    cur = st["count"]
    numf, sidef = font(BC_B, 31 * k), font(BC_S, 15 * k)
    cream = (244, 242, 234, 255)
    p.text((ecx, ey + 1 * k), str(cur), numf, cream, "mm")
    if cur - 1 >= 1:
        p.text((ecx - 17 * k, ey + 2 * k), str(cur - 1), sidef, (140, 139, 134, 255), "mm")
    if cur + 1 <= st["count_of"]:
        p.text((ecx + 17 * k, ey + 2 * k), str(cur + 1), sidef, (140, 139, 134, 255), "mm")
    p.poly([(ecx - 5 * k, ey - gr), (ecx + 5 * k, ey - gr), (ecx, ey - gr + 8 * k)], fill=(224, 42, 49, 255))
    p.arc((ecx - gr + 3 * k, ey - gr + 3 * k, ecx + gr - 3 * k, ey + gr - 3 * k), 200, 250, (255, 255, 255, 60), 2 * k)
    _engraved(p, (ecx, plate[3] - 11 * k), f"{st['count_label']} · OF {st['count_of']}", font(BC_B, 9.5 * k), "mm", 1.9 * k, k=k)

    # format dial
    fcx = w - 16 * k - 31 * k
    ir = _knob(p, fcx, pc - 6 * k, 29 * k, k)
    lay = st["layout"]
    top, bottom = ("STRIP", "SHEET") if lay == "strip" else ("SHEET", "STRIP")
    p.text((fcx, pc - 10 * k), top, font(BC_B, 12.5 * k), (190, 26, 33, 255), "mm", 0.9 * k)
    p.text((fcx, pc + 2 * k), bottom, font(BC_S, 9.5 * k), (70, 71, 72, 255), "mm", 0.7 * k)
    p.rrect((fcx - 29 * k - 9 * k, pc - 8.5 * k, fcx - 29 * k - 1 * k, pc - 3.5 * k), 1 * k, fill=RED)
    _engraved(p, (fcx, plate[3] - 11 * k), "FORMAT", font(BC_B, 9.5 * k), "mm", 2.2 * k, k=k)

    # ---------------- viewfinder
    vf = g["viewfinder"]
    p.shadows([(vf, 8 * k, 6 * k, 4 * k, 0.75)])
    _metal(p, vf, [(0, (246, 246, 244)), (0.5, (150, 152, 153)), (1, (220, 221, 219))], 8 * k)
    p.rrect((vf[0] + 1 * k, vf[1] + 1 * k, vf[2] - 1 * k, vf[3] - 1 * k), 7.5 * k, outline=(255, 255, 255, 150), width=1 * k)
    inner = (vf[0] + 4 * k, vf[1] + 4 * k, vf[2] - 4 * k, vf[3] - 4 * k)
    p.rrect(inner, 5 * k, fill=(40, 41, 42, 255))
    p.rrect(g["stage"], 4 * k, fill=STAGE_BG["classic"] + (255,))

    # ---------------- the four keys
    kinds = st["kinds"]
    names = {"menu": "MENU", "gallery": "ROLL", "fx": "EFFECTS", "layout": "FORMAT", "camera": "CAMERA"}
    for i, kind in enumerate(kinds):
        r = g["rail"][i]
        cx, cy, rad = (r[0] + r[2]) / 2, (r[1] + r[3]) / 2, (r[2] - r[0]) / 2
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
            _jewel(p, r[2] + 2 * k, r[1] + 1 * k, 5.5 * k, lit=st["effects_on"])
        p.text((cx, r[3] + 13 * k), names[kind], font(BC_S, 11.5 * k), (228, 228, 225, 255), "mm", 2.6 * k)

    # ---------------- printer gauge
    if st["printer"] is not None:
        _gauge(p, g["printer"], k, st["printer"])

    # ---------------- along the bottom: label tape, the design's name plate, the date wheels
    _tape(p, g["tape"], st["tape"], k)
    name = g["plate_name"]
    p.shadows([(name, 4 * k, 3 * k, 2.5 * k, 0.6)])
    _metal(p, name, [(0, (242, 242, 240)), (0.6, (185, 187, 187)), (1, (215, 216, 214))], 4 * k)
    p.rrect(name, 4 * k, outline=(110, 112, 113, 255), width=0.8 * k)
    ny = (name[1] + name[3]) / 2
    for bx_, sgn in ((name[0] + 20 * k, -1), (name[2] - 20 * k, 1)):
        p.poly([(bx_ + sgn * 6 * k, ny + 1 * k), (bx_ - sgn * 5 * k, ny - 6 * k), (bx_ - sgn * 5 * k, ny + 8 * k)], fill=(255, 255, 255, 190))
        p.poly([(bx_ + sgn * 6 * k, ny), (bx_ - sgn * 5 * k, ny - 7 * k), (bx_ - sgn * 5 * k, ny + 7 * k)], fill=ENGRAVE)
    for vx in (name[0] + 40 * k, name[2] - 40 * k):
        p.line([(vx, name[1] + 6 * k), (vx, name[3] - 6 * k)], (120, 122, 123, 255), 0.8 * k)
        p.line([(vx + 0.9 * k, name[1] + 6 * k), (vx + 0.9 * k, name[3] - 6 * k)], (250, 250, 248, 255), 0.8 * k)
    label = st["plate_text"]
    _engraved(p, ((name[0] + name[2]) / 2, ny), label, p.fit(label, BC_B, 14.5 * k, name[2] - name[0] - 96 * k, spacing=2.4 * k), "mm", 2.4 * k, k=k)

    dt = g["date"]
    p.shadows([(dt, 4 * k, 3 * k, 2.5 * k, 0.6)])
    _metal(p, dt, [(0, (242, 242, 240)), (1, (142, 144, 145))], 4 * k)
    cw = (dt[2] - dt[0] - 8 * k - 6 * k) / 3
    for i, part in enumerate(st["date"]):
        wx = dt[0] + 4 * k + i * (cw + 3 * k)
        win = (wx, dt[1] + 4 * k, wx + cw, dt[3] - 4 * k)
        p.rrect(win, 2 * k, fill=(14, 14, 14, 255))
        p.text(((win[0] + win[2]) / 2, (win[1] + win[3]) / 2), part, font(BC_S, 19 * k), (244, 242, 234, 255), "mm")
        p.rect((win[0], win[1], win[2], win[1] + 2.5 * k), fill=(0, 0, 0, 150))
        p.rect((win[0], win[3] - 2.5 * k, win[2], win[3]), fill=(0, 0, 0, 120))

    # ---------------- the strip shows through the viewfinder, with a soft dark edge like glass
    stage = g["stage"]
    p.hole(stage, 4 * k)
    x0, y0, x1, y1 = p.b(stage)
    sw_, sh_ = x1 - x0, y1 - y0
    edge = Image.new("L", (sw_, sh_), 150)
    m = p.s(7 * k)
    ImageDraw.Draw(edge).rounded_rectangle((m, m, sw_ - m, sh_ - m), radius=p.s(4 * k), fill=0)
    edge = edge.filter(ImageFilter.GaussianBlur(4 * k * SS))
    clip = Image.new("L", (sw_, sh_), 0)
    ImageDraw.Draw(clip).rounded_rectangle((0, 0, sw_ - 1, sh_ - 1), radius=p.s(4 * k), fill=255)
    patch = Image.new("RGBA", (sw_, sh_), (0, 0, 0, 255))
    patch.putalpha(Image.composite(edge, Image.new("L", (sw_, sh_), 0), clip))
    p.img.paste(patch, (x0, y0), patch)
    return p.done(), g


def render_main(look, w, h, st):
    """(RGBA picture of everything around the strip, geometry). See photobooth.py for `st`."""
    return (_modern if look == "modern" else _classic)(w, h, st)


# --------------------------------------------------------------------------------- countdown

def render_countdown(look, w, h, value, count, count_of, frac=1.0):
    """What goes over the full-screen camera while it counts down (RGBA)."""
    k = h / 480.0
    p = Pen(w, h)
    cx, cy = w / 2, h / 2
    if look == "modern":
        for box in ((14 * k, 14 * k, 60 * k, 60 * k, 0), (w - 60 * k, 14 * k, w - 14 * k, 60 * k, 1),
                    (w - 60 * k, h - 60 * k, w - 14 * k, h - 14 * k, 2), (14 * k, h - 60 * k, 60 * k, h - 14 * k, 3)):
            x0, y0, x1, y1, q = box
            pts = [[(x0, y1), (x0, y0), (x1, y0)], [(x0, y0), (x1, y0), (x1, y1)],
                   [(x1, y0), (x1, y1), (x0, y1)], [(x1, y1), (x0, y1), (x0, y0)]][q]
            p.cap_line(pts, (255, 255, 255, 235), 3 * k)
        # photo n of N
        f = font(PJS, 15 * k, 800)
        label = f"Photo {count} of {count_of}"
        pw = p.text_w(label, f) + 58 * k
        pill = (28 * k, 28 * k, 28 * k + pw, 72 * k)
        p.shadows([(pill, 22 * k, 8 * k, 4 * k, 0.35)])
        p.rrect(pill, 22 * k, fill=WHITE)
        p.circle(pill[0] + 22 * k, 50 * k, 15 * k, fill=BLUE)
        p.text((pill[0] + 22 * k, 50 * k), str(count), font(PJS, 15 * k, 800), WHITE, "mm")
        p.text((pill[0] + 46 * k, 50 * k), label, f, INK, "lm")
        # progress, top right
        sw, gap = 26 * k, 6 * k
        x = w - 28 * k - count_of * sw - (count_of - 1) * gap
        back = (x - 10 * k, 36 * k, w - 18 * k, 64 * k)
        p.rrect(back, 14 * k, fill=(13, 16, 23, 185))
        for i in range(count_of):
            col = WHITE if i < count - 1 else (91, 134, 255, 255) if i == count - 1 else (120, 128, 142, 255)
            p.rrect((x + i * (sw + gap), 46 * k, x + i * (sw + gap) + sw, 54 * k), 4 * k, fill=col)
        # the number in its ring
        R = 96 * k
        p.circle(cx, cy - 6 * k, R, fill=(13, 16, 23, 170))
        ring = (cx - R, cy - 6 * k - R, cx + R, cy - 6 * k + R)
        p.arc(ring, 0, 360, (255, 255, 255, 70), 10 * k)
        p.arc(ring, -90, -90 + 360 * max(0.02, min(1.0, frac)), WHITE, 10 * k)
        p.text((cx, cy - 10 * k), str(value), font(PJS, 132 * k, 800), WHITE, "mm")
        msg = "Look up at the camera"
        f = font(PJS, 18 * k, 800)
        mw = p.text_w(msg, f) + 76 * k
        pill = (cx - mw / 2, h - 86 * k, cx + mw / 2, h - 34 * k)
        p.shadows([(pill, 26 * k, 10 * k, 6 * k, 0.4)])
        p.rrect(pill, 26 * k, fill=WHITE)
        ax = pill[0] + 30 * k
        ay = (pill[1] + pill[3]) / 2
        p.cap_line([(ax, ay + 9 * k), (ax, ay - 9 * k)], BLUE, 2.8 * k)
        p.cap_line([(ax - 7 * k, ay - 2 * k), (ax, ay - 9 * k), (ax + 7 * k, ay - 2 * k)], BLUE, 2.8 * k)
        p.text((pill[0] + 50 * k, ay), msg, f, INK, "lm")
    else:
        # the dark corners of a viewfinder
        q = 8  # built small and stretched: it is only a soft shadow
        vw, vh = max(2, p.img.width // q), max(2, p.img.height // q)
        vig = Image.new("L", (vw, vh), 175)
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
                battery=None, title="Design 11", chip="2x6 strip · 4 photos", design=11, designs=37,
                switch_text="11 of 37 · swipe to change", count_label="PHOTO", count=2, count_of=4,
                count_side="2 left", segments=["done", "now", "todo", "todo"], printer="ready",
                printer_title="Printer ready", printer_sub="Nothing waiting", phone=True,
                cta=["Press the big button", "for photo 2"], layout="strip", tape="PRESS THE SHUTTER",
                plate_text="No. 11 · STRIP OF 4", date=("11", "14", "26"), strip_rects=[])
    tiles = []
    for look in LOOKS:
        im, g = render_main(look, W, H, base)
        bg = Image.new("RGBA", (W, H), STAGE_BG[look] + (255,))
        bg.alpha_composite(im)
        tiles.append(bg)
        cd = Image.new("RGBA", (W, H), (90, 60, 60, 255))
        cd.alpha_composite(render_countdown(look, W, H, 3, 2, 4, 0.6))
        tiles.append(cd)
    sheet = Image.new("RGB", (W * 2 + 10, H * 2 + 10), "white")
    for i, t in enumerate(tiles):
        sheet.paste(t.convert("RGB"), ((i % 2) * (W + 10), (i // 2) * (H + 10)))
    sheet.save(sys.argv[1] if len(sys.argv) > 1 else "looks.png")
