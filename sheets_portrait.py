"""Portrait BIG SHEET designs (4x6, 1200x1800, portrait photos). Each returns
(image, slots, extra JSON) and is listed in DESIGNS at the bottom."""
import math, random
from PIL import Image, ImageDraw, ImageFilter

import all_frames as af
from all_frames import font, rgba, bold, star_points, army_star, spaced_text, camo, OCP_BASE, OCP_LAYERS, \
    ARMY_GOLD, ARMY_BLACK, ARMY_WHITE, hibiscus, sparkle, heart, bowtie, dress, flower, leaf, dog_tag, ball_chain, \
    WOODLAND_BASE, WOODLAND_LAYERS
from sheet_kit import *
import realistic
import sheets_landscape as SL

W, H = P
CX, CY = W // 2, H // 2


# ---------- Gallery White (4) ----------
def gallery_white():
    slots = grid(2, 2, 70, 70, W - 70, H - 190, 44)
    img = new(P, (252, 251, 248))
    d = draw(img)
    for x, y, w, h in slots:
        d.rectangle((x - 14, y - 14, x + w + 13, y + h + 13), outline=rgba((200, 198, 192)), width=2)
    spaced_text(d, (CX, H - 95), "MEMORIES", font("PoiretOne.ttf", 64), rgba((60, 60, 60)), 22)
    return cut(img, slots), slots, {}


# ---------- Instax wall (4) ----------
def instax_wall():
    img = noise(P, (150, 104, 66), 8, 202)
    d = draw(img)
    for y in range(0, H, 150):  # wooden planks
        d.line((0, y, W, y), fill=rgba((96, 62, 36)), width=6)
        rnd = random.Random(y)
        for k in range(18):
            yy = y + rnd.uniform(10, 140)
            d.line((0, yy, W, yy + rnd.uniform(-6, 6)), fill=(110, 70, 40, 60), width=2)
    vignette(img, 0.5, (40, 24, 10))
    slots = []
    pw, ph = 400, 540
    rows = [(150, [(150, 0), (650, 0)]), (930, [(150, 0), (650, 0)])]
    for k, (ty, cards) in enumerate(rows):
        d = draw(img)
        d.line([(0, ty - 30), (W / 2, ty + 10), (W, ty - 30)], fill=rgba((230, 220, 190)), width=5, joint="curve")  # twine
        for j, (x, _) in enumerate(cards):
            y = ty + 50
            card = (x - 25, y - 35, x + pw + 25, y + ph + 110)
            shadow(img, card, offset=(8, 14), blur=12, alpha=140)
            d = draw(img)
            d.rectangle(card, fill=rgba((252, 252, 248)))
            cx = x + pw / 2
            d.rectangle((cx - 16, ty - 40, cx + 16, y + 10), fill=rgba((206, 170, 120)))  # clothespin
            d.rectangle((cx - 16, ty - 40, cx + 16, y + 10), outline=rgba((150, 116, 70)), width=2)
            d.ellipse((cx - 8, ty - 6, cx + 8, ty + 10), fill=rgba((160, 160, 170)))
            d.text((cx, y + ph + 60), ["summer!", "us <3", "golden hour", "the crew"][k * 2 + j], font=vfont("Caveat.ttf", 52, 600),
                   fill=rgba((50, 50, 90)), anchor="mm")
            slots.append([x, y, pw, ph])
    glows = layer(img)
    gd = ImageDraw.Draw(glows)
    for k in range(13):  # fairy lights along the top twine
        x = k * 100 + 20
        y = 120 + 40 * math.sin(math.pi * k / 12)
        gd.ellipse((x - 22, y - 22, x + 22, y + 22), fill=(255, 220, 140, 150))
    img.alpha_composite(glows.filter(ImageFilter.GaussianBlur(14)))
    d = draw(img)
    for k in range(13):
        x = k * 100 + 20
        y = 120 + 40 * math.sin(math.pi * k / 12)
        d.ellipse((x - 9, y - 9, x + 9, y + 9), fill=rgba((255, 246, 210)))
    d.line([(k * 100 + 20, 120 + 40 * math.sin(math.pi * k / 12)) for k in range(13)], fill=rgba((60, 60, 50)), width=3)
    return cut(img, slots), slots, {}


# ---------- Victorian cabinet card (2) ----------
def cabinet_card():
    img = noise(P, (60, 40, 30), 6, 203)
    d = draw(img)
    card = (70, 70, W - 70, H - 70)
    shadow(img, card, offset=(10, 16), blur=16, alpha=160)
    d = draw(img)
    d.rectangle(card, fill=rgba((206, 186, 150)))
    inner = (110, 110, W - 110, H - 110)
    d.rectangle(inner, outline=rgba((160, 120, 60)), width=6)
    d.rectangle((124, 124, W - 124, H - 124), outline=rgba((190, 150, 80)), width=2)
    for cx, cy in ((124, 124), (W - 124, 124), (124, H - 124), (W - 124, H - 124)):
        for k in range(4):
            a = math.pi / 2 * k + math.pi / 4
            leaf(d, cx + 18 * math.cos(a), cy + 18 * math.sin(a), 40, 14, math.degrees(a), rgba((160, 120, 60)))
    slots = grid(2, 2, 190, 220, W - 190, 1340, 50, 50)
    for x, y, w, h in slots:
        d.rounded_rectangle((x - 14, y - 14, x + w + 14, y + h + 14), radius=34, fill=rgba((120, 90, 50)))
    d.text((CX, 1450), "The Photo Booth Studio", font=font("GreatVibes.ttf", 100), fill=rgba((110, 74, 30)), anchor="mm")
    spaced_text(d, (CX, 1560), "FINE PORTRAITS  ·  HONOLULU", vfont("Cinzel.ttf", 36, 700), rgba((110, 74, 30)), 6)
    d.text((CX, 1630), "Duplicates may always be had", font=font("OldStandard.ttf", 26), fill=rgba((130, 96, 50)), anchor="mm")
    img = cut(img, slots, radius=24)
    over = layer(img)  # warm sepia age tone over the photos
    od = ImageDraw.Draw(over)
    for x, y, w, h in slots:
        od.rounded_rectangle((x, y, x + w, y + h), radius=24, fill=(120, 80, 30, 38))
    img.alpha_composite(over)
    return img, slots, {}


# ---------- Magazine cover (3) ----------
def magazine_cover():
    slots = [[0, 0, W, H]]
    insets = [[830, 960, 300, 380], [830, 1370, 300, 380]]
    img = new(P, (255, 255, 255))
    for x, y, w, h in insets:
        draw(img).rectangle((x - 10, y - 10, x + w + 10, y + h + 10), fill=rgba((255, 255, 255)))
    # The cover photo shows everywhere except the insets' white borders.
    img.putalpha(255)
    m = Image.new("L", P, 0)
    md = ImageDraw.Draw(m)
    for x, y, w, h in insets:
        md.rectangle((x - 10, y - 10, x + w + 9, y + h + 9), fill=255)
        md.rectangle((x, y, x + w - 1, y + h - 1), fill=0)
    img.putalpha(m)
    shade = layer(img)
    sd = ImageDraw.Draw(shade)
    for y in range(320):
        sd.line((0, y, W, y), fill=(0, 0, 0, int(150 * (1 - y / 320))))
    for x in range(500):
        sd.line((x, 400, x, H), fill=(0, 0, 0, int(80 * (1 - x / 500))))
    img.alpha_composite(shade)
    d = draw(img)
    d.text((CX, 30), "SNAP", font=bold("Oswald.ttf", 300, 700), fill=rgba((235, 30, 60)), anchor="mt")
    d.text((CX, 380), "THE PHOTO BOOTH ISSUE  ·  OCTOBER", font=bold("Oswald.ttf", 40, 500), fill=rgba((255, 255, 255)), anchor="mm")
    lines = [("EXCLUSIVE", "Inside the most", "fun night ever"), ("STYLE", "Who wore it", "best? (You.)"),
             ("10 WAYS", "to strike the", "perfect pose")]
    y = 520
    for head, a, b in lines:
        for txt, f, col, dy in ((head, bold("Oswald.ttf", 64, 700), (255, 210, 40), 0),
                                (a, bold("Oswald.ttf", 42, 400), (255, 255, 255), 76),
                                (b, bold("Oswald.ttf", 42, 400), (255, 255, 255), 124)):
            d.text((60, y + dy), txt, font=f, fill=rgba(col), anchor="lt", stroke_width=3, stroke_fill=(0, 0, 0, 160))
        y += 230
    d.text((830, 935), "ALSO INSIDE:", font=bold("Oswald.ttf", 34, 700), fill=rgba((255, 210, 40)), anchor="lb",
           stroke_width=2, stroke_fill=(0, 0, 0, 160))
    bx, by = 60, H - 170
    d.rectangle((bx - 20, by - 20, bx + 240, by + 130), fill=rgba((255, 255, 255)))
    rnd = random.Random(204)
    x = bx
    while x < bx + 220:
        w = rnd.choice([2, 3, 5])
        d.rectangle((x, by, x + w, by + 90), fill=rgba((0, 0, 0)))
        x += w + rnd.choice([2, 3, 4])
    d.text((bx + 110, by + 110), "0 26100 00001 8", font=font("VT323.ttf", 28), fill=rgba((0, 0, 0)), anchor="mm")
    # Slot 1 is the whole cover, under the insets; the stamp goes top right, clear of the barcode.
    return img, slots + insets, {"stamp": "tr"}


# ---------- Movie poster (3) ----------
def movie_poster():
    img = vgrad(P, [(0, (10, 10, 20)), (0.6, (30, 20, 40)), (1, (8, 8, 12))])
    d = draw(img)
    rays = layer(img)
    rd = ImageDraw.Draw(rays)
    for k in range(9):  # searchlights
        a = math.radians(-120 + k * 8)
        rd.polygon([(CX, H * 0.62), (CX + 2000 * math.cos(a - 0.03), H * 0.62 + 2000 * math.sin(a - 0.03)),
                    (CX + 2000 * math.cos(a + 0.03), H * 0.62 + 2000 * math.sin(a + 0.03))], fill=(255, 230, 180, 22))
    img.alpha_composite(rays.filter(ImageFilter.GaussianBlur(8)))
    d = draw(img)
    d.text((CX, 90), "THIS FALL... IT'S PICTURE DAY", font=font("Bebas.ttf", 56), fill=rgba((230, 220, 200)), anchor="mm")
    slots = grid(3, 1, 80, 180, W - 80, 640, 30)
    for x, y, w, h in slots:
        d.rectangle((x - 4, y - 4, x + w + 3, y + h + 3), fill=rgba((0, 0, 0)))
    gradient_text(img, (CX, 830), "THE PHOTO", font("Bebas.ttf", 230), GOLD_LEAF, shadow_offset=(8, 10), stroke_fill=(0, 0, 0))
    gradient_text(img, (CX, 1050), "BOOTH", font("Bebas.ttf", 300), GOLD_LEAF, shadow_offset=(8, 10), stroke_fill=(0, 0, 0))
    d = draw(img)
    d.text((CX, 1250), "Some memories are worth framing.", font=font("OldStandard.ttf", 44), fill=rgba((230, 220, 200)), anchor="mm")
    billing = ("A PHOTO BOOTH PRODUCTION  STARRING THE BEST CREW  WITH SPECIAL GUEST THE FLASH  MUSIC BY THE PLAYLIST  "
               "EDITED BY NOBODY  DIRECTOR OF PHOTOGRAPHY THE SELF TIMER  PRODUCED BY GOOD VIBES  WRITTEN AND DIRECTED BY YOU")
    f = font("Bebas.ttf", 34)
    words, lines, cur = billing.split(), [], ""
    for wd in words:
        if d.textlength(cur + " " + wd, font=f) > W - 200:
            lines.append(cur)
            cur = wd
        else:
            cur = (cur + " " + wd).strip()
    lines.append(cur)
    for k, line in enumerate(lines):
        d.text((CX, 1400 + k * 40), line, font=f, fill=rgba((200, 190, 170)), anchor="mm")
    d.text((CX, H - 70), "COMING SOON", font=font("Bebas.ttf", 70), fill=rgba((255, 255, 255)), anchor="mm")
    return cut(img, slots), slots, {}


# ---------- Trading cards (4) ----------
def trading_cards():
    img = noise(P, (30, 70, 40), 6, 206)
    d = draw(img)
    for y in range(0, H, 90):  # outfield turf stripes
        d.rectangle((0, y, W, y + 45), fill=(255, 255, 255, 12))
    teams = [((200, 40, 40), "SMILERS"), ((30, 70, 170), "POSERS"), ((240, 160, 20), "FLASHERS"), ((40, 140, 90), "CANDIDS")]
    slots = []
    cw, ch = 500, 780
    for k, (cx0, cy0) in enumerate(((70, 80), (630, 80), (70, 940), (630, 940))):
        colour, team = teams[k]
        card = (cx0, cy0, cx0 + cw, cy0 + ch)
        shadow(img, card, offset=(8, 14), blur=12, alpha=150, radius=20)
        d = draw(img)
        d.rounded_rectangle(card, radius=20, fill=rgba((250, 248, 240)))
        d.rounded_rectangle((cx0 + 18, cy0 + 18, cx0 + cw - 18, cy0 + ch - 18), radius=12, fill=rgba(colour))
        px, py, pw, ph = cx0 + 40, cy0 + 40, cw - 80, 560
        d.rectangle((px - 6, py - 6, px + pw + 6, py + ph + 6), fill=rgba((250, 248, 240)))
        slots.append([px, py, pw, ph])
        d.polygon([(cx0 + 18, cy0 + 620), (cx0 + cw - 18, cy0 + 600), (cx0 + cw - 18, cy0 + 690), (cx0 + 18, cy0 + 710)],
                  fill=rgba((250, 248, 240)))
        d.text((cx0 + cw / 2, cy0 + 655), f"#{k + 1}  {team}", font=bold("Oswald.ttf", 48, 700), fill=rgba(colour), anchor="mm")
        d.text((cx0 + cw / 2, cy0 + 735), "ROOKIE  ·  2026", font=bold("Oswald.ttf", 30, 500), fill=rgba((255, 255, 255)), anchor="mm")
        d.ellipse((cx0 + cw - 120, cy0 + 500, cx0 + cw - 30, cy0 + 590), fill=rgba((255, 210, 40)), outline=rgba((0, 0, 0)), width=3)
        d.polygon(star_points(cx0 + cw - 75, cy0 + 545, 30), fill=rgba(colour))
    return cut(img, slots), slots, {"stamp": "tl"}


# ---------- Wanted poster (2) ----------
def wanted():
    img = noise(P, (90, 60, 36), 8, 207)  # weathered wood behind
    d = draw(img)
    for x in range(0, W, 200):
        d.line((x, 0, x, H), fill=rgba((60, 40, 24)), width=8)
    vignette(img, 0.6)
    sheet = paper((W - 120, H - 120), (226, 204, 160), 208, amount=9, stains=4)
    m = Image.new("L", sheet.size, 0)  # torn edges
    md = ImageDraw.Draw(m)
    rnd = random.Random(208)
    sw, sh = sheet.size
    pts = [(rnd.uniform(0, 14), y) for y in range(0, sh, 30)] + [(x, sh - rnd.uniform(0, 14)) for x in range(0, sw, 30)]
    pts += [(sw - rnd.uniform(0, 14), y) for y in range(sh, 0, -30)] + [(x, rnd.uniform(0, 14)) for x in range(sw, 0, -30)]
    md.polygon(pts, fill=255)
    sheet.putalpha(m)
    shadow(img, (60, 60, W - 60, H - 60), offset=(10, 14), blur=14, alpha=170)
    img.alpha_composite(sheet, (60, 60))
    d = draw(img)
    ink = (60, 34, 20, 255)
    d.text((CX, 250), "WANTED", font=font("Rye.ttf", 230), fill=ink, anchor="mm")
    d.text((CX, 420), "FOR HAVING TOO MUCH FUN", font=font("Rye.ttf", 56), fill=ink, anchor="mm")
    d.line((140, 480, W - 140, 480), fill=ink, width=4)
    slots = grid(2, 1, 150, 530, W - 150, 1130, 60)
    for x, y, w, h in slots:
        d.rectangle((x - 8, y - 8, x + w + 7, y + h + 7), outline=ink, width=6)
    d.text((CX, 1240), "DEAD OR ALIVE  ·  PREFERABLY SMILING", font=font("Rye.ttf", 40), fill=ink, anchor="mm")
    d.text((CX, 1390), "REWARD", font=font("Rye.ttf", 120), fill=ink, anchor="mm")
    d.text((CX, 1540), "$1,000,000", font=font("Rye.ttf", 130), fill=rgba((150, 30, 20)), anchor="mm")
    d.text((CX, 1660), "Last seen at the photo booth", font=font("SpecialElite.ttf", 36), fill=ink, anchor="mm")
    for nx, ny in ((110, 110), (W - 110, 110), (110, H - 110), (W - 110, H - 110)):  # nails
        d.ellipse((nx - 14, ny - 14, nx + 14, ny + 14), fill=rgba((90, 90, 96)))
        d.ellipse((nx - 6, ny - 9, nx + 2, ny - 1), fill=(220, 220, 230, 200))
    img = cut(img, slots)
    over = layer(img)
    ImageDraw.Draw(over).rectangle((0, 0, W, H), fill=(140, 100, 40, 30))  # sepia on the photos
    over.putalpha(Image.composite(over.getchannel("A"), Image.new("L", P, 0), Image.eval(img.getchannel("A"), lambda a: 255 - a)))
    img.alpha_composite(over)
    return img, slots, {}


# ---------- Tarot cards (2) ----------
def tarot_card(img, box, title, numeral, symbol):
    x0, y0, x1, y1 = box
    gold = (214, 176, 96)
    shadow(img, box, offset=(10, 16), blur=14, alpha=170, radius=24)
    d = draw(img)
    d.rounded_rectangle(box, radius=24, fill=rgba((24, 20, 46)))
    d.rounded_rectangle((x0 + 16, y0 + 16, x1 - 16, y1 - 16), radius=16, outline=rgba(gold), width=4)
    d.rounded_rectangle((x0 + 28, y0 + 28, x1 - 28, y1 - 28), radius=12, outline=rgba(gold), width=1)
    rnd = random.Random(numeral)
    for _ in range(60):
        sx, sy = rnd.uniform(x0 + 40, x1 - 40), rnd.uniform(y0 + 40, y1 - 40)
        d.ellipse((sx - 2, sy - 2, sx + 2, sy + 2), fill=(255, 240, 200, rnd.randint(80, 200)))
    cx = (x0 + x1) / 2
    d.text((cx, y0 + 80), numeral, font=vfont("Cinzel.ttf", 56, 700), fill=rgba(gold), anchor="mm")
    symbol(d, cx, y0 + 175)
    d.text((cx, y1 - 90), title, font=vfont("Cinzel.ttf", 60, 700), fill=rgba(gold), anchor="mm")
    for s in (-1, 1):
        d.line((cx + s * 60, y1 - 150, cx + s * 180, y1 - 150), fill=rgba(gold), width=2)
    pw = x1 - x0 - 120
    return (x0 + 60, y0 + 250, x1 - 60, y0 + 250 + pw * 4 // 3)


def tarot():
    img = noise(P, (14, 10, 26), 5, 209)
    d = draw(img)
    rnd = random.Random(209)
    for _ in range(300):
        x, y = rnd.uniform(0, W), rnd.uniform(0, H)
        d.ellipse((x - 1.5, y - 1.5, x + 1.5, y + 1.5), fill=(255, 255, 255, rnd.randint(60, 200)))
    gold = (214, 176, 96, 255)

    def sun(d, cx, cy):
        d.ellipse((cx - 40, cy - 40, cx + 40, cy + 40), fill=gold)
        for k in range(16):
            a = math.tau * k / 16
            d.line((cx + 52 * math.cos(a), cy + 52 * math.sin(a), cx + 74 * math.cos(a), cy + 74 * math.sin(a)), fill=gold, width=5)

    def star(d, cx, cy):
        d.polygon(star_points(cx, cy, 70, inner=0.4), fill=gold)
        for k in range(6):
            a = math.tau * k / 6
            sparkle(d, cx + 95 * math.cos(a), cy + 70 * math.sin(a), 12, gold)

    slots = []
    for box, title, num, sym in (((70, 200, 580, 1240), "THE SUN", "XIX", sun), ((620, 200, 1130, 1240), "THE STAR", "XVII", star)):
        x0, y0, x1, y1 = tarot_card(img, box, title, num, sym)
        slots.append([int(x0), int(y0), int(x1 - x0), int(y1 - y0)])
    d = draw(img)
    for k in range(12):  # a zodiac ring of little stars under the cards
        a = math.tau * k / 12
        sparkle(d, CX + 380 * math.cos(a), 1530 + 120 * math.sin(a), 10, gold)
    d.text((CX, 1530), "your future: more photos", font=font("GreatVibes.ttf", 80), fill=gold, anchor="mm")
    d.ellipse((CX - 30, 50, CX + 30, 110), outline=gold, width=4)  # crescent
    d.ellipse((CX - 14, 44, CX + 40, 104), fill=rgba((14, 10, 26)))
    return cut(img, slots, radius=8), slots, {}


# ---------- Newspaper (3) ----------
def newspaper():
    slots = [[60, 450, 700, 900], [800, 450, 340, 440], [800, 960, 340, 440]]
    img, d, ink = SL.newspaper(P, slots, 210, "BEST NIGHT EVER", "Booth reports record smiles; experts baffled")
    for x, y, w, h in slots:
        d.rectangle((x - 4, y - 4, x + w + 3, y + h + 3), outline=ink, width=3)
    cap = font("OldStandard.ttf", 24)
    d.text((60, 1385), "ABOVE: The moment it all began.", font=cap, fill=ink, anchor="lm")
    d.text((800, 1430), "More photos, page 2", font=cap, fill=ink, anchor="lm")
    d.line((50, 1460, W - 50, 1460), fill=ink, width=2)
    d.text((60, 1495), "WEATHER: 100% CHANCE OF FUN", font=font("OldStandardBold.ttf", 30), fill=ink, anchor="lm")
    fake_text(d, (60, 1530, 580, H - 60), 26, (70, 66, 60, 255), 211)
    fake_text(d, (620, 1530, W - 60, H - 60), 26, (70, 66, 60, 255), 212)
    return cut(img, slots), slots, {}


# ---------- Passport (2) ----------
def passport():
    img = SL.passport_spread(P, 213)
    d = draw(img)
    navy = (30, 40, 80, 255)
    d.text((70, 80), "PASSPORT", font=vfont("Cinzel.ttf", 64, 700), fill=navy, anchor="lm")
    d.text((70, 140), "PASSEPORT  ·  PASAPORTE", font=font("OldStandard.ttf", 28), fill=navy, anchor="lm")
    army_like = (W - 150, 110)
    d.ellipse((army_like[0] - 70, army_like[1] - 70, army_like[0] + 70, army_like[1] + 70), outline=navy, width=4)
    d.polygon(star_points(*army_like, 46), fill=navy)
    slots = [[80, 220, 450, 600], [650, 1050, 470, 560]]
    label, value = font("OldStandard.ttf", 24), font("SpecialElite.ttf", 36)
    y = 230
    for lab, val in (("Type", "P"), ("Surname / Nom", "PHOTOBOOTH"), ("Given names", "THE BEST"), ("", "CREW"),
                     ("Nationality", "FUN"), ("Date of issue", "TODAY"), ("Authority", "THE BOOTH")):
        if lab:
            d.text((580, y), lab, font=label, fill=navy, anchor="lt")
        d.text((580, y + 28), val, font=value, fill=rgba((20, 20, 20)), anchor="lt")
        y += 84
    d.rectangle((60, 860, W - 60, 990), fill=(255, 255, 255, 120))
    mrz = font("VT323.ttf", 46)
    d.text((76, 895), "P<FUNPHOTOBOOTH<<THE<BEST<CREW<<<", font=mrz, fill=rgba((20, 20, 20)), anchor="lm")
    d.text((76, 955), "2610260FUN<<<<<<<<<<<<<<<<<<<<06", font=mrz, fill=rgba((20, 20, 20)), anchor="lm")
    d.rounded_rectangle((610, 1020, W - 50, H - 60), radius=16, fill=(255, 250, 240, 200), outline=navy, width=3)
    d.text((630, 1640), "VISA · ENTRY PERMIT", font=vfont("Cinzel.ttf", 30, 700), fill=navy, anchor="lm")
    mat(img, slots, 6, (255, 255, 255), drop=False)
    img = cut(img, slots)
    rubber_stamp(img, (300, 1250), 140, ["ADMITTED", "HONOLULU", "OCT 2026"], (180, 30, 40, 230), 14, 4)
    rubber_stamp(img, (300, 1580), 110, ["ARRIVED", "PHOTO BOOTH", "★"], (30, 70, 160, 220), -10, 5)
    rubber_stamp(img, (450, 760), 90, ["APPROVED", "★ FUN ★"], (40, 120, 70, 210), -18, 6, box=True)
    return img, slots, {}


# ---------- Museum wall (3) ----------
def museum_wall():
    img = SL.damask(P, (24, 48, 44), (32, 62, 56, 255), 214)
    vignette(img, 0.6, (6, 14, 12))
    for x in (CX,):
        light = layer(img)
        ImageDraw.Draw(light).polygon([(x - 50, 0), (x + 50, 0), (x + 420, 1100), (x - 420, 1100)], fill=(255, 230, 180, 50))
        img.alpha_composite(light.filter(ImageFilter.GaussianBlur(50)))
    slots = [[310, 150, 580, 760], [150, 1140, 360, 460], [690, 1140, 360, 460]]
    for s in slots:
        gold_frame(img, s, 70 if s[2] > 450 else 52)
    plaque(img, (CX, 1015), "PORTRAIT OF JOY", "Oil on photo booth, 2026")
    plaque(img, (330, 1700), "NO. 1", w=180, h=56)
    plaque(img, (870, 1700), "NO. 2", w=180, h=56)
    return cut(img, slots), slots, {}


# ---------- Our favorite day (4) ----------
def favorite_day():
    slots = [[90, 260, 480, 620], [660, 230, 450, 600], [140, 1020, 430, 560], [650, 980, 460, 600]]
    return SL.favorite_day(P, slots, 215)


# ---------- Arcade ----------
def pac_maze():
    return SL.pac_maze(P, grid(2, 2, 170, 330, W - 170, 1500, 150, 140))


def invaders():
    return SL.invaders(P, grid(3, 1, 90, 720, W - 90, 1190, 50), rows=5)


def falling_blocks():
    img = new(P, (16, 16, 40))
    d = draw(img)
    s = 50
    for x in range(0, W, s):
        d.line((x, 0, x, H), fill=(255, 255, 255, 14), width=2)
    for y in range(0, H, s):
        d.line((0, y, W, y), fill=(255, 255, 255, 14), width=2)
    pa = font("PressStart.ttf", 30)
    d.rectangle((40, 40, W - 40, 230), fill=rgba((8, 8, 24)), outline=rgba((200, 200, 230)), width=6)
    for k, (lab, val) in enumerate((("SCORE", "026100"), ("LINES", "42"), ("LEVEL", "09"))):
        d.text((80 + k * 330, 100), lab, font=pa, fill=rgba((255, 255, 255)), anchor="lm")
        d.text((80 + k * 330, 160), val, font=font("PressStart.ttf", 38), fill=rgba((255, 220, 60)), anchor="lm")
    slots = grid(2, 2, 110, 300, W - 110, 1430, 60, 50)
    tetromino(d, "T", 60, 250, s)
    tetromino(d, "I", 500, 250, s, 0)
    tetromino(d, "Z", 980, 240, s)
    rnd = random.Random(216)
    kinds = list(TETROMINOES)
    for col in range(0, W // s):
        height = rnd.choice([4, 5, 5, 6, 6, 7])
        for r in range(height):
            if r == 3 and col % 7 == 3:
                continue  # a gap waiting for the I piece
            bevel_block(d, col * s, H - (r + 1) * s, s, TETROMINOES[rnd.choice(kinds)][1])
    for x, y, sw, sh in slots:
        d.rectangle((x - 12, y - 12, x + sw + 11, y + sh + 11), fill=rgba((230, 230, 250)))
    return cut(img, slots), slots, {}


# ---------- Hawaii travel poster (2) ----------
def hawaii_poster():
    img = SL.travel_poster(P, None, 217, 190)
    d = draw(img)
    spaced_text(d, (CX, 340), "FLY TO THE ISLANDS OF ALOHA", vfont("Cinzel.ttf", 42, 700), rgba((255, 240, 210)), 6)
    slots = grid(2, 1, 120, 430, W - 120, 1000, 50)
    mat(img, slots, 14, (250, 240, 220))
    d = draw(img)
    d.rectangle((26, 26, W - 27, H - 27), outline=rgba((250, 240, 220)), width=10)
    d.text((CX, H - 80), "PAN-PACIFIC PHOTO BOOTH LINES", font=vfont("Cinzel.ttf", 34, 600), fill=rgba((250, 240, 220)), anchor="mm")
    return cut(img, slots), slots, {}


# ---------- Aloha shirt (4) ----------
def aloha_shirt():
    img = SL.aloha_print(P, 218, base=(150, 24, 30))
    slots = grid(2, 2, 110, 110, W - 110, H - 230, 70, 60)
    mat(img, slots, 18, (252, 248, 236), radius=10)
    d = draw(img)
    box = (CX - 160, H - 180, CX + 160, H - 70)
    shadow(img, box, offset=(3, 5), blur=4, alpha=120)
    d = draw(img)
    d.rectangle(box, fill=rgba((250, 244, 228)))
    d.rectangle((box[0] + 8, box[1] + 8, box[2] - 8, box[3] - 8), outline=rgba((30, 60, 120)), width=2)
    d.text((CX, box[1] + 42), "Aloha", font=font("GreatVibes.ttf", 64), fill=rgba((30, 60, 120)), anchor="mm")
    d.text((CX, box[1] + 86), "MADE IN HAWAII", font=font("SpecialElite.ttf", 18), fill=rgba((60, 60, 60)), anchor="mm")
    return cut(img, slots, radius=6), slots, {}


# ---------- Postcards (2 each) ----------
def postcard_hawaii():
    img = paper(P, (240, 228, 200), 219)
    d = draw(img)
    d.rectangle((24, 24, W - 25, H - 25), outline=rgba((170, 60, 50)), width=6)
    d.text((100, 120), "Greetings from", font=font("GreatVibes.ttf", 100), fill=rgba((30, 60, 110)), anchor="lm")
    gradient_text(img, (CX - 40, 330), "HAWAII", font("Limelight.ttf", 190),
                  [(0, (255, 200, 60)), (0.5, (230, 90, 50)), (1, (170, 40, 70))], stroke=10, stroke_fill=(30, 60, 110))
    postage_stamp(img, (W - 230, 60, W - 70, 260), SL.hawaii_stamp)
    postmark(img, (W - 330, 110), 64, "HONOLULU", waves=False)
    slots = grid(2, 1, 100, 460, W - 100, 1180, 50)
    mat(img, slots, 14, (255, 255, 255))
    d = draw(img)
    d.text((CX, 1320), "Wish you were here!", font=font("GreatVibes.ttf", 100), fill=rgba((30, 60, 110)), anchor="mm")
    hand = vfont("Caveat.ttf", 52, 500)
    for k, line in enumerate(("Sun, sand and the best people.", "Back soon, with more photos! - us")):
        d.text((CX, 1470 + k * 70), line, font=hand, fill=rgba((40, 50, 110)), anchor="mm")
    return cut(img, slots), slots, {}


def postcard_airmail():
    img = paper(P, (246, 240, 226), 220, amount=5, stains=2)
    airmail_border(img, 48, 60)
    d = draw(img)
    lab = (100, 100, 480, 190)
    d.rectangle(lab, fill=rgba((30, 60, 150)))
    d.text(((lab[0] + lab[2]) / 2, 130), "PAR AVION", font=font("Bebas.ttf", 52), fill=rgba((255, 255, 255)), anchor="mm")
    d.text(((lab[0] + lab[2]) / 2, 170), "BY AIR MAIL", font=font("SpecialElite.ttf", 24), fill=rgba((255, 255, 255)), anchor="mm")
    postage_stamp(img, (W - 250, 90, W - 100, 270), SL.airmail_stamp)
    postmark(img, (W - 330, 270), 72, "PAR AVION", colour=(170, 30, 40, 200), angle=10, waves=False)
    d = draw(img)
    d.text((CX, 380), "Miss you already!", font=vfont("Caveat.ttf", 110, 700), fill=rgba((30, 50, 120)), anchor="mm")
    slots = grid(2, 1, 120, 480, W - 120, 1200, 60)
    mat(img, slots, 16, (255, 255, 255))
    d = draw(img)
    hand = vfont("Caveat.ttf", 54, 500)
    for k, line in enumerate(("Dear you,", "The trip was amazing, the photos", "even better. See you soon!", "xoxo")):
        d.text((130, 1320 + k * 72), line, font=hand, fill=rgba((40, 50, 110)), anchor="lm")
    return cut(img, slots), slots, {}


# ---------- Art Deco gold (3) ----------
def art_deco():
    bg, gold, soft = (16, 22, 30), (210, 174, 100), (120, 104, 70)
    img = new(P, bg)
    d = draw(img)
    d.rectangle((24, 24, W - 25, H - 25), outline=rgba(gold), width=5)
    d.rectangle((40, 40, W - 41, H - 41), outline=rgba(soft), width=2)
    deco_corners(d, (56, 56, W - 57, H - 57), rgba(gold), 110)
    deco_fan(d, CX, 330, 230, rgba(soft), rays=15, width=3)
    gradient_text(img, (CX, 210), "PHOTOBOOTH", font("Limelight.ttf", 104), GOLD_LEAF)
    d = draw(img)
    slots = [[350, 420, 500, 660], [150, 1190, 420, 540], [630, 1190, 420, 540]]
    for x, y, w, h in slots:
        d.rectangle((x - 18, y - 18, x + w + 17, y + h + 17), outline=rgba(gold), width=3)
        d.rectangle((x - 9, y - 9, x + w + 8, y + h + 8), outline=rgba(soft), width=2)
    spaced_text(d, (CX, 1135), "SMILE · SNAP · REPEAT", font("PoiretOne.ttf", 46), rgba(gold), 8)
    for k in range(-3, 4):  # stepped chevrons between rows
        d.line((CX + k * 60 - 20, 1112, CX + k * 60, 1097, CX + k * 60 + 20, 1112), fill=rgba(soft), width=3)
    return cut(img, slots), slots, {}


# ---------- Comic (4) ----------
def comic():
    img = new(P, (255, 214, 40))
    SL.halftone(img, (240, 150, 20))
    d = draw(img)
    slots = [[50, 50, 520, 700], [630, 50, 520, 620], [630, 720, 520, 610], [50, 820, 520, 700]]
    for x, y, w, h in slots:
        d.rectangle((x - 12, y - 12, x + w + 11, y + h + 11), fill=rgba((0, 0, 0)))
    cap = (630, 1380, 1150, 1560)
    d.rectangle(cap, fill=rgba((255, 248, 200)), outline=rgba((0, 0, 0)), width=8)
    d.text((660, 1430), "MEANWHILE, AT", font=bold("Oswald.ttf", 52, 700), fill=rgba((0, 0, 0)), anchor="lm")
    d.text((660, 1505), "THE PHOTO BOOTH...", font=bold("Oswald.ttf", 50, 700), fill=rgba((0, 0, 0)), anchor="lm")
    img = cut(img, slots)
    d = draw(img)
    SL.burst(d, 600, 760, 130, 12, rgba((255, 60, 40)), rgba((0, 0, 0)))
    d.text((600, 760), "WOW!", font=font("Limelight.ttf", 70), fill=rgba((255, 240, 60)), anchor="mm", stroke_width=4,
           stroke_fill=rgba((0, 0, 0)))
    bx, by = 60, 1590
    d.ellipse((bx, by, bx + 540, by + 180), fill=rgba((255, 255, 255)), outline=rgba((0, 0, 0)), width=7)
    d.polygon([(bx + 120, by + 30), (bx + 70, by - 60), (bx + 200, by + 20)], fill=rgba((255, 255, 255)))
    d.line([(bx + 120, by + 28), (bx + 70, by - 60), (bx + 200, by + 18)], fill=rgba((0, 0, 0)), width=7)
    d.text((bx + 270, by + 90), "SAY CHEESE!", font=bold("Oswald.ttf", 72, 700), fill=rgba((0, 0, 0)), anchor="mm")
    return img, slots, {}


# ---------- Army ----------
def army_camo():
    img = camo(OCP_BASE, OCP_LAYERS, seed=222, size=P)
    slots = grid(2, 2, 80, 330, W - 80, H - 90, 40)
    shadow(img, (60, 40, W - 60, 270))
    d = draw(img)
    d.rectangle((60, 40, W - 60, 270), fill=rgba((56, 58, 40)), outline=rgba((30, 30, 20)), width=6)
    army_star(d, 200, 155, 80)
    spaced_text(d, (CX + 90, 155), "U.S. ARMY", bold("Oswald.ttf", 130, 700), rgba((226, 214, 170)), 14)
    for x, y, w, h in slots:
        d.rectangle((x - 8, y - 8, x + w + 7, y + h + 7), outline=rgba((30, 28, 20)), width=6)
    return cut(img, slots, radius=6), slots, {}


def army_blues():
    """Army dress blues: navy wool, gold braid, brass buttons."""
    navy, gold = (22, 30, 58), (214, 176, 80)
    img = noise(P, navy, 5, 223, scale=2)
    d = draw(img)
    for x in (60, W - 60):  # gold braid down both sides
        for t in range(0, H, 24):
            d.line((x - 18, t, x + 18, t + 18), fill=rgba(gold), width=6)
        d.line((x - 22, 0, x - 22, H), fill=rgba((170, 130, 50)), width=3)
        d.line((x + 22, 0, x + 22, H), fill=rgba((170, 130, 50)), width=3)
    army_star(d, CX, 180, 110)
    spaced_text(d, (CX, 370), "U.S. ARMY", bold("Oswald.ttf", 120, 700), rgba(ARMY_WHITE), 16)
    slots = [[360, 450, 480, 620], [150, 1170, 420, 540], [630, 1170, 420, 540]]
    for x, y, w, h in slots:
        d.rectangle((x - 10, y - 10, x + w + 9, y + h + 9), outline=rgba(gold), width=6)
    for k, y in enumerate(range(520, 1080, 140)):  # brass buttons between
        for bx in (220, W - 220):
            d.ellipse((bx - 26, y - 26, bx + 26, y + 26), fill=rgba(gold), outline=rgba((150, 110, 40)), width=3)
            d.polygon(star_points(bx, y + 2, 12), fill=rgba((150, 110, 40)))
    spaced_text(d, (CX, 1120), "THIS WE'LL DEFEND", bold("Oswald.ttf", 44, 600), rgba(gold), 10)
    return cut(img, slots), slots, {}


def army_dog_tags():
    img = camo(WOODLAND_BASE, WOODLAND_LAYERS, seed=224, size=P)
    slots = grid(2, 1, 100, 300, W - 100, 1100, 60)
    shadow(img, (150, 70, W - 150, 230))
    d = draw(img)
    d.rectangle((150, 70, W - 150, 230), fill=rgba((40, 44, 30)), outline=rgba((20, 22, 14)), width=6)
    spaced_text(d, (CX, 150), "U.S. ARMY", font("StardosStencil.ttf", 120), rgba((226, 214, 170)), 14)
    for x, y, w, h in slots:
        d.rectangle((x - 10, y - 10, x + w + 9, y + h + 9), outline=rgba((24, 26, 18)), width=8)
    d = draw(img)
    ball_chain(d, [(120, 1170), (280, 1330), (480, 1420), (720, 1420), (920, 1330), (1080, 1170)])
    dog_tag(img, 430, 1540, 190, 8, ["U.S. ARMY", "HOOAH!", "ARMY STRONG"])
    dog_tag(img, 790, 1550, 190, -10, ["U.S. ARMY", "BE ALL YOU", "CAN BE"])
    return cut(img, slots), slots, {}


# ================= THE ATKINSONS (wedding) =================
NAME = "The Atkinsons"


def atk_gown():
    blush, gown, gold, lace = (243, 228, 224), (255, 255, 253), (198, 161, 91), (226, 208, 203)
    img = noise(P, blush, 3, 230)
    d = draw(img)
    for side in (-1, 1):  # sweetheart bodice at the top, as on the gown strip
        d.ellipse((CX + side * 180 - 190, 90, CX + side * 180 + 190, 250), fill=rgba(gown))
    d.polygon([(CX - 370, 170), (CX + 370, 170), (CX + 262, 300), (CX - 262, 300)], fill=rgba(gown))
    d.polygon([(CX - 40, 88), (CX + 40, 88), (CX, 150)], fill=rgba(blush))
    for side in (-1, 1):
        for k in range(15):
            t = math.pi * (0.08 + 0.84 * k / 14)
            px, py = CX + side * 180 - 190 * math.cos(t), 170 - 80 * math.sin(t)
            d.ellipse((px - 7, py - 7, px + 7, py + 7), fill=rgba(gown), outline=rgba(lace), width=2)
    for k in range(-5, 6):
        for row in (205, 245):
            d.ellipse((CX + k * 48 - 4, row - 4, CX + k * 48 + 4, row + 4), fill=rgba(lace))
    d.rectangle((CX - 264, 292, CX + 264, 308), fill=rgba(gold))
    for y in range(0, H, 44):  # lace scallops down the sides
        for x in (0, W):
            d.ellipse((x - 26, y, x + 26, y + 44), fill=rgba(gown))
            d.ellipse((x - 7, y + 15, x + 7, y + 29), fill=rgba(lace))
    slots = grid(2, 1, 110, 380, W - 110, 1130, 60)
    for x, y, w, h in slots:
        shadow(img, (x - 14, y - 14, x + w + 14, y + h + 14), offset=(4, 8), blur=10, alpha=70)
        draw(img).rectangle((x - 14, y - 14, x + w + 14, y + h + 14), fill=rgba(gown), outline=rgba(gold), width=3)
    d = draw(img)
    for px in range(80, W - 70, 30):  # pearl strand
        d.ellipse((px - 8, 1190, px + 8, 1206), fill=rgba(gown), outline=rgba(lace), width=2)
    d.polygon([(CX - 300, 1500), (CX + 300, 1500), (W - 40, H), (40, H)], fill=rgba(gown))  # the skirt
    for k in range(-4, 5):
        d.line((CX + k * 60, 1520, CX + k * 170, H), fill=rgba((240, 230, 226)), width=3)
    d.rectangle((CX - 302, 1490, CX + 302, 1512), fill=rgba(gold))
    d.text((CX, 1330), NAME, font=font("GreatVibes.ttf", 160), fill=rgba(gold), anchor="mm")
    spaced_text(d, (CX, 1440), "TWO HEARTS  ·  ONE LOVE", font("PoiretOne.ttf", 44), rgba(gold), 8)
    return cut(img, slots), slots, {}


def atk_deco_ivory():
    bg, gold, soft = (247, 241, 230), (176, 141, 77), (210, 188, 145)
    img = noise(P, bg, 3, 231)
    d = draw(img)
    d.rectangle((24, 24, W - 25, H - 25), outline=rgba(gold), width=5)
    d.rectangle((40, 40, W - 41, H - 41), outline=rgba(soft), width=2)
    deco_corners(d, (56, 56, W - 57, H - 57), rgba(gold), 100)
    for x in range(110, W - 110, 16):  # the deco band from the strips
        d.line((x, 70, x, 120), fill=rgba(soft), width=3)
    d.rectangle((CX - 170, 64, CX + 170, 126), fill=rgba(bg))
    d.polygon([(CX, 72), (CX + 22, 95), (CX, 118), (CX - 22, 95)], outline=rgba(gold), width=4)
    slots = grid(2, 2, 120, 180, W - 120, 1460, 60, 50)
    for x, y, w, h in slots:
        d.rectangle((x - 14, y - 14, x + w + 13, y + h + 13), outline=rgba(gold), width=3)
    ry, r = 1560, 34
    for ccx in (CX - 22, CX + 22):
        d.ellipse((ccx - r, ry - r, ccx + r, ry + r), outline=rgba(gold), width=6)
    gradient_text(img, (CX, 1680), NAME, font("GreatVibes.ttf", 150), GOLD_LEAF)
    return cut(img, slots), slots, {}


def atk_garden():
    cream, sage, dsage, blush, gold = (246, 242, 233), (138, 154, 123), (94, 110, 82), (232, 180, 176), (196, 160, 98)
    img = paper(P, cream, 232, amount=3, fibres=False)
    d = draw(img)
    d.rectangle((24, 24, W - 25, H - 25), outline=rgba(sage), width=3)
    slots = [[310, 300, 580, 760], [110, 1130, 460, 560], [630, 1130, 460, 560]]
    for x, y, w, h in slots:
        d.rectangle((x - 10, y - 10, x + w + 9, y + h + 9), outline=rgba(sage), width=3)
    over = layer(img)
    o = ImageDraw.Draw(over, "RGBA")
    rnd = random.Random(232)
    for side in (-1, 1):  # climbing vines
        base = 70 if side < 0 else W - 70
        prev = None
        for y in range(60, H - 60, 8):
            x = base + 12 * math.sin(y / 95)
            if prev:
                o.line([prev, (x, y)], fill=rgba(dsage), width=5)
            prev = (x, y)
            if y % 64 == 0:
                ang = (-35 if (y // 64) % 2 else 35) + (0 if side < 0 else 180)
                leaf(o, x + math.cos(math.radians(ang)) * 26, y + math.sin(math.radians(ang)) * 26, 58, 24, ang,
                     rgba(sage if rnd.random() > 0.3 else dsage))
    for (x, y, w, h), corner in zip(slots, [(1, 0), (0, 1), (1, 1)]):
        fx, fy = x + corner[0] * w, y + corner[1] * h
        for k in range(5):
            leaf(o, fx + rnd.randint(-50, 50), fy + rnd.randint(-50, 50), 64, 24, rnd.randint(0, 180), rgba(sage))
        flower(o, fx, fy, 42, rgba(blush), rgba(gold))
    img.alpha_composite(over)
    d = draw(img)
    for k in range(-6, 7):
        leaf(d, CX + k * 38, 210 + abs(k) * 5, 52, 20, 90 + k * 12, rgba(sage if k % 2 else dsage))
    d.text((CX, 120), NAME, font=font("GreatVibes.ttf", 140), fill=rgba(dsage), anchor="mm")
    spaced_text(d, (CX, H - 70), "A GARDEN OF LOVE", font("PoiretOne.ttf", 44), rgba(sage), 10)
    return cut(img, slots), slots, {}


def atk_champagne():
    wine, gold, soft, fizz = (74, 20, 38), (216, 178, 110), (140, 90, 80), (232, 200, 130)
    img = new(P, wine)
    d = draw(img)
    d.rectangle((24, 24, W - 25, H - 25), outline=rgba(gold), width=4)
    d.rectangle((38, 38, W - 39, H - 39), outline=rgba(soft), width=2)
    f = af.flute_img(110, rgba(gold), rgba(fizz))
    left, right = f.rotate(-18, expand=True, resample=Image.BICUBIC), f.rotate(18, expand=True, resample=Image.BICUBIC)
    img.alpha_composite(left, (CX - left.width + 45, 40))
    img.alpha_composite(right, (CX - 45, 40))
    d = draw(img)
    sparkle(d, CX, 70, 26, rgba(gold))
    slots = [[100, 390, 480, 620], [620, 390, 480, 620], [390, 1120, 420, 520]]
    for x, y, w, h in slots:
        d.rectangle((x - 10, y - 10, x + w + 9, y + h + 9), outline=rgba(gold), width=3)
    d.text((CX, 1720), NAME, font=font("GreatVibes.ttf", 120), fill=rgba(gold), anchor="mm")
    spaced_text(d, (CX, 1065), "CHEERS TO LOVE", font("PoiretOne.ttf", 44), rgba(gold), 10)
    return cut(img, slots), slots, {}


def atk_just_married():
    navy, blush, gold, white = (30, 42, 71), (242, 196, 192), (212, 175, 106), (250, 248, 244)
    img = new(P, navy)
    d = draw(img)
    letters = "JUST MARRIED"
    n = len(letters)
    pts = [(80 + i * ((W - 160) / (n - 1)), 40 + 60 * math.sin(math.pi * i / (n - 1))) for i in range(n)]
    d.line(pts, fill=rgba(gold), width=4)
    colours = [white, blush, gold]
    for i, (ch, (px, py)) in enumerate(zip(letters, pts)):
        if ch == " ":
            continue
        d.polygon([(px - 42, py), (px + 42, py), (px, py + 150)], fill=rgba(colours[i % 3]))
        d.text((px, py + 48), ch, font=font("Limelight.ttf", 50), fill=rgba(navy), anchor="mm")
    rnd = random.Random(234)
    for _ in range(320):
        x, y = rnd.randint(20, W - 20), rnd.randint(230, H - 20)
        c = rgba(rnd.choice([blush, gold, white]))
        r = rnd.random()
        if r < 0.35:
            heart(d, x, y, rnd.randint(8, 14), c)
        elif r < 0.7:
            s = rnd.randint(3, 6)
            d.ellipse((x - s, y - s, x + s, y + s), fill=c)
        else:
            sparkle(d, x, y, rnd.randint(7, 12), c)
    slots = grid(2, 2, 110, 280, W - 110, 1500, 60, 50)
    for x, y, w, h in slots:
        d.rectangle((x - 12, y - 12, x + w + 11, y + h + 11), fill=rgba(white))
    img = cut(img, slots)
    d = draw(img)
    heart(d, CX, 1560, 22, rgba(blush))
    d.text((CX, 1690), NAME, font=font("GreatVibes.ttf", 140), fill=rgba(white), anchor="mm")
    return img, slots, {}


DESIGNS = [
    ("Gallery White", gallery_white), ("Instax Wall", instax_wall), ("Cabinet Card", cabinet_card),
    ("Magazine Cover", magazine_cover), ("Movie Poster", movie_poster), ("Trading Cards", trading_cards),
    ("Wanted Poster", wanted), ("Tarot Cards", tarot), ("Newspaper", newspaper), ("Passport", passport),
    ("Museum Wall", museum_wall), ("Our Favorite Day", favorite_day), ("Pac-Maze", pac_maze),
    ("Space Invaders", invaders), ("Falling Blocks", falling_blocks), ("Hawaii Travel Poster", hawaii_poster),
    ("Aloha Shirt", aloha_shirt), ("Postcard: Greetings from Hawaii", postcard_hawaii),
    ("Postcard: Air Mail", postcard_airmail), ("Art Deco", art_deco), ("Comic Book", comic),
    ("Army Camo", army_camo), ("Army Dress Blues", army_blues), ("Army Dog Tags", army_dog_tags),
    ("The Atkinsons: The Gown", atk_gown), ("The Atkinsons: Deco Ivory", atk_deco_ivory),
    ("The Atkinsons: Garden Party", atk_garden), ("The Atkinsons: Champagne", atk_champagne),
    ("The Atkinsons: Just Married", atk_just_married),
    ("Realistic: Space", lambda: realistic.space(P)), ("Realistic: Ocean", lambda: realistic.ocean(P)),
    ("Realistic: Plants", lambda: realistic.plants(P)), ("Realistic: Outdoors", lambda: realistic.outdoors(P)),
]
