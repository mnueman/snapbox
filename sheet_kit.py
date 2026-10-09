"""Drawing kit for the BIG SHEET designs (sheet_frames.py): canvas helpers, textures and
reusable pieces (gold frames, arcade sprites, newsprint, stamps, TVs...). Everything takes its
size from the image it draws on, so the same piece works on landscape and portrait sheets."""
import math, random
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

import all_frames as af
from all_frames import font, rgba, star_points, spaced_text

af.FONT_URLS.update({
    name: "https://raw.githubusercontent.com/google/fonts/main/" + path for name, path in {
        "Unifraktur.ttf": "ofl/unifrakturmaguntia/UnifrakturMaguntia-Book.ttf",
        "Playfair.ttf": "ofl/playfairdisplay/PlayfairDisplay%5Bwght%5D.ttf",
        "OldStandard.ttf": "ofl/oldstandardtt/OldStandard-Regular.ttf",
        "OldStandardBold.ttf": "ofl/oldstandardtt/OldStandard-Bold.ttf",
        "PressStart.ttf": "ofl/pressstart2p/PressStart2P-Regular.ttf",
        "Rye.ttf": "ofl/rye/Rye-Regular.ttf",
        "Caveat.ttf": "ofl/caveat/Caveat%5Bwght%5D.ttf",
        "Cinzel.ttf": "ofl/cinzel/Cinzel%5Bwght%5D.ttf",
        "Bebas.ttf": "ofl/bebasneue/BebasNeue-Regular.ttf",
        "Monoton.ttf": "ofl/monoton/Monoton-Regular.ttf",
        "Dancing.ttf": "ofl/dancingscript/DancingScript%5Bwght%5D.ttf",
        "SpecialElite.ttf": "apache/specialelite/SpecialElite-Regular.ttf",
    }.items()})

L = (1800, 1200)  # landscape 6x4
P = (1200, 1800)  # portrait 4x6


def vfont(name, size, weight):
    """A variable font at a given weight."""
    f = font(name, size)
    f.set_variation_by_axes([weight])
    return f


def new(size, colour):
    return Image.new("RGBA", size, rgba(colour))


def draw(img):
    return ImageDraw.Draw(img, "RGBA")


def layer(img):
    return Image.new("RGBA", img.size, (0, 0, 0, 0))


def grid(cols, rows, x0, y0, x1, y1, gap, gap_y=None):
    gap_y = gap if gap_y is None else gap_y
    w = (x1 - x0 - gap * (cols - 1)) // cols
    h = (y1 - y0 - gap_y * (rows - 1)) // rows
    return [[x0 + c * (w + gap), y0 + r * (h + gap_y), w, h] for r in range(rows) for c in range(cols)]


def centred(cols, rows, w, h, gap, area, gap_y=None):
    """cols x rows photos of w x h, centred in area (x0, y0, x1, y1)."""
    gap_y = gap if gap_y is None else gap_y
    x0, y0, x1, y1 = area
    tw, th = cols * w + (cols - 1) * gap, rows * h + (rows - 1) * gap_y
    ox, oy = x0 + (x1 - x0 - tw) // 2, y0 + (y1 - y0 - th) // 2
    return [[ox + c * (w + gap), oy + r * (h + gap_y), w, h] for r in range(rows) for c in range(cols)]


def cut(img, slots, radius=0):
    """Makes the photo openings transparent (everything else is made opaque first, so translucent
    drawing never leaves see-through spots outside the photos)."""
    img.putalpha(255)
    mask = Image.new("L", img.size, 255)
    md = ImageDraw.Draw(mask)
    for x, y, w, h in slots:
        md.rounded_rectangle((x, y, x + w - 1, y + h - 1), radius=radius, fill=0)
    img.putalpha(mask)
    return img


def vgrad(size, stops):
    """Vertical gradient through [(t, colour)] stops."""
    w, h = size
    img = Image.new("RGBA", size)
    d = ImageDraw.Draw(img)
    for y in range(h):
        t = y / max(1, h - 1)
        for (t0, c0), (t1, c1) in zip(stops, stops[1:]):
            if t <= t1:
                k = (t - t0) / max(1e-6, t1 - t0)
                d.line((0, y, w, y), fill=tuple(int(a + (b - a) * k) for a, b in zip(c0, c1)) + (255,))
                break
    return img


def noise(size, base, amount, seed, blur=0.0, scale=1):
    """Flat colour with grain (paper, fabric, card). scale > 1 makes coarser grain."""
    w, h = size
    rnd = np.random.default_rng(seed)
    n = rnd.normal(0, amount, (h // scale + 1, w // scale + 1, 1)).astype(np.float32)
    n = np.repeat(np.repeat(n, scale, 0), scale, 1)[:h, :w]
    arr = np.clip(np.array(base, np.float32)[None, None, :] + n, 0, 255).astype(np.uint8)
    img = Image.fromarray(arr, "RGB")
    if blur:
        img = img.filter(ImageFilter.GaussianBlur(blur))
    return img.convert("RGBA")


def paper(size, base, seed, amount=7, fibres=True, stains=0):
    """Old paper: grain, faint fibres, darker edges, optional age spots."""
    img = noise(size, base, amount, seed, blur=0.6)
    w, h = size
    rnd = random.Random(seed)
    d = draw(img)
    if fibres:
        for _ in range(w * h // 9000):
            x, y = rnd.uniform(0, w), rnd.uniform(0, h)
            a = rnd.uniform(0, math.pi)
            ln = rnd.uniform(6, 22)
            d.line((x, y, x + ln * math.cos(a), y + ln * math.sin(a)), fill=(120, 100, 70, 40), width=1)
    for _ in range(stains):
        x, y, r = rnd.uniform(0, w), rnd.uniform(0, h), rnd.uniform(30, 120)
        st = layer(img)
        ImageDraw.Draw(st).ellipse((x - r, y - r, x + r, y + r), outline=(140, 100, 50, 50), width=6)
        img.alpha_composite(st.filter(ImageFilter.GaussianBlur(6)))
    vignette(img, 0.35, (90, 60, 30))
    return img


def vignette(img, strength, colour=(0, 0, 0)):
    """Darkens the edges towards colour."""
    w, h = img.size
    ys = np.linspace(-1, 1, h, dtype=np.float32)[:, None]
    xs = np.linspace(-1, 1, w, dtype=np.float32)[None, :]
    a = np.clip(((xs * xs + ys * ys) / 2) ** 1.6 * strength * 255, 0, 255).astype(np.uint8)
    over = Image.new("RGBA", img.size, rgba(colour))
    over.putalpha(Image.fromarray(a, "L"))
    img.alpha_composite(over)


def shadow(img, box, offset=(10, 14), blur=14, alpha=120, radius=0):
    sh = layer(img)
    x0, y0, x1, y1 = box
    ImageDraw.Draw(sh).rounded_rectangle((x0 + offset[0], y0 + offset[1], x1 + offset[0], y1 + offset[1]),
                                         radius=radius, fill=(0, 0, 0, alpha))
    img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(blur)))


def mat(img, slots, pad, colour, radius=0, drop=True, outline=None):
    """A border (mat, print margin) around each photo, with a soft drop shadow."""
    for x, y, w, h in slots:
        box = (x - pad, y - pad, x + w + pad - 1, y + h + pad - 1)
        if drop:
            shadow(img, box, offset=(6, 9), blur=10, alpha=110, radius=radius)
        draw(img).rounded_rectangle(box, radius=radius, fill=rgba(colour),
                                    outline=rgba(outline) if outline else None, width=3)


def glow(img, painter, blur, times=2):
    """Draws painter(draw) on a layer, adds it blurred (the glow) then sharp."""
    g = layer(img)
    painter(ImageDraw.Draw(g, "RGBA"))
    soft = g.filter(ImageFilter.GaussianBlur(blur))
    for _ in range(times):
        img.alpha_composite(soft)
    img.alpha_composite(g)


def text_shadow(img, xy, text, f, fill, shadow_fill=(0, 0, 0, 140), offset=(5, 6), blur=4, anchor="mm", **kw):
    sh = layer(img)
    ImageDraw.Draw(sh).text((xy[0] + offset[0], xy[1] + offset[1]), text, font=f, fill=shadow_fill, anchor=anchor, **kw)
    img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(blur)))
    draw(img).text(xy, text, font=f, fill=rgba(fill) if len(fill) == 3 else fill, anchor=anchor, **kw)


def gradient_text(img, xy, text, f, stops, anchor="mm", stroke=0, stroke_fill=None, shadow_offset=None):
    """Text filled with a vertical gradient (chrome, sunset, gold leaf)."""
    mask = Image.new("L", img.size, 0)
    ImageDraw.Draw(mask).text(xy, text, font=f, fill=255, anchor=anchor)
    box = mask.getbbox()
    if not box:
        return
    if shadow_offset:
        sh = layer(img)
        ImageDraw.Draw(sh).text((xy[0] + shadow_offset[0], xy[1] + shadow_offset[1]), text, font=f,
                                fill=rgba(stroke_fill or (0, 0, 0)), anchor=anchor, stroke_width=stroke,
                                stroke_fill=rgba(stroke_fill or (0, 0, 0)))
        img.alpha_composite(sh)
    if stroke:
        draw(img).text(xy, text, font=f, fill=rgba(stroke_fill), anchor=anchor, stroke_width=stroke,
                       stroke_fill=rgba(stroke_fill))
    g = vgrad((box[2] - box[0] + 1, box[3] - box[1] + 1), stops)
    full = layer(img)
    full.paste(g, (box[0], box[1]))
    img.paste(full, (0, 0), mask)


GOLD_LEAF = [(0, (250, 226, 150)), (0.45, (214, 170, 80)), (0.55, (170, 124, 50)), (1, (238, 204, 120))]
CHROME = [(0, (255, 255, 255)), (0.45, (180, 190, 210)), (0.55, (80, 90, 120)), (1, (220, 228, 245))]


# ---------------- frames and borders ----------------
def gold_frame(img, slot, thick, ornate=True):
    """An ornate gilded picture frame around a photo: bevelled moulding, beads, corner bosses."""
    x, y, w, h = slot
    d = draw(img)
    shadow(img, (x - thick, y - thick, x + w + thick, y + h + thick), offset=(14, 22), blur=22, alpha=170)
    d = draw(img)
    steps = [(1.0, (120, 84, 30)), (0.86, (226, 186, 96)), (0.7, (176, 132, 52)), (0.55, (246, 214, 130)),
             (0.36, (150, 108, 40)), (0.2, (214, 172, 84)), (0.08, (90, 60, 20))]
    for k, colour in steps:
        t = thick * k
        d.rectangle((x - t, y - t, x + w + t, y + h + t), fill=rgba(colour))
    d.rectangle((x - 2, y - 2, x + w + 2, y + h + 2), fill=rgba((60, 40, 14)))
    if ornate:
        bead = max(3, int(thick * 0.06))
        mid = thick * 0.45
        for t in range(0, w + int(2 * mid), int(bead * 3.2)):
            for yy in (y - mid, y + h + mid):
                cx = x - mid + t
                d.ellipse((cx - bead, yy - bead, cx + bead, yy + bead), fill=rgba((252, 226, 150)),
                          outline=rgba((140, 100, 36)))
        for t in range(0, h + int(2 * mid), int(bead * 3.2)):
            for xx in (x - mid, x + w + mid):
                cy = y - mid + t
                d.ellipse((xx - bead, cy - bead, xx + bead, cy + bead), fill=rgba((252, 226, 150)),
                          outline=rgba((140, 100, 36)))
        r = thick * 0.55
        for cx, cy in ((x - mid, y - mid), (x + w + mid, y - mid), (x - mid, y + h + mid), (x + w + mid, y + h + mid)):
            d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=rgba((226, 186, 96)), outline=rgba((120, 84, 30)), width=3)
            for k in range(8):
                a = math.pi * k / 4
                af.leaf(d, cx + r * 0.55 * math.cos(a), cy + r * 0.55 * math.sin(a), r * 0.75, r * 0.32,
                        math.degrees(a), rgba((250, 218, 130)))
            d.ellipse((cx - r * 0.25, cy - r * 0.25, cx + r * 0.25, cy + r * 0.25), fill=rgba((150, 108, 40)))


def plaque(img, centre, text, sub=None, w=300, h=70):
    """Brass museum label under a painting."""
    cx, cy = centre
    box = (cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)
    shadow(img, box, offset=(3, 4), blur=4, alpha=120)
    d = draw(img)
    d.rectangle(box, fill=rgba((200, 164, 92)), outline=rgba((120, 90, 40)), width=3)
    d.text((cx, cy - (10 if sub else 0)), text, font=vfont("Cinzel.ttf", 26, 700), fill=rgba((50, 34, 10)), anchor="mm")
    if sub:
        d.text((cx, cy + 18), sub, font=font("OldStandard.ttf", 20), fill=rgba((60, 44, 18)), anchor="mm")


def deco_corners(d, box, colour, size, width=4):
    """Art Deco stepped corner ornaments inside box."""
    x0, y0, x1, y1 = box
    for cx, cy, sx, sy in ((x0, y0, 1, 1), (x1, y0, -1, 1), (x0, y1, 1, -1), (x1, y1, -1, -1)):
        for k in range(3):
            o = k * size * 0.22
            d.line((cx + sx * o, cy + sy * (size - o), cx + sx * o, cy + sy * o, cx + sx * (size - o), cy + sy * o),
                   fill=colour, width=width, joint="curve")
        d.polygon([(cx + sx * size * 0.75, cy + sy * size * 0.75), (cx + sx * size * 0.88, cy + sy * size * 0.62),
                   (cx + sx * size, cy + sy * size * 0.75), (cx + sx * size * 0.88, cy + sy * size * 0.88)], fill=colour)


def deco_fan(d, cx, cy, r, colour, rays=9, start=180, end=360, width=4):
    """A sunburst fan (Art Deco), rays from (cx, cy)."""
    for k in range(rays):
        a = math.radians(start + (end - start) * k / (rays - 1))
        d.line((cx, cy, cx + r * math.cos(a), cy + r * math.sin(a)), fill=colour, width=width)
    for rr in (r * 0.35, r * 0.7, r):
        d.arc((cx - rr, cy - rr, cx + rr, cy + rr), start, end, fill=colour, width=width)


# ---------------- arcade ----------------
def pixel_sprite(d, x, y, rows, px, palette):
    """Pixel art: rows of characters, each a colour key in palette ('.' = clear)."""
    for r, row in enumerate(rows):
        for c, ch in enumerate(row):
            if ch != "." and ch in palette:
                d.rectangle((x + c * px, y + r * px, x + (c + 1) * px - 1, y + (r + 1) * px - 1), fill=palette[ch])


def pacman(d, cx, cy, r, mouth=35, facing=0, colour=(255, 230, 0, 255)):
    d.pieslice((cx - r, cy - r, cx + r, cy + r), facing + mouth, facing + 360 - mouth, fill=colour)


def ghost(d, cx, cy, r, colour, look=(1, 0), scared=False):
    """Arcade ghost: dome, wavy skirt, eyes looking somewhere."""
    body = (40, 60, 220, 255) if scared else colour
    d.pieslice((cx - r, cy - r, cx + r, cy + r), 180, 360, fill=body)
    d.rectangle((cx - r, cy, cx + r, cy + r * 0.8), fill=body)
    n = 4
    for k in range(n):
        x0 = cx - r + k * 2 * r / n
        d.polygon([(x0, cy + r * 0.8), (x0 + r / n, cy + r * 1.05), (x0 + 2 * r / n, cy + r * 0.8)], fill=body)
    if scared:
        for ex in (-0.35, 0.35):
            d.rectangle((cx + ex * r - r * 0.08, cy - r * 0.2, cx + ex * r + r * 0.08, cy - r * 0.04), fill=(255, 220, 200, 255))
        d.line([(cx - r * 0.6, cy + r * 0.4), (cx - r * 0.3, cy + r * 0.25), (cx, cy + r * 0.4), (cx + r * 0.3, cy + r * 0.25),
                (cx + r * 0.6, cy + r * 0.4)], fill=(255, 220, 200, 255), width=max(2, int(r * 0.08)))
        return
    for ex in (-0.38, 0.38):
        ex_c, ey_c = cx + ex * r, cy - r * 0.15
        d.ellipse((ex_c - r * 0.24, ey_c - r * 0.3, ex_c + r * 0.24, ey_c + r * 0.3), fill=(255, 255, 255, 255))
        px, py = ex_c + look[0] * r * 0.11, ey_c + look[1] * r * 0.13
        d.ellipse((px - r * 0.12, py - r * 0.13, px + r * 0.12, py + r * 0.13), fill=(30, 50, 200, 255))


GHOSTS = [(255, 0, 0, 255), (255, 184, 255, 255), (0, 255, 255, 255), (255, 184, 82, 255)]


def maze_walls(d, rects, colour, width=6, gap=12, radius=16):
    """Double-line arcade maze walls around each rectangle."""
    for x0, y0, x1, y1 in rects:
        d.rounded_rectangle((x0, y0, x1, y1), radius=radius, outline=colour, width=width)
        d.rounded_rectangle((x0 + gap, y0 + gap, x1 - gap, y1 - gap), radius=max(2, radius - gap), outline=colour, width=width)


def bevel_block(d, x, y, s, colour):
    """A falling-block tile with a light top-left and dark bottom-right bevel."""
    r, g, b = colour[:3]
    light = (min(255, r + 80), min(255, g + 80), min(255, b + 80), 255)
    dark = (r // 2, g // 2, b // 2, 255)
    e = max(3, s // 7)
    d.rectangle((x, y, x + s - 1, y + s - 1), fill=(r, g, b, 255))
    d.polygon([(x, y), (x + s, y), (x + s - e, y + e), (x + e, y + e), (x + e, y + s - e), (x, y + s)], fill=light)
    d.polygon([(x + s, y + s), (x, y + s), (x + e, y + s - e), (x + s - e, y + s - e), (x + s - e, y + e), (x + s, y)], fill=dark)


TETROMINOES = {"I": ([(0, 0), (1, 0), (2, 0), (3, 0)], (0, 220, 240)), "O": ([(0, 0), (1, 0), (0, 1), (1, 1)], (250, 220, 0)),
               "T": ([(0, 0), (1, 0), (2, 0), (1, 1)], (170, 60, 230)), "S": ([(1, 0), (2, 0), (0, 1), (1, 1)], (60, 220, 60)),
               "Z": ([(0, 0), (1, 0), (1, 1), (2, 1)], (240, 50, 50)), "J": ([(0, 0), (0, 1), (1, 1), (2, 1)], (40, 90, 240)),
               "L": ([(2, 0), (0, 1), (1, 1), (2, 1)], (250, 150, 20))}


def tetromino(d, kind, x, y, s, rot=0):
    cells, colour = TETROMINOES[kind]
    for _ in range(rot % 4):
        cells = [(-cy, cx) for cx, cy in cells]
    mx, my = min(c[0] for c in cells), min(c[1] for c in cells)
    for cx, cy in cells:
        bevel_block(d, x + (cx - mx) * s, y + (cy - my) * s, s, colour)


INVADERS = [
    ["..x.....x..", "...x...x...", "..xxxxxxx..", ".xx.xxx.xx.", "xxxxxxxxxxx", "x.xxxxxxx.x", "x.x.....x.x", "...xx.xx..."],
    ["...xxxx...", ".xxxxxxxx.", "xxxxxxxxxx", "xxx.xx.xxx", "xxxxxxxxxx", "..xx..xx..", ".xx.xx.xx.", "xx......xx"],
    ["...xx...", "..xxxx..", ".xxxxxx.", "xx.xx.xx", "xxxxxxxx", "..x..x..", ".x.xx.x.", "x.x..x.x"],
]


# ---------------- print and paper ----------------
def fake_text(d, box, line_h, colour, seed, para_every=7, indent=True):
    """Columns of 'text': short grey bars of word lengths, ragged right, paragraph breaks."""
    x0, y0, x1, y1 = box
    rnd = random.Random(seed)
    y, n = y0, 0
    while y + line_h * 0.6 <= y1:
        x = x0 + (line_h * 1.2 if indent and n % para_every == 0 else 0)
        end = x1 if n % para_every != para_every - 1 else x0 + (x1 - x0) * rnd.uniform(0.3, 0.7)
        while x < end - 12:
            wlen = min(end - x, rnd.uniform(line_h * 0.6, line_h * 2.6))
            d.rectangle((x, y + line_h * 0.25, x + wlen, y + line_h * 0.62), fill=colour)
            x += wlen + line_h * 0.35
        y += line_h
        n += 1


def guilloche(img, colours, seed, density=26, amp=40):
    """Security-printing wavy line pattern (passports, banknotes)."""
    w, h = img.size
    d = draw(img)
    rnd = random.Random(seed)
    for k in range(density):
        c = colours[k % len(colours)]
        phase = rnd.uniform(0, math.tau)
        period = rnd.uniform(160, 320)
        y_base = h * k / density
        pts = [(x, y_base + amp * math.sin(x / period * math.tau + phase) + amp * 0.5 * math.sin(x / (period * 0.37) + phase))
               for x in range(0, w + 8, 8)]
        d.line(pts, fill=c, width=2)
    for k in range(density // 2):
        c = colours[(k + 1) % len(colours)]
        phase = rnd.uniform(0, math.tau)
        x_base = w * k / (density // 2)
        pts = [(x_base + amp * math.sin(y / 230 * math.tau + phase), y) for y in range(0, h + 8, 8)]
        d.line(pts, fill=c, width=1)


def rubber_stamp(img, centre, r, lines, colour, angle, seed, ring=True, box=False):
    """A slightly patchy inked stamp (passport, postmark)."""
    cx, cy = centre
    size = int(r * 2.6)
    st = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(st)
    c = size / 2
    if ring and not box:
        d.ellipse((c - r, c - r, c + r, c + r), outline=colour, width=max(3, int(r * 0.06)))
        d.ellipse((c - r * 0.82, c - r * 0.82, c + r * 0.82, c + r * 0.82), outline=colour, width=max(2, int(r * 0.03)))
    if box:
        d.rounded_rectangle((c - r * 1.2, c - r * 0.7, c + r * 1.2, c + r * 0.7), radius=r * 0.15, outline=colour,
                            width=max(3, int(r * 0.06)))
    fs = [int(r * 0.32), int(r * 0.24), int(r * 0.2)]
    total = len(lines)
    for i, text in enumerate(lines):
        y = c + (i - (total - 1) / 2) * r * 0.36
        d.text((c, y), text, font=font("SpecialElite.ttf", fs[min(i, 2)]), fill=colour, anchor="mm")
    # Patchy ink: knock random specks out.
    rnd = np.random.default_rng(seed)
    a = np.asarray(st.getchannel("A"), np.float32)
    patch = rnd.random(a.shape) * 255
    blotch = np.asarray(Image.fromarray((rnd.random((size // 12 + 1, size // 12 + 1)) * 255).astype(np.uint8))
                        .resize((size, size), Image.BICUBIC), np.float32)
    a = a * (patch > 40) * np.clip(blotch / 160, 0.45, 1.0)
    st.putalpha(Image.fromarray(a.clip(0, 255).astype(np.uint8)))
    st = st.rotate(angle, resample=Image.BICUBIC)
    img.alpha_composite(st, (int(cx - c), int(cy - c)))


def postage_stamp(img, box, inner, perf=10, seed=0):
    """A perforated postage stamp; inner(draw, box) paints its picture. Returns the inner box."""
    x0, y0, x1, y1 = box
    shadow(img, box, offset=(4, 6), blur=5, alpha=90)
    d = draw(img)
    d.rectangle(box, fill=rgba((252, 250, 244)))
    bg = img.getpixel((int(x0) - 30, int(y0) - 30)) if x0 > 30 and y0 > 30 else (240, 230, 210, 255)
    step = perf * 2.2
    t = x0
    while t <= x1:
        for yy in (y0, y1):
            d.ellipse((t - perf / 2, yy - perf / 2, t + perf / 2, yy + perf / 2), fill=bg)
        t += step
    t = y0
    while t <= y1:
        for xx in (x0, x1):
            d.ellipse((xx - perf / 2, t - perf / 2, xx + perf / 2, t + perf / 2), fill=bg)
        t += step
    ib = (x0 + perf * 1.6, y0 + perf * 1.6, x1 - perf * 1.6, y1 - perf * 1.6)
    inner(d, ib)
    return ib


def postmark(img, centre, r, town, colour=(30, 30, 40, 200), angle=-12, waves=True):
    rubber_stamp(img, centre, r, [town, "★ 2026 ★", "PHOTO BOOTH"], colour, angle, seed=hash(town) % 1000)
    if waves:
        d = draw(img)
        cx, cy = centre
        for k in range(5):
            y = cy - r * 0.5 + k * r * 0.25
            pts = [(cx + r * 1.1 + t, y + 8 * math.sin(t / 22)) for t in range(0, int(r * 3), 6)]
            d.line(pts, fill=colour, width=4)


def airmail_border(img, inset, band, colours=((200, 30, 40), (30, 60, 150))):
    """The red-and-blue diagonal stripes round an airmail envelope."""
    w, h = img.size
    stripes = layer(img)
    sd = ImageDraw.Draw(stripes)
    step = band * 1.6
    k = 0
    t = -h
    while t < w + h:
        c = colours[k % 2] if k % 4 < 2 else None
        c = [colours[0], None, colours[1], None][k % 4]
        if c:
            sd.polygon([(t, 0), (t + band, 0), (t + band - h, h), (t - h, h)], fill=rgba(c))
        t += step / 2
        k += 1
    mask = Image.new("L", img.size, 255)
    ImageDraw.Draw(mask).rectangle((inset, inset, w - inset, h - inset), fill=0)
    img.paste(stripes, (0, 0), Image.composite(stripes.getchannel("A"), Image.new("L", img.size, 0), mask))


def washi_tape(img, centre, length, width, angle, colour, pattern=None):
    """A strip of patterned paper tape with torn ends."""
    cx, cy = centre
    t = Image.new("RGBA", (int(length) + 20, int(width) + 20), (0, 0, 0, 0))
    d = ImageDraw.Draw(t)
    pts = [(10, 10)]
    rnd = random.Random(int(cx * 7 + cy))
    for y in range(10, int(width) + 10, 6):
        pts.append((10 + rnd.uniform(-4, 4), y))
    pts.append((10, width + 10))
    pts2 = [(length + 10 + rnd.uniform(-4, 4), y) for y in range(int(width) + 10, 9, -6)]
    d.polygon(pts + pts2, fill=colour)
    if pattern == "dots":
        for x in range(24, int(length), 26):
            for y in range(20, int(width), 22):
                d.ellipse((x - 4, y - 4, x + 4, y + 4), fill=(255, 255, 255, 140))
    elif pattern == "stripes":
        for x in range(0, int(length) + int(width), 22):
            d.line((x, 10, x - width, width + 10), fill=(255, 255, 255, 110), width=7)
    t = t.rotate(angle, expand=True, resample=Image.BICUBIC)
    img.alpha_composite(t, (int(cx - t.width / 2), int(cy - t.height / 2)))


def ticket_stub(img, centre, w, h, angle, colour, title, sub):
    cx, cy = centre
    t = Image.new("RGBA", (int(w) + 30, int(h) + 30), (0, 0, 0, 0))
    d = ImageDraw.Draw(t)
    d.rectangle((15, 15, w + 15, h + 15), fill=colour)
    for k in range(int(h // 18)):  # notched edges
        y = 15 + k * 18 + 9
        d.ellipse((15 - 6, y - 6, 15 + 6, y + 6), fill=(0, 0, 0, 0))
        d.ellipse((w + 15 - 6, y - 6, w + 15 + 6, y + 6), fill=(0, 0, 0, 0))
    d.line((15 + w * 0.72, 22, 15 + w * 0.72, h + 8), fill=(255, 255, 255, 160), width=3)
    d.text((15 + w * 0.36, 15 + h * 0.38), title, font=vfont("Cinzel.ttf", int(h * 0.26), 700), fill=(255, 255, 255, 255), anchor="mm")
    d.text((15 + w * 0.36, 15 + h * 0.7), sub, font=font("SpecialElite.ttf", int(h * 0.16)), fill=(255, 255, 255, 230), anchor="mm")
    d.text((15 + w * 0.86, 15 + h / 2), "No. 026", font=font("SpecialElite.ttf", int(h * 0.14)), fill=(255, 255, 255, 230), anchor="mm")
    t = t.rotate(angle, expand=True, resample=Image.BICUBIC)
    img.alpha_composite(t, (int(cx - t.width / 2), int(cy - t.height / 2)))


def pressed_flower(img, centre, r, colour, seed):
    """A small dried flower with a stem, a little faded."""
    cx, cy = centre
    rnd = random.Random(seed)
    d = draw(img)
    a = rnd.uniform(0, math.tau)
    d.line((cx, cy, cx + r * 3 * math.cos(a), cy + r * 3 * math.sin(a)), fill=(110, 120, 70, 200), width=3)
    for k in range(3):
        t = rnd.uniform(0.3, 0.9)
        lx, ly = cx + r * 3 * t * math.cos(a), cy + r * 3 * t * math.sin(a)
        af.leaf(d, lx + 10 * math.cos(a + 1.2), ly + 10 * math.sin(a + 1.2), r * 0.9, r * 0.36,
                math.degrees(a + 1.2), (120, 130, 80, 200))
    for k in range(6):
        b = math.tau * k / 6 + rnd.uniform(-0.2, 0.2)
        af.leaf(d, cx + r * 0.6 * math.cos(b), cy + r * 0.6 * math.sin(b), r * 1.1, r * 0.55, math.degrees(b), colour)
    d.ellipse((cx - r * 0.25, cy - r * 0.25, cx + r * 0.25, cy + r * 0.25), fill=(230, 180, 60, 230))


# ---------------- vintage TV ----------------
def vintage_tv(img, body, screen, style, seed=0):
    """A vintage TV set around a screen (x, y, w, h): style picks the cabinet. Returns the
    screen glass box, which the caller adds as a photo slot."""
    x0, y0, x1, y1 = body
    sx, sy, sw, sh = screen
    rnd = random.Random(seed)
    shadow(img, body, offset=(16, 22), blur=20, alpha=170, radius=40)
    d = draw(img)
    if style == "wood":  # 1960s walnut console
        wood = noise((int(x1 - x0), int(y1 - y0)), (112, 66, 34), 10, seed, scale=1)
        wd = ImageDraw.Draw(wood)
        for k in range(0, int(y1 - y0), 7):  # grain
            wd.line((0, k + 3 * math.sin(k / 30), x1 - x0, k + 3 * math.sin(k / 30 + 2)),
                    fill=(84, 46, 22, rnd.randint(40, 110)), width=2)
        m = Image.new("L", wood.size, 0)
        ImageDraw.Draw(m).rounded_rectangle((0, 0, wood.width - 1, wood.height - 1), radius=36, fill=255)
        img.paste(wood, (int(x0), int(y0)), m)
        d = draw(img)
        d.rounded_rectangle(body, radius=36, outline=rgba((60, 32, 14)), width=6)
        bezel = (210, 196, 170)
    elif style == "orange":  # space-age round-cornered plastic
        d.rounded_rectangle(body, radius=int((x1 - x0) * 0.2), fill=rgba((236, 110, 30)))
        d.rounded_rectangle((x0 + 12, y0 + 10, x1 - 30, y0 + 40), radius=14, fill=(255, 180, 120, 120))
        bezel = (250, 240, 225)
    elif style == "cream":  # 1950s portable
        d.rounded_rectangle(body, radius=30, fill=rgba((232, 222, 196)))
        d.rounded_rectangle(body, radius=30, outline=rgba((170, 150, 110)), width=5)
        bezel = (120, 110, 96)
        d.rounded_rectangle(((x0 + x1) / 2 - 90, y0 - 34, (x0 + x1) / 2 + 90, y0 + 6), radius=18, outline=rgba((90, 80, 66)),
                            width=12)  # carry handle
    else:  # chrome and black
        d.rounded_rectangle(body, radius=26, fill=rgba((30, 30, 34)))
        d.rounded_rectangle((x0 + 8, y0 + 8, x1 - 8, y1 - 8), radius=22, outline=rgba((200, 204, 210)), width=8)
        bezel = (60, 60, 66)
    pad = max(18, int(min(sw, sh) * 0.07))
    d.rounded_rectangle((sx - pad, sy - pad, sx + sw + pad, sy + sh + pad), radius=int(min(sw, sh) * 0.16), fill=rgba(bezel))
    d.rounded_rectangle((sx - 10, sy - 10, sx + sw + 10, sy + sh + 10), radius=int(min(sw, sh) * 0.13),
                        fill=rgba((24, 22, 20)))
    return (sx, sy, sx + sw, sy + sh)


def tv_knobs(img, x, y, n, r, colour=(70, 60, 50), gap=None):
    d = draw(img)
    gap = gap or r * 2.8
    for k in range(n):
        cy = y + k * gap
        d.ellipse((x - r - 4, cy - r - 4, x + r + 4, cy + r + 4), fill=rgba((30, 26, 22)))
        d.ellipse((x - r, cy - r, x + r, cy + r), fill=rgba(colour))
        for t in range(12):
            a = math.tau * t / 12
            d.line((x + r * 0.75 * math.cos(a), cy + r * 0.75 * math.sin(a), x + r * math.cos(a), cy + r * math.sin(a)),
                   fill=rgba((40, 34, 28)), width=3)
        d.line((x, cy, x + r * 0.7 * math.cos(-0.9 + k), cy + r * 0.7 * math.sin(-0.9 + k)), fill=rgba((235, 225, 200)), width=5)


def crt_glass(img, slots, radius):
    """Scanlines and a glass reflection drawn over the photos (inside the openings, translucent)."""
    over = layer(img)
    od = ImageDraw.Draw(over)
    for x, y, w, h in slots:
        for yy in range(int(y), int(y + h), 5):
            od.line((x, yy, x + w, yy), fill=(0, 0, 0, 38), width=2)
        od.ellipse((x + w * 0.05, y - h * 0.4, x + w * 0.75, y + h * 0.35), fill=(255, 255, 255, 26))
    m = Image.new("L", img.size, 0)
    md = ImageDraw.Draw(m)
    for x, y, w, h in slots:
        md.rounded_rectangle((x, y, x + w - 1, y + h - 1), radius=radius, fill=255)
    vig = layer(img)
    vd = ImageDraw.Draw(vig)
    for x, y, w, h in slots:  # darker CRT corners
        for k in range(14):
            vd.rounded_rectangle((x + k, y + k, x + w - k, y + h - k), radius=radius, outline=(0, 0, 0, 60 - k * 4), width=2)
    over.alpha_composite(vig)
    over.putalpha(Image.composite(over.getchannel("A"), Image.new("L", img.size, 0), m))
    img.alpha_composite(over)
