"""Landscape BIG SHEET designs (6x4, 1800x1200, landscape photos). Each returns
(image, slots, extra JSON) and is listed in DESIGNS at the bottom."""
import math, random
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

import all_frames as af
from all_frames import font, rgba, bold, star_points, army_star, spaced_text, camo, OCP_BASE, OCP_LAYERS, \
    ARMY_GOLD, ARMY_BLACK, ARMY_WHITE, palm, hibiscus, monstera, sparkle, heart, bowtie, dress, flower, leaf, \
    dog_tag, ball_chain, WOODLAND_BASE, WOODLAND_LAYERS
from sheet_kit import *

W, H = L
CX, CY = W // 2, H // 2


# ---------- Gallery White (4) ----------
def gallery_white():
    slots = grid(2, 2, 70, 60, W - 70, H - 150, 40)
    img = new(L, (252, 251, 248))
    d = draw(img)
    for x, y, w, h in slots:
        d.rectangle((x - 14, y - 14, x + w + 13, y + h + 13), outline=rgba((200, 198, 192)), width=2)
    spaced_text(d, (CX, H - 78), "MEMORIES", font("PoiretOne.ttf", 64), rgba((60, 60, 60)), 24)
    d.line((CX - 520, H - 78, CX - 260, H - 78), fill=rgba((150, 150, 150)), width=2)
    d.line((CX + 260, H - 78, CX + 520, H - 78), fill=rgba((150, 150, 150)), width=2)
    return cut(img, slots), slots, {}


# ---------- Polaroid Cork Board (3) ----------
def polaroid_cork():
    img = noise(L, (176, 132, 88), 22, 2, blur=0.8)
    d = draw(img)
    rnd = random.Random(2)
    for _ in range(2500):
        x, y, r = rnd.uniform(0, W), rnd.uniform(0, H), rnd.uniform(1, 4)
        d.ellipse((x - r, y - r, x + r, y + r), fill=(110, 76, 44, 160) if rnd.random() < 0.6 else (214, 176, 128, 160))
    vignette(img, 0.5, (60, 36, 16))
    pw, ph = 500, 375
    slots, captions = [], ["good times", "best friends", "say cheese"]
    for i, (px, py) in enumerate(((95, 330), (650, 270), (1205, 350))):
        box = (px - 30, py - 30, px + pw + 30, py + ph + 150)
        shadow(img, box)
        d = draw(img)
        d.rectangle(box, fill=rgba((250, 249, 244)))
        d.text((px + pw / 2, py + ph + 72), captions[i], font=vfont("Caveat.ttf", 76, 600), fill=rgba((40, 40, 70)), anchor="mm")
        d.ellipse((px + pw / 2 - 16, py - 64, px + pw / 2 + 16, py - 32), fill=rgba((220, 40, 50)))  # push pin
        d.ellipse((px + pw / 2 - 7, py - 58, px + pw / 2 + 1, py - 50), fill=(255, 255, 255, 180))
        slots.append([px, py, pw, ph])
    return cut(img, slots), slots, {}


# ---------- Contact Sheet (3) ----------
def contact_sheet():
    img = paper(L, (232, 230, 224), 3, amount=4, fibres=False)
    d = draw(img)
    d.rectangle((0, 330, W, 900), fill=rgba((22, 18, 14)))
    for x in range(30, W, 92):
        for y in (350, 840):
            d.rounded_rectangle((x, y, x + 50, y + 40), radius=8, fill=rgba((232, 230, 224)))
    slots = grid(3, 1, 70, 440, W - 70, 790, 40)
    edge = font("VT323.ttf", 40)
    for i, (x, y, w, h) in enumerate(slots):
        d.text((x + 10, 432), f"{14 + i}", font=edge, fill=rgba((255, 170, 40)), anchor="lb")
        d.text((x + w - 10, 432), f"{14 + i}A  ▸", font=edge, fill=rgba((255, 170, 40)), anchor="rb")
        d.text((x + w / 2, 835), "SAFETY FILM 400", font=edge, fill=rgba((255, 170, 40)), anchor="mb")
    d.text((CX, 140), "CONTACT SHEET", font=font("PoiretOne.ttf", 70), fill=rgba((40, 40, 40)), anchor="mm")
    d.text((90, 1080), "ROLL 26  ·  FRAMES 14-16", font=font("VT323.ttf", 44), fill=rgba((90, 90, 90)), anchor="lm")
    d.text((W - 90, 1080), "keeper!", font=vfont("Caveat.ttf", 70, 700), fill=(220, 40, 40, 230), anchor="rm")
    x, y, w, h = slots[1]
    d.ellipse((x - 28, y - 30, x + w + 28, y + h + 30), outline=(220, 40, 40, 230), width=7)
    return cut(img, slots), slots, {}


# ---------- Postcard: Greetings from Hawaii (2) ----------
def hawaii_stamp(d, box):
    x0, y0, x1, y1 = box
    d.rectangle(box, fill=rgba((60, 150, 170)))
    d.rectangle((x0, (y0 + y1) / 2 + 20, x1, y1), fill=rgba((230, 200, 140)))
    hibiscus(d, (x0 + x1) / 2, (y0 + y1) / 2 - 10, (x1 - x0) * 0.28, rgba((240, 70, 90)), rgba((150, 20, 50)))
    d.text(((x0 + x1) / 2, y1 - 14), "HAWAII 8¢", font=font("SpecialElite.ttf", 20), fill=rgba((40, 40, 40)), anchor="mb")


def postcard_hawaii():
    img = paper(L, (240, 228, 200), 5)
    d = draw(img)
    d.rectangle((24, 24, W - 25, H - 25), outline=rgba((170, 60, 50)), width=6)
    d.text((140, 120), "Greetings from", font=font("GreatVibes.ttf", 110), fill=rgba((30, 60, 110)), anchor="lm")
    gradient_text(img, (800, 250), "HAWAII", font("Limelight.ttf", 200),
                  [(0, (255, 200, 60)), (0.5, (230, 90, 50)), (1, (170, 40, 70))], stroke=10, stroke_fill=(30, 60, 110))
    postage_stamp(img, (W - 260, 70, W - 80, 290), hawaii_stamp)
    postmark(img, (W - 320, 230), 80, "HONOLULU")
    slots = grid(2, 1, 110, 400, W - 110, 975, 60)
    mat(img, slots, 14, (255, 255, 255))
    draw(img).text((W - 140, 1080), "Wish you were here!", font=font("GreatVibes.ttf", 80), fill=rgba((30, 60, 110)), anchor="rm")
    return cut(img, slots), slots, {}


# ---------- Postcard: Air Mail (2) ----------
def airmail_stamp(d, box):
    x0, y0, x1, y1 = box
    d.rectangle(box, fill=rgba((30, 60, 150)))
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2 - 8
    d.polygon([(cx - 50, cy + 6), (cx + 50, cy - 6), (cx + 50, cy + 6), (cx - 50, cy + 12)], fill=rgba((240, 240, 240)))  # plane
    d.polygon([(cx - 6, cy), (cx + 14, cy - 34), (cx + 26, cy - 34), (cx + 14, cy + 2)], fill=rgba((240, 240, 240)))
    d.polygon([(cx - 6, cy + 8), (cx + 14, cy + 40), (cx + 26, cy + 40), (cx + 14, cy + 6)], fill=rgba((240, 240, 240)))
    d.text((cx, y1 - 12), "AIR MAIL 25¢", font=font("SpecialElite.ttf", 18), fill=rgba((255, 255, 255)), anchor="mb")


def postcard_airmail():
    img = paper(L, (246, 240, 226), 51, amount=5, stains=2)
    airmail_border(img, 48, 60)
    d = draw(img)
    d.rectangle((48, 48, W - 49, H - 49), outline=rgba((200, 190, 170)), width=2)
    lab = (110, 95, 520, 185)
    d.rectangle(lab, fill=rgba((30, 60, 150)))
    d.text(((lab[0] + lab[2]) / 2, (lab[1] + lab[3]) / 2 - 14), "PAR AVION", font=font("Bebas.ttf", 52),
           fill=rgba((255, 255, 255)), anchor="mm")
    d.text(((lab[0] + lab[2]) / 2, (lab[1] + lab[3]) / 2 + 24), "BY AIR MAIL", font=font("SpecialElite.ttf", 26),
           fill=rgba((255, 255, 255)), anchor="mm")
    d.text((CX, 140), "Miss you already!", font=vfont("Caveat.ttf", 96, 700), fill=rgba((30, 50, 120)), anchor="mm")
    for k, bx in enumerate((W - 440, W - 260)):
        postage_stamp(img, (bx, 80, bx + 150, 260), airmail_stamp if k else hawaii_stamp)
    postmark(img, (W - 380, 250), 78, "PAR AVION", colour=(170, 30, 40, 200), angle=10)
    slots = grid(2, 1, 130, 320, W - 130, 940, 70)
    mat(img, slots, 16, (255, 255, 255))
    d = draw(img)
    for x, y, w, h in slots:  # paper clips
        cx = x + w - 80
        d.rounded_rectangle((cx - 18, y - 60, cx + 18, y + 50), radius=18, outline=rgba((150, 156, 166)), width=7)
        d.rounded_rectangle((cx - 9, y - 40, cx + 9, y + 34), radius=9, outline=rgba((150, 156, 166)), width=6)
    d.text((W - 140, 1060), "xoxo", font=vfont("Caveat.ttf", 80, 600), fill=rgba((180, 30, 50)), anchor="rm")
    return cut(img, slots), slots, {}


# ---------- Postcard: the back (2) ----------
def postcard_back():
    img = paper(L, (238, 230, 210), 52, amount=6, stains=3)
    d = draw(img)
    d.line((1040, 120, 1040, H - 120), fill=rgba((120, 100, 80)), width=3)
    d.text((70, 70), "POST CARD", font=vfont("Cinzel.ttf", 54, 700), fill=rgba((90, 70, 50)), anchor="lm")
    d.text((1000, 70), "CORRESPONDENCE  |  ADDRESS", font=font("OldStandard.ttf", 26), fill=rgba((120, 100, 80)), anchor="rm")
    slots = [[90, 150, 880, 520], [90, 720, 520, 400]]
    mat(img, slots, 12, (255, 255, 255))
    d = draw(img)
    hand = vfont("Caveat.ttf", 58, 500)
    lines = ["Having the best", "time! Wish you", "were here.", "", "- love, us"]
    for k, line in enumerate(lines):
        d.text((660, 760 + k * 66), line, font=hand, fill=rgba((40, 50, 110)), anchor="lm")
    postage_stamp(img, (W - 250, 90, W - 90, 280), hawaii_stamp)
    postmark(img, (W - 300, 250), 80, "ALOHA")
    for k in range(4):  # address lines
        y = 560 + k * 110
        d.line((1110, y, W - 110, y), fill=rgba((120, 100, 80)), width=3)
    d.text((1130, 540), "The Best Friends", font=hand, fill=rgba((40, 50, 110)), anchor="ls")
    d.text((1130, 650), "123 Photo Booth Lane", font=hand, fill=rgba((40, 50, 110)), anchor="ls")
    d.text((1130, 760), "Honolulu, HI 96815", font=hand, fill=rgba((40, 50, 110)), anchor="ls")
    d.text((1130, 980), "PLACE STAMP ABOVE", font=font("OldStandard.ttf", 22), fill=rgba((150, 130, 110)), anchor="ls")
    return cut(img, slots), slots, {}


# ---------- Postcard: Linen "Greetings from Paradise" (3) ----------
def linen(size, base, seed):
    """Linen-finish card: fine woven crosshatch like 1940s postcards."""
    img = noise(size, base, 5, seed)
    d = draw(img)
    w, h = size
    for y in range(0, h, 4):
        d.line((0, y, w, y), fill=(255, 255, 255, 26), width=1)
    for x in range(0, w, 4):
        d.line((x, 0, x, h), fill=(0, 0, 0, 16), width=1)
    return img


def postcard_paradise():
    img = linen(L, (250, 226, 170), 53)
    sky = vgrad((W, 520), [(0, (40, 120, 200)), (1, (250, 190, 120))])
    img.alpha_composite(sky)
    d = draw(img)
    d.ellipse((CX - 140, 300, CX + 140, 580), fill=rgba((255, 236, 160)))
    d.rectangle((0, 470, W, 520), fill=rgba((30, 120, 160)))
    for x in range(0, W, 30):
        d.line((x, 480 + (x % 90) // 15, x + 20, 480 + (x % 90) // 15), fill=(255, 255, 255, 120), width=3)
    palm(d, 80, 560, 420, 110, rgba((20, 60, 40)), seed=31)
    palm(d, W - 80, 560, 400, -110, rgba((20, 60, 40)), seed=32)
    # Big block letters with a 3D drop and a dark outline, like the linen-era classics.
    f = font("Limelight.ttf", 230)
    for k in range(14, 0, -1):
        d.text((CX + k, 300 + k), "PARADISE", font=f, fill=rgba((120, 40, 30)), anchor="mm")
    gradient_text(img, (CX, 300), "PARADISE", f, [(0, (255, 230, 120)), (0.5, (250, 140, 40)), (1, (220, 60, 50))],
                  stroke=6, stroke_fill=(60, 30, 20))
    d = draw(img)
    d.text((CX, 110), "Greetings from", font=font("GreatVibes.ttf", 100), fill=rgba((255, 255, 255)), anchor="mm",
           stroke_width=4, stroke_fill=rgba((60, 30, 20)))
    slots = grid(3, 1, 90, 650, W - 90, 1080, 40)
    mat(img, slots, 12, (252, 244, 226))
    d = draw(img)
    d.rectangle((20, 20, W - 21, H - 21), outline=rgba((255, 255, 255)), width=14)
    return cut(img, slots), slots, {}


# ---------- Magazine Cover (1) ----------
def magazine_cover():
    slots = [[0, 0, W, H]]
    img = cut(new(L, (255, 255, 255)), slots)
    shade = layer(img)
    sd = ImageDraw.Draw(shade)
    for y in range(260):
        sd.line((0, y, W, y), fill=(0, 0, 0, int(150 * (1 - y / 260))))
    for x in range(560):
        sd.line((x, 0, x, H), fill=(0, 0, 0, int(90 * (1 - x / 560))))
    img.alpha_composite(shade)
    d = draw(img)
    d.text((60, 30), "SNAP", font=bold("Oswald.ttf", 230, 700), fill=rgba((235, 30, 60)), anchor="lt")
    d.text((640, 70), "THE PHOTO BOOTH ISSUE", font=bold("Oswald.ttf", 44, 500), fill=rgba((255, 255, 255)), anchor="lt")
    d.text((640, 128), "OCTOBER EDITION  ·  $0.00", font=bold("Oswald.ttf", 34, 400), fill=rgba((255, 255, 255)), anchor="lt")
    lines = [("EXCLUSIVE", "Inside the most", "fun night ever"), ("STYLE", "Who wore it", "best? (You.)"),
             ("10 WAYS", "to strike the", "perfect pose")]
    y = 380
    for head, a, b in lines:
        for txt, f, col, dy in ((head, bold("Oswald.ttf", 60, 700), (255, 210, 40), 0),
                                (a, bold("Oswald.ttf", 40, 400), (255, 255, 255), 72),
                                (b, bold("Oswald.ttf", 40, 400), (255, 255, 255), 118)):
            d.text((60, y + dy), txt, font=f, fill=rgba(col), anchor="lt", stroke_width=3, stroke_fill=(0, 0, 0, 160))
        y += 210
    bx, by = W - 300, H - 170  # barcode bottom right; the date stamp goes bottom left instead
    d.rectangle((bx - 20, by - 20, bx + 240, by + 130), fill=rgba((255, 255, 255)))
    rnd = random.Random(7)
    x = bx
    while x < bx + 220:
        w = rnd.choice([2, 3, 5])
        d.rectangle((x, by, x + w, by + 90), fill=rgba((0, 0, 0)))
        x += w + rnd.choice([2, 3, 4])
    d.text((bx + 110, by + 110), "0 26100 00001 8", font=font("VT323.ttf", 28), fill=rgba((0, 0, 0)), anchor="mm")
    return img, slots, {"stamp": "bl"}


# ---------- Comic Book (3) ----------
def burst(d, cx, cy, r, points, fill, outline):
    pts = [(cx + (r if i % 2 == 0 else r * 0.62) * math.cos(math.pi * i / points),
            cy + (r if i % 2 == 0 else r * 0.62) * math.sin(math.pi * i / points)) for i in range(points * 2)]
    d.polygon(pts, fill=fill)
    d.line(pts + [pts[0]], fill=outline, width=8)


def halftone(img, colour, spacing=26, base=5, amp=4):
    d = draw(img)
    w, h = img.size
    for y in range(0, h, spacing):
        for x in range(0, w, spacing):
            r = base + amp * math.sin(x / 140) * math.cos(y / 160)
            d.ellipse((x - r, y - r, x + r, y + r), fill=rgba(colour))


def comic_book():
    img = new(L, (255, 214, 40))
    halftone(img, (240, 150, 20))
    d = draw(img)
    slots = [[50, 50, 1060, 760], [1150, 50, W - 1200, 355], [1150, 455, W - 1200, 355]]
    for x, y, w, h in slots:
        d.rectangle((x - 12, y - 12, x + w + 11, y + h + 11), fill=rgba((0, 0, 0)))
    cap = (50, 870, 1100, 1150)
    d.rectangle(cap, fill=rgba((255, 248, 200)), outline=rgba((0, 0, 0)), width=8)
    d.text((80, 940), "MEANWHILE, AT THE", font=bold("Oswald.ttf", 64, 700), fill=rgba((0, 0, 0)), anchor="lm")
    d.text((80, 1040), "PHOTO BOOTH...", font=bold("Oswald.ttf", 96, 700), fill=rgba((0, 0, 0)), anchor="lm")
    img = cut(img, slots)
    d = draw(img)
    burst(d, 1080, 110, 120, 12, rgba((255, 60, 40)), rgba((0, 0, 0)))
    d.text((1080, 110), "POW!", font=font("Limelight.ttf", 68), fill=rgba((255, 240, 60)), anchor="mm",
           stroke_width=4, stroke_fill=rgba((0, 0, 0)))
    bx, by = 1220, 900
    d.ellipse((bx, by, bx + 420, by + 170), fill=rgba((255, 255, 255)), outline=rgba((0, 0, 0)), width=7)
    d.polygon([(bx + 90, by + 150), (bx + 40, by + 230), (bx + 160, by + 160)], fill=rgba((255, 255, 255)))
    d.line([(bx + 90, by + 152), (bx + 40, by + 230), (bx + 160, by + 162)], fill=rgba((0, 0, 0)), width=7)
    d.text((bx + 210, by + 85), "SMILE!", font=bold("Oswald.ttf", 72, 700), fill=rgba((0, 0, 0)), anchor="mm")
    return img, slots, {}


# ---------- Newspaper front page (3) ----------
def newspaper(size, slots, seed, headline, sub):
    """Shared front page: masthead, rules, headline, columns of text around the photos."""
    w, h = size
    img = paper(size, (236, 230, 214), seed, amount=5, fibres=False)
    d = draw(img)
    ink = (28, 26, 24, 255)
    d.text((w / 2, 100), "The Daily Snapshot", font=font("Unifraktur.ttf", 128 if w > h else 112), fill=ink, anchor="mm")
    d.line((50, 180, w - 50, 180), fill=ink, width=6)
    d.line((50, 190, w - 50, 190), fill=ink, width=2)
    meta = font("OldStandard.ttf", 26)
    d.text((60, 214), "VOL. XXVI · No. 10", font=meta, fill=ink, anchor="lm")
    d.text((w / 2, 214), "★  LATE CITY EDITION  ★", font=meta, fill=ink, anchor="mm")
    d.text((w - 60, 214), "PRICE: ONE SMILE", font=meta, fill=ink, anchor="rm")
    d.line((50, 238, w - 50, 238), fill=ink, width=2)
    hl = font("OldStandardBold.ttf", 92 if w > h else 76)
    d.text((w / 2, 310), headline, font=hl, fill=ink, anchor="mm")
    d.text((w / 2, 384), sub, font=font("OldStandard.ttf", 36), fill=ink, anchor="mm")
    d.line((50, 420, w - 50, 420), fill=ink, width=2)
    return img, d, ink


def newspaper_landscape():
    slots = [[60, 450, 900, 600], [1000, 450, 360, 250], [1000, 790, 360, 250]]
    img, d, ink = newspaper(L, slots, 61, "LOCAL CREW HAS BEST NIGHT EVER", "Witnesses report “nonstop laughing”; booth confirms all poses were iconic")
    grey = (70, 66, 60, 255)
    for x, y, w, h in slots:
        d.rectangle((x - 4, y - 4, x + w + 3, y + h + 3), outline=ink, width=3)
    cap = font("OldStandard.ttf", 24)
    d.text((60, 1080), "ABOVE: The scene of the fun, moments before history was made.", font=cap, fill=ink, anchor="lm")
    d.text((1000, 1072), "Exclusive photos", font=cap, fill=ink, anchor="lm")
    d.line((1390, 450, 1390, 1140), fill=ink, width=2)
    d.text((1420, 470), "FUN LEVELS", font=font("OldStandardBold.ttf", 34), fill=ink, anchor="lm")
    d.text((1420, 510), "AT RECORD HIGH", font=font("OldStandardBold.ttf", 34), fill=ink, anchor="lm")
    fake_text(d, (1420, 550, W - 60, 1140), 26, grey, 62)
    d.text((1000, 755), "SEE PAGE 2", font=font("OldStandard.ttf", 22), fill=ink, anchor="lm")
    return cut(img, slots), slots, {}


# ---------- Passport (2) ----------
def passport_spread(size, seed):
    w, h = size
    img = new(size, (226, 236, 228))
    guilloche(img, [(150, 190, 175, 255), (190, 170, 210, 255), (170, 200, 220, 255)], seed)
    return img


def passport_landscape():
    img = passport_spread(L, 71)
    d = draw(img)
    d.line((CX, 0, CX, H), fill=rgba((150, 160, 150)), width=4)  # the book's fold
    sh = layer(img)
    ImageDraw.Draw(sh).rectangle((CX - 40, 0, CX + 40, H), fill=(0, 0, 0, 40))
    img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(20)))
    d = draw(img)
    navy = (30, 40, 80, 255)
    d.text((70, 70), "PASSPORT", font=vfont("Cinzel.ttf", 56, 700), fill=navy, anchor="lm")
    d.text((70, 120), "PASSEPORT  ·  PASAPORTE", font=font("OldStandard.ttf", 26), fill=navy, anchor="lm")
    slots = [[80, 190, 420, 560], [CX + 120, 260, 660, 470]]
    slots = [[80, 200, 460, 345], [CX + 110, 300, 700, 470]]
    label = font("OldStandard.ttf", 22)
    value = font("SpecialElite.ttf", 34)
    fields = [("Type / Type", "P"), ("Surname / Nom", "PHOTOBOOTH"), ("Given names / Prénoms", "THE BEST CREW"),
              ("Nationality", "FUN"), ("Date of issue", "TODAY"), ("Authority", "THE PHOTO BOOTH")]
    y = 200
    for lab, val in fields:
        d.text((590, y), lab, font=label, fill=navy, anchor="lt")
        d.text((590, y + 26), val, font=value, fill=rgba((20, 20, 20)), anchor="lt")
        y += 82
    d.rectangle((70, 1010, CX - 50, 1150), fill=(255, 255, 255, 120))
    mrz = font("VT323.ttf", 50)
    d.text((86, 1050), "P<FUNPHOTOBOOTH<<THE<BEST<CREW<<<<<", font=mrz, fill=rgba((20, 20, 20)), anchor="lm")
    d.text((86, 1110), "2610260FUN<<<<<<<<<<<<<<<<<<<<<<06", font=mrz, fill=rgba((20, 20, 20)), anchor="lm")
    # Visa page: the second photo with entry stamps.
    vx, vy = CX + 70, 220
    d.rounded_rectangle((vx, vy, W - 70, 840), radius=16, fill=(255, 250, 240, 200), outline=navy, width=3)
    d.text((vx + 30, vy + 40), "VISA  ·  ENTRY PERMIT", font=vfont("Cinzel.ttf", 34, 700), fill=navy, anchor="lm")
    mat(img, slots, 6, (255, 255, 255), drop=False)
    img = cut(img, slots)
    rubber_stamp(img, (W - 230, 960), 120, ["ADMITTED", "HONOLULU", "OCT 2026"], (180, 30, 40, 230), 14, 1)
    rubber_stamp(img, (CX + 260, 1000), 105, ["ARRIVED", "PHOTO BOOTH", "★"], (30, 70, 160, 220), -10, 2)
    rubber_stamp(img, (430, 600), 90, ["APPROVED", "★ FUN ★"], (40, 120, 70, 210), -18, 3, box=True)
    return img, slots, {}


# ---------- Museum wall (3) ----------
def damask(size, base, accent, seed):
    img = noise(size, base, 4, seed)
    d = draw(img)
    w, h = size
    for y in range(-60, h + 120, 160):
        for x in range(-60, w + 120, 140):
            ox = 70 if (y // 160) % 2 else 0
            cx, cy = x + ox, y
            for k in range(4):
                a = math.pi / 2 * k
                leaf(d, cx + 22 * math.cos(a), cy + 30 * math.sin(a), 46, 18, math.degrees(a), accent)
            d.ellipse((cx - 8, cy - 8, cx + 8, cy + 8), fill=accent)
    return img


def museum_wall():
    img = damask(L, (70, 24, 34), (88, 34, 44, 255), 81)
    vignette(img, 0.6, (20, 6, 10))
    for x in (380, CX, W - 380):  # gallery spotlights from above
        light = layer(img)
        ImageDraw.Draw(light).polygon([(x - 40, 0), (x + 40, 0), (x + 260, 900), (x - 260, 900)], fill=(255, 230, 180, 50))
        img.alpha_composite(light.filter(ImageFilter.GaussianBlur(50)))
    slots = [[640, 150, 520, 390], [140, 260, 400, 300], [W - 540, 260, 400, 300]]
    for s in slots:
        gold_frame(img, s, 64 if s[2] > 450 else 50)
    d = draw(img)
    d.rectangle((0, 1040, W, H), fill=rgba((40, 14, 20)))  # wainscot rail
    d.line((0, 1040, W, 1040), fill=rgba((150, 110, 50)), width=8)
    plaque(img, (CX, 690), "PORTRAIT OF JOY", "Oil on photo booth, 2026")
    plaque(img, (340, 680), "NO. 1", "Study in smiles", w=230)
    plaque(img, (W - 340, 680), "NO. 2", "The candid", w=230)
    d = draw(img)
    for x in range(380, W - 300, 160):  # velvet rope
        d.line((x, 960, x + 160, 960), fill=rgba((150, 20, 30)), width=10)
    for x in range(380, W - 300 + 1, 160):
        d.rectangle((x - 8, 930, x + 8, 1040), fill=rgba((200, 164, 92)))
        d.ellipse((x - 16, 914, x + 16, 946), fill=rgba((220, 184, 110)))
    return cut(img, slots), slots, {}


# ---------- Our Favorite Day: scrapbook (4) ----------
def favorite_day(size=L, slots=None, seed=91):
    w, h = size
    img = paper(size, (238, 232, 218), seed, amount=6, stains=1)
    d = draw(img)
    for y in range(80, h, 46):  # faint ruled lines, like a journal
        d.line((0, y, w, y), fill=(150, 170, 200, 50), width=2)
    slots = slots or [[100, 220, 760, 450], [990, 250, 700, 420], [160, 790, 600, 330], [900, 790, 560, 330]]
    rnd = random.Random(seed)
    for x, y, sw, sh in slots:
        shadow(img, (x - 18, y - 18, x + sw + 18, y + sh + 18), offset=(8, 12), blur=10, alpha=120)
        draw(img).rectangle((x - 18, y - 18, x + sw + 18, y + sh + 18), fill=rgba((255, 255, 253)))
    for (x, y, sw, sh), col, pat in zip(slots, [(240, 170, 180, 220), (170, 210, 200, 220), (250, 220, 140, 220), (190, 180, 230, 220)],
                                        ["dots", "stripes", "dots", "stripes"]):
        washi_tape(img, (x + sw * 0.5, y - 14), 220, 52, rnd.uniform(-8, 8), col, pat)
    ticket_stub(img, (w - 150, h - 280) if w > h else (w - 250, h - 120), 260, 116, -78 if w > h else -8,
                (200, 70, 70, 255), "ADMIT ONE", "THE BEST DAY")
    pressed_flower(img, (w - 110, 160) if w > h else (w - 110, 300), 30, (240, 150, 170, 220), seed)
    pressed_flower(img, (70, h - 90), 28, (250, 210, 120, 220), seed + 1)
    d = draw(img)
    d.text((w / 2, 100), "our favorite day", font=font("GreatVibes.ttf", 120), fill=rgba((60, 50, 90)),
           anchor="mm")
    hand = vfont("Caveat.ttf", 46, 600)
    notes = ["best. day. ever.", "lol ❤", "us!!", "never forget"]
    for (x, y, sw, sh), note in zip(slots, notes):
        d.text((x + sw - 10, y + sh + 50), note, font=hand, fill=rgba((70, 70, 140)), anchor="rm")
    for k in range(5):  # doodled hearts and stars
        x, y = rnd.uniform(0.05, 0.95) * w, rnd.uniform(0.05, 0.95) * h
        if rnd.random() < 0.5:
            heart(d, x, y, 14, (220, 80, 110, 160))
        else:
            d.polygon(star_points(x, y, 16), outline=(90, 90, 160, 200), width=3)
    return cut(img, slots), slots, {}


# ---------- TV stack (4) ----------
def tv_stack():
    img = noise(L, (40, 34, 44), 6, 101)
    d = draw(img)
    for x in range(0, W, 80):  # dark striped wallpaper
        d.rectangle((x, 0, x + 40, H), fill=(255, 255, 255, 10))
    vignette(img, 0.7)
    floor = (0, 1080, W, H)
    d.rectangle(floor, fill=rgba((60, 40, 28)))
    sets = [((70, 110, 870, 640), (150, 170, 560, 400), "wood"),
            ((930, 60, 1730, 600), (1010, 120, 540, 400), "orange"),
            ((110, 680, 860, 1080), (180, 735, 440, 300), "cream"),
            ((930, 650, 1730, 1080), (1000, 705, 520, 320), "chrome")]
    slots = []
    for k, (body, screen, style) in enumerate(sets):
        vintage_tv(img, body, screen, style, seed=k)
        x, y, w, h = screen
        knob_x = body[2] - 80
        if style in ("wood", "chrome", "cream"):
            tv_knobs(img, knob_x, y + 70, 2, 30, gap=110)
            d = draw(img)
            for g in range(5):  # speaker grille
                d.line((knob_x - 40, y + 260 + g * 20, knob_x + 40, y + 260 + g * 20), fill=rgba((40, 30, 24)), width=6)
        else:
            tv_knobs(img, knob_x, y + 80, 3, 26, colour=(250, 240, 225), gap=90)
        slots.append(list(screen))
    d = draw(img)
    for x0, x1 in ((180, 260), (720, 800)):  # wood TV legs
        d.line((x0, 640, x0 - 20, 690), fill=rgba((60, 32, 14)), width=16)
    d.line((560, 110, 470, 10), fill=rgba((80, 80, 86)), width=8)  # rabbit ears on the wood set
    d.line((560, 110, 680, 14), fill=rgba((80, 80, 86)), width=8)
    d.ellipse((520, 80, 600, 130), fill=rgba((50, 50, 56)))
    labels = font("VT323.ttf", 44)
    for (x, y, w, h), ch in zip(slots, ["CH 2", "CH 4", "CH 7", "CH 9"]):
        d.text((x + w - 16, y + 14), ch, font=labels, fill=(120, 255, 140, 255), anchor="rt")
    img = cut(img, slots, radius=40)
    crt_glass(img, slots, 40)
    return img, slots, {"stamp": "bl"}


# ---------- Arcade high score (4) ----------
def arcade():
    img = new(L, (8, 6, 20))
    d = draw(img)
    px = 20
    colours = [(255, 50, 120), (60, 220, 255), (255, 220, 40), (120, 255, 90)]
    for i, x in enumerate(range(0, W, px)):
        for y in (0, px, H - 2 * px, H - px):
            if (i + y // px) % 3 == 0:
                d.rectangle((x, y, x + px - 2, y + px - 2), fill=rgba(colours[i % 4]))
    for j, y in enumerate(range(0, H, px)):
        for x in (0, px, W - 2 * px, W - px):
            if (j + x // px) % 3 == 0:
                d.rectangle((x, y, x + px - 2, y + px - 2), fill=rgba(colours[j % 4]))
    slots = grid(2, 2, 90, 200, W - 90, H - 80, 40)
    f = font("VT323.ttf", 80)
    d.text((100, 110), "1UP  PLAYER 1", font=f, fill=rgba((255, 50, 120)), anchor="lm")
    d.text((W - 100, 110), "HIGH SCORE 999990", font=f, fill=rgba((60, 220, 255)), anchor="rm")
    heart_px = ["01100110", "11111111", "11111111", "01111110", "00111100", "00011000"]
    for hx in (CX - 110, CX - 30, CX + 50):
        pixel_sprite(d, hx, 85, [r.replace("1", "h").replace("0", ".") for r in heart_px], 9, {"h": rgba((255, 50, 80))})
    for x, y, w, h in slots:
        d.rectangle((x - 10, y - 10, x + w + 9, y + h + 9), outline=rgba((255, 255, 255)), width=6)
    return cut(img, slots), slots, {}


# ---------- Pac-Maze (4) ----------
def pac_maze(size=L, slots=None):
    w, h = size
    img = new(size, (0, 0, 0))
    d = draw(img)
    blue = (33, 33, 222, 255)
    slots = slots or grid(2, 2, 170, 210, w - 170, h - 140, 150, 110)
    maze_walls(d, [(18, 120, w - 18, h - 18)], blue, width=7, gap=14, radius=30)
    maze_walls(d, [(x - 34, y - 34, x + sw + 34, y + sh + 34) for x, y, sw, sh in slots], blue, width=6, gap=12, radius=22)
    # Dots and power pellets along the corridors between the walls.
    xs = sorted({slots[0][0] - 75, slots[0][0] + slots[0][2] + 75, slots[-1][0] + slots[-1][2] + 75})
    ys = sorted({slots[0][1] - 75, slots[0][1] + slots[0][3] + 55, slots[-1][1] + slots[-1][3] + 75})
    peach = (255, 184, 151, 255)
    for y in ys:
        for x in range(int(xs[0]), int(xs[-1]) + 1, 42):
            d.ellipse((x - 6, y - 6, x + 6, y + 6), fill=peach)
    for x in xs:
        for y in range(int(ys[0]), int(ys[-1]) + 1, 42):
            d.ellipse((x - 6, y - 6, x + 6, y + 6), fill=peach)
    for x, y in ((xs[0], ys[0]), (xs[-1], ys[0]), (xs[0], ys[-1]), (xs[-1], ys[-1])):
        d.ellipse((x - 20, y - 20, x + 20, y + 20), fill=peach)
    # Pac-Man chasing four ghosts along the top corridor.
    ty = ys[0]
    for x, y in ((xs[0] + 180 + k * 42, ty) for k in range(4)):
        d.ellipse((x - 9, y - 9, x + 9, y + 9), fill=(0, 0, 0, 255))  # eaten dots
    pacman(d, xs[0] + 360, ty, 44, facing=0)
    for k, colour in enumerate(GHOSTS):
        ghost(d, xs[0] + 520 + k * 120, ty, 44, colour, look=(1, 0) if k % 2 else (1, -0.5))
    ghost(d, xs[-1], ys[1] + 180 if len(ys) > 1 else ty, 44, GHOSTS[0], scared=True)
    pa = font("PressStart.ttf", 38)
    d.text((60, 62), "1UP", font=pa, fill=rgba((255, 255, 255)), anchor="lm")
    d.text((200, 62), "003450", font=pa, fill=rgba((255, 255, 255)), anchor="lm")
    d.text((w / 2, 62), "HIGH SCORE", font=pa, fill=rgba((255, 255, 255)), anchor="mm")
    d.text((w - 60, 62), "999990", font=pa, fill=rgba((255, 255, 255)), anchor="rm")
    d.text((w / 2, ys[1] if len(ys) > 2 else h / 2), "READY!", font=font("PressStart.ttf", 34), fill=rgba((255, 255, 0)),
           anchor="mm")
    for k in range(3):  # lives
        pacman(d, 70 + k * 64, h - 60, 22, facing=180)
    cherry = ["....gg", "...g..", "..g...", ".rr.rr", "rrrrrr", "rrr.rr", ".r..r."]
    pixel_sprite(d, w - 140, h - 100, cherry, 9, {"g": rgba((0, 200, 0)), "r": rgba((240, 0, 0))})
    return cut(img, slots, radius=10), slots, {}


# ---------- Space invaders (3) ----------
def invaders(size=L, slots=None, rows=3):
    w, h = size
    img = new(size, (0, 0, 8))
    d = draw(img)
    rnd = random.Random(111)
    for _ in range(400):
        x, y, s = rnd.uniform(0, w), rnd.uniform(0, h), rnd.choice([1, 1, 2, 3])
        d.rectangle((x, y, x + s, y + s), fill=(255, 255, 255, rnd.randint(80, 220)))
    green = (60, 255, 80, 255)
    colours = [(255, 80, 200, 255), (80, 220, 255, 255), (255, 240, 80, 255)]
    for r in range(rows):
        sprite = INVADERS[r % 3]
        n = 9 if w > h else 6
        for c in range(n):
            x = w * 0.08 + c * (w * 0.84 / (n - 1)) - 40
            pixel_sprite(d, x, 130 + r * 70, [row.replace("x", "c") for row in sprite], 8, {"c": colours[r % 3]})
    slots = slots or grid(3, 1, 90, 400, w - 90, 820, 50)
    for x, y, sw, sh in slots:
        d.rectangle((x - 8, y - 8, x + sw + 7, y + sh + 7), outline=green, width=6)
    bunker = ["..xxxxxx..", ".xxxxxxxx.", "xxxxxxxxxx", "xxxxxxxxxx", "xxx....xxx", "xx......xx"]
    for k in range(4):
        pixel_sprite(d, w * (0.14 + 0.24 * k), h - 260, [r.replace("x", "g") for r in bunker], 12, {"g": green})
    cannon = [".....x.....", "....xxx....", ".xxxxxxxxx.", "xxxxxxxxxxx", "xxxxxxxxxxx"]
    pixel_sprite(d, w / 2 - 60, h - 150, [r.replace("x", "g") for r in cannon], 11, {"g": green})
    d.line((w / 2 - 5, h - 160, w / 2 - 5, h - 330), fill=(255, 255, 255, 255), width=6)
    d.line((0, h - 80, w, h - 80), fill=green, width=6)
    pa = font("PressStart.ttf", 34)
    d.text((60, 60), "SCORE<1> 0420", font=pa, fill=rgba((255, 255, 255)), anchor="lm")
    d.text((w - 60, 60), "HI-SCORE 9990", font=pa, fill=rgba((255, 255, 255)), anchor="rm")
    d.text((w / 2, h - 40), "INSERT COIN", font=font("PressStart.ttf", 26), fill=rgba((255, 255, 255)), anchor="mm")
    ufo = ["....xxxx....", "..xxxxxxxx..", ".xxxxxxxxxx.", "xx.xx.xx.xxx", "xxxxxxxxxxxx", "..xxx..xxx..", "...x....x..."]
    pixel_sprite(d, w - 260, 90 if w > h else 100, [r.replace("x", "r") for r in ufo], 8, {"r": rgba((255, 40, 40))})
    return cut(img, slots), slots, {}


# ---------- Falling blocks (4) ----------
def falling_blocks(size=L, slots=None):
    w, h = size
    img = new(size, (16, 16, 40))
    d = draw(img)
    for x in range(0, w, 50):
        d.line((x, 0, x, h), fill=(255, 255, 255, 14), width=2)
    for y in range(0, h, 50):
        d.line((0, y, w, y), fill=(255, 255, 255, 14), width=2)
    s = 50
    slots = slots or [[140, 110, 600, 450], [790, 110, 600, 450], [140, 640, 600, 450], [790, 640, 600, 450]]
    # A stacked well on the right with the next piece and the score.
    panel = (1440, 60, w - 40, h - 60)
    d.rectangle(panel, fill=rgba((8, 8, 24)), outline=rgba((200, 200, 230)), width=6)
    pa = font("PressStart.ttf", 26)
    d.text((panel[0] + 30, 110), "NEXT", font=pa, fill=rgba((255, 255, 255)), anchor="lm")
    tetromino(d, "T", panel[0] + 70, 150, 50)
    for k, (lab, val) in enumerate((("SCORE", "026100"), ("LINES", "42"), ("LEVEL", "09"))):
        d.text((panel[0] + 30, 330 + k * 130), lab, font=pa, fill=rgba((255, 255, 255)), anchor="lm")
        d.text((panel[0] + 30, 380 + k * 130), val, font=font("PressStart.ttf", 34), fill=rgba((255, 220, 60)), anchor="lm")
    rnd = random.Random(121)
    kinds = list(TETROMINOES)
    # Pieces tumbling down the gaps and piled along the bottom.
    for x, y, rot, kind in ((20, 120, 1, "I"), (20, 600, 0, "L"), (1390 - 110, 560, 1, "S"), (680, 560, 0, "O"),
                            (20, 900, 2, "J")):
        tetromino(d, kind, x, y, s, rot)
    for col in range(0, 28):
        height = rnd.choice([0, 0, 1, 1, 1])
        for r in range(height):
            bevel_block(d, col * s, h - (r + 1) * s, s, TETROMINOES[rnd.choice(kinds)][1])
    for x, y, sw, sh in slots:
        d.rectangle((x - 12, y - 12, x + sw + 11, y + sh + 11), fill=rgba((230, 230, 250)))
    return cut(img, slots), slots, {}


# ---------- Handheld consoles, linked (2) ----------
def handheld(img, box, screen):
    x0, y0, x1, y1 = box
    sx, sy, sw, sh = screen
    shadow(img, box, offset=(14, 20), blur=18, alpha=150, radius=40)
    d = draw(img)
    d.rounded_rectangle(box, radius=40, fill=rgba((196, 196, 188)))
    d.rounded_rectangle((x0, y0, x1, y1), radius=40, outline=rgba((150, 150, 144)), width=5)
    d.pieslice((x1 - 200, y1 - 200, x1 + 200, y1 + 200), 180, 270, fill=rgba((186, 186, 178)))  # the classic rounded corner
    d.rounded_rectangle((sx - 70, sy - 60, sx + sw + 70, sy + sh + 70), radius=24, fill=rgba((90, 92, 110)))
    d.ellipse((sx - 52, sy + sh / 2 - 10, sx - 32, sy + sh / 2 + 10), fill=rgba((220, 30, 40)))
    d.text((sx - 42, sy + sh / 2 + 32), "BATTERY", font=font("OldStandard.ttf", 14), fill=rgba((200, 200, 210)), anchor="mm")
    d.text(((x0 + x1) / 2 - 40, sy + sh + 110), "PHOTO BOY", font=vfont("Cinzel.ttf", 38, 900), fill=rgba((40, 40, 120)),
           anchor="mm")
    cx, cy = x0 + 130, y1 - 190  # D-pad
    d.rectangle((cx - 60, cy - 20, cx + 60, cy + 20), fill=rgba((40, 40, 44)))
    d.rectangle((cx - 20, cy - 60, cx + 20, cy + 60), fill=rgba((40, 40, 44)))
    for k, (bx, by) in enumerate(((x1 - 210, cy + 20), (x1 - 110, cy - 40))):
        d.ellipse((bx - 36, by - 36, bx + 36, by + 36), fill=rgba((170, 30, 80)))
        d.text((bx, by + 60), "BA"[k], font=vfont("Cinzel.ttf", 26, 900), fill=rgba((40, 40, 120)), anchor="mm")
    for k in range(2):
        mx = (x0 + x1) / 2 - 60 + k * 100
        d.rounded_rectangle((mx - 34, y1 - 80, mx + 34, y1 - 64), radius=8, fill=rgba((120, 120, 120)))
    for k in range(6):
        gx = x1 - 160 + k * 22
        d.line((gx, y1 - 110, gx - 30, y1 - 40), fill=rgba((150, 150, 144)), width=6)


def handhelds():
    img = noise(L, (58, 120, 150), 6, 131)
    halftone(img, (70, 135, 165), spacing=36, base=4, amp=3)
    slots = [[150, 200, 520, 440], [1130, 200, 520, 440]]
    for k, (box, scr) in enumerate((((60, 60, 860, 1140), slots[0]), ((940, 60, 1740, 1140), slots[1]))):
        handheld(img, box, scr)
    d = draw(img)
    for px in (842, 942):  # link cable: a plug in each, the wire sagging between
        d.rounded_rectangle((px - 16, 330, px + 16, 400), radius=6, fill=rgba((80, 80, 90)))
    d.line([(842, 400), (860, 470), (900, 500), (940, 470), (942, 400)], fill=rgba((50, 50, 60)), width=14, joint="curve")
    img = cut(img, slots, radius=6)
    over = layer(img)
    od = ImageDraw.Draw(over)
    for x, y, w, h in slots:  # a faint green LCD tint and pixel grid over the photos
        od.rectangle((x, y, x + w, y + h), fill=(120, 160, 30, 40))
        for yy in range(y, y + h, 6):
            od.line((x, yy, x + w, yy), fill=(0, 0, 0, 22), width=1)
    img.alpha_composite(over)
    d = draw(img)
    d.text((CX, 1170), "2 PLAYER LINK", font=font("PressStart.ttf", 22), fill=rgba((255, 255, 255)), anchor="mb")
    return img, slots, {}


# ---------- Marquee (3) ----------
def marquee():
    img = new(L, (90, 8, 16))
    d = draw(img)
    for x in range(0, W, 60):
        d.rectangle((x, 0, x + 30, H), fill=rgba((120, 14, 26)))
        d.line((x + 30, 0, x + 30, H), fill=(0, 0, 0, 60), width=4)
    vignette(img, 0.8)
    board = (70, 230, W - 70, 920)
    shadow(img, board, offset=(0, 20), blur=30, alpha=200)
    d = draw(img)
    d.rectangle(board, fill=rgba((24, 20, 18)), outline=rgba((200, 160, 70)), width=10)
    sign = (380, 30, W - 380, 200)
    d.rectangle(sign, fill=rgba((250, 244, 228)), outline=rgba((200, 160, 70)), width=10)
    d.text((CX, 115), "NOW SHOWING", font=font("Limelight.ttf", 100), fill=rgba((150, 20, 30)), anchor="mm")
    slots = grid(3, 1, 150, 330, W - 150, 740, 50)
    for k, (x, y, w, h) in enumerate(slots):
        d.text((x + w / 2, 815), ["THE SMILE", "THE POSE", "THE ENCORE"][k], font=font("Limelight.ttf", 46),
               fill=rgba((255, 220, 140)), anchor="mm")
    bulbs = layer(img)
    bd = ImageDraw.Draw(bulbs)
    x0, y0, x1, y1 = board
    pts = [(x, y0 + 30) for x in range(x0 + 40, x1 - 20, 66)] + [(x, y1 - 30) for x in range(x0 + 40, x1 - 20, 66)]
    pts += [(x0 + 30, y) for y in range(y0 + 96, y1 - 60, 66)] + [(x1 - 30, y) for y in range(y0 + 96, y1 - 60, 66)]
    pts += [(x, sign[3] + 24) for x in range(sign[0] + 30, sign[2], 70)]
    for x, y in pts:
        bd.ellipse((x - 26, y - 26, x + 26, y + 26), fill=(255, 200, 90, 160))
    img.alpha_composite(bulbs.filter(ImageFilter.GaussianBlur(12)))
    d = draw(img)
    for x, y in pts:
        d.ellipse((x - 12, y - 12, x + 12, y + 12), fill=rgba((255, 246, 210)))
    d.rectangle((520, 990, W - 520, 1120), fill=rgba((24, 20, 18)), outline=rgba((200, 160, 70)), width=6)
    d.text((CX, 1055), "STARRING  YOU", font=font("Limelight.ttf", 60), fill=rgba((255, 220, 140)), anchor="mm")
    return cut(img, slots), slots, {}


# ---------- Hawaii travel poster (3) ----------
def travel_poster(size, slots, seed, title_y, headline=True):
    """Vintage travel-poster landscape: layered sunset sky, Diamond Head, sea, an outrigger
    canoe and dark palm fronds, with grain and a slight print misregistration."""
    w, h = size
    img = vgrad(size, [(0, (250, 176, 90)), (0.35, (246, 120, 90)), (0.6, (120, 70, 130)), (1, (30, 40, 90))])
    d = draw(img)
    horizon = h * 0.62
    sun = (w * 0.7, horizon - h * 0.08)
    for k, r in enumerate((h * 0.2, h * 0.15, h * 0.11)):  # banded sun
        d.ellipse((sun[0] - r, sun[1] - r, sun[0] + r, sun[1] + r), fill=rgba([(255, 200, 120), (255, 220, 140), (255, 240, 190)][k]))
    for k in range(4):
        y = sun[1] + h * 0.02 + k * h * 0.025
        d.rectangle((sun[0] - h * 0.2, y, sun[0] + h * 0.2, y + h * 0.008), fill=rgba((246, 140, 90)))
    # Diamond Head in three layers of haze.
    for k, (col, lift) in enumerate((((150, 90, 120), 0.14), ((110, 70, 110), 0.1), ((70, 50, 90), 0.06))):
        pts = [(0, horizon)]
        rnd = random.Random(seed + k)
        for i in range(13):
            x = w * (0.05 + i * 0.07)
            y = horizon - h * lift * math.sin(math.pi * i / 12) ** 0.7 - rnd.uniform(0, h * 0.02)
            pts.append((x, y))
        pts.append((w, horizon))
        d.polygon(pts, fill=rgba(col))
    sea = vgrad((w, int(h - horizon)), [(0, (60, 90, 150)), (1, (20, 40, 90))])
    img.alpha_composite(sea, (0, int(horizon)))
    d = draw(img)
    for k in range(40):  # sun glitter
        y = horizon + 10 + k * (h - horizon) / 44
        half = h * 0.12 * (1 - k / 44)
        d.line((sun[0] - half, y, sun[0] + half, y), fill=(255, 210, 150, int(200 * (1 - k / 44))), width=3)
    # Outrigger canoe with paddlers.
    cx, cy = w * 0.32, horizon + (h - horizon) * 0.35
    dark = (20, 16, 30, 255)
    d.polygon([(cx - 160, cy), (cx + 170, cy), (cx + 130, cy + 22), (cx - 130, cy + 22)], fill=dark)
    d.line((cx - 120, cy + 50, cx + 120, cy + 50), fill=dark, width=8)
    for t in (-80, 60):
        d.line((cx + t, cy + 10, cx + t, cy + 50), fill=dark, width=6)
    for k in range(4):
        px = cx - 110 + k * 70
        d.ellipse((px - 10, cy - 50, px + 10, cy - 30), fill=dark)
        d.line((px, cy - 30, px, cy), fill=dark, width=10)
        d.line((px - 30, cy - 28, px + 30, cy + 34), fill=dark, width=4)
    palm(d, w * 0.04, h + 40, h * 0.75, w * 0.12, dark, frond_len=h * 0.32, seed=seed + 5)
    palm(d, w * 0.98, h + 40, h * 0.62, -w * 0.08, dark, frond_len=h * 0.28, seed=seed + 6)
    # Grain over everything, the way a lithograph print looks.
    grain = noise(size, (128, 128, 128), 18, seed)
    grain.putalpha(28)
    img.alpha_composite(grain)
    d = draw(img)
    if headline:
        f = font("Monoton.ttf", int(min(w, h) * 0.16))
        d.text((w / 2 + 6, title_y + 6), "HAWAII", font=f, fill=rgba((40, 30, 60)), anchor="mm")
        d.text((w / 2, title_y), "HAWAII", font=f, fill=rgba((255, 240, 210)), anchor="mm")
    return img


def hawaii_poster():
    art_w = 1060
    img = new(L, (246, 236, 214))
    art = travel_poster((art_w, H), None, 141, 170)
    img.alpha_composite(art)
    d = draw(img)
    spaced_text(d, (art_w / 2, 330), "FLY TO THE ISLANDS", vfont("Cinzel.ttf", 46, 700), rgba((255, 240, 210)), 8)
    spaced_text(d, (art_w / 2, 390), "OF ALOHA", vfont("Cinzel.ttf", 46, 700), rgba((255, 240, 210)), 8)
    d.text((art_w / 2, H - 70), "PAN-PACIFIC PHOTO BOOTH LINES", font=vfont("Cinzel.ttf", 32, 600), fill=rgba((250, 240, 220)),
           anchor="mm")
    grain = noise((W - art_w, H), (128, 128, 128), 10, 142)
    grain.putalpha(20)
    img.alpha_composite(grain, (art_w, 0))
    slots = grid(1, 3, art_w + 70, 70, W - 70, H - 70, 0, 40)
    mat(img, slots, 12, (255, 252, 244))
    d = draw(img)
    d.rectangle((26, 26, W - 27, H - 27), outline=rgba((250, 240, 220)), width=10)
    d.line((art_w, 26, art_w, H - 26), fill=rgba((250, 240, 220)), width=10)
    return cut(img, slots), slots, {}


# ---------- Aloha shirt print (4) ----------
def plumeria(d, cx, cy, r, colour, centre, angle=0):
    for k in range(5):
        a = math.radians(angle + k * 72)
        leaf(d, cx + r * 0.55 * math.cos(a), cy + r * 0.55 * math.sin(a), r * 1.1, r * 0.6, angle + k * 72 + 20, colour)
    d.ellipse((cx - r * 0.25, cy - r * 0.25, cx + r * 0.25, cy + r * 0.25), fill=centre)


def aloha_print(size, seed, base=(22, 34, 72)):
    """A dense, overlapping Aloha-shirt print on woven fabric."""
    w, h = size
    img = noise(size, base, 6, seed)
    rnd = random.Random(seed)
    greens = [(30, 120, 80, 255), (50, 150, 100, 255), (20, 90, 70, 255), (80, 170, 110, 255)]
    for _ in range(int(w * h / 60000)):
        monstera(img, rnd.uniform(-60, w + 60), rnd.uniform(-60, h + 60), rnd.randint(110, 200), rnd.randint(0, 359),
                 rnd.choice(greens), (10, 60, 40, 255))
    d = draw(img)
    for _ in range(int(w * h / 40000)):  # palm-frond sprays
        cx, cy, a0 = rnd.uniform(0, w), rnd.uniform(0, h), rnd.uniform(0, 360)
        for k in range(9):
            a = math.radians(a0 + k * 12)
            leaf(d, cx + 70 * math.cos(a), cy + 70 * math.sin(a), 140, 22, math.degrees(a), rnd.choice(greens))
    for _ in range(int(w * h / 26000)):
        x, y = rnd.uniform(0, w), rnd.uniform(0, h)
        if rnd.random() < 0.55:
            petal, dark = rnd.choice([((240, 60, 80), (150, 20, 40)), ((250, 140, 50), (190, 70, 20)), ((250, 200, 210), (200, 90, 120))])
            hibiscus(d, x, y, rnd.randint(55, 85), rgba(petal), rgba(dark), angle=rnd.randint(0, 72))
        else:
            plumeria(d, x, y, rnd.randint(28, 44), (255, 250, 236, 255), (250, 200, 60, 255), rnd.randint(0, 72))
    for y in range(0, h, 3):  # weave
        d.line((0, y, w, y), fill=(255, 255, 255, 12), width=1)
    return img


def aloha_shirt():
    img = aloha_print(L, 151)
    slots = grid(2, 2, 160, 90, W - 160, H - 90, 80, 60)
    mat(img, slots, 18, (252, 248, 236), radius=10)
    d = draw(img)
    # A sewn-in label in the middle.
    box = (CX - 120, CY - 46, CX + 120, CY + 46)
    shadow(img, box, offset=(3, 5), blur=4, alpha=120)
    d = draw(img)
    d.rectangle(box, fill=rgba((250, 244, 228)))
    d.rectangle((box[0] + 8, box[1] + 8, box[2] - 8, box[3] - 8), outline=rgba((180, 40, 50)), width=2)
    d.text((CX, CY - 8), "Aloha", font=font("GreatVibes.ttf", 56), fill=rgba((180, 40, 50)), anchor="mm")
    d.text((CX, CY + 28), "MADE IN HAWAII", font=font("SpecialElite.ttf", 16), fill=rgba((60, 60, 60)), anchor="mm")
    for k in range(int((box[2] - box[0]) / 14)):  # stitches
        x = box[0] + 4 + k * 14
        d.line((x, box[1] + 3, x + 7, box[1] + 3), fill=rgba((120, 100, 80)), width=2)
        d.line((x, box[3] - 3, x + 7, box[3] - 3), fill=rgba((120, 100, 80)), width=2)
    return cut(img, slots, radius=6), slots, {}


# ---------- Army camo (4) ----------
def army_camo():
    img = camo(OCP_BASE, OCP_LAYERS, seed=115, size=L)
    slots = grid(2, 2, 330, 60, W - 60, H - 60, 36)
    shadow(img, (40, 40, 290, H - 40))
    d = draw(img)
    d.rectangle((40, 40, 290, H - 40), fill=rgba((56, 58, 40)), outline=rgba((30, 30, 20)), width=6)
    army_star(d, 165, 210, 85)
    words = Image.new("RGBA", (800, 200), (0, 0, 0, 0))
    spaced_text(ImageDraw.Draw(words), (400, 100), "U.S. ARMY", bold("Oswald.ttf", 150, 700), rgba((226, 214, 170)), 16)
    words = words.rotate(90, expand=True)
    img.alpha_composite(words, (165 - words.width // 2, 750 - words.height // 2))
    d = draw(img)
    for x, y, w, h in slots:
        d.rectangle((x - 8, y - 8, x + w + 7, y + h + 7), outline=rgba((30, 28, 20)), width=6)
    return cut(img, slots, radius=6), slots, {}


# ---------- Army black & gold (3) ----------
def army_gold():
    img = new(L, ARMY_BLACK)
    d = draw(img)
    for x in range(-H, W, 46):
        d.line((x, H, x + H, 0), fill=rgba((38, 38, 38)), width=3)
    d.rectangle((0, 0, 560, H), fill=rgba((12, 12, 12)))
    d.line((560, 0, 560, H), fill=rgba(ARMY_GOLD), width=8)
    army_star(d, 280, 330, 170)
    spaced_text(d, (280, 680), "U.S. ARMY", bold("Oswald.ttf", 100, 700), rgba(ARMY_WHITE), 10)
    spaced_text(d, (280, 800), "BE ALL YOU", bold("Oswald.ttf", 62, 600), rgba(ARMY_GOLD), 8)
    spaced_text(d, (280, 880), "CAN BE", bold("Oswald.ttf", 62, 600), rgba(ARMY_GOLD), 8)
    for k in range(5):
        d.polygon(star_points(280 + (k - 2) * 60, 1010, 18), fill=rgba(ARMY_WHITE))
    slots = [[620, 60, W - 680, 620]] + grid(2, 1, 620, 720, W - 60, H - 60, 40)
    for x, y, w, h in slots:
        d.rectangle((x - 8, y - 8, x + w + 7, y + h + 7), outline=rgba(ARMY_GOLD), width=6)
    return cut(img, slots), slots, {}


# ---------- Army stars & stripes (2) ----------
def army_flag():
    NAVY, RED, WHITE = (26, 38, 82), (178, 34, 52), (255, 255, 255)
    img = new(L, WHITE)
    d = draw(img)
    stripe = H / 13
    for k in range(0, 13, 2):
        d.rectangle((0, k * stripe, W, (k + 1) * stripe), fill=rgba(RED))
    d.rectangle((0, 0, W, 300), fill=rgba(NAVY))
    for row in range(3):
        for col in range(18):
            x, y = 50 + col * 100 + (50 if row % 2 else 0), 60 + row * 90
            if x < W - 30 and not (CX - 420 < x < CX + 420):
                d.polygon(star_points(x, y, 22), fill=rgba(WHITE))
    army_star(d, CX - 300, 150, 95)
    spaced_text(d, (CX + 120, 150), "U.S. ARMY", bold("Oswald.ttf", 120, 700), rgba(WHITE), 16)
    d.line((0, 300, W, 300), fill=rgba(ARMY_GOLD), width=8)
    slots = grid(2, 1, 100, 400, W - 100, 980, 70)
    for x, y, w, h in slots:
        d.rectangle((x - 16, y - 16, x + w + 15, y + h + 15), fill=rgba(NAVY))
        d.rectangle((x - 7, y - 7, x + w + 6, y + h + 6), outline=rgba(ARMY_GOLD), width=4)
    return cut(img, slots), slots, {}


# ================= THE ATKINSONS (wedding) =================
NAME = "The Atkinsons"


def atk_deco_black():
    """Art Deco black and gold: stepped borders, sunburst fans, the name in gold leaf."""
    bg, gold, soft = (14, 14, 16), (206, 170, 100), (120, 100, 66)
    img = new(L, bg)
    d = draw(img)
    for x in range(0, W, 24):  # faint vertical pinstripes
        d.line((x, 0, x, H), fill=rgba((24, 24, 26)), width=2)
    d.rectangle((24, 24, W - 25, H - 25), outline=rgba(gold), width=5)
    d.rectangle((40, 40, W - 41, H - 41), outline=rgba(soft), width=2)
    deco_corners(d, (56, 56, W - 57, H - 57), rgba(gold), 90)
    slots = grid(2, 2, 190, 300, W - 190, H - 110, 70, 50)
    for x, y, w, h in slots:
        d.rectangle((x - 16, y - 16, x + w + 15, y + h + 15), outline=rgba(gold), width=3)
        d.rectangle((x - 8, y - 8, x + w + 7, y + h + 7), outline=rgba(soft), width=2)
    gradient_text(img, (CX, 150), NAME, font("GreatVibes.ttf", 170), GOLD_LEAF)
    d = draw(img)
    for s in (-1, 1):
        d.line((CX + s * 360, 160, CX + s * 700, 160), fill=rgba(soft), width=2)
        d.polygon([(CX + s * 700, 150), (CX + s * 712, 160), (CX + s * 700, 170), (CX + s * 688, 160)], fill=rgba(gold))
    ry = (slots[0][1] + slots[0][3] + slots[2][1]) / 2  # interlocking rings between the rows
    for cx in (CX - 20, CX + 20):
        d.ellipse((cx - 28, ry - 28, cx + 28, ry + 28), outline=rgba(gold), width=5)
    return cut(img, slots), slots, {}


def atk_gown():
    """The bride's gown: blush satin, lace scallops, pearl strands, gold belt."""
    blush, gown, gold, lace = (243, 228, 224), (255, 255, 253), (198, 161, 91), (226, 208, 203)
    img = noise(L, blush, 3, 162)
    d = draw(img)
    for x in range(0, W, 44):  # lace scallops top and bottom
        for y in (0, H):
            d.ellipse((x, y - 26, x + 44, y + 26), fill=rgba(gown))
            d.ellipse((x + 15, y - 7, x + 29, y + 7), fill=rgba(lace))
    for y in (40, H - 40):  # pearl strands
        for x in range(30, W, 30):
            d.ellipse((x - 9, y - 9, x + 9, y + 9), fill=rgba(gown), outline=rgba(lace), width=2)
            d.ellipse((x - 4, y - 5, x, y - 1), fill=(255, 255, 255, 255))
    slots = grid(3, 1, 90, 300, W - 90, 720, 50)
    for x, y, w, h in slots:
        shadow(img, (x - 14, y - 14, x + w + 14, y + h + 14), offset=(4, 8), blur=10, alpha=70)
        draw(img).rectangle((x - 14, y - 14, x + w + 14, y + h + 14), fill=rgba(gown), outline=rgba(gold), width=3)
    d = draw(img)
    d.rectangle((0, 820, W, 840), fill=rgba(gold))  # the gold belt
    d.text((CX, 170), NAME, font=font("GreatVibes.ttf", 160), fill=rgba(gold), anchor="mm")
    spaced_text(d, (CX, 930), "TWO HEARTS  ·  ONE LOVE", font("PoiretOne.ttf", 52), rgba(gold), 8)
    dress(d, CX - 70, 990, 60, rgba(gown), rgba(gold))
    bowtie(d, CX + 80, 1050, 40, rgba((40, 40, 44)))
    return cut(img, slots), slots, {}


def atk_garden():
    """Garden party: eucalyptus garland, blush roses, sage, the couple's name in green."""
    cream, sage, dsage, blush, gold = (246, 242, 233), (138, 154, 123), (94, 110, 82), (232, 180, 176), (196, 160, 98)
    img = paper(L, cream, 163, amount=3, fibres=False)
    d = draw(img)
    d.rectangle((24, 24, W - 25, H - 25), outline=rgba(sage), width=3)
    slots = [[110, 300, 820, 615], [1000, 200, 690, 400], [1000, 650, 690, 400]]
    for x, y, w, h in slots:
        d.rectangle((x - 10, y - 10, x + w + 9, y + h + 9), outline=rgba(sage), width=3)
    over = layer(img)
    o = ImageDraw.Draw(over, "RGBA")
    rnd = random.Random(163)
    for k in range(-14, 15):  # garland along the top
        x = CX - 300 + k * 40 - 400
        if 0 < x < 960:
            leaf(o, x, 120 + 30 * math.sin(k / 3), 60, 24, 80 + k * 9, rgba(sage if k % 2 else dsage))
    for (x, y, w, h), corner in zip(slots, [(0, 0), (1, 0), (1, 1)]):
        fx, fy = x + corner[0] * w, y + corner[1] * h
        for k in range(6):
            leaf(o, fx + rnd.randint(-60, 60), fy + rnd.randint(-60, 60), 70, 26, rnd.randint(0, 180),
                 rgba(sage if rnd.random() > 0.4 else dsage))
        flower(o, fx, fy, 44, rgba(blush), rgba(gold))
        flower(o, fx + rnd.choice([-60, 60]), fy + rnd.choice([-50, 50]), 28, rgba((248, 214, 210)), rgba(gold))
    img.alpha_composite(over)
    d = draw(img)
    d.text((480, 190), NAME, font=font("GreatVibes.ttf", 150), fill=rgba(dsage), anchor="mm")
    spaced_text(d, (CX, H - 70), "A GARDEN OF LOVE", font("PoiretOne.ttf", 46), rgba(sage), 10)
    return cut(img, slots), slots, {}


def atk_champagne():
    """Champagne toast: wine red, gold rules, two flutes clinking with sparkles."""
    wine, gold, soft, fizz = (74, 20, 38), (216, 178, 110), (140, 90, 80), (232, 200, 130)
    img = new(L, wine)
    d = draw(img)
    d.rectangle((24, 24, W - 25, H - 25), outline=rgba(gold), width=4)
    d.rectangle((38, 38, W - 39, H - 39), outline=rgba(soft), width=2)
    f = af.flute_img(120, rgba(gold), rgba(fizz))
    left, right = f.rotate(-18, expand=True, resample=Image.BICUBIC), f.rotate(18, expand=True, resample=Image.BICUBIC)
    img.alpha_composite(left, (CX - left.width + 50, 400))
    img.alpha_composite(right, (CX - 50, 400))
    d = draw(img)
    sparkle(d, CX, 430, 30, rgba(gold))
    for dx, dy, s in [(-80, 400, 12), (85, 390, 14), (-50, 480, 8), (60, 470, 9)]:
        sparkle(d, CX + dx, dy, s, rgba(gold))
    slots = [[100, 260, 620, 465], [100, 770, 620, 340], [W - 720, 260, 620, 465], [W - 720, 770, 620, 340]]
    for x, y, w, h in slots:
        d.rectangle((x - 10, y - 10, x + w + 9, y + h + 9), outline=rgba(gold), width=3)
    d.text((CX, 140), NAME, font=font("GreatVibes.ttf", 150), fill=rgba(gold), anchor="mm")
    spaced_text(d, (CX, 860), "CHEERS", font("PoiretOne.ttf", 56), rgba(gold), 14)
    spaced_text(d, (CX, 930), "TO LOVE", font("PoiretOne.ttf", 56), rgba(gold), 14)
    return cut(img, slots), slots, {}


def atk_just_married():
    """Just Married: navy, pennant bunting, confetti and hearts."""
    navy, blush, gold, white = (30, 42, 71), (242, 196, 192), (212, 175, 106), (250, 248, 244)
    img = new(L, navy)
    d = draw(img)
    letters = "JUST MARRIED"
    n = len(letters)
    pts = [(150 + i * ((W - 300) / (n - 1)), 40 + 70 * math.sin(math.pi * i / (n - 1))) for i in range(n)]
    d.line(pts, fill=rgba(gold), width=5)
    colours = [white, blush, gold]
    for i, (ch, (px, py)) in enumerate(zip(letters, pts)):
        if ch == " ":
            continue
        d.polygon([(px - 50, py), (px + 50, py), (px, py + 170)], fill=rgba(colours[i % 3]))
        d.text((px, py + 55), ch, font=font("Limelight.ttf", 60), fill=rgba(navy), anchor="mm")
    rnd = random.Random(164)
    slots = grid(3, 1, 90, 340, W - 90, 760, 50)
    for _ in range(320):
        x, y = rnd.randint(20, W - 20), rnd.randint(250, H - 20)
        c = rgba(rnd.choice([blush, gold, white]))
        r = rnd.random()
        if r < 0.35:
            heart(d, x, y, rnd.randint(8, 14), c)
        elif r < 0.7:
            s = rnd.randint(3, 6)
            d.ellipse((x - s, y - s, x + s, y + s), fill=c)
        else:
            sparkle(d, x, y, rnd.randint(7, 12), c)
    for x, y, w, h in slots:
        d.rectangle((x - 12, y - 12, x + w + 11, y + h + 11), fill=rgba(white))
    img = cut(img, slots)
    d = draw(img)
    heart(d, CX, 880, 24, rgba(blush))
    d.text((CX, 1020), NAME, font=font("GreatVibes.ttf", 140), fill=rgba(white), anchor="mm")
    return img, slots, {}


DESIGNS = [
    ("Gallery White", gallery_white), ("Polaroid Cork Board", polaroid_cork), ("Contact Sheet", contact_sheet),
    ("Postcard: Greetings from Hawaii", postcard_hawaii), ("Postcard: Air Mail", postcard_airmail),
    ("Postcard: The Back", postcard_back), ("Postcard: Greetings from Paradise", postcard_paradise),
    ("Magazine Cover", magazine_cover), ("Comic Book", comic_book), ("Newspaper", newspaper_landscape),
    ("Passport", passport_landscape), ("Museum Wall", museum_wall), ("Our Favorite Day", favorite_day),
    ("TV Stack", tv_stack), ("Arcade High Score", arcade), ("Pac-Maze", pac_maze), ("Space Invaders", invaders),
    ("Falling Blocks", falling_blocks), ("Handhelds", handhelds), ("Marquee", marquee),
    ("Hawaii Travel Poster", hawaii_poster), ("Aloha Shirt", aloha_shirt),
    ("Army Camo", army_camo), ("Army Black & Gold", army_gold), ("Army Stars & Stripes", army_flag),
    ("The Atkinsons: Deco", atk_deco_black), ("The Atkinsons: The Gown", atk_gown),
    ("The Atkinsons: Garden Party", atk_garden), ("The Atkinsons: Champagne", atk_champagne),
    ("The Atkinsons: Just Married", atk_just_married),
]
