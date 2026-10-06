"""All custom photobooth strip frames.
Generates frame11 (Deco Silver), the Atkinsons wedding set (frame12..frame19), the fun set
(frame20..frame25), the mall booth set (frame26..frame31), the Army set (frame32..frame33, frame38..frame40) and
the Hawaii set (frame34..frame37) (1200x3600 PNG with transparent photo openings + slot JSON).
The date stamp and vintage light effects are add-ons in the app, not frames.
Usage (from the photobooth folder): python3 all_frames.py [frame numbers, default all]
"""
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import json, math, os, random, sys, urllib.request
import numpy as np

NAME = "The   Atkinsons"
OUT = "frames"
W, H = 1200, 3600
CX = W // 2
FONT_URLS = {
    "GreatVibes.ttf": "https://raw.githubusercontent.com/google/fonts/main/ofl/greatvibes/GreatVibes-Regular.ttf",
    "Limelight.ttf": "https://raw.githubusercontent.com/google/fonts/main/ofl/limelight/Limelight-Regular.ttf",
    "PoiretOne.ttf": "https://raw.githubusercontent.com/google/fonts/main/ofl/poiretone/PoiretOne-Regular.ttf",
    "VT323.ttf": "https://raw.githubusercontent.com/google/fonts/main/ofl/vt323/VT323-Regular.ttf",
    "Pacifico.ttf": "https://raw.githubusercontent.com/google/fonts/main/ofl/pacifico/Pacifico-Regular.ttf",
    "Oswald.ttf": "https://raw.githubusercontent.com/google/fonts/main/ofl/oswald/Oswald%5Bwght%5D.ttf",
    "StardosStencil.ttf": "https://raw.githubusercontent.com/google/fonts/main/ofl/stardosstencil/StardosStencil-Bold.ttf",
}
FONT_DIR = os.path.join(OUT, "fonts")

def font(name, size):
    os.makedirs(FONT_DIR, exist_ok=True)
    p = os.path.join(FONT_DIR, name)
    if not os.path.exists(p):
        urllib.request.urlretrieve(FONT_URLS[name], p)
    return ImageFont.truetype(p, size)

def rgba(c, a=255):
    return tuple(c) + (a,)

def layout(top, bottom, gap=36, x0=60, w=1080):
    h = (H - top - bottom - 3 * gap) // 4
    return [[x0, top + i * (h + gap), w, h] for i in range(4)]

def cut(img, slots, inset=6, radius=22, keyline=None, kw=3):
    d = ImageDraw.Draw(img)
    mask = Image.new("L", (W, H), 255)
    md = ImageDraw.Draw(mask)
    for x, y, w, h in slots:
        if keyline:
            d.rounded_rectangle([x+inset-12, y+inset-12, x+w-inset+11, y+h-inset+11],
                                radius=radius+10, outline=rgba(keyline), width=kw)
        md.rounded_rectangle([x+inset, y+inset, x+w-inset-1, y+h-inset-1], radius=radius, fill=0)
    alpha = Image.composite(img.getchannel("A"), Image.new("L", (W, H), 0), mask)
    img.putalpha(alpha)
    return img

def heart(d, cx, cy, s, fill):
    r = s / 2
    d.ellipse([cx - s, cy - r, cx, cy + r], fill=fill)
    d.ellipse([cx, cy - r, cx + s, cy + r], fill=fill)
    d.polygon([(cx - s + 1, cy + r * 0.35), (cx + s - 1, cy + r * 0.35), (cx, cy + s * 1.15)], fill=fill)

def bowtie(d, cx, cy, s, fill, knot=None):
    d.polygon([(cx, cy), (cx - s, cy - s * 0.6), (cx - s, cy + s * 0.6)], fill=fill)
    d.polygon([(cx, cy), (cx + s, cy - s * 0.6), (cx + s, cy + s * 0.6)], fill=fill)
    k = s * 0.28
    d.rounded_rectangle([cx - k, cy - k * 1.2, cx + k, cy + k * 1.2], radius=k * 0.4, fill=knot or fill)

def dress(d, cx, top, s, fill, accent):
    # bodice
    d.polygon([(cx - s*0.32, top), (cx + s*0.32, top), (cx + s*0.22, top + s*0.55), (cx - s*0.22, top + s*0.55)], fill=fill)
    d.ellipse([cx - s*0.36, top - s*0.12, cx - s*0.02, top + s*0.12], fill=fill)
    d.ellipse([cx + s*0.02, top - s*0.12, cx + s*0.36, top + s*0.12], fill=fill)
    # skirt
    d.polygon([(cx - s*0.24, top + s*0.55), (cx + s*0.24, top + s*0.55), (cx + s*0.75, top + s*1.6), (cx - s*0.75, top + s*1.6)], fill=fill)
    d.line([cx - s*0.24, top + s*0.55, cx + s*0.24, top + s*0.55], fill=accent, width=max(2, int(s*0.06)))

def leaf(d, cx, cy, length, width, angle, fill):
    pts = []
    for i in range(24):
        t = 2 * math.pi * i / 24
        x = length / 2 * math.cos(t)
        y = width / 2 * math.sin(t) * (abs(math.cos(t)) ** 0.0) * (1 - 0.35 * abs(math.cos(t)))
        a = math.radians(angle)
        pts.append((cx + x * math.cos(a) - y * math.sin(a), cy + x * math.sin(a) + y * math.cos(a)))
    d.polygon(pts, fill=fill)

def flower(d, cx, cy, r, petal, center):
    for k in range(5):
        a = 2 * math.pi * k / 5 - math.pi / 2
        px, py = cx + r * 0.75 * math.cos(a), cy + r * 0.75 * math.sin(a)
        d.ellipse([px - r * 0.55, py - r * 0.55, px + r * 0.55, py + r * 0.55], fill=petal)
    d.ellipse([cx - r * 0.3, cy - r * 0.3, cx + r * 0.3, cy + r * 0.3], fill=center)

def sparkle(d, cx, cy, s, fill):
    d.polygon([(cx, cy - s), (cx + s * 0.22, cy - s * 0.22), (cx + s, cy), (cx + s * 0.22, cy + s * 0.22),
               (cx, cy + s), (cx - s * 0.22, cy + s * 0.22), (cx - s, cy), (cx - s * 0.22, cy - s * 0.22)], fill=fill)

def name(d, y, fill, size=150):
    d.text((CX, y), NAME, font=font("GreatVibes.ttf", size), fill=rgba(fill), anchor="mm")

def save(img, slots, n):
    img.save(os.path.join(OUT, f"frame{n}.png"))
    with open(os.path.join(OUT, f"frame{n}.json"), "w") as f:
        json.dump({"slots": slots}, f, indent=2)

# ---------- 14: Black Tie (the groom's tux) ----------
def black_tie():
    BLACK, SHIRT, SATIN, WHITE = (14, 14, 16), (250, 250, 247), (60, 60, 66), (245, 245, 240)
    slots = layout(top=330, bottom=330)
    img = Image.new("RGBA", (W, H), rgba(BLACK))
    d = ImageDraw.Draw(img)
    # shirt V opening and satin lapel edges
    d.polygon([(CX - 260, 0), (CX + 260, 0), (CX, 300)], fill=rgba(SHIRT))
    d.line([(CX - 260, 0), (CX, 300)], fill=rgba(SATIN), width=14)
    d.line([(CX + 260, 0), (CX, 300)], fill=rgba(SATIN), width=14)
    for sy in (170, 225):
        d.ellipse([CX - 9, sy - 9, CX + 9, sy + 9], fill=rgba(BLACK))
    bowtie(d, CX, 70, 70, rgba(BLACK), rgba((40, 40, 44)))
    # pocket square
    d.polygon([(860, 250), (950, 250), (905, 205)], fill=rgba(WHITE))
    d.line([(840, 252), (970, 252)], fill=rgba(SATIN), width=4)
    # buttons between photos
    for x, y, w, h in slots[:-1]:
        d.ellipse([CX - 11, y + h + 7, CX + 11, y + h + 29], fill=rgba(SATIN))
    cut(img, slots, keyline=SATIN)
    d = ImageDraw.Draw(img)
    fy = slots[-1][1] + slots[-1][3]
    bowtie(d, CX, fy + 75, 34, rgba(WHITE), rgba((200, 200, 195)))
    for s in (-1, 1):
        d.line([CX + s * 70, fy + 75, CX + s * 300, fy + 75], fill=rgba(SATIN), width=2)
    name(d, fy + 205, WHITE)
    return img, slots

# ---------- 15: The Gown (the bride's dress) ----------
def the_gown():
    BLUSH, GOWN, GOLD, LACE = (243, 228, 224), (255, 255, 253), (198, 161, 91), (226, 208, 203)
    slots = layout(top=320, bottom=420)
    img = Image.new("RGBA", (W, H), rgba(BLUSH))
    d = ImageDraw.Draw(img)
    # fitted sweetheart bodice
    for side in (-1, 1):
        d.ellipse([CX + side*180 - 190, 90, CX + side*180 + 190, 250], fill=rgba(GOWN))
    d.polygon([(CX - 370, 170), (CX + 370, 170), (CX + 262, 300), (CX - 262, 300)], fill=rgba(GOWN))
    d.polygon([(CX - 40, 88), (CX + 40, 88), (CX, 150)], fill=rgba(BLUSH))
    for side in (-1, 1):  # pearl trim along neckline
        for k in range(15):
            t = math.pi * (0.08 + 0.84 * k / 14)
            px = CX + side*180 - 190 * math.cos(t)
            py = 170 - 80 * math.sin(t)
            d.ellipse([px - 7, py - 7, px + 7, py + 7], fill=rgba(GOWN), outline=rgba(LACE), width=2)
    for k in range(-5, 6):  # lace dots on bodice
        for row in (205, 245):
            d.ellipse([CX + k*48 - 4, row - 4, CX + k*48 + 4, row + 4], fill=rgba(LACE))
    d.rectangle([CX - 264, 292, CX + 264, 308], fill=rgba(GOLD))
    # lace scallops on both edges
    for y in range(0, H, 44):
        for x in (0, W):
            d.ellipse([x - 26, y, x + 26, y + 44], fill=rgba(GOWN))
            d.ellipse([x - 7, y + 15, x + 7, y + 29], fill=rgba(LACE))
    # pearl strands between photos
    for x, y, w, h in slots[:-1]:
        for px in range(120, W - 110, 34):
            d.ellipse([px - 6, y + h + 12, px + 6, y + h + 24], fill=rgba(GOWN), outline=rgba(LACE), width=2)
    # skirt
    fy = slots[-1][1] + slots[-1][3]
    d.polygon([(CX - 260, fy + 40), (CX + 260, fy + 40), (W - 30, H), (30, H)], fill=rgba(GOWN))
    for k in range(-4, 5):
        d.line([CX + k * 50, fy + 60, CX + k * 150, H], fill=rgba((240, 230, 226)), width=3)
    d.rectangle([CX - 262, fy + 30, CX + 262, fy + 52], fill=rgba(GOLD))
    cut(img, slots, keyline=GOLD)
    d = ImageDraw.Draw(img)
    name(d, fy + 220, GOLD)
    d.text((CX, fy + 330), "TWO HEARTS  ·  ONE LOVE", font=font("PoiretOne.ttf", 42), fill=rgba(GOLD), anchor="mm")
    return img, slots

# ---------- 16: Garden Party (greenery, florals, tux + dress) ----------
def garden():
    CREAM, SAGE, DSAGE, BLUSH, GOLD = (246, 242, 233), (138, 154, 123), (94, 110, 82), (232, 180, 176), (196, 160, 98)
    slots = layout(top=180, bottom=360)
    img = Image.new("RGBA", (W, H), rgba(CREAM))
    d = ImageDraw.Draw(img)
    d.rectangle([24, 24, W - 25, H - 25], outline=rgba(SAGE), width=3)
    cut(img, slots, keyline=SAGE)
    over = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    o = ImageDraw.Draw(over)
    rnd = random.Random(7)
    for side in (-1, 1):  # climbing vines that spill over photo edges
        base = 40 if side < 0 else W - 40
        prev = None
        for y in range(40, H - 380, 8):
            x = base + 10 * math.sin(y / 95)
            if prev:
                o.line([prev, (x, y)], fill=rgba(DSAGE), width=5)
            prev = (x, y)
            if y % 64 == 0:
                ang = (-35 if (y // 64) % 2 else 35) + (0 if side < 0 else 180)
                leaf(o, x + math.cos(math.radians(ang)) * 26, y + math.sin(math.radians(ang)) * 26,
                     58, 24, ang, rgba(SAGE if rnd.random() > 0.3 else DSAGE))
    for (x, y, w, h), corner in zip(slots, [(0, 0), (1, 1), (0, 1), (1, 0)]):
        fx, fy_ = x + corner[0] * w, y + corner[1] * h
        flower(o, fx, fy_, 34, rgba(BLUSH), rgba(GOLD))
        for k in range(3):
            leaf(o, fx + rnd.randint(-40, 40), fy_ + rnd.randint(-40, 40), 50, 20, rnd.randint(0, 180), rgba(SAGE))
    img.alpha_composite(over)
    d = ImageDraw.Draw(img)
    # header garland
    for k in range(-6, 7):
        leaf(d, CX + k * 34, 100 + abs(k) * 4, 46, 18, 90 + k * 12, rgba(SAGE if k % 2 else DSAGE))
    flower(d, CX, 96, 30, rgba(BLUSH), rgba(GOLD))
    fy = slots[-1][1] + slots[-1][3]
    bowtie(d, CX - 55, fy + 85, 28, rgba(DSAGE))
    dress(d, CX + 55, fy + 52, 44, rgba(BLUSH), rgba(GOLD))
    for s in (-1, 1):
        d.line([CX + s * 120, fy + 85, CX + s * 330, fy + 85], fill=rgba(SAGE), width=2)
    name(d, fy + 205, DSAGE, 135)
    d.text((CX, fy + 300), "A GARDEN OF LOVE", font=font("PoiretOne.ttf", 40), fill=rgba(SAGE), anchor="mm")
    return img, slots

# ---------- 17: Just Married (bunting + confetti) ----------
def just_married():
    NAVY, BLUSH, GOLD, WHITE = (30, 42, 71), (242, 196, 192), (212, 175, 106), (250, 248, 244)
    slots = layout(top=300, bottom=320)
    img = Image.new("RGBA", (W, H), rgba(NAVY))
    d = ImageDraw.Draw(img)
    letters = "JUST MARRIED"
    n = len(letters)
    pts = [(100 + i * (1000 / (n - 1)), 70 + 60 * math.sin(math.pi * i / (n - 1))) for i in range(n)]
    d.line(pts, fill=rgba(GOLD), width=4)
    lf = font("Limelight.ttf", 52)
    colors = [WHITE, BLUSH, GOLD]
    for i, (ch, (px, py)) in enumerate(zip(letters, pts)):
        if ch == " ":
            continue
        d.polygon([(px - 40, py), (px + 40, py), (px, py + 150)], fill=rgba(colors[i % 3]))
        d.text((px, py + 48), ch, font=lf, fill=rgba(NAVY), anchor="mm")
    rnd = random.Random(3)
    for _ in range(260):  # confetti
        x, y = rnd.randint(20, W - 20), rnd.randint(260, H - 20)
        if y > H - 260 and 120 < x < W - 120:
            continue
        c = rgba(rnd.choice([BLUSH, GOLD, WHITE]))
        r = rnd.random()
        if r < 0.35:
            heart(d, x, y, rnd.randint(8, 14), c)
        elif r < 0.7:
            s = rnd.randint(3, 6); d.ellipse([x - s, y - s, x + s, y + s], fill=c)
        else:
            sparkle(d, x, y, rnd.randint(7, 12), c)
    cut(img, slots, keyline=GOLD)
    d = ImageDraw.Draw(img)
    fy = slots[-1][1] + slots[-1][3]
    heart(d, CX, fy + 60, 22, rgba(BLUSH))
    name(d, fy + 175, WHITE)
    return img, slots

# ---------- 18: Champagne Toast ----------
def flute_img(s, gold, fizz):
    im = Image.new("RGBA", (int(s * 1.2), int(s * 3)), (0, 0, 0, 0))
    g = ImageDraw.Draw(im)
    cx = im.width / 2
    bowl = [(cx - s * 0.3, 10), (cx + s * 0.3, 10), (cx + s * 0.18, s * 1.5), (cx - s * 0.18, s * 1.5)]
    g.polygon([(cx - s * 0.27, s * 0.45), (cx + s * 0.27, s * 0.45), (cx + s * 0.18, s * 1.5), (cx - s * 0.18, s * 1.5)], fill=fizz)
    g.polygon(bowl, outline=gold, width=7)
    g.line([cx, s * 1.5, cx, s * 2.5], fill=gold, width=7)
    g.ellipse([cx - s * 0.32, s * 2.45, cx + s * 0.32, s * 2.6], outline=gold, width=7)
    for k in range(6):
        bx, by = cx + (k % 3 - 1) * s * 0.08, s * (1.35 - k * 0.15)
        g.ellipse([bx - 5, by - 5, bx + 5, by + 5], outline=(255, 245, 220, 255), width=2)
    return im

def champagne():
    WINE, GOLD, SOFT, FIZZ = (74, 20, 38), (216, 178, 110), (140, 90, 80), (232, 200, 130)
    slots = layout(top=340, bottom=330)
    img = Image.new("RGBA", (W, H), rgba(WINE))
    d = ImageDraw.Draw(img)
    d.rectangle([24, 24, W - 25, H - 25], outline=rgba(GOLD), width=4)
    d.rectangle([38, 38, W - 39, H - 39], outline=rgba(SOFT), width=2)
    f = flute_img(100, rgba(GOLD), rgba(FIZZ))
    left, right = f.rotate(-18, expand=True, resample=Image.BICUBIC), f.rotate(18, expand=True, resample=Image.BICUBIC)
    img.alpha_composite(left, (CX - left.width + 40, 20))
    img.alpha_composite(right, (CX - 40, 20))
    sparkle(d, CX, 62, 26, rgba(GOLD))
    for dx, dy, s in [(-70, 40, 10), (75, 30, 12), (-40, 110, 7), (55, 95, 8)]:
        sparkle(d, CX + dx, dy, s, rgba(GOLD))
    for side in (-1, 1):
        d.line([CX + side * 190, 170, CX + side * 500, 170], fill=rgba(SOFT), width=2)
        d.ellipse([CX + side * 500 - 6, 164, CX + side * 500 + 6, 176], fill=rgba(GOLD))
    cut(img, slots, keyline=GOLD)
    d = ImageDraw.Draw(img)
    fy = slots[-1][1] + slots[-1][3]
    d.text((CX, fy + 75), "CHEERS TO LOVE", font=font("PoiretOne.ttf", 46), fill=rgba(GOLD), anchor="mm")
    name(d, fy + 200, GOLD)
    return img, slots

# ---------- 19: Film Reel ----------
def film_reel():
    BLACK, HOLE, GOLD, WHITE = (12, 12, 12), (240, 236, 226), (201, 166, 98), (248, 246, 240)
    slots = layout(top=200, bottom=320, x0=86, w=1028)
    img = Image.new("RGBA", (W, H), rgba(BLACK))
    d = ImageDraw.Draw(img)
    for y in range(20, H - 20, 58):
        for x in (18, W - 48):
            d.rounded_rectangle([x, y, x + 30, y + 36], radius=6, fill=rgba(HOLE))
    small = font("PoiretOne.ttf", 30)
    for i, (x, y, w, h) in enumerate(slots):
        d.text((x + 12, y - 22), f"No. {i + 1}", font=small, fill=rgba(GOLD), anchor="lm")
    d.text((CX, 100), "TAKE ONE  ·  FOREVER", font=font("PoiretOne.ttf", 48), fill=rgba(GOLD), anchor="mm")
    cut(img, slots, inset=4, radius=10, keyline=(70, 70, 70), kw=2)
    d = ImageDraw.Draw(img)
    fy = slots[-1][1] + slots[-1][3]
    heart(d, CX, fy + 60, 18, rgba(GOLD))
    name(d, fy + 180, WHITE)
    return img, slots


# ---------- 11: Deco Silver (original PHOTOBOOTH design) ----------
def deco_silver():
    BG, SILVER, DIM = (18, 18, 18), (205, 205, 200), (120, 120, 116)
    slots = layout(top=150, bottom=H - (150 + 4 * 770 + 3 * 40), gap=40)
    img = Image.new("RGBA", (W, H), rgba(BG))
    d = ImageDraw.Draw(img)
    d.rectangle([24, 24, W - 25, H - 25], outline=rgba(SILVER), width=4)
    d.rectangle([38, 38, W - 39, H - 39], outline=rgba(DIM), width=2)
    for x in range(70, W - 70, 16):
        d.line([x, 62, x, 118], fill=rgba(SILVER), width=4)
    d.rectangle([CX - 150, 58, CX + 150, 122], fill=rgba(BG))
    d.ellipse([CX - 26, 64, CX + 26, 116], outline=rgba(SILVER), width=4)
    d.ellipse([CX - 10, 80, CX + 10, 100], fill=rgba(SILVER))
    for dx in (-95, 95):
        d.polygon([(CX + dx, 78), (CX + dx + 12, 90), (CX + dx, 102), (CX + dx - 12, 90)], fill=rgba(SILVER))
    cut(img, slots, keyline=SILVER)
    d = ImageDraw.Draw(img)
    fy = slots[-1][1] + slots[-1][3] + 20
    d.text((CX, fy + 62), "PHOTOBOOTH", font=font("Limelight.ttf", 104), fill=rgba(SILVER), anchor="mm")
    d.line([150, fy + 128, W - 150, fy + 128], fill=rgba(DIM), width=2)
    d.text((CX, fy + 172), "SMILE  ·  SNAP  ·  REPEAT", font=font("PoiretOne.ttf", 46), fill=rgba(SILVER), anchor="mm")
    return img, slots

# ---------- 12 & 13: Deco Gold (ivory and black) ----------
def deco_gold(bg, gold, soft):
    slots = layout(top=150, bottom=H - (150 + 4 * 740 + 3 * 36))
    img = Image.new("RGBA", (W, H), rgba(bg))
    d = ImageDraw.Draw(img)
    d.rectangle([24, 24, W - 25, H - 25], outline=rgba(gold), width=4)
    d.rectangle([38, 38, W - 39, H - 39], outline=rgba(soft), width=2)
    for x in range(70, W - 70, 16):
        d.line([x, 62, x, 118], fill=rgba(soft), width=3)
    d.rectangle([CX - 150, 58, CX + 150, 122], fill=rgba(bg))
    d.polygon([(CX, 68), (CX + 22, 90), (CX, 112), (CX - 22, 90)], outline=rgba(gold), width=4)
    for dx in (-90, 90):
        d.ellipse([CX + dx - 7, 83, CX + dx + 7, 97], fill=rgba(gold))
    cut(img, slots, keyline=gold)
    d = ImageDraw.Draw(img)
    fy = slots[-1][1] + slots[-1][3]
    ry, r = fy + 78, 34
    for ccx in (CX - 22, CX + 22):
        d.ellipse([ccx - r, ry - r, ccx + r, ry + r], outline=rgba(gold), width=6)
    dx, dy = CX + 22, ry - r
    d.polygon([(dx, dy - 16), (dx + 11, dy - 4), (dx, dy + 6), (dx - 11, dy - 4)], fill=rgba(bg), outline=rgba(gold), width=3)
    for s in (-1, 1):
        d.line([CX + s * 80, ry, CX + s * 300, ry], fill=rgba(soft), width=2)
        d.ellipse([CX + s * 300 - 5, ry - 5, CX + s * 300 + 5, ry + 5], fill=rgba(soft))
    name(d, fy + 205, gold)
    return img, slots

def deco_ivory():
    return deco_gold((247, 241, 230), (176, 141, 77), (210, 188, 145))

def deco_black():
    return deco_gold((16, 16, 16), (201, 166, 98), (125, 105, 70))

# ================= FUN SET (no words, just vibes) =================
def vgrad(top_c, bot_c):
    g = Image.new("RGBA", (W, H))
    d = ImageDraw.Draw(g)
    for y in range(H):
        t = y / (H - 1)
        d.line([0, y, W, y], fill=tuple(int(a + (b - a) * t) for a, b in zip(top_c, bot_c)) + (255,))
    return g

def glow_lines(img, rects, color, radius, width=4, blur=14):
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    g = ImageDraw.Draw(layer)
    for r in rects:
        g.rounded_rectangle(r, radius=radius, outline=rgba(color), width=width * 4)
    img.alpha_composite(layer.filter(ImageFilter.GaussianBlur(blur)))
    d = ImageDraw.Draw(img)
    for r in rects:
        d.rounded_rectangle(r, radius=radius, outline=rgba(color), width=width)

def hole_rects(slots, pad=12, inset=6):
    return [[x + inset - pad, y + inset - pad, x + w - inset + pad - 1, y + h - inset + pad - 1] for x, y, w, h in slots]

# ---------- 20: Seventies ----------
def seventies():
    CREAM, BROWN = (244, 233, 214), (92, 58, 33)
    STRIPES = [(196, 78, 38), (226, 128, 43), (234, 178, 52), (122, 140, 72)]
    slots = layout(top=190, bottom=380)
    img = Image.new("RGBA", (W, H), rgba(CREAM))
    d = ImageDraw.Draw(img)
    for i, c in enumerate(STRIPES):
        d.rectangle([0, 40 + i * 28, W, 40 + i * 28 + 22], fill=rgba(c))
    cut(img, slots, radius=48, keyline=BROWN, kw=4)
    d = ImageDraw.Draw(img)
    base = H - 40
    for i, c in enumerate(STRIPES):
        r = 300 - i * 52
        d.pieslice([CX - r, base - r, CX + r, base + r], 180, 360, fill=rgba(c))
    d.pieslice([CX - 92, base - 92, CX + 92, base + 92], 180, 360, fill=rgba(CREAM))
    d.rectangle([0, base, W, H], fill=rgba(BROWN))
    return img, slots

# ---------- 21: Synthwave ----------
def synthwave():
    NEON_PINK, NEON_CYAN = (255, 64, 170), (40, 230, 255)
    slots = layout(top=140, bottom=480)
    img = vgrad((14, 4, 36), (46, 8, 72))
    d = ImageDraw.Draw(img)
    rnd = random.Random(21)
    for _ in range(140):
        x, y, s = rnd.randint(30, W - 30), rnd.randint(20, H - 500), rnd.choice([1, 2, 2, 3])
        d.ellipse([x - s, y - s, x + s, y + s], fill=(255, 255, 255, rnd.randint(120, 255)))
    horizon = H - 210
    SUN = 360
    sun = Image.new("RGBA", (SUN, SUN), (0, 0, 0, 0))
    sg = ImageDraw.Draw(sun)
    for y in range(SUN):
        t = y / (SUN - 1)
        sg.line([0, y, SUN, y], fill=(255, int(220 - 160 * t), int(60 + 120 * t), 255))
    m = Image.new("L", (SUN, SUN), 0)
    mg = ImageDraw.Draw(m)
    mg.ellipse([0, 0, SUN - 1, SUN - 1], fill=255)
    for k, yy in enumerate(range(190, SUN, 26)):
        mg.rectangle([0, yy, SUN, yy + 5 + k * 3], fill=0)
    sun.putalpha(m)
    img.alpha_composite(sun, (CX - SUN // 2, horizon - 240))
    d.rectangle([0, horizon, W, H], fill=(14, 4, 36, 255))
    grid = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gg = ImageDraw.Draw(grid)
    for k in range(-14, 15):
        gg.line([CX + k * 18, horizon, CX + k * 190, H], fill=rgba(NEON_PINK), width=3)
    y, step = horizon, 10
    while y < H:
        gg.line([0, y, W, y], fill=rgba(NEON_PINK), width=3)
        step *= 1.35
        y += step
    img.alpha_composite(grid.filter(ImageFilter.GaussianBlur(5)))
    img.alpha_composite(grid)
    glow_lines(img, hole_rects(slots), NEON_CYAN, radius=30)
    cut(img, slots)
    return img, slots

# ---------- 22: Pop Dots (comic panels) ----------
def pop_dots():
    YELLOW, RED, BLACK, WHITE = (255, 217, 61), (230, 57, 70), (17, 17, 17), (255, 255, 255)
    slots = layout(top=110, bottom=420)
    img = Image.new("RGBA", (W, H), rgba(YELLOW))
    d = ImageDraw.Draw(img)
    for row, y in enumerate(range(0, H, 36)):
        for x in range(18 if row % 2 else 0, W + 36, 36):
            edge = min(x, W - x) / (W / 2)
            r = 4 + 10 * (1 - edge)
            d.ellipse([x - r, y - r, x + r, y + r], fill=rgba(RED))
    for x, y, w, h in slots:
        d.rectangle([x - 6, y - 6, x + w + 6, y + h + 6], fill=rgba(BLACK))
    cut(img, slots, inset=6, radius=2)
    d = ImageDraw.Draw(img)
    cy = H - 210
    def burst(rad_out, rad_in, fill, n=16):
        pts = []
        for k in range(n * 2):
            a = math.pi * k / n
            r = rad_out if k % 2 == 0 else rad_in
            pts.append((CX + r * math.cos(a), cy + r * math.sin(a) * 0.82))
        d.polygon(pts, fill=fill)
    burst(220, 140, rgba(BLACK))
    burst(200, 125, rgba(RED))
    burst(120, 80, rgba(WHITE))
    sparkle(d, CX, cy, 50, rgba(YELLOW))
    return img, slots

# ---------- 23: Memphis ----------
def memphis():
    BG = (255, 246, 233)
    COLORS = [(0, 166, 166), (255, 107, 157), (255, 196, 0), (17, 17, 17), (88, 86, 214)]
    slots = layout(top=170, bottom=380)
    img = Image.new("RGBA", (W, H), rgba(BG))
    d = ImageDraw.Draw(img)
    rnd = random.Random(23)
    for _ in range(320):
        x, y = rnd.randint(0, W), rnd.randint(0, H)
        c = rgba(rnd.choice(COLORS))
        kind = rnd.random()
        s = rnd.randint(20, 46)
        if kind < 0.25:
            pts = [(x + i * 9, y + s * 0.45 * math.sin(i * 0.9)) for i in range(10)]
            d.line(pts, fill=c, width=9, joint="curve")
        elif kind < 0.45:
            d.polygon([(x, y - s), (x + s, y + s * 0.7), (x - s, y + s * 0.7)], fill=c)
        elif kind < 0.65:
            d.ellipse([x - s * 0.6, y - s * 0.6, x + s * 0.6, y + s * 0.6], outline=c, width=9)
        elif kind < 0.8:
            pts = [(x + i * 16, y + (14 if i % 2 else -14)) for i in range(6)]
            d.line(pts, fill=c, width=9)
        else:
            d.ellipse([x - 10, y - 10, x + 10, y + 10], fill=c)
    for x, y, w, h in slots:  # offset shadow blocks
        d.rectangle([x + 20, y + 20, x + w + 14, y + h + 14], fill=rgba((17, 17, 17)))
        d.rectangle([x - 6, y - 6, x + w + 6, y + h + 6], fill=rgba(BG), outline=rgba((17, 17, 17)), width=5)
    cut(img, slots, inset=6, radius=4)
    return img, slots

# ---------- 24: Checkerboard ----------
def checker():
    A, B, YELLOW, BLACK = (186, 160, 255), (255, 255, 255), (255, 214, 10), (17, 17, 17)
    slots = layout(top=120, bottom=330, x0=90, w=1020)
    img = Image.new("RGBA", (W, H), rgba(B))
    d = ImageDraw.Draw(img)
    sq = 60
    for gy in range(0, H, sq):
        for gx in range(0, W, sq):
            if (gx // sq + gy // sq) % 2 == 0:
                d.rectangle([gx, gy, gx + sq - 1, gy + sq - 1], fill=rgba(A))
    shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    for x, y, w, h in slots:
        sd.rounded_rectangle([x - 4, y + 14, x + w + 14, y + h + 24], radius=34, fill=(0, 0, 0, 110))
    img.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(10)))
    d = ImageDraw.Draw(img)
    for x, y, w, h in slots:
        d.rounded_rectangle([x - 18, y - 18, x + w + 18, y + h + 18], radius=40, fill=rgba(B))
    cut(img, slots, radius=26)
    d = ImageDraw.Draw(img)
    cy, r = H - 165, 110  # smiley
    d.ellipse([CX - r - 8, cy - r - 8, CX + r + 8, cy + r + 8], fill=rgba(BLACK))
    d.ellipse([CX - r, cy - r, CX + r, cy + r], fill=rgba(YELLOW))
    for ex in (-38, 38):
        d.ellipse([CX + ex - 13, cy - 45, CX + ex + 13, cy - 5], fill=rgba(BLACK))
    d.arc([CX - 66, cy - 40, CX + 66, cy + 66], 20, 160, fill=rgba(BLACK), width=12)
    return img, slots

# ---------- 25: Cosmos ----------
def cosmos():
    STAR, GOLD, RING, PLANET = (255, 255, 255), (255, 214, 140), (190, 200, 255), (120, 90, 220)
    slots = layout(top=180, bottom=380)
    img = vgrad((8, 10, 32), (24, 16, 64))
    d = ImageDraw.Draw(img)
    rnd = random.Random(25)
    for _ in range(330):
        x, y = rnd.randint(10, W - 10), rnd.randint(10, H - 10)
        s = rnd.choice([1, 1, 2, 2, 3])
        d.ellipse([x - s, y - s, x + s, y + s], fill=(255, 255, 255, rnd.randint(110, 255)))
    for _ in range(18):
        sparkle(d, rnd.randint(30, W - 30), rnd.randint(30, H - 30), rnd.randint(8, 16), rgba(GOLD))
    # crescent moon and a shooting star up top
    d.ellipse([110, 40, 210, 140], fill=rgba(GOLD))
    d.ellipse([140, 30, 240, 130], fill=(10, 12, 36, 255))
    trail = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    td = ImageDraw.Draw(trail)
    td.line([(760, 50), (1060, 130)], fill=(255, 255, 255, 200), width=6)
    img.alpha_composite(trail.filter(ImageFilter.GaussianBlur(3)))
    sparkle(d, 1060, 130, 18, rgba(STAR))
    glow_lines(img, hole_rects(slots), RING, radius=30, width=3, blur=10)
    cut(img, slots)
    d = ImageDraw.Draw(img)
    cy = H - 200  # ringed planet
    d.ellipse([CX - 330, cy - 60, CX + 330, cy + 60], outline=rgba(RING), width=10)
    d.ellipse([CX - 130, cy - 130, CX + 130, cy + 130], fill=rgba(PLANET))
    d.chord([CX - 130, cy - 130, CX + 130, cy + 130], 200, 340, fill=rgba((150, 120, 240)))
    d.arc([CX - 330, cy - 60, CX + 330, cy + 60], 0, 180, fill=rgba(RING), width=10)
    return img, slots

# ================= MALL BOOTH SET (plain 90s/2000s strips) =================
def plain_strip(bg):
    slots = layout(top=60, bottom=180, gap=40)
    img = Image.new("RGBA", (W, H), rgba(bg))
    cut(img, slots, inset=0, radius=0)
    return img, slots

def mall_white():
    return plain_strip((255, 255, 255))

def mall_black():
    return plain_strip((10, 10, 10))

def baby_pink():
    return plain_strip((255, 209, 220))

def baby_blue():
    return plain_strip((190, 222, 255))

# ================= ARMY SET =================
ARMY_GOLD, ARMY_BLACK, ARMY_WHITE = (255, 204, 1), (18, 18, 18), (255, 255, 255)
# OCP (Operational Camouflage Pattern), the Army uniform: tan base with vertical blotches.
OCP_BASE = (186, 172, 136)
OCP_LAYERS = [((158, 140, 102), 46, 150, 230), ((116, 110, 78), 30, 120, 200),
              ((100, 80, 57), 17, 95, 160), ((78, 77, 54), 10, 70, 120), ((216, 206, 176), 8, 55, 85)]

def bold(name, size, weight=700):
    f = font(name, size)
    f.set_variation_by_axes([weight])
    return f

def smooth_noise(seed, cell_x, cell_y, blur, size=(W, H)):
    """Soft random field (float array): random values on a coarse grid, smoothly enlarged."""
    rnd = np.random.default_rng(seed)
    w, h = size
    gw, gh = w // cell_x + 3, h // cell_y + 3
    grid = (rnd.random((gh, gw)) * 255).astype(np.uint8)
    img = Image.fromarray(grid, "L").resize((gw * cell_x, gh * cell_y), Image.BICUBIC)
    img = img.crop((cell_x, cell_y, cell_x + w, cell_y + h))
    return np.asarray(img.filter(ImageFilter.GaussianBlur(blur)), np.float32)

def camo(base, layers, seed, size=(W, H)):
    img = Image.new("RGBA", size, rgba(base))
    for k, (color, cover, cx, cy) in enumerate(layers):
        n = (smooth_noise(seed + 11 * k, cx, cy, cx / 6, size) * 0.8
             + smooth_noise(seed + 11 * k + 5, max(4, cx // 5), max(4, cy // 5), 1.5, size) * 0.2)
        mask = Image.fromarray(((n > np.percentile(n, 100 - cover)) * 255).astype(np.uint8), "L")
        img.paste(rgba(color), (0, 0) + size, mask)
    return img

def star_points(cx, cy, r, inner=0.382, rot=-90):
    return [(cx + (r if i % 2 == 0 else r * inner) * math.cos(math.radians(rot + 36 * i)),
             cy + (r if i % 2 == 0 else r * inner) * math.sin(math.radians(rot + 36 * i)))
            for i in range(10)]

def army_star(d, cx, cy, r):
    """Gold star in a black box with a gold rule, the star's points reaching the box edges."""
    half_w, top, bottom = r * 0.951, cy - r, cy + r * 0.809
    d.rectangle([cx - half_w * 1.08, top - r * 0.06, cx + half_w * 1.08, bottom + r * 0.14],
                fill=rgba(ARMY_BLACK))
    d.rectangle([cx - half_w * 0.98, top + r * 0.03, cx + half_w * 0.98, bottom + r * 0.05],
                outline=rgba(ARMY_GOLD), width=max(3, int(r * 0.05)))
    d.polygon(star_points(cx, cy, r), fill=rgba(ARMY_WHITE))
    d.polygon(star_points(cx, cy + r * 0.02, r * 0.9), fill=rgba(ARMY_BLACK))
    d.polygon(star_points(cx, cy + r * 0.03, r * 0.82), fill=rgba(ARMY_GOLD))

def spaced_text(d, xy, text, f, fill, spacing, anchor_y="mm", **kw):
    """Text centred on xy with extra space between letters (uniform tapes and stencils)."""
    widths = [d.textlength(ch, font=f) for ch in text]
    x = xy[0] - (sum(widths) + spacing * (len(text) - 1)) / 2
    for ch, w in zip(text, widths):
        d.text((x, xy[1]), ch, font=f, fill=fill, anchor="l" + anchor_y[1], **kw)
        x += w + spacing

def tape(img, box, text, seed):
    """Uniform name tape: OCP fabric strip, stitched edge, black block letters."""
    x0, y0, x1, y1 = box
    shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rectangle([x0 + 8, y0 + 12, x1 + 8, y1 + 12], fill=(0, 0, 0, 150))
    img.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(10)))
    fabric = camo((200, 188, 152), [(c, cov, cx // 2, cy // 2) for c, cov, cx, cy in OCP_LAYERS[:3]],
                  seed, size=(x1 - x0, y1 - y0))
    img.alpha_composite(fabric, (x0, y0))
    d = ImageDraw.Draw(img, "RGBA")
    d.rectangle(box, outline=rgba((70, 64, 46)), width=6)
    for x in range(x0 + 14, x1 - 14, 22):  # stitching
        d.line([x, y0 + 13, x + 11, y0 + 13], fill=rgba((60, 54, 40)), width=3)
        d.line([x, y1 - 13, x + 11, y1 - 13], fill=rgba((60, 54, 40)), width=3)
    spaced_text(d, ((x0 + x1) / 2, (y0 + y1) / 2 + 4), text, bold("Oswald.ttf", int((y1 - y0) * 0.66)),
                rgba((16, 16, 14)), 14)

# ---------- 32: Army Camo ----------
def army_camo():
    slots = layout(top=470, bottom=330, gap=40)
    img = camo(OCP_BASE, OCP_LAYERS, seed=32)
    d = ImageDraw.Draw(img, "RGBA")
    army_star(d, CX, 150, 110)
    tape(img, (CX - 380, 300, CX + 380, 430), "U.S. ARMY", seed=7)
    glow_lines(img, hole_rects(slots), (40, 38, 28), radius=10, width=4, blur=8)
    img.putalpha(255)  # translucent drawing above must not leave see-through spots
    cut(img, slots, inset=6, radius=8)
    d = ImageDraw.Draw(img, "RGBA")
    fy = slots[-1][1] + slots[-1][3]
    plate = (CX - 470, fy + 95, CX + 470, fy + 245)
    shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rectangle([plate[0] + 8, plate[1] + 12, plate[2] + 8, plate[3] + 12], fill=(0, 0, 0, 150))
    img.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(10)))
    d = ImageDraw.Draw(img, "RGBA")
    d.rectangle(plate, fill=rgba((62, 60, 42)), outline=rgba((36, 34, 24)), width=6)
    spaced_text(d, (CX, fy + 172), "THIS WE'LL DEFEND", font("StardosStencil.ttf", 72),
                rgba((222, 210, 176)), 8)
    return img, slots

# ---------- 33: Army Black & Gold ----------
def army_gold():
    slots = layout(top=520, bottom=330, gap=44)
    img = Image.new("RGBA", (W, H), rgba(ARMY_BLACK))
    d = ImageDraw.Draw(img, "RGBA")
    for x in range(-H, W, 46):  # faint diagonal pinstripes
        d.line([x, H, x + H, 0], fill=(40, 40, 40, 255), width=3)
    # Camo bands top and bottom, edged in gold.
    band = camo(OCP_BASE, OCP_LAYERS, seed=33)
    img.paste(band.crop((0, 0, W, 34)), (0, 0))
    img.paste(band.crop((0, H - 34, W, H)), (0, H - 34))
    d.line([0, 36, W, 36], fill=rgba(ARMY_GOLD), width=6)
    d.line([0, H - 37, W, H - 37], fill=rgba(ARMY_GOLD), width=6)
    army_star(d, CX, 200, 120)
    spaced_text(d, (CX, 420), "U.S. ARMY", bold("Oswald.ttf", 128), rgba(ARMY_WHITE), 18)
    for x, y, w, h in slots:
        d.rectangle([x - 4, y - 4, x + w + 3, y + h + 3], outline=rgba(ARMY_GOLD), width=6)
    for (x, y, w, h), nxt in zip(slots, slots[1:]):
        gy = (y + h + nxt[1]) / 2
        d.line([90, gy, CX - 46, gy], fill=rgba(ARMY_GOLD), width=3)
        d.line([CX + 46, gy, W - 90, gy], fill=rgba(ARMY_GOLD), width=3)
        d.polygon(star_points(CX, gy + 2, 20), fill=rgba(ARMY_GOLD))
    img.putalpha(255)  # translucent drawing above must not leave see-through spots
    cut(img, slots, inset=0, radius=0)
    d = ImageDraw.Draw(img, "RGBA")
    fy = slots[-1][1] + slots[-1][3]
    spaced_text(d, (CX, fy + 120), "BE ALL YOU CAN BE", bold("Oswald.ttf", 84, 600), rgba(ARMY_GOLD), 12)
    for k in range(5):
        d.polygon(star_points(CX + (k - 2) * 70, fy + 225, 20), fill=rgba(ARMY_WHITE))
    return img, slots

# Classic M81 woodland: khaki base, big green and brown shapes, black branches.
WOODLAND_BASE = (178, 162, 118)
WOODLAND_LAYERS = [((92, 106, 60), 42, 200, 150), ((114, 84, 54), 30, 170, 130), ((34, 34, 30), 15, 110, 80)]

def dog_tag(img, cx, cy, s, angle, lines):
    """A stamped steel dog tag: rounded, notched, a hole at one end, raised letters."""
    w, h = int(s * 1.9), int(s * 1.12)
    layer = Image.new("RGBA", (w + 40, h + 40), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer, "RGBA")
    box = (20, 20, 20 + w, 20 + h)
    d.rounded_rectangle(box, radius=int(s * 0.32), fill=(186, 190, 196, 255), outline=(110, 114, 120, 255), width=4)
    d.rounded_rectangle((box[0] + 8, box[1] + 8, box[2] - 8, box[3] - 8), radius=int(s * 0.26),
                        outline=(214, 218, 224, 255), width=3)
    d.ellipse((box[0] + 14, box[1] + h / 2 - 10, box[0] + 34, box[1] + h / 2 + 10), fill=(0, 0, 0, 0),
              outline=(110, 114, 120, 255), width=3)
    f = bold("Oswald.ttf", int(h * 0.2), 600)
    for i, text in enumerate(lines):
        y = box[1] + h * (0.28 + 0.24 * i)
        d.text((box[0] + 52 + 2, y + 2), text, font=f, fill=(235, 238, 242, 255), anchor="lm")
        d.text((box[0] + 52, y), text, font=f, fill=(90, 94, 100, 255), anchor="lm")
    layer = layer.rotate(angle, resample=Image.BICUBIC, expand=True)
    shadow = Image.new("RGBA", layer.size, (0, 0, 0, 0))
    shadow.putalpha(layer.getchannel("A").point(lambda v: v * 0.45))
    img.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(8)), (int(cx - layer.width / 2 + 10), int(cy - layer.height / 2 + 12)))
    img.alpha_composite(layer, (int(cx - layer.width / 2), int(cy - layer.height / 2)))

def ball_chain(d, pts, r=7):
    """Beads along a polyline, like the chain dog tags hang on."""
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        n = max(1, int(math.hypot(x1 - x0, y1 - y0) / (r * 2.3)))
        for k in range(n):
            x, y = x0 + (x1 - x0) * k / n, y0 + (y1 - y0) * k / n
            d.ellipse((x - r, y - r, x + r, y + r), fill=(150, 154, 160, 255), outline=(90, 94, 100, 255), width=2)
            d.ellipse((x - r * 0.4, y - r * 0.6, x + r * 0.1, y - r * 0.1), fill=(230, 232, 236, 255))

def plate(img, box, fill, edge, text, f, colour, spacing=10):
    x0, y0, x1, y1 = box
    shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rectangle([x0 + 8, y0 + 12, x1 + 8, y1 + 12], fill=(0, 0, 0, 150))
    img.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(10)))
    d = ImageDraw.Draw(img, "RGBA")
    d.rectangle(box, fill=rgba(fill), outline=rgba(edge), width=6)
    spaced_text(d, ((x0 + x1) / 2, (y0 + y1) / 2), text, f, rgba(colour), spacing)

# ---------- 38: Army Woodland ----------
def army_woodland():
    slots = layout(top=420, bottom=460, gap=40)
    img = camo(WOODLAND_BASE, WOODLAND_LAYERS, seed=38)
    plate(img, (CX - 420, 120, CX + 420, 300), (40, 44, 30), (20, 22, 14), "U.S. ARMY",
          font("StardosStencil.ttf", 140), (226, 214, 170), 16)
    glow_lines(img, hole_rects(slots), (24, 26, 18), radius=10, width=4, blur=8)
    img.putalpha(255)  # translucent drawing above must not leave see-through spots
    cut(img, slots, inset=6, radius=8)
    d = ImageDraw.Draw(img, "RGBA")
    fy = slots[-1][1] + slots[-1][3]
    ball_chain(d, [(140, fy + 30), (300, fy + 150), (500, fy + 225), (700, fy + 225), (900, fy + 150), (1060, fy + 30)])
    dog_tag(img, 430, fy + 290, 185, 8, ["U.S. ARMY", "HOOAH!", "ARMY STRONG"])
    dog_tag(img, 790, fy + 300, 185, -10, ["U.S. ARMY", "BE ALL YOU", "CAN BE"])
    return img, slots

# ---------- 39: Army Stars & Stripes ----------
def army_stars_stripes():
    NAVY, RED, WHITE = (26, 38, 82), (178, 34, 52), (255, 255, 255)
    slots = layout(top=520, bottom=330, gap=44, x0=110, w=980)
    img = Image.new("RGBA", (W, H), rgba(WHITE))
    d = ImageDraw.Draw(img, "RGBA")
    stripe = W / 13
    for k in range(0, 13, 2):
        d.rectangle((k * stripe, 0, (k + 1) * stripe, H), fill=rgba(RED))
    d.rectangle((0, 0, W, 470), fill=rgba(NAVY))
    for row in range(5):  # field of stars
        for col in range(11):
            x = 55 + col * 109 + (54 if row % 2 else 0)
            y = 40 + row * 86
            if x < W - 30 and not (CX - 200 < x < CX + 200) and not (CX - 400 < x < CX + 400 and y > 300):
                d.polygon(star_points(x, y, 20), fill=rgba(WHITE))
    army_star(d, CX, 175, 120)
    spaced_text(d, (CX, 395), "U.S. ARMY", bold("Oswald.ttf", 110), rgba(WHITE), 16)
    d.line((0, 470, W, 470), fill=rgba(ARMY_GOLD), width=8)
    for x, y, w, h in slots:
        d.rectangle([x - 14, y - 14, x + w + 13, y + h + 13], fill=rgba(NAVY))
        d.rectangle([x - 6, y - 6, x + w + 5, y + h + 5], outline=rgba(ARMY_GOLD), width=4)
    fy = slots[-1][1] + slots[-1][3]
    d.rectangle((0, fy + 60, W, H), fill=rgba(NAVY))
    d.line((0, fy + 60, W, fy + 60), fill=rgba(ARMY_GOLD), width=8)
    spaced_text(d, (CX, fy + 175), "HOOAH!", bold("Oswald.ttf", 130), rgba(WHITE), 20)
    for sx in (150, W - 150):
        d.polygon(star_points(sx, fy + 180, 40), fill=rgba(ARMY_GOLD))
    img.putalpha(255)
    cut(img, slots, inset=0, radius=0)
    return img, slots

# ---------- 40: Army Ammo Crate ----------
def army_crate():
    OD, OD_DARK, STENCIL = (78, 86, 40), (52, 58, 26), (232, 200, 64)
    slots = layout(top=470, bottom=380, gap=50, x0=90, w=1020)
    rnd = np.random.default_rng(40)
    # Painted wood: OD paint with grain streaks running along the planks.
    grain = rnd.normal(0, 1, (H // 8, W)).astype(np.float32)
    grain = np.asarray(Image.fromarray(((grain * 25) + 128).clip(0, 255).astype(np.uint8), "L")
                       .resize((W, H), Image.BILINEAR).filter(ImageFilter.GaussianBlur(1.2)), np.float32) - 128
    arr = np.array(OD, np.float32)[None, None, :] + grain[..., None] * 0.35
    img = Image.fromarray(arr.clip(0, 255).astype(np.uint8), "RGB").convert("RGBA")
    d = ImageDraw.Draw(img, "RGBA")
    for y in range(0, H, 300):  # plank seams
        d.line((0, y, W, y), fill=rgba(OD_DARK), width=8)
        d.line((0, y + 5, W, y + 5), fill=(255, 255, 255, 30), width=2)
    STEEL = (120, 124, 116)
    for cx, cy in ((0, 0), (W, 0), (0, H), (W, H)):  # corner brackets with rivets
        sx, sy = (1 if cx == 0 else -1), (1 if cy == 0 else -1)
        pts = [(cx, cy), (cx + sx * 190, cy), (cx + sx * 190, cy + sy * 60), (cx + sx * 60, cy + sy * 60),
               (cx + sx * 60, cy + sy * 190), (cx, cy + sy * 190)]
        d.polygon(pts, fill=rgba(STEEL), outline=rgba((70, 72, 66)))
        for rx, ry in ((cx + sx * 30, cy + sy * 30), (cx + sx * 140, cy + sy * 30), (cx + sx * 30, cy + sy * 140)):
            d.ellipse((rx - 11, ry - 11, rx + 11, ry + 11), fill=rgba((160, 164, 156)), outline=rgba((60, 62, 56)), width=2)
    sten = font("StardosStencil.ttf", 64)
    spaced_text(d, (CX, 120), "PROPERTY OF", sten, rgba(STENCIL), 10)
    spaced_text(d, (CX, 280), "U.S. ARMY", font("StardosStencil.ttf", 190), rgba(STENCIL), 18)
    spaced_text(d, (CX, 410), "1 EA  ·  PHOTO STRIP  ·  CAL. 4X6", font("StardosStencil.ttf", 44), rgba(STENCIL), 4)
    for x, y, w, h in slots:
        d.rectangle([x - 16, y - 16, x + w + 15, y + h + 15], fill=rgba(OD_DARK))
    fy = slots[-1][1] + slots[-1][3]
    spaced_text(d, (CX, fy + 120), "HANDLE WITH CARE", font("StardosStencil.ttf", 84), rgba(STENCIL), 10)
    spaced_text(d, (CX, fy + 230), "THIS SIDE UP", font("StardosStencil.ttf", 56), rgba(STENCIL), 8)
    for ax in (CX - 300, CX + 300):  # stencilled up arrows
        d.polygon([(ax, fy + 196), (ax - 26, fy + 226), (ax - 9, fy + 226), (ax - 9, fy + 262),
                   (ax + 9, fy + 262), (ax + 9, fy + 226), (ax + 26, fy + 226)], fill=rgba(STENCIL))
    img.putalpha(255)
    cut(img, slots, inset=0, radius=0)
    return img, slots

# ================= HAWAII SET =================
def palm(d, bx, by, h, lean, color, frond_len=None, seed=0):
    """Palm tree silhouette: a curved, tapering trunk and drooping fronds with leaflets."""
    rnd = random.Random(seed)
    pts = [(bx + lean * t * t, by - h * t) for t in (i / 24 for i in range(25))]
    for i in range(24):
        d.line([pts[i], pts[i + 1]], fill=color, width=max(3, int(h * 0.055 * (1 - 0.45 * i / 24))))
        if i % 2 == 0:  # trunk rings
            x, y = pts[i]
            w = h * 0.03 * (1 - 0.45 * i / 24)
            d.line([x - w, y, x + w, y - 4], fill=color, width=3)
    tx, ty = pts[-1]
    L = frond_len or h * 0.5
    for deg in (-172, -140, -112, -82, -52, -22, 8, 165, 196):
        a = math.radians(deg + rnd.uniform(-8, 8))
        ln = L * rnd.uniform(0.8, 1.1)
        spine = [(tx + math.cos(a) * ln * s, ty + math.sin(a) * ln * s * 0.55 + ln * 0.42 * s * s)
                 for s in (j / 16 for j in range(17))]
        d.line(spine, fill=color, width=max(3, int(ln * 0.035)), joint="curve")
        for j in range(2, 17):
            x, y = spine[j]
            px, py = spine[j - 1]
            ang = math.atan2(y - py, x - px)
            leaflet = ln * 0.2 * (1 - j / 19)
            for side in (-1, 1):
                b = ang + side * 1.1 + 0.35
                d.line([(x, y), (x + math.cos(b) * leaflet, y + math.sin(b) * leaflet + leaflet * 0.5)],
                       fill=color, width=max(2, int(ln * 0.022)))

def starfish(d, cx, cy, r, fill, dots, rot=-90):
    d.polygon(star_points(cx, cy, r, inner=0.45, rot=rot), fill=fill)
    for k in range(5):
        a = math.radians(rot + 72 * k)
        for t in (0.25, 0.45, 0.65):
            x, y = cx + r * t * math.cos(a), cy + r * t * math.sin(a)
            s = r * 0.05
            d.ellipse([x - s, y - s, x + s, y + s], fill=dots)

def shell(d, cx, cy, r, fill, rib, rot=0):
    """Scallop shell: a ribbed fan on a little hinge."""
    d.pieslice([cx - r, cy - r, cx + r, cy + r], 200 + rot, 340 + rot, fill=fill)
    for k in range(8):
        a = math.radians(205 + rot + k * 130 / 7)
        d.line([(cx, cy), (cx + r * 0.95 * math.cos(a), cy + r * 0.95 * math.sin(a))], fill=rib, width=max(2, int(r * 0.05)))
    d.polygon([(cx - r * 0.25, cy + r * 0.05), (cx + r * 0.25, cy + r * 0.05), (cx + r * 0.12, cy - r * 0.15),
               (cx - r * 0.12, cy - r * 0.15)], fill=fill)

def hibiscus(d, cx, cy, r, petal, dark, stamen=(255, 220, 90), angle=0):
    for k in range(5):
        a = math.radians(angle + k * 72)
        leaf(d, cx + r * 0.52 * math.cos(a), cy + r * 0.52 * math.sin(a), r * 1.08, r * 0.98, angle + k * 72, petal)
    for k in range(5):  # veins
        a = math.radians(angle + k * 72)
        d.line([(cx, cy), (cx + r * 0.75 * math.cos(a), cy + r * 0.75 * math.sin(a))], fill=dark, width=max(2, int(r * 0.04)))
    d.ellipse([cx - r * 0.24, cy - r * 0.24, cx + r * 0.24, cy + r * 0.24], fill=dark)
    a = math.radians(angle + 36)
    ex, ey = cx + r * 0.95 * math.cos(a), cy + r * 0.95 * math.sin(a)
    d.line([(cx, cy), (ex, ey)], fill=dark, width=max(3, int(r * 0.07)))
    for k in range(6):
        b = a + (k - 2.5) * 0.35
        x, y = ex + r * 0.1 * math.cos(b), ey + r * 0.1 * math.sin(b)
        s = r * 0.05
        d.ellipse([x - s, y - s, x + s, y + s], fill=stamen)

def monstera(img, cx, cy, size, angle, color, vein):
    """Split monstera leaf, drawn on its own layer so the slits can be cut out."""
    c = size
    layer = Image.new("RGBA", (2 * size, 2 * size), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.ellipse([c - size * 0.8, c - size * 0.72, c + size * 0.8, c + size * 0.78], fill=color)
    d.polygon([(c, c - size * 0.22), (c - size * 0.16, c - size * 0.8), (c + size * 0.16, c - size * 0.8)], fill=(0, 0, 0, 0))
    for side in (-1, 1):
        for k in range(5):
            y = c + size * (-0.42 + k * 0.27)
            d.line([(c + side * size * 0.3, y + size * 0.04), (c + side * size * 0.9, y - size * 0.14)],
                   fill=(0, 0, 0, 0), width=max(4, size // 13))
    d.line([(c, c - size * 0.22), (c, c + size * 0.76)], fill=vein, width=max(3, size // 28))
    layer = layer.rotate(angle, resample=Image.BICUBIC)
    img.alpha_composite(layer, (int(cx - c), int(cy - c)))

def flipflop(img, cx, cy, s, sole, strap, angle):
    c = int(s * 1.5)
    layer = Image.new("RGBA", (2 * c, 2 * c), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for off, col in ((s * 0.05, tuple(int(v * 0.7) for v in sole[:3]) + (255,)), (0, sole)):
        d.ellipse([c - s * 0.42, c - s + off, c + s * 0.42, c - s * 0.05 + off], fill=col)
        d.ellipse([c - s * 0.34, c + s * 0.05 + off, c + s * 0.34, c + s * 0.95 + off], fill=col)
        d.polygon([(c - s * 0.4, c - s * 0.45 + off), (c + s * 0.4, c - s * 0.45 + off),
                   (c + s * 0.3, c + s * 0.5 + off), (c - s * 0.3, c + s * 0.5 + off)], fill=col)
    post = (c, c - s * 0.62)
    for side in (-1, 1):
        d.line([post, (c + side * s * 0.38, c + s * 0.08)], fill=strap, width=int(s * 0.13))
    d.ellipse([c - s * 0.08, c - s * 0.7, c + s * 0.08, c - s * 0.54], fill=strap)
    layer = layer.rotate(angle, resample=Image.BICUBIC)
    shadow = Image.new("RGBA", layer.size, (0, 0, 0, 0))
    shadow.putalpha(layer.getchannel("A").point(lambda v: v * 0.35))
    img.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(10)), (cx - c + 14, cy - c + 18))
    img.alpha_composite(layer, (cx - c, cy - c))

def sunglasses(d, cx, cy, s, frame, lens):
    for side in (-1, 1):
        x = cx + side * s * 0.55
        d.rounded_rectangle([x - s * 0.45, cy - s * 0.32, x + s * 0.45, cy + s * 0.34], radius=s * 0.22, fill=frame)
        d.rounded_rectangle([x - s * 0.37, cy - s * 0.24, x + s * 0.37, cy + s * 0.26], radius=s * 0.17, fill=lens)
        d.line([x - s * 0.22, cy - s * 0.12, x - s * 0.05, cy - s * 0.2], fill=(255, 255, 255, 200), width=max(2, int(s * 0.06)))
        d.line([x + side * s * 0.45, cy - s * 0.2, x + side * s * 0.75, cy - s * 0.3], fill=frame, width=max(3, int(s * 0.08)))
    d.arc([cx - s * 0.16, cy - s * 0.2, cx + s * 0.16, cy + s * 0.08], 200, 340, fill=frame, width=max(3, int(s * 0.08)))

def beach_ball(d, cx, cy, r):
    cols = [(230, 50, 50), (255, 255, 255), (40, 120, 230), (255, 255, 255), (255, 200, 30), (255, 255, 255)]
    for k, col in enumerate(cols):
        d.pieslice([cx - r, cy - r, cx + r, cy + r], k * 60 - 90, k * 60 - 30, fill=rgba(col))
    d.ellipse([cx - r * 0.2, cy - r * 0.2, cx + r * 0.2, cy + r * 0.2], fill=rgba((255, 255, 255)))
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=(0, 0, 0, 60), width=3)
    d.chord([cx - r * 0.75, cy - r * 0.85, cx - r * 0.1, cy - r * 0.35], 180, 360, fill=(255, 255, 255, 90))

def wave_line(d, y, amp, period, phase, fill, width, x0=0, x1=W):
    pts = [(x, y + amp * math.sin(2 * math.pi * x / period + phase)) for x in range(x0, x1 + 1, 8)]
    d.line(pts, fill=fill, width=width, joint="curve")

def sand_texture(img, top, seed, base=(232, 212, 168)):
    rnd = np.random.default_rng(seed)
    h = H - top
    n = rnd.normal(0, 9, (h, W, 1)).astype(np.float32)
    arr = np.clip(np.array(base, np.float32)[None, None, :] + n, 0, 255).astype(np.uint8)
    img.paste(Image.fromarray(arr, "RGB").convert("RGBA"), (0, top))
    d = ImageDraw.Draw(img, "RGBA")
    for _ in range(int(W * h / 900)):
        x, y = rnd.integers(0, W), top + rnd.integers(0, h)
        c = (150, 120, 80, 140) if rnd.random() < 0.6 else (255, 250, 235, 180)
        d.point((int(x), int(y)), fill=c)

# ---------- 34: Hawaii Beach Day (realistic: sky, Diamond Head, sea, sand) ----------
def beach_day():
    slots = layout(top=480, bottom=360, gap=40)
    horizon = 380
    img = vgrad((52, 128, 214), (178, 218, 245))
    d = ImageDraw.Draw(img, "RGBA")
    sea = vgrad((18, 92, 150), (40, 190, 196))
    img.paste(sea.crop((0, horizon, W, H)), (0, horizon))
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse([80, 40, 300, 260], fill=(255, 250, 220, 255))
    img.alpha_composite(glow.filter(ImageFilter.GaussianBlur(40)))
    d.ellipse([150, 110, 230, 190], fill=rgba((255, 253, 235)))
    clouds = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    cd = ImageDraw.Draw(clouds)
    rnd = random.Random(34)
    for cx, cy in ((520, 120), (860, 70), (1080, 200)):
        for _ in range(7):
            w, h = rnd.randint(70, 150), rnd.randint(30, 60)
            ox, oy = rnd.randint(-110, 110), rnd.randint(-20, 20)
            cd.ellipse([cx + ox - w, cy + oy - h, cx + ox + w, cy + oy + h], fill=(255, 255, 255, 200))
    img.alpha_composite(clouds.filter(ImageFilter.GaussianBlur(14)))
    d = ImageDraw.Draw(img, "RGBA")
    # Diamond Head on the horizon, hazy with distance.
    ridge = [(560, horizon), (640, 330), (700, 300), (760, 262), (830, 250), (900, 270), (960, 236),
             (1020, 252), (1090, 300), (1160, 330), (1200, 336), (1200, horizon)]
    d.polygon(ridge, fill=rgba((96, 128, 118)))
    d.polygon([(x, y + 14) for x, y in ridge[1:-1]] + [(1200, horizon), (640, horizon)], fill=rgba((84, 114, 104)))
    d.line([0, horizon, W, horizon], fill=rgba((30, 100, 150)), width=3)
    # Sparkles and wave streaks on the water, busier towards the shore.
    rnd = random.Random(340)
    for _ in range(900):
        y = rnd.uniform(horizon + 6, H - 330)
        t = (y - horizon) / (H - horizon)
        ln = rnd.uniform(8, 40) * (0.4 + 2.5 * t)
        x = rnd.uniform(-20, W)
        d.line([x, y, x + ln, y], fill=(255, 255, 255, int(rnd.uniform(60, 160))), width=max(1, int(1 + 3 * t)))
    # Shore: wet sand, dry sand, foam.
    shore = H - 300
    sand_texture(img, shore, 34)
    d = ImageDraw.Draw(img, "RGBA")
    wet = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    wd = ImageDraw.Draw(wet)
    pts = [(x, shore + 70 + 18 * math.sin(x / 110)) for x in range(0, W + 1, 10)]
    wd.polygon([(0, shore)] + pts + [(W, shore)], fill=(150, 120, 80, 110))
    img.alpha_composite(wet.filter(ImageFilter.GaussianBlur(6)))
    d = ImageDraw.Draw(img, "RGBA")
    for k, a in ((0, 255), (1, 170), (2, 110)):
        wave_line(d, shore - 6 + 20 * k, 10, 180 + 40 * k, k * 1.7, (255, 255, 255, a), 14 - 3 * k)
    starfish(d, 230, H - 110, 52, rgba((236, 120, 62)), rgba((255, 200, 150)), rot=-80)
    shell(d, 960, H - 90, 46, rgba((250, 228, 208)), rgba((210, 160, 130)), rot=10)
    shell(d, 1050, H - 150, 30, rgba((245, 210, 190)), rgba((200, 150, 120)), rot=-20)
    palm(d, 40, horizon + 90, 360, 130, rgba((24, 52, 34)), seed=1)
    palm(d, 1190, horizon + 90, 300, -110, rgba((24, 52, 34)), seed=2)
    title = font("GreatVibes.ttf", 190)
    d.text((CX + 5, 255), "Hawaii", font=title, fill=(0, 40, 80, 120), anchor="mm")
    d.text((CX, 250), "Hawaii", font=title, fill=rgba((255, 255, 255)), anchor="mm")
    glow_lines(img, hole_rects(slots), (255, 255, 255), radius=18, width=4, blur=10)
    img.putalpha(255)  # translucent drawing above must not leave see-through spots
    cut(img, slots, inset=6, radius=14)
    return img, slots

# ---------- 35: Hawaii Sunset (realistic: sunset sky, sun on the water, palm silhouettes) ----------
def beach_sunset():
    slots = layout(top=330, bottom=520, gap=40)
    horizon = H - 250
    img = Image.new("RGBA", (W, H))
    d = ImageDraw.Draw(img, "RGBA")
    stops = [(0, (34, 26, 84)), (0.35, (112, 48, 128)), (0.62, (214, 82, 108)),
             (0.85, (250, 146, 74)), (1.0, (255, 214, 130))]
    for y in range(horizon):
        t = y / horizon
        for (t0, c0), (t1, c1) in zip(stops, stops[1:]):
            if t <= t1:
                k = (t - t0) / (t1 - t0)
                d.line([0, y, W, y], fill=tuple(int(a + (b - a) * k) for a, b in zip(c0, c1)) + (255,))
                break
    rnd = random.Random(35)
    for _ in range(120):  # first stars in the deep blue
        x, y = rnd.randint(0, W), rnd.randint(0, 700)
        s = rnd.choice([1, 1, 2])
        d.ellipse([x - s, y - s, x + s, y + s], fill=(255, 255, 255, rnd.randint(90, 220)))
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse([CX - 330, horizon - 330, CX + 330, horizon + 330], fill=(255, 190, 90, 200))
    img.alpha_composite(glow.filter(ImageFilter.GaussianBlur(70)))
    d = ImageDraw.Draw(img, "RGBA")
    d.ellipse([CX - 150, horizon - 150, CX + 150, horizon + 150], fill=rgba((255, 236, 170)))
    sea = vgrad((60, 36, 82), (24, 18, 46))
    img.paste(sea.crop((0, horizon, W, H)), (0, horizon))
    d = ImageDraw.Draw(img, "RGBA")
    for k in range(26):  # the sun's path on the water
        y = horizon + 8 + k * 9
        half = 150 * (1 - k / 30) * rnd.uniform(0.6, 1.0)
        off = rnd.uniform(-20, 20)
        d.line([CX - half + off, y, CX + half + off, y], fill=(255, 196, 110, int(220 * (1 - k / 32))), width=4)
    for x, y, s in ((300, H - 470, 22), (360, H - 500, 16), (860, H - 520, 18)):  # birds
        d.arc([x - s, y - s / 2, x, y + s / 2], 200, 340, fill=rgba((40, 20, 50)), width=4)
        d.arc([x, y - s / 2, x + s, y + s / 2], 200, 340, fill=rgba((40, 20, 50)), width=4)
    dark = rgba((22, 12, 30))
    d.polygon([(0, H), (0, horizon + 40), (260, horizon + 90), (420, H)], fill=dark)
    d.polygon([(W, H), (W, horizon + 60), (900, horizon + 110), (760, H)], fill=dark)
    palm(d, 110, horizon + 120, 330, 90, dark, frond_len=200, seed=5)
    palm(d, 40, horizon + 140, 240, 40, dark, frond_len=150, seed=6)
    palm(d, 1110, horizon + 130, 300, -90, dark, frond_len=190, seed=7)
    glow_lines(img, hole_rects(slots), (255, 214, 160), radius=18, width=3, blur=12)
    img.putalpha(255)  # translucent drawing above must not leave see-through spots
    cut(img, slots, inset=6, radius=14)
    d = ImageDraw.Draw(img, "RGBA")
    title = font("GreatVibes.ttf", 170)
    d.text((CX, 160), "Aloha", font=title, fill=rgba((255, 228, 190)), anchor="mm")
    return img, slots

# ---------- 36: Aloha Hibiscus (fun) ----------
def aloha_hibiscus():
    slots = layout(top=420, bottom=330, gap=44, x0=90, w=1020)
    img = vgrad((30, 196, 206), (14, 150, 180))
    rnd = random.Random(36)
    greens = [(26, 140, 74, 255), (40, 170, 90, 255), (18, 112, 62, 255)]
    spots = [(0, 0), (W, 0), (0, H), (W, H), (0, H // 3), (W, H // 3), (0, 2 * H // 3), (W, 2 * H // 3),
             (CX, H - 30), (CX - 300, 30), (CX + 320, 40)]
    for x, y in spots:
        monstera(img, x + rnd.randint(-40, 40), y + rnd.randint(-40, 40), rnd.randint(150, 230),
                 rnd.randint(0, 359), rnd.choice(greens), (10, 80, 44, 255))
    d = ImageDraw.Draw(img, "RGBA")
    pinks = [((255, 80, 120), (170, 20, 60)), ((255, 60, 60), (150, 10, 30)),
             ((255, 200, 60), (210, 90, 30)), ((255, 130, 170), (190, 40, 90))]
    for x, y in spots + [(0, H // 6), (W, H // 2), (0, H // 2), (W, 5 * H // 6)]:
        petal, dark = rnd.choice(pinks)
        hibiscus(d, x + rnd.randint(-30, 60) * (1 if x < CX else -1), y + rnd.randint(-60, 60),
                 rnd.randint(60, 95), rgba(petal), rgba(dark), angle=rnd.randint(0, 72))
    glow_lines(img, hole_rects(slots), (255, 255, 255), radius=26, width=6, blur=8)
    img.putalpha(255)  # translucent drawing above must not leave see-through spots
    cut(img, slots, inset=6, radius=22)
    d = ImageDraw.Draw(img, "RGBA")
    title = font("Pacifico.ttf", 170)
    d.text((CX, 200), "Aloha!", font=title, fill=rgba((255, 255, 255)), anchor="mm",
           stroke_width=12, stroke_fill=rgba((214, 40, 90)))
    fy = slots[-1][1] + slots[-1][3]
    d.text((CX, fy + 160), "from Hawaii", font=font("Pacifico.ttf", 84), fill=rgba((255, 255, 255)),
           anchor="mm", stroke_width=8, stroke_fill=rgba((14, 120, 150)))
    return img, slots

# ---------- 37: Flip Flops (fun) ----------
def flip_flops():
    slots = layout(top=470, bottom=480, gap=48, x0=80, w=1040)
    img = Image.new("RGBA", (W, H))
    sand_texture(img, 0, 37, base=(240, 220, 176))
    d = ImageDraw.Draw(img, "RGBA")
    for x, y, w, h in slots:  # white instant-photo borders with a soft shadow
        sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(sh).rectangle([x - 14, y - 4, x + w + 26, y + h + 30], fill=(80, 60, 30, 110))
        img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(12)))
        d.rectangle([x - 20, y - 20, x + w + 19, y + h + 19], fill=rgba((255, 255, 255)))
    rnd = random.Random(37)
    for (x, y, w, h), nxt in zip(slots, slots[1:]):  # little treasures between the photos
        gy = (y + h + nxt[1]) // 2
        if rnd.random() < 0.5:
            starfish(d, rnd.choice([40, W - 40]), gy, 30, rgba((240, 120, 70)), rgba((255, 200, 160)), rot=rnd.randint(0, 72))
        else:
            shell(d, rnd.choice([40, W - 40]), gy + 10, 26, rgba((255, 230, 214)), rgba((210, 160, 130)), rot=rnd.randint(-30, 30))
    beach_ball(d, 170, 170, 115)
    sunglasses(d, 1000, 120, 120, rgba((30, 30, 34)), rgba((40, 150, 190)))
    title = font("Pacifico.ttf", 120)
    d.text((CX + 60, 300), "Life's a Beach", font=title, fill=rgba((255, 110, 90)), anchor="mm",
           stroke_width=8, stroke_fill=rgba((255, 255, 255)))
    img.putalpha(255)  # translucent drawing above must not leave see-through spots
    cut(img, slots, inset=0, radius=0)
    fy = slots[-1][1] + slots[-1][3]
    flipflop(img, 470, fy + 250, 150, rgba((255, 110, 90)), rgba((30, 170, 190)), angle=12)
    flipflop(img, 730, fy + 230, 150, rgba((255, 110, 90)), rgba((30, 170, 190)), angle=-8)
    d = ImageDraw.Draw(img, "RGBA")
    starfish(d, 170, fy + 300, 70, rgba((240, 120, 70)), rgba((255, 200, 160)), rot=-60)
    shell(d, 1030, fy + 330, 60, rgba((255, 228, 210)), rgba((210, 160, 130)), rot=8)
    return img, slots

DESIGNS = [(11, "Deco Silver", deco_silver), (12, "Deco Gold Ivory", deco_ivory), (13, "Deco Gold Black", deco_black),
           (14, "Black Tie", black_tie), (15, "The Gown", the_gown), (16, "Garden Party", garden),
           (17, "Just Married", just_married), (18, "Champagne Toast", champagne), (19, "Film Reel", film_reel),
           (20, "Seventies", seventies), (21, "Synthwave", synthwave), (22, "Pop Dots", pop_dots),
           (23, "Memphis", memphis), (24, "Checkerboard", checker), (25, "Cosmos", cosmos),
           (26, "Mall Booth White", mall_white), (27, "Mall Booth Black", mall_black),
           (30, "Baby Pink", baby_pink), (31, "Baby Blue", baby_blue),
           (32, "Army Camo", army_camo), (33, "Army Black & Gold", army_gold),
           (34, "Hawaii Beach Day", beach_day), (35, "Hawaii Sunset", beach_sunset),
           (36, "Aloha Hibiscus", aloha_hibiscus), (37, "Flip Flops", flip_flops),
           (38, "Army Woodland", army_woodland), (39, "Army Stars & Stripes", army_stars_stripes),
           (40, "Army Ammo Crate", army_crate)]

if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    only = {int(a) for a in sys.argv[1:]}
    for n, label, fn in DESIGNS:
        if only and n not in only:
            continue
        img, slots = fn()
        save(img, slots, n)
        print(f"frame{n}: {label}")
