"""BIG SHEET designs: one 6x4 landscape print (1800x1200 PNG with transparent photo openings +
slot JSON) in frames/sheets/. Reuses the drawing helpers in all_frames.py.
Usage (from the photobooth folder): python3 sheet_frames.py [sheet numbers, default all]
"""
import json, math, os, random, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

import all_frames as af
from all_frames import (font, rgba, bold, star_points, army_star, spaced_text, smooth_noise, camo,
                        OCP_BASE, OCP_LAYERS, ARMY_GOLD, ARMY_BLACK, ARMY_WHITE, palm, hibiscus,
                        monstera, sparkle, flower)

SW, SH = 1800, 1200
CX, CY = SW // 2, SH // 2
OUT = os.path.join("frames", "sheets")
# all_frames' helpers (cut, vgrad, glow_lines, sand_texture...) draw at its W x H; point them at
# the sheet size.
af.W, af.H, af.CX = SW, SH, CX
cut, vgrad, glow_lines, hole_rects = af.cut, af.vgrad, af.glow_lines, af.hole_rects


def grid(cols, rows, x0, y0, x1, y1, gap):
    w = (x1 - x0 - gap * (cols - 1)) // cols
    h = (y1 - y0 - gap * (rows - 1)) // rows
    return [[x0 + c * (w + gap), y0 + r * (h + gap), w, h] for r in range(rows) for c in range(cols)]


def new(colour):
    return Image.new("RGBA", (SW, SH), rgba(colour))


def draw(img):
    return ImageDraw.Draw(img, "RGBA")


def finish(img, slots, **kw):
    img.putalpha(255)  # translucent drawing must not leave see-through spots outside the photos
    cut(img, slots, **kw)
    return img, slots


def noise_texture(base, amount, seed, blur=0.0):
    rnd = np.random.default_rng(seed)
    n = rnd.normal(0, amount, (SH, SW, 1)).astype(np.float32)
    arr = np.clip(np.array(base, np.float32)[None, None, :] + n, 0, 255).astype(np.uint8)
    img = Image.fromarray(arr, "RGB")
    if blur:
        img = img.filter(ImageFilter.GaussianBlur(blur))
    return img.convert("RGBA")


def shadow_box(img, box, offset=(10, 14), blur=14, alpha=120):
    layer = Image.new("RGBA", (SW, SH), (0, 0, 0, 0))
    x0, y0, x1, y1 = box
    ImageDraw.Draw(layer).rectangle((x0 + offset[0], y0 + offset[1], x1 + offset[0], y1 + offset[1]),
                                    fill=(0, 0, 0, alpha))
    img.alpha_composite(layer.filter(ImageFilter.GaussianBlur(blur)))


def glow_text(img, xy, text, f, colour, glow, anchor="mm", blur=14):
    layer = Image.new("RGBA", (SW, SH), (0, 0, 0, 0))
    ImageDraw.Draw(layer).text(xy, text, font=f, fill=rgba(glow), anchor=anchor)
    g = layer.filter(ImageFilter.GaussianBlur(blur))
    img.alpha_composite(g)
    img.alpha_composite(g)
    draw(img).text(xy, text, font=f, fill=rgba(colour), anchor=anchor)


def gradient_text(img, xy, text, f, stops, anchor="mm", stroke=0, stroke_fill=None):
    """Text filled with a vertical gradient (chrome, sunset)."""
    mask = Image.new("L", (SW, SH), 0)
    ImageDraw.Draw(mask).text(xy, text, font=f, fill=255, anchor=anchor)
    box = mask.getbbox()
    if not box:
        return
    if stroke:
        draw(img).text(xy, text, font=f, fill=rgba(stroke_fill), anchor=anchor, stroke_width=stroke,
                       stroke_fill=rgba(stroke_fill))
    g = Image.new("RGBA", (SW, SH), (0, 0, 0, 0))
    gd = ImageDraw.Draw(g)
    y0, y1 = box[1], box[3]
    for y in range(y0, y1 + 1):
        t = (y - y0) / max(1, y1 - y0)
        for (t0, c0), (t1, c1) in zip(stops, stops[1:]):
            if t <= t1:
                k = (t - t0) / max(1e-6, t1 - t0)
                gd.line((box[0], y, box[2], y), fill=tuple(int(a + (b - a) * k) for a, b in zip(c0, c1)) + (255,))
                break
    img.paste(g, (0, 0), mask)


# ---------- 1: Gallery White (4) ----------
def gallery_white():
    slots = grid(2, 2, 70, 60, SW - 70, SH - 150, 40)
    img = new((252, 251, 248))
    d = draw(img)
    for x, y, w, h in slots:
        d.rectangle((x - 14, y - 14, x + w + 13, y + h + 13), outline=rgba((200, 198, 192)), width=2)
    spaced_text(d, (CX, SH - 78), "MEMORIES", font("PoiretOne.ttf", 64), rgba((60, 60, 60)), 24)
    d.line((CX - 520, SH - 78, CX - 260, SH - 78), fill=rgba((150, 150, 150)), width=2)
    d.line((CX + 260, SH - 78, CX + 520, SH - 78), fill=rgba((150, 150, 150)), width=2)
    return finish(img, slots, inset=0, radius=0)


# ---------- 2: Polaroid Cork Board (3) ----------
def polaroid_cork():
    img = noise_texture((176, 132, 88), 22, 2, blur=0.8)
    d = draw(img)
    rnd = random.Random(2)
    for _ in range(2500):  # cork flecks
        x, y, r = rnd.uniform(0, SW), rnd.uniform(0, SH), rnd.uniform(1, 4)
        d.ellipse((x - r, y - r, x + r, y + r), fill=(110, 76, 44, 160) if rnd.random() < 0.6 else (214, 176, 128, 160))
    pw, ph = 500, 375
    slots, captions = [], ["good times", "best friends", "say cheese"]
    for i, (px, py) in enumerate(((95, 330), (650, 270), (1205, 350))):
        frame_box = (px - 30, py - 30, px + pw + 30, py + ph + 150)
        shadow_box(img, frame_box)
        d = draw(img)
        d.rectangle(frame_box, fill=rgba((250, 249, 244)))
        d.text((px + pw / 2, py + ph + 70), captions[i], font=font("GreatVibes.ttf", 64), fill=rgba((40, 40, 70)), anchor="mm")
        tape = (px + pw / 2 - 90, py - 62, px + pw / 2 + 90, py - 6)
        d.rectangle(tape, fill=(240, 232, 200, 190))
        slots.append([px, py, pw, ph])
    return finish(img, slots, inset=0, radius=0)


# ---------- 3: Contact Sheet (3) ----------
def contact_sheet():
    img = new((232, 230, 224))
    d = draw(img)
    band = (0, 330, SW, 900)
    d.rectangle(band, fill=rgba((22, 18, 14)))
    for x in range(30, SW, 92):
        for y in (350, 840):
            d.rounded_rectangle((x, y, x + 50, y + 40), radius=8, fill=rgba((232, 230, 224)))
    slots = grid(3, 1, 70, 440, SW - 70, 790, 40)  # 3:2, like 35 mm frames
    edge = font("VT323.ttf", 40)
    for i, (x, y, w, h) in enumerate(slots):
        d.text((x + 10, 432), f"{14 + i}", font=edge, fill=rgba((255, 170, 40)), anchor="lb")
        d.text((x + w - 10, 432), f"{14 + i}A  ▸", font=edge, fill=rgba((255, 170, 40)), anchor="rb")
        d.text((x + w / 2, 835), "SAFETY FILM 400", font=edge, fill=rgba((255, 170, 40)), anchor="mb")
    d.text((CX, 140), "CONTACT SHEET", font=font("PoiretOne.ttf", 70), fill=rgba((40, 40, 40)), anchor="mm")
    d.text((90, 1080), "ROLL 26  ·  FRAMES 14-16", font=font("VT323.ttf", 44), fill=rgba((90, 90, 90)), anchor="lm")
    for k, (x, y, w, h) in enumerate(slots):  # grease-pencil circle on the keeper
        if k == 1:
            d.ellipse((x - 28, y - 30, x + w + 28, y + h + 30), outline=(220, 40, 40, 230), width=7)
    return finish(img, slots, inset=0, radius=0)


# ---------- 4: Groovy 70s (2) ----------
def groovy_70s():
    img = new((246, 234, 208))
    d = draw(img)
    colours = [(120, 66, 30), (206, 92, 32), (236, 150, 40), (240, 196, 80)]
    for cx, cy in ((0, SH), (SW, 0)):
        for k, c in enumerate(colours):
            r = 520 - k * 90
            d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=rgba(c))
        d.ellipse((cx - 160, cy - 160, cx + 160, cy + 160), fill=rgba((246, 234, 208)))
    slots = grid(2, 1, 120, 200, SW - 120, 760, 70)
    for x, y, w, h in slots:
        d.rounded_rectangle((x - 18, y - 18, x + w + 17, y + h + 17), radius=60, fill=rgba((120, 66, 30)))
    d.text((CX, 930), "GROOVY", font=font("Limelight.ttf", 120), fill=rgba((206, 92, 32)), anchor="mm",
           stroke_width=6, stroke_fill=rgba((120, 66, 30)))
    return finish(img, slots, inset=0, radius=46)


# ---------- 5: Vintage Postcard (2) ----------
def vintage_postcard():
    img = noise_texture((240, 228, 200), 6, 5)
    d = draw(img)
    d.rectangle((24, 24, SW - 25, SH - 25), outline=rgba((170, 60, 50)), width=6)
    d.text((140, 120), "Greetings from", font=font("GreatVibes.ttf", 110), fill=rgba((30, 60, 110)), anchor="lm")
    gradient_text(img, (800, 250), "HAWAII", font("Limelight.ttf", 200),
                  [(0, (255, 200, 60)), (0.5, (230, 90, 50)), (1, (170, 40, 70))], stroke=10, stroke_fill=(30, 60, 110))
    d = draw(img)
    sx, sy = SW - 260, 70  # stamp with a perforated edge and a postmark
    d.rectangle((sx, sy, sx + 180, sy + 220), fill=rgba((255, 255, 255)))
    for t in range(0, 181, 18):
        for yy in (sy, sy + 220):
            d.ellipse((sx + t - 6, yy - 6, sx + t + 6, yy + 6), fill=rgba((240, 228, 200)))
    for t in range(0, 221, 18):
        for xx in (sx, sx + 180):
            d.ellipse((xx - 6, sy + t - 6, xx + 6, sy + t + 6), fill=rgba((240, 228, 200)))
    d.rectangle((sx + 18, sy + 18, sx + 162, sy + 202), fill=rgba((60, 150, 170)))
    hibiscus(d, sx + 90, sy + 100, 50, rgba((240, 70, 90)), rgba((150, 20, 50)))
    d.ellipse((sx - 140, sy + 120, sx + 40, sy + 300), outline=(40, 40, 40, 150), width=5)
    for k in range(4):
        y = sy + 160 + k * 26
        d.arc((sx - 20 + k * 3, y - 20, sx + 260, y + 20), 200, 340, fill=(40, 40, 40, 140), width=4)
    slots = grid(2, 1, 110, 400, SW - 110, 975, 60)
    d.text((SW - 140, 1080), "Wish you were here!", font=font("GreatVibes.ttf", 80), fill=rgba((30, 60, 110)),
           anchor="rm")
    for x, y, w, h in slots:
        shadow_box(img, (x - 14, y - 14, x + w + 13, y + h + 13), blur=10, alpha=90)
        draw(img).rectangle((x - 14, y - 14, x + w + 13, y + h + 13), fill=rgba((255, 255, 255)))
    return finish(img, slots, inset=0, radius=0)


# ---------- 6: Neon Night (4) ----------
def neon_night():
    img = new((14, 12, 26))
    d = draw(img)
    for y in range(0, SH, 60):  # dark brick wall
        off = 60 if (y // 60) % 2 else 0
        for x in range(-off, SW, 120):
            d.rectangle((x + 3, y + 3, x + 117, y + 57), fill=rgba((24, 20, 40)))
    slots = grid(2, 2, 80, 200, SW - 80, SH - 60, 50)
    for k, rect in enumerate(hole_rects(slots, pad=14, inset=0)):
        glow_lines(img, [rect], (255, 60, 200) if k in (0, 3) else (60, 230, 255), radius=20, width=5, blur=14)
    glow_text(img, (CX, 105), "Good Times", font("Pacifico.ttf", 120), (255, 230, 250), (255, 60, 200))
    return finish(img, slots, inset=0, radius=16)


# ---------- 7: Magazine Cover (1) ----------
def magazine_cover():
    slots = [[0, 0, SW, SH]]
    img = new((255, 255, 255))
    img, slots = finish(img, slots, inset=0, radius=0)
    d = draw(img)
    shade = Image.new("RGBA", (SW, SH), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shade)
    for y in range(260):  # darken the top so the masthead reads on any photo
        sd.line((0, y, SW, y), fill=(0, 0, 0, int(150 * (1 - y / 260))))
    for x in range(520):
        sd.line((x, 0, x, SH), fill=(0, 0, 0, int(90 * (1 - x / 520))))
    img.alpha_composite(shade)
    d = draw(img)
    d.text((60, 30), "SNAP", font=bold("Oswald.ttf", 230, 700), fill=rgba((235, 30, 60)), anchor="lt")
    d.text((640, 70), "THE PHOTO BOOTH ISSUE", font=bold("Oswald.ttf", 44, 500), fill=rgba((255, 255, 255)), anchor="lt")
    d.text((640, 128), "OCTOBER EDITION  ·  $0.00", font=bold("Oswald.ttf", 34, 400), fill=rgba((255, 255, 255)), anchor="lt")
    lines = [("EXCLUSIVE", "Inside the most", "fun night ever"), ("STYLE", "Who wore it", "best? (You.)"),
             ("10 WAYS", "to strike the", "perfect pose")]
    y = 420
    for head, a, b in lines:
        d.text((60, y), head, font=bold("Oswald.ttf", 60, 700), fill=rgba((255, 210, 40)), anchor="lt",
               stroke_width=3, stroke_fill=(0, 0, 0, 160))
        d.text((60, y + 72), a, font=bold("Oswald.ttf", 40, 400), fill=rgba((255, 255, 255)), anchor="lt",
               stroke_width=2, stroke_fill=(0, 0, 0, 160))
        d.text((60, y + 118), b, font=bold("Oswald.ttf", 40, 400), fill=rgba((255, 255, 255)), anchor="lt",
               stroke_width=2, stroke_fill=(0, 0, 0, 160))
        y += 230
    bx, by = SW - 300, SH - 170  # barcode
    d.rectangle((bx - 20, by - 20, bx + 240, by + 130), fill=rgba((255, 255, 255)))
    rnd = random.Random(7)
    x = bx
    while x < bx + 220:
        w = rnd.choice([2, 3, 5])
        d.rectangle((x, by, x + w, by + 90), fill=rgba((0, 0, 0)))
        x += w + rnd.choice([2, 3, 4])
    d.text((bx + 110, by + 110), "0 26100 00001 8", font=font("VT323.ttf", 28), fill=rgba((0, 0, 0)), anchor="mm")
    return img, slots


# ---------- 8: Comic Book (3) ----------
def burst(d, cx, cy, r, points, fill, outline):
    pts = []
    for i in range(points * 2):
        a = math.pi * i / points
        rr = r if i % 2 == 0 else r * 0.62
        pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
    d.polygon(pts, fill=fill, outline=outline)
    d.line(pts + [pts[0]], fill=outline, width=8)


def comic_book():
    img = new((255, 214, 40))
    d = draw(img)
    for y in range(0, SH, 26):  # halftone dots
        for x in range(0, SW, 26):
            r = 5 + 4 * math.sin(x / 140) * math.cos(y / 160)
            d.ellipse((x - r, y - r, x + r, y + r), fill=rgba((240, 150, 20)))
    slots = [[50, 50, 1060, 760], [1150, 50, SW - 1200, 355], [1150, 455, SW - 1200, 355]]
    for x, y, w, h in slots:
        d.rectangle((x - 12, y - 12, x + w + 11, y + h + 11), fill=rgba((0, 0, 0)))
    img, slots = finish(img, slots, inset=0, radius=0)
    d = draw(img)
    cap = (50, 870, 1100, 1150)  # narration box
    d.rectangle(cap, fill=rgba((255, 248, 200)), outline=rgba((0, 0, 0)), width=8)
    d.text((80, 940), "MEANWHILE, AT THE", font=bold("Oswald.ttf", 64, 700), fill=rgba((0, 0, 0)), anchor="lm")
    d.text((80, 1040), "PHOTO BOOTH...", font=bold("Oswald.ttf", 96, 700), fill=rgba((0, 0, 0)), anchor="lm")
    burst(d, 1080, 110, 120, 12, rgba((255, 60, 40)), rgba((0, 0, 0)))
    d.text((1080, 110), "POW!", font=font("Limelight.ttf", 68), fill=rgba((255, 240, 60)), anchor="mm",
           stroke_width=4, stroke_fill=rgba((0, 0, 0)))
    bx, by = 1220, 900  # speech bubble
    d.ellipse((bx, by, bx + 420, by + 170), fill=rgba((255, 255, 255)), outline=rgba((0, 0, 0)), width=7)
    d.polygon([(bx + 90, by + 150), (bx + 40, by + 230), (bx + 160, by + 160)], fill=rgba((255, 255, 255)))
    d.line([(bx + 90, by + 152), (bx + 40, by + 230), (bx + 160, by + 162)], fill=rgba((0, 0, 0)), width=7)
    d.text((bx + 210, by + 85), "SMILE!", font=bold("Oswald.ttf", 72, 700), fill=rgba((0, 0, 0)), anchor="mm")
    return img, slots


# ---------- 9: Y2K Chrome (4) ----------
def y2k_chrome():
    img = Image.new("RGBA", (SW, SH))
    arr = np.zeros((SH, SW, 3), np.float32)
    ys, xs = np.mgrid[0:SH, 0:SW].astype(np.float32)
    t = (xs / SW + ys / SH) / 2
    arr[..., 0] = 230 + 25 * np.sin(t * 6.0)
    arr[..., 1] = 190 + 40 * np.sin(t * 6.0 + 2.0)
    arr[..., 2] = 240 + 15 * np.sin(t * 6.0 + 4.0)
    img = Image.fromarray(arr.clip(0, 255).astype(np.uint8), "RGB").convert("RGBA")
    d = draw(img)
    rnd = random.Random(9)
    for _ in range(60):
        sparkle(d, rnd.uniform(0, SW), rnd.uniform(0, SH), rnd.uniform(8, 26), (255, 255, 255, 230))
    slots = grid(2, 2, 90, 230, SW - 90, SH - 70, 50)
    glow_lines(img, hole_rects(slots, pad=12, inset=0), (255, 255, 255), radius=40, width=6, blur=12)
    gradient_text(img, (CX, 115), "BESTIES", bold("Oswald.ttf", 160, 700),
                  [(0, (255, 255, 255)), (0.45, (170, 180, 210)), (0.55, (90, 100, 140)), (1, (230, 235, 255))],
                  stroke=8, stroke_fill=(120, 80, 200))
    return finish(img, slots, inset=0, radius=34)


# ---------- 10: Minimal Modern (3) ----------
def minimal_modern():
    img = new((244, 242, 238))
    d = draw(img)
    slots = [[80, 170, 1080, 800 - 0]]
    slots[0][3] = SH - 230 - 170
    slots += grid(1, 2, 1196, 170, SW - 80, SH - 230, 36)
    d.line((80, 110, SW - 80, 110), fill=rgba((30, 30, 30)), width=3)
    d.line((80, SH - 150, SW - 80, SH - 150), fill=rgba((30, 30, 30)), width=3)
    spaced_text(d, (330, SH - 92), "MOMENTS", bold("Oswald.ttf", 56, 400), rgba((30, 30, 30)), 18)
    d.text((SW - 80, SH - 92), "No. 01", font=bold("Oswald.ttf", 44, 300), fill=rgba((30, 30, 30)), anchor="rm")
    d.text((80, 70), "PHOTO BOOTH", font=bold("Oswald.ttf", 36, 400), fill=rgba((30, 30, 30)), anchor="lm")
    d.text((SW - 80, 70), "—  SERIES A", font=bold("Oswald.ttf", 36, 300), fill=rgba((30, 30, 30)), anchor="rm")
    return finish(img, slots, inset=0, radius=0)


# ---------- 11: Photo Album (4) ----------
def photo_album():
    img = noise_texture((34, 64, 46), 8, 11)
    d = draw(img)
    slots = grid(2, 2, 110, 90, SW - 110, SH - 170, 70)
    for x, y, w, h in slots:
        shadow_box(img, (x, y, x + w, y + h), offset=(6, 8), blur=8, alpha=140)
    d = draw(img)
    img, slots = finish(img, slots, inset=0, radius=0)
    d = draw(img)
    s = 60
    for x, y, w, h in slots:  # black photo corners
        for cx, cy, sx, sy in ((x, y, 1, 1), (x + w, y, -1, 1), (x, y + h, 1, -1), (x + w, y + h, -1, -1)):
            d.polygon([(cx - sx * 8, cy - sy * 8), (cx + sx * s, cy - sy * 8), (cx - sx * 8, cy + sy * s)],
                      fill=rgba((16, 16, 16)))
    d.text((CX, SH - 85), "our favorite day", font=font("GreatVibes.ttf", 90), fill=rgba((240, 236, 220)), anchor="mm")
    return img, slots


# ---------- 12: Retro TVs (2) ----------
def retro_tvs():
    img = new((120, 78, 44))
    d = draw(img)
    for x in range(0, SW, 90):  # wood panelling
        d.rectangle((x, 0, x + 86, SH), fill=rgba((138 + (x // 90 % 3) * 8, 90, 52)))
        d.line((x + 88, 0, x + 88, SH), fill=rgba((80, 50, 26)), width=4)
    d.rectangle((0, SH - 150, SW, SH), fill=rgba((70, 44, 24)))  # the shelf
    slots = []
    for i, tx in enumerate((110, 950)):
        body = (tx, 170, tx + 740, 960)
        shadow_box(img, body)
        d = draw(img)
        d.rounded_rectangle(body, radius=50, fill=rgba((214, 196, 160)), outline=rgba((120, 100, 70)), width=6)
        scr = [tx + 50, 230, 520, 420]
        d.rounded_rectangle((scr[0] - 18, scr[1] - 18, scr[0] + scr[2] + 18, scr[1] + scr[3] + 18), radius=46,
                            fill=rgba((40, 36, 32)))
        for k in range(2):  # knobs
            kx, ky = tx + 650, 330 + k * 150
            d.ellipse((kx - 40, ky - 40, kx + 40, ky + 40), fill=rgba((80, 64, 44)), outline=rgba((40, 30, 20)), width=4)
            d.line((kx, ky, kx + 26, ky - 26), fill=rgba((230, 220, 200)), width=6)
        for k in range(5):
            d.line((tx + 610, 620 + k * 26, tx + 700, 620 + k * 26), fill=rgba((120, 100, 70)), width=6)
        d.line((tx + 370, 170, tx + 250, 40), fill=rgba((60, 60, 60)), width=8)  # antennas
        d.line((tx + 370, 170, tx + 500, 50), fill=rgba((60, 60, 60)), width=8)
        d.ellipse((tx + 330, 140, tx + 410, 200), fill=rgba((60, 60, 60)))
        d.text((tx + 290, 905), f"CHANNEL {i + 1}", font=font("VT323.ttf", 60), fill=rgba((90, 70, 40)), anchor="mm")
        for lx in (tx + 120, tx + 620):  # legs
            d.line((lx, 960, lx + (-30 if lx < tx + 370 else 30), 1060), fill=rgba((60, 40, 20)), width=14)
        slots.append(scr)
    return finish(img, slots, inset=0, radius=40)


# ---------- 13: Arcade (4) ----------
def arcade():
    img = new((8, 6, 20))
    d = draw(img)
    px = 20
    colours = [(255, 50, 120), (60, 220, 255), (255, 220, 40), (120, 255, 90)]
    for i, x in enumerate(range(0, SW, px)):  # pixel border
        for y in (0, px, SH - 2 * px, SH - px):
            if (i + y // px) % 3 == 0:
                d.rectangle((x, y, x + px - 2, y + px - 2), fill=rgba(colours[i % 4]))
    for j, y in enumerate(range(0, SH, px)):
        for x in (0, px, SW - 2 * px, SW - px):
            if (j + x // px) % 3 == 0:
                d.rectangle((x, y, x + px - 2, y + px - 2), fill=rgba(colours[j % 4]))
    slots = grid(2, 2, 90, 200, SW - 90, SH - 80, 40)
    f = font("VT323.ttf", 80)
    d.text((100, 110), "1UP  PLAYER 1", font=f, fill=rgba((255, 50, 120)), anchor="lm")
    d.text((SW - 100, 110), "HIGH SCORE 999990", font=f, fill=rgba((60, 220, 255)), anchor="rm")
    heart = ["01100110", "11111111", "11111111", "01111110", "00111100", "00011000"]
    for k, hx in enumerate((CX - 110, CX - 30, CX + 50)):
        for r, row in enumerate(heart):
            for c, bit in enumerate(row):
                if bit == "1":
                    d.rectangle((hx + c * 9, 85 + r * 9, hx + c * 9 + 8, 85 + r * 9 + 8), fill=rgba((255, 50, 80)))
    for x, y, w, h in slots:
        d.rectangle((x - 10, y - 10, x + w + 9, y + h + 9), outline=rgba((255, 255, 255)), width=6)
    return finish(img, slots, inset=0, radius=0)


# ---------- 14: Flower Power (2) ----------
def daisy(d, cx, cy, r, petal, centre):
    for k in range(12):
        a = 2 * math.pi * k / 12
        af.leaf(d, cx + r * 0.55 * math.cos(a), cy + r * 0.55 * math.sin(a), r * 0.9, r * 0.36, math.degrees(a), petal)
    d.ellipse((cx - r * 0.3, cy - r * 0.3, cx + r * 0.3, cy + r * 0.3), fill=centre)


def flower_power():
    img = new((176, 228, 206))
    d = draw(img)
    rnd = random.Random(14)
    petals = [(255, 255, 255), (255, 120, 170), (255, 200, 60), (255, 140, 60), (170, 120, 255)]
    for _ in range(46):
        x, y = rnd.uniform(-40, SW + 40), rnd.uniform(-40, SH + 40)
        daisy(d, x, y, rnd.uniform(50, 120), rgba(rnd.choice(petals)), rgba((255, 160, 40)))
    slots = grid(2, 1, 130, 190, SW - 130, 740, 80)
    for x, y, w, h in slots:
        d.rounded_rectangle((x - 22, y - 22, x + w + 21, y + h + 21), radius=50, fill=rgba((255, 255, 255)))
    d.text((CX, 930), "Peace & Love", font=font("Pacifico.ttf", 110), fill=rgba((255, 110, 160)), anchor="mm",
           stroke_width=10, stroke_fill=rgba((255, 255, 255)))
    return finish(img, slots, inset=0, radius=36)


# ---------- 15: Army Camo (4) ----------
def army_camo_sheet():
    img = camo(OCP_BASE, OCP_LAYERS, seed=115, size=(SW, SH))
    slots = grid(2, 2, 330, 60, SW - 60, SH - 60, 36)
    d = draw(img)
    shadow_box(img, (40, 40, 290, SH - 40))
    d = draw(img)
    d.rectangle((40, 40, 290, SH - 40), fill=rgba((56, 58, 40)), outline=rgba((30, 30, 20)), width=6)
    army_star(d, 165, 210, 85)
    words = Image.new("RGBA", (800, 200), (0, 0, 0, 0))
    spaced_text(ImageDraw.Draw(words), (400, 100), "U.S. ARMY", bold("Oswald.ttf", 150, 700), rgba((226, 214, 170)), 16)
    words = words.rotate(90, expand=True)
    img.alpha_composite(words, (165 - words.width // 2, 750 - words.height // 2))
    d = draw(img)
    glow_lines(img, hole_rects(slots, pad=10, inset=0), (30, 28, 20), radius=8, width=4, blur=8)
    return finish(img, slots, inset=0, radius=6)


# ---------- 16: Army Black & Gold (3) ----------
def army_gold_sheet():
    img = new(ARMY_BLACK)
    d = draw(img)
    for x in range(-SH, SW, 46):
        d.line((x, SH, x + SH, 0), fill=rgba((38, 38, 38)), width=3)
    d.rectangle((0, 0, 560, SH), fill=rgba((12, 12, 12)))
    d.line((560, 0, 560, SH), fill=rgba(ARMY_GOLD), width=8)
    army_star(d, 280, 330, 170)
    spaced_text(d, (280, 680), "U.S. ARMY", bold("Oswald.ttf", 100, 700), rgba(ARMY_WHITE), 10)
    spaced_text(d, (280, 800), "BE ALL YOU", bold("Oswald.ttf", 62, 600), rgba(ARMY_GOLD), 8)
    spaced_text(d, (280, 880), "CAN BE", bold("Oswald.ttf", 62, 600), rgba(ARMY_GOLD), 8)
    for k in range(5):
        d.polygon(star_points(280 + (k - 2) * 60, 1010, 18), fill=rgba(ARMY_WHITE))
    slots = [[620, 60, SW - 680, 620]]
    slots += grid(2, 1, 620, 720, SW - 60, SH - 60, 40)
    for x, y, w, h in slots:
        d.rectangle((x - 8, y - 8, x + w + 7, y + h + 7), outline=rgba(ARMY_GOLD), width=6)
    return finish(img, slots, inset=0, radius=0)


# ---------- 17: Army Stars & Stripes (2) ----------
def army_flag_sheet():
    NAVY, RED, WHITE = (26, 38, 82), (178, 34, 52), (255, 255, 255)
    img = new(WHITE)
    d = draw(img)
    stripe = SH / 13
    for k in range(0, 13, 2):
        d.rectangle((0, k * stripe, SW, (k + 1) * stripe), fill=rgba(RED))
    d.rectangle((0, 0, SW, 300), fill=rgba(NAVY))
    for row in range(3):
        for col in range(18):
            x, y = 50 + col * 100 + (50 if row % 2 else 0), 60 + row * 90
            if x < SW - 30 and not (CX - 420 < x < CX + 420):
                d.polygon(star_points(x, y, 22), fill=rgba(WHITE))
    army_star(d, CX - 300, 150, 95)
    spaced_text(d, (CX + 120, 150), "U.S. ARMY", bold("Oswald.ttf", 120, 700), rgba(WHITE), 16)
    d.line((0, 300, SW, 300), fill=rgba(ARMY_GOLD), width=8)
    slots = grid(2, 1, 100, 400, SW - 100, 980, 70)
    for x, y, w, h in slots:
        d.rectangle((x - 16, y - 16, x + w + 15, y + h + 15), fill=rgba(NAVY))
        d.rectangle((x - 7, y - 7, x + w + 6, y + h + 6), outline=rgba(ARMY_GOLD), width=4)
    return finish(img, slots, inset=0, radius=0)


# ---------- 18: Aloha (3) ----------
def aloha_sheet():
    img = vgrad((30, 196, 206), (14, 150, 180))
    rnd = random.Random(18)
    greens = [(26, 140, 74, 255), (40, 170, 90, 255), (18, 112, 62, 255)]
    spots = [(0, 0), (SW, 0), (0, SH), (SW, SH), (CX, 0), (CX, SH), (0, CY), (SW, CY)]
    for x, y in spots:
        monstera(img, x + rnd.randint(-30, 30), y + rnd.randint(-30, 30), rnd.randint(170, 240), rnd.randint(0, 359),
                 rnd.choice(greens), (10, 80, 44, 255))
    d = draw(img)
    pinks = [((255, 80, 120), (170, 20, 60)), ((255, 60, 60), (150, 10, 30)), ((255, 200, 60), (210, 90, 30))]
    for x, y in spots + [(300, 0), (1500, SH), (0, 300), (SW, 900)]:
        petal, dark = rnd.choice(pinks)
        hibiscus(d, x, y, rnd.randint(70, 100), rgba(petal), rgba(dark), angle=rnd.randint(0, 72))
    slots = [[110, 210, 960, 720]]
    slots += grid(1, 2, 1120, 210, SW - 110, 930, 40)
    glow_lines(img, hole_rects(slots, pad=12, inset=0), (255, 255, 255), radius=28, width=6, blur=8)
    img, slots = finish(img, slots, inset=0, radius=24)
    d = draw(img)
    d.text((CX, 100), "Aloha!", font=font("Pacifico.ttf", 130), fill=rgba((255, 255, 255)), anchor="mm",
           stroke_width=10, stroke_fill=rgba((214, 40, 90)))
    return img, slots


# ---------- 19: Beach Sunset (2) ----------
def beach_sunset_sheet():
    horizon = SH - 170
    img = Image.new("RGBA", (SW, SH))
    d = draw(img)
    stops = [(0, (34, 26, 84)), (0.4, (130, 50, 130)), (0.7, (230, 90, 100)), (1.0, (255, 196, 110))]
    for y in range(horizon):
        t = y / horizon
        for (t0, c0), (t1, c1) in zip(stops, stops[1:]):
            if t <= t1:
                k = (t - t0) / (t1 - t0)
                d.line((0, y, SW, y), fill=tuple(int(a + (b - a) * k) for a, b in zip(c0, c1)) + (255,))
                break
    glow = Image.new("RGBA", (SW, SH), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse((CX - 300, horizon - 300, CX + 300, horizon + 300), fill=(255, 190, 90, 200))
    img.alpha_composite(glow.filter(ImageFilter.GaussianBlur(60)))
    d = draw(img)
    d.ellipse((CX - 130, horizon - 130, CX + 130, horizon + 130), fill=rgba((255, 236, 170)))
    d.rectangle((0, horizon, SW, SH), fill=rgba((40, 24, 60)))
    for k in range(14):
        y = horizon + 10 + k * 11
        half = 140 * (1 - k / 16)
        d.line((CX - half, y, CX + half, y), fill=(255, 196, 110, int(220 * (1 - k / 16))), width=4)
    dark = rgba((22, 12, 30))
    palm(d, 60, SH, 520, 120, dark, frond_len=240, seed=19)
    palm(d, SW - 60, SH, 480, -120, dark, frond_len=230, seed=20)
    slots = grid(2, 1, 230, 250, SW - 230, 740, 60)
    for x, y, w, h in slots:
        d.rectangle((x - 16, y - 16, x + w + 15, y + h + 15), fill=rgba((255, 248, 236)))
    d.text((CX, 120), "Aloha", font=font("GreatVibes.ttf", 150), fill=rgba((255, 228, 190)), anchor="mm")
    return finish(img, slots, inset=0, radius=0)


# ---------- 20: Cinema Marquee (1) ----------
def cinema_marquee():
    img = new((90, 8, 16))
    d = draw(img)
    for x in range(0, SW, 60):  # velvet curtain folds
        d.rectangle((x, 0, x + 30, SH), fill=rgba((120, 14, 26)))
    glow = Image.new("RGBA", (SW, SH), (0, 0, 0, 0))
    ImageDraw.Draw(glow).rectangle((120, 150, SW - 120, SH - 120), fill=(0, 0, 0, 200))
    img.alpha_composite(glow.filter(ImageFilter.GaussianBlur(30)))
    d = draw(img)
    board = (150, 170, SW - 150, SH - 160)
    d.rectangle(board, fill=rgba((24, 20, 18)), outline=rgba((200, 160, 70)), width=10)
    slots = [[250, 270, SW - 500, SH - 540]]
    d.rectangle((150, 30, SW - 150, 150), fill=rgba((24, 20, 18)), outline=rgba((200, 160, 70)), width=8)
    glow_text(img, (CX, 92), "NOW SHOWING", font("Limelight.ttf", 90), (255, 236, 180), (255, 180, 60))
    d = draw(img)
    d.text((CX, SH - 78), "STARRING  YOU", font=font("Limelight.ttf", 64), fill=rgba((255, 220, 140)), anchor="mm")
    bulbs = Image.new("RGBA", (SW, SH), (0, 0, 0, 0))
    bd = ImageDraw.Draw(bulbs)
    x0, y0, x1, y1 = board
    pts = [(x, y0 + 30) for x in range(x0 + 30, x1 - 20, 70)] + [(x, y1 - 30) for x in range(x0 + 30, x1 - 20, 70)]
    pts += [(x0 + 30, y) for y in range(y0 + 100, y1 - 60, 70)] + [(x1 - 30, y) for y in range(y0 + 100, y1 - 60, 70)]
    d.rectangle((150, SH - 130, SW - 150, SH - 26), fill=rgba((24, 20, 18)), outline=rgba((200, 160, 70)), width=6)
    d.text((CX, SH - 78), "STARRING  YOU", font=font("Limelight.ttf", 64), fill=rgba((255, 220, 140)), anchor="mm")
    for x, y in pts:
        bd.ellipse((x - 26, y - 26, x + 26, y + 26), fill=(255, 200, 90, 160))
    img.alpha_composite(bulbs.filter(ImageFilter.GaussianBlur(12)))
    d = draw(img)
    for x, y in pts:
        d.ellipse((x - 13, y - 13, x + 13, y + 13), fill=rgba((255, 246, 210)))
    return finish(img, slots, inset=0, radius=0)


DESIGNS = [(1, "Gallery White", gallery_white), (2, "Polaroid Cork Board", polaroid_cork),
           (3, "Contact Sheet", contact_sheet), (4, "Groovy 70s", groovy_70s),
           (5, "Vintage Postcard", vintage_postcard), (6, "Neon Night", neon_night),
           (7, "Magazine Cover", magazine_cover), (8, "Comic Book", comic_book),
           (9, "Y2K Chrome", y2k_chrome), (10, "Minimal Modern", minimal_modern),
           (11, "Photo Album", photo_album), (12, "Retro TVs", retro_tvs), (13, "Arcade", arcade),
           (14, "Flower Power", flower_power), (15, "Army Camo", army_camo_sheet),
           (16, "Army Black & Gold", army_gold_sheet), (17, "Army Stars & Stripes", army_flag_sheet),
           (18, "Aloha", aloha_sheet), (19, "Beach Sunset", beach_sunset_sheet),
           (20, "Cinema Marquee", cinema_marquee)]

if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    only = {int(a) for a in sys.argv[1:]}
    for n, label, fn in DESIGNS:
        if only and n not in only:
            continue
        img, slots = fn()
        img.save(os.path.join(OUT, f"sheet{n}.png"))
        with open(os.path.join(OUT, f"sheet{n}.json"), "w") as f:
            json.dump({"slots": slots, "name": label}, f, indent=2)
        print(f"sheet{n}: {label} ({len(slots)} photos)")
