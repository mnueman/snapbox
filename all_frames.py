"""All custom photobooth strip frames.
Generates frame11 (Deco Silver), the Atkinsons wedding set (frame12..frame19),
and the fun set (frame20..frame25) (1200x3600 PNG with transparent photo openings + slot JSON).
Usage (from the photobooth folder): python3 wedding_collection.py
"""
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import datetime, json, math, os, random, urllib.request

NAME = "The   Atkinsons"
# Date for the disposable-camera stamp frames. Change to the event date, e.g. "'27 06 14"
DATE_STAMP = datetime.date.today().strftime("'%y %m %d")
OUT = "frames"
W, H = 1200, 3600
CX = W // 2
FONT_URLS = {
    "GreatVibes.ttf": "https://raw.githubusercontent.com/google/fonts/main/ofl/greatvibes/GreatVibes-Regular.ttf",
    "Limelight.ttf": "https://raw.githubusercontent.com/google/fonts/main/ofl/limelight/Limelight-Regular.ttf",
    "PoiretOne.ttf": "https://raw.githubusercontent.com/google/fonts/main/ofl/poiretone/PoiretOne-Regular.ttf",
    "VT323.ttf": "https://raw.githubusercontent.com/google/fonts/main/ofl/vt323/VT323-Regular.ttf",
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
def plain_strip(bg, stamp=False):
    slots = layout(top=60, bottom=180, gap=40)
    img = Image.new("RGBA", (W, H), rgba(bg))
    cut(img, slots, inset=0, radius=0)
    if stamp:
        over = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        o = ImageDraw.Draw(over)
        f = font("VT323.ttf", 64)
        for x, y, w, h in slots:
            o.text((x + w - 40, y + h - 36), DATE_STAMP, font=f, fill=(255, 140, 30, 255), anchor="rs")
        img.alpha_composite(over.filter(ImageFilter.GaussianBlur(4)))
        img.alpha_composite(over)
    return img, slots

def mall_white():
    return plain_strip((255, 255, 255))

def mall_black():
    return plain_strip((10, 10, 10))

def stamp_white():
    return plain_strip((255, 255, 255), stamp=True)

def stamp_black():
    return plain_strip((10, 10, 10), stamp=True)

def baby_pink():
    return plain_strip((255, 209, 220))

def baby_blue():
    return plain_strip((190, 222, 255))

DESIGNS = [(11, "Deco Silver", deco_silver), (12, "Deco Gold Ivory", deco_ivory), (13, "Deco Gold Black", deco_black),
           (14, "Black Tie", black_tie), (15, "The Gown", the_gown), (16, "Garden Party", garden),
           (17, "Just Married", just_married), (18, "Champagne Toast", champagne), (19, "Film Reel", film_reel),
           (20, "Seventies", seventies), (21, "Synthwave", synthwave), (22, "Pop Dots", pop_dots),
           (23, "Memphis", memphis), (24, "Checkerboard", checker), (25, "Cosmos", cosmos),
           (26, "Mall Booth White", mall_white), (27, "Mall Booth Black", mall_black),
           (28, "Date Stamp White", stamp_white), (29, "Date Stamp Black", stamp_black),
           (30, "Baby Pink", baby_pink), (31, "Baby Blue", baby_blue)]

if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    for n, label, fn in DESIGNS:
        img, slots = fn()
        save(img, slots, n)
        print(f"frame{n}: {label}")
