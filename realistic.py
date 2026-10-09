"""Realistic themed frames (space, ocean, plants, outdoors) for every shape: strips
(frames/frame41..44), landscape sheets and portrait sheets (registered in sheets_landscape.py /
sheets_portrait.py). Painted procedurally with layered noise, lighting and depth haze.
Usage (from the photobooth folder): python3 realistic.py   (writes the strips; the sheets are
built by sheet_frames.py)
"""
import json, math, os, random
import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

import all_frames as af
from all_frames import font, rgba, spaced_text
from sheet_kit import cut, draw, layer, vfont, shadow, vignette, L, P

STRIP = (1200, 3600)


# ---------------- noise ----------------
def value_noise(w, h, cell, rnd):
    gw, gh = max(2, w // cell + 3), max(2, h // cell + 3)
    grid = (rnd.random((gh, gw)) * 255).astype(np.uint8)
    img = Image.fromarray(grid, "L").resize((gw * cell, gh * cell), Image.BICUBIC)
    return np.asarray(img.crop((cell, cell, cell + w, cell + h)), np.float32) / 255.0


def fbm(size, seed, base=256, octaves=6, gain=0.5):
    """Fractal noise in 0..1: octaves of smooth noise, each half the size and weight."""
    w, h = size
    rnd = np.random.default_rng(seed)
    out = np.zeros((h, w), np.float32)
    amp, total, cell = 1.0, 0.0, base
    for _ in range(octaves):
        out += amp * value_noise(w, h, max(2, int(cell)), rnd)
        total += amp
        amp *= gain
        cell /= 2
    out /= total
    return (out - out.min()) / max(1e-6, out.max() - out.min())


def ridged(size, seed, base=256, octaves=6):
    """Ridged noise: sharp crests like mountain ranges."""
    n = fbm(size, seed, base, octaves)
    return 1.0 - np.abs(n * 2 - 1)


def smoothstep(a, b, x):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def palette(t, stops):
    """Maps t (0..1 array) through colour stops [(t, (r, g, b))] to an RGB float array."""
    t = np.clip(t, 0, 1)
    out = np.zeros(t.shape + (3,), np.float32)
    for (t0, c0), (t1, c1) in zip(stops, stops[1:]):
        m = (t >= t0) & (t <= t1)
        k = ((t - t0) / max(1e-6, t1 - t0))[m][:, None]
        out[m] = np.array(c0, np.float32) * (1 - k) + np.array(c1, np.float32) * k
    return out


def to_img(arr):
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGB").convert("RGBA")


def screen_add(img, glow_img):
    base = img.convert("RGB")
    return ImageChops.screen(base, glow_img.convert("RGB")).convert("RGBA")


# ================= SPACE =================
def warp_fbm(size, seed, base, octaves=6, amount=0.25):
    """Domain-warped fractal noise: wispy, flowing shapes (nebulae, clouds, water)."""
    w, h = size
    n = fbm(size, seed, base, octaves)
    qx = fbm(size, seed + 101, base, 4)
    qy = fbm(size, seed + 202, base, 4)
    ys, xs = np.mgrid[0:h, 0:w]
    sx = np.clip(xs + (qx - 0.5) * amount * w, 0, w - 1).astype(np.int32)
    sy = np.clip(ys + (qy - 0.5) * amount * h, 0, h - 1).astype(np.int32)
    return n[sy, sx]


def noise1d(n, seed, base, octaves=6):
    return fbm((n, 4), seed, base, octaves)[1]


def add_stars(arr, seed, density, max_bright=1.0):
    """Pinpoint stars: mostly faint, a power-law few bright, slightly coloured, soft cores."""
    h, w = arr.shape[:2]
    rnd = np.random.default_rng(seed)
    n = int(w * h * density)
    xs = rnd.integers(0, w, n)
    ys = rnd.integers(0, h, n)
    b = (rnd.pareto(2.6, n) * 0.12).clip(0, 1.6) * max_bright
    temps = rnd.choice(3, n, p=[0.6, 0.25, 0.15])
    tint = np.array([(255, 255, 255), (200, 215, 255), (255, 225, 190)], np.float32)[temps]
    star = np.zeros_like(arr)
    np.add.at(star, (ys, xs), tint * b[:, None])
    soft = np.stack([np.asarray(Image.fromarray(np.clip(star[..., c], 0, 255).astype(np.uint8)).filter(
        ImageFilter.GaussianBlur(0.7)), np.float32) for c in range(3)], -1)
    arr += star * 0.6 + soft * 2.2
    # A few bright stars get a halo and faint diffraction spikes.
    big = np.argsort(b)[-max(3, n // 600):]
    glow = Image.new("RGB", (w, h), "black")
    gd = ImageDraw.Draw(glow)
    for i in big:
        x, y, bb = xs[i], ys[i], b[i]
        r = 1.5 + 2 * min(bb, 1.2)
        col = tuple(int(v * 0.4) for v in tint[i])
        gd.ellipse((x - r, y - r, x + r, y + r), fill=col)
        ln = r * 9
        gd.line((x - ln, y, x + ln, y), fill=col, width=1)
        gd.line((x, y - ln, x, y + ln), fill=col, width=1)
    arr += np.asarray(glow.filter(ImageFilter.GaussianBlur(2.5)), np.float32) * 1.2
    return arr


def starfield(size, seed):
    w, h = size
    arr = np.zeros((h, w, 3), np.float32)
    arr[...] = (2, 3, 8)
    base = max(w, h) // 2
    n1 = warp_fbm(size, seed + 1, base, 7, 0.35)
    n2 = warp_fbm(size, seed + 2, int(base * 0.8), 7, 0.3)
    dust = warp_fbm(size, seed + 3, base // 2, 6, 0.25)
    a = smoothstep(0.5, 1.0, n1) ** 2.2
    b = smoothstep(0.55, 1.0, n2) ** 2.4
    arr += a[..., None] * np.array((150, 50, 130), np.float32)
    arr += b[..., None] * np.array((35, 95, 170), np.float32)
    arr += (a * b)[..., None] * np.array((140, 100, 70), np.float32)
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    band = np.exp(-(((xs / w - 0.5) * 0.7 + (ys / h - 0.5)) ** 2) / 0.03)
    arr += (band * smoothstep(0.3, 0.9, n2))[..., None] * np.array((50, 46, 56), np.float32)
    arr *= (0.35 + 0.65 * smoothstep(0.3, 0.75, dust))[..., None]  # dark dust lanes
    arr = add_stars(arr, seed, 0.0035 * (1 + band.mean()), 1.4)
    dense = add_stars(np.zeros_like(arr), seed + 7, 0.004, 0.5)  # the Milky Way's star clouds
    arr += dense * band[..., None]
    return to_img(arr)


def planet(diameter, kind, seed, light=(-0.55, -0.45, 0.7), tilt=0.25):
    """A lit sphere with a surface texture mapped on (lat/long), an atmosphere where it has one.
    Returns an RGBA image a little larger than the planet (room for the glow)."""
    D = int(diameter)
    pad = int(D * 0.12)
    S = D + 2 * pad
    yy, xx = np.mgrid[0:S, 0:S].astype(np.float32)
    x = (xx - S / 2) / (D / 2)
    y = (yy - S / 2) / (D / 2)
    r2 = x * x + y * y
    inside = r2 <= 1
    z = np.sqrt(np.clip(1 - r2, 0, 1))
    # Tilt the axis, then latitude/longitude for the texture lookup.
    ct, st_ = math.cos(tilt), math.sin(tilt)
    xr, yr = x * ct - y * st_, x * st_ + y * ct
    lat = np.arcsin(np.clip(yr, -1, 1))
    lon = np.arctan2(xr, z)
    TW, TH = 1024, 512
    rnd = random.Random(seed)
    if kind == "gas":
        turb = fbm((TW, TH), seed, base=128, octaves=6)
        v = np.linspace(-1, 1, TH, dtype=np.float32)[:, None]
        bands = np.sin(v * 22 + turb * 4.0) * 0.5 + 0.5
        fine = np.sin(v * 70 + turb * 9) * 0.5 + 0.5
        tex = palette(0.3 + 0.4 * (bands * 0.7 + fine * 0.3), [(0, (150, 100, 70)), (0.35, (205, 165, 120)), (0.6, (232, 212, 182)),
                                                               (0.8, (190, 130, 90)), (1, (130, 90, 70))])
        sy, sx = int(TH * 0.62), int(TW * 0.55)  # a great storm
        yy2, xx2 = np.mgrid[0:TH, 0:TW]
        spot = np.exp(-(((xx2 - sx) / 60.0) ** 2 + ((yy2 - sy) / 26.0) ** 2))
        tex = tex * (1 - spot[..., None]) + spot[..., None] * np.array((200, 90, 60), np.float32)
    elif kind == "earth":
        hmap = fbm((TW, TH), seed, base=200, octaves=7)
        clouds = fbm((TW, TH), seed + 9, base=90, octaves=6)
        v = np.abs(np.linspace(-1, 1, TH, dtype=np.float32))[:, None] * np.ones((1, TW), np.float32)
        sea = palette(hmap / 0.55, [(0, (10, 30, 80)), (1, (30, 90, 150))])
        land = palette((hmap - 0.55) / 0.45, [(0, (60, 110, 50)), (0.4, (120, 120, 60)), (0.7, (150, 120, 80)), (1, (220, 220, 220))])
        is_land = (hmap > 0.55)[..., None]
        tex = np.where(is_land, land, sea)
        ice = smoothstep(0.78, 0.9, v)[..., None]
        tex = tex * (1 - ice) + ice * 245
        cl = smoothstep(0.55, 0.8, clouds)[..., None]
        tex = tex * (1 - cl * 0.9) + cl * 0.9 * 250
    elif kind == "mars":
        hmap = fbm((TW, TH), seed, base=160, octaves=7)
        tex = palette(hmap, [(0, (90, 40, 25)), (0.45, (170, 80, 45)), (0.7, (200, 110, 70)), (1, (225, 160, 120))])
        v = np.abs(np.linspace(-1, 1, TH, dtype=np.float32))[:, None] * np.ones((1, TW), np.float32)
        tex = tex * (1 - smoothstep(0.86, 0.95, v)[..., None]) + smoothstep(0.86, 0.95, v)[..., None] * 235
    elif kind == "moon":
        hmap = fbm((TW, TH), seed, base=150, octaves=7)
        tex = palette(hmap, [(0, (70, 70, 72)), (0.5, (140, 138, 135)), (1, (200, 198, 195))])
        img_t = to_img(tex)
        cd = ImageDraw.Draw(img_t, "RGBA")
        for _ in range(140):  # craters: dark floor, bright rim on one side
            cx, cy, cr = rnd.uniform(0, TW), rnd.uniform(0, TH), rnd.uniform(4, 34) * rnd.random() ** 1.5 + 3
            cd.ellipse((cx - cr, cy - cr, cx + cr, cy + cr), fill=(40, 40, 42, 90))
            cd.arc((cx - cr, cy - cr, cx + cr, cy + cr), 160, 340, fill=(230, 228, 225, 120), width=max(1, int(cr / 6)))
        tex = np.asarray(img_t.convert("RGB"), np.float32)
    else:  # "ice": a pale blue ice giant
        turb = fbm((TW, TH), seed, base=200, octaves=5)
        v = np.linspace(-1, 1, TH, dtype=np.float32)[:, None]
        bands = np.sin(v * 9 + turb * 2) * 0.5 + 0.5
        tex = palette(bands, [(0, (90, 150, 200)), (0.5, (140, 200, 230)), (1, (180, 225, 240))])
    u = ((lon / (2 * math.pi) + 0.5) * (TW - 1)).astype(np.int32) % TW
    vv = ((lat / math.pi + 0.5) * (TH - 1)).astype(np.int32).clip(0, TH - 1)
    col = tex[vv, u]
    lx, ly, lz = light
    ln = math.sqrt(lx * lx + ly * ly + lz * lz)
    ndl = (x * lx + y * ly + z * lz) / ln
    shade = 0.03 + 0.97 * smoothstep(-0.08, 0.55, ndl) * (0.55 + 0.45 * ndl.clip(0, 1))
    if kind in ("gas", "ice"):
        shade = shade * (0.6 + 0.4 * z ** 0.5)  # limb darkening
    rgb = col * shade[..., None]
    alpha = np.clip((1 - r2) * D * 0.5, 0, 1) * 255  # anti-aliased edge
    out = np.dstack([rgb, alpha]).astype(np.float32)
    img = Image.fromarray(np.clip(out, 0, 255).astype(np.uint8), "RGBA")
    if kind in ("earth", "ice"):
        # Atmosphere: a thin glowing rim on the lit side.
        rim = np.exp(-((np.sqrt(r2) - 1.0) / 0.035) ** 2) * smoothstep(-0.3, 0.6, (x * lx + y * ly) / ln + 0.2)
        rc = np.array((110, 170, 255) if kind == "earth" else (170, 220, 255), np.float32)
        glow = np.dstack([np.broadcast_to(rc, rim.shape + (3,)), rim * 230]).astype(np.uint8)
        g = Image.fromarray(glow, "RGBA").filter(ImageFilter.GaussianBlur(D * 0.01))
        img = Image.alpha_composite(img, g)
    return img


def ringed_planet(diameter, seed, light=(-0.55, -0.45, 0.7)):
    """A gas giant with smooth, banded rings (with a dark gap), the far half behind the planet
    and the planet's shadow falling on the rings behind it."""
    D = int(diameter)
    body = planet(D, "gas", seed, light, tilt=0.35)
    S = int(D * 2.6)
    ys, xs = np.mgrid[0:S, 0:S].astype(np.float32)
    c = S / 2
    tilt = math.radians(-18)
    x = (xs - c) * math.cos(tilt) - (ys - c) * math.sin(tilt)
    y = (xs - c) * math.sin(tilt) + (ys - c) * math.cos(tilt)
    flat = 0.27
    r = np.sqrt(x * x + (y / flat) ** 2) / (D / 2)
    prof = noise1d(1024, seed, 160, 7)
    idx = np.clip(((r - 1.25) / (2.3 - 1.25) * 1023), 0, 1023).astype(np.int32)
    dens = prof[idx] * (r > 1.25) * (r < 2.3)
    dens *= 1 - np.exp(-((r - 1.85) / 0.04) ** 2) * 0.95  # Cassini division
    dens = dens ** 1.3
    col = np.dstack([215 * np.ones_like(r), 195 * np.ones_like(r), 160 * np.ones_like(r)]) * (0.7 + 0.5 * prof[idx])[..., None]
    behind = y < 0
    in_shadow = behind & (np.abs(x) < D / 2 * 0.95) & (y > -D * 0.9)
    dens = np.where(in_shadow, dens * 0.35, dens)
    alpha = np.clip(dens * 255, 0, 230)
    rings = Image.fromarray(np.dstack([np.clip(col, 0, 255), alpha]).astype(np.uint8), "RGBA")
    back, front = rings.copy(), rings.copy()
    mb = Image.fromarray((behind * 255).astype(np.uint8), "L")
    back.putalpha(ImageChops.multiply(back.getchannel("A"), mb))
    front.putalpha(ImageChops.multiply(front.getchannel("A"), ImageChops.invert(mb)))
    out = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    out.alpha_composite(back)
    out.alpha_composite(body, (int(c - body.width / 2), int(c - body.height / 2)))
    out.alpha_composite(front)
    return out


def place(img, sprite, cx, cy):
    img.alpha_composite(sprite, (int(cx - sprite.width / 2), int(cy - sprite.height / 2)))


def space_scene(size, slots, seed, planets):
    """Starfield, nebula and planets [(kind, cx, cy, diameter)] painted around the photos."""
    img = starfield(size, seed)
    for kind, cx, cy, dia in planets:
        sprite = ringed_planet(dia, seed + int(cx)) if kind == "rings" else planet(dia, kind, seed + int(cx + cy))
        place(img, sprite, cx, cy)
    return img


def thin_frame(img, slots, colour, width=3, glow_colour=None, radius=8):
    d = draw(img)
    if glow_colour:
        g = layer(img)
        gd = ImageDraw.Draw(g)
        for x, y, w, h in slots:
            gd.rounded_rectangle((x - 6, y - 6, x + w + 5, y + h + 5), radius=radius + 4, outline=glow_colour, width=12)
        img.alpha_composite(g.filter(ImageFilter.GaussianBlur(10)))
        d = draw(img)
    for x, y, w, h in slots:
        d.rounded_rectangle((x - 4, y - 4, x + w + 3, y + h + 3), radius=radius, outline=colour, width=width)


# ================= OCEAN =================
def god_rays(size, src, seed, reach):
    """Light shafts fanning down from a point above the surface."""
    w, h = size
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    sx, sy = src
    ang = np.arctan2(xs - sx, ys - sy)
    t = (ang - ang.min()) / max(1e-6, ang.max() - ang.min())
    rays = noise1d(4096, seed, 70, 5)[np.clip((t * 4095).astype(np.int32), 0, 4095)]
    rays = smoothstep(0.45, 1.0, rays) ** 1.5
    dist = np.sqrt((xs - sx) ** 2 + (ys - sy) ** 2)
    return rays * np.exp(-dist / reach)


def caustics(size, seed, scale):
    w, h = size
    n = warp_fbm(size, seed, scale, 4, 0.08)
    n2 = warp_fbm(size, seed + 1, int(scale * 0.8), 4, 0.08)
    web = (1 - np.abs(np.sin(n * 20))) * (1 - np.abs(np.sin(n2 * 18)))
    return web ** 5


def branch_coral(d, x, y, ang, ln, width, colour, depth, rnd):
    if depth == 0 or ln < 6:
        d.ellipse((x - width, y - width, x + width, y + width), fill=tuple(min(255, int(v * 1.25)) for v in colour) + (255,))
        return
    x2, y2 = x + ln * math.cos(ang), y + ln * math.sin(ang)
    d.line((x, y, x2, y2), fill=colour + (255,), width=max(2, int(width)))
    d.line((x + width * 0.3, y, x2 + width * 0.3, y2), fill=tuple(min(255, int(v * 1.2)) for v in colour) + (200,),
           width=max(1, int(width * 0.3)))
    for k in range(rnd.choice([2, 2, 3])):
        branch_coral(d, x2, y2, ang + rnd.uniform(-0.6, 0.6), ln * rnd.uniform(0.62, 0.8), width * 0.72, colour, depth - 1, rnd)


def brain_coral(dia, colour, seed):
    D = int(dia)
    ys, xs = np.mgrid[0:int(D * 0.62), 0:D].astype(np.float32)
    # Unit size a little inside the image, so the bumpy outline never gets clipped flat.
    x = (xs - D / 2) / (D / 2) * 1.25
    y = (ys - D * 0.62) / (D * 0.62) * 1.25
    th = np.arctan2(y, x)
    ph = (seed % 100) / 10
    rr = 1 + 0.1 * np.sin(3 * th + ph) + 0.06 * np.sin(7 * th + ph * 2) + 0.04 * np.sin(13 * th)
    r2 = (x * x + y * y) / (rr * rr)
    z = np.sqrt(np.clip(1 - r2, 0, 1))
    maze = ridged((D, int(D * 0.62)), seed, base=max(4, D // 24), octaves=2)
    shade = (0.35 + 0.65 * np.clip(-0.5 * x - 0.7 * y + 0.5 * z, 0, 1)) * (0.8 + 0.2 * smoothstep(0.6, 0.95, maze))
    rgb = np.array(colour, np.float32)[None, None, :] * shade[..., None]
    alpha = (r2 <= 1) * 255
    return Image.fromarray(np.dstack([np.clip(rgb, 0, 255), alpha]).astype(np.uint8), "RGBA")


def sea_fan(d, x, y, height, colour, rnd):
    tips = []
    for k in range(26):
        a = math.radians(-160 + k * 140 / 25)
        ln = height * rnd.uniform(0.75, 1.0)
        pts = [(x, y)]
        cx, cy = x, y
        for s in range(6):
            cx += ln / 6 * math.cos(a + rnd.uniform(-0.1, 0.1))
            cy += ln / 6 * math.sin(a + rnd.uniform(-0.1, 0.1))
            pts.append((cx, cy))
        d.line(pts, fill=colour + (220,), width=2)
        tips.append(pts)
    for s in range(2, 6):  # the lace between the branches
        d.line([p[s] for p in tips], fill=colour + (110,), width=1)


def kelp(d, x, floor, top, scale, colour, rnd):
    pts = []
    for t in np.arange(floor, top, -10):
        sway = 40 * scale * math.sin((floor - t) / 160 + x) * (floor - t) / (floor - top + 1)
        pts.append((x + sway, t))
    d.line(pts, fill=tuple(int(v * 0.7) for v in colour) + (230,), width=max(2, int(5 * scale)), joint="curve")
    for i, (px, py) in enumerate(pts[2::3]):
        side = 1 if i % 2 else -1
        ln, wd = rnd.uniform(90, 160) * scale, rnd.uniform(18, 30) * scale
        a = math.radians(-90 + side * rnd.uniform(25, 50))
        blade = [(px, py)]
        for s in np.linspace(0, 1, 12):
            bx = px + ln * s * math.cos(a)
            by = py + ln * s * math.sin(a) + 20 * scale * math.sin(s * math.pi)
            blade.append((bx - wd * math.sin(math.pi * s) * math.sin(a) * 0.5, by + wd * math.sin(math.pi * s) * math.cos(a) * 0.5))
        for s in np.linspace(1, 0, 12):
            bx = px + ln * s * math.cos(a)
            by = py + ln * s * math.sin(a) + 20 * scale * math.sin(s * math.pi)
            blade.append((bx + wd * math.sin(math.pi * s) * math.sin(a) * 0.5, by - wd * math.sin(math.pi * s) * math.cos(a) * 0.5))
        d.polygon(blade, fill=colour + (190,))
        d.line(blade[:13], fill=tuple(min(255, int(v * 1.3)) for v in colour) + (120,), width=1)
    d.ellipse((pts[0][0] - 10 * scale, floor - 6 * scale, pts[0][0] + 10 * scale, floor + 6 * scale),
              fill=tuple(int(v * 0.5) for v in colour) + (255,))


def manta(d, cx, cy, s, colour):
    pts = []
    for t in np.linspace(0, 1, 30):
        pts.append((cx - s * t, cy + s * 0.15 * math.sin(math.pi * t) - s * 0.35 * t ** 1.5))
    for t in np.linspace(1, 0, 30):
        pts.append((cx - s * t * 0.8, cy + s * 0.35 * (1 - t) + s * 0.1 * t))
    right = [(2 * cx - x, y) for x, y in pts]
    d.polygon(pts, fill=colour)
    d.polygon(right, fill=colour)
    d.ellipse((cx - s * 0.22, cy - s * 0.1, cx + s * 0.22, cy + s * 0.55), fill=colour)
    d.line((cx, cy + s * 0.5, cx, cy + s * 1.3), fill=colour, width=max(2, int(s * 0.03)))


def ocean_scene(size, slots, seed):
    w, h = size
    rnd = random.Random(seed)
    ys = np.linspace(0, 1, h, dtype=np.float32)[:, None] * np.ones((1, w), np.float32)
    arr = palette(ys, [(0, (70, 190, 210)), (0.12, (24, 130, 175)), (0.45, (8, 70, 118)), (1, (2, 18, 40))])
    arr += god_rays(size, (w * 0.45, -h * 0.25), seed, h * 0.55)[..., None] * np.array((120, 190, 190), np.float32)
    arr += (caustics(size, seed, max(60, w // 9)) * (1 - smoothstep(0.0, 0.25, ys)))[..., None] * np.array((120, 200, 200), np.float32)
    snow = np.random.default_rng(seed).random((h, w)) > 0.9993  # marine snow
    arr[snow] += 70
    img = to_img(arr)
    # The surface from below: bright, rippled.
    surf = layer(img)
    sd = ImageDraw.Draw(surf)
    for k in range(24):
        y = k * h * 0.002
        pts = [(x, y + 7 * math.sin(x / 37 + k * 1.3) + 4 * math.sin(x / 13 + k)) for x in range(0, w + 8, 8)]
        sd.line(pts, fill=(230, 255, 255, 120 - k * 4), width=3)
    img.alpha_composite(surf.filter(ImageFilter.GaussianBlur(1.5)))
    # Far away: a manta and a fish school, faded into the blue.
    far = layer(img)
    fd = ImageDraw.Draw(far)
    manta(fd, w * 0.7, h * 0.3, w * 0.13, (20, 70, 105, 200))
    cx, cy = w * 0.3, h * 0.45
    for _ in range(140):
        fx, fy = cx + rnd.gauss(0, w * 0.15), cy + rnd.gauss(0, h * 0.04)
        s = rnd.uniform(8, 15) * w / 1200
        fd.ellipse((fx - s, fy - s * 0.35, fx + s, fy + s * 0.35), fill=(25, 85, 115, 200))
        fd.polygon([(fx + s * 0.8, fy), (fx + s * 1.5, fy - s * 0.4), (fx + s * 1.5, fy + s * 0.4)], fill=(25, 85, 115, 200))
    img.alpha_composite(far.filter(ImageFilter.GaussianBlur(2.5)))
    # The sea floor: rippled sand with caustic light, hazed blue with distance.
    floor_y = int(h * 0.84)
    fh = h - floor_y
    sy_, sx_ = np.mgrid[0:fh, 0:w].astype(np.float32)
    warp = fbm((w, fh), seed + 30, 90, 4)
    ripple = np.sin((sx_ * 0.045 + warp * 9 + sy_ * 0.02)) * 0.5 + 0.5
    grain = fbm((w, fh), seed + 31, 6, 3)
    sand = palette(0.35 + 0.35 * ripple + 0.3 * grain, [(0, (130, 115, 85)), (1, (215, 196, 150))])
    sand += caustics((w, fh), seed + 32, max(40, w // 14))[..., None] * 70
    fade = (1 - sy_ / fh)[..., None] * 0.55
    sand = sand * (1 - fade) + np.array((20, 80, 110), np.float32) * fade
    sand_img = to_img(sand)
    m = Image.new("L", (w, fh), 0)
    ImageDraw.Draw(m).polygon([(0, 40)] + [(x, 40 + 25 * math.sin(x / 170) + 12 * math.sin(x / 53)) for x in range(0, w + 10, 10)]
                              + [(w, fh), (0, fh)], fill=255)
    img.paste(sand_img, (0, floor_y), m.filter(ImageFilter.GaussianBlur(3)))
    # Reef: rocks, brain coral, branching coral, sea fans; kelp rising up the sides.
    reef = layer(img)
    rd = ImageDraw.Draw(reef, "RGBA")
    for _ in range(int(w / 140)):
        x = rnd.uniform(0, w)
        top = rnd.uniform(0.25, 0.55) * h
        kelp(rd, x if rnd.random() < 0.5 else rnd.choice([rnd.uniform(0, 0.12), rnd.uniform(0.88, 1)]) * w,
             floor_y + 50, top, w / 1200, rnd.choice([(150, 130, 50), (110, 120, 50), (170, 140, 60)]), rnd)
    for _ in range(int(w / 90)):
        x = rnd.uniform(0, w)
        y = floor_y + rnd.uniform(30, fh * 0.7)
        r = rnd.uniform(40, 90) * w / 1200
        rock = brain_coral(r * 2.4, rnd.choice([(118, 108, 96), (100, 104, 92), (130, 116, 100)]), rnd.randint(0, 9999))
        rk = np.asarray(rock, np.float32)  # boulder: no maze, mottled with algae
        mott = fbm((rock.width, rock.height), rnd.randint(0, 9999), base=max(4, rock.width // 12), octaves=4)
        rk[..., :3] *= (0.9 + 0.2 * mott)[..., None]
        rk[..., 1] += smoothstep(0.65, 0.85, mott) * 14
        rock = Image.fromarray(np.clip(rk, 0, 255).astype(np.uint8), "RGBA")
        reef.alpha_composite(rock, (int(x - rock.width / 2), int(y - rock.height)))
    for _ in range(int(w / 110)):
        x, y = rnd.uniform(0, w), floor_y + rnd.uniform(40, fh * 0.8)
        kind = rnd.random()
        colour = rnd.choice([(240, 120, 90), (250, 170, 80), (210, 90, 160), (150, 90, 200), (250, 210, 130), (90, 200, 190)])
        if kind < 0.35:
            bc = brain_coral(rnd.uniform(90, 170) * w / 1200, colour, rnd.randint(0, 9999))
            reef.alpha_composite(bc, (int(x - bc.width / 2), int(y - bc.height)))
        elif kind < 0.75:
            for k in range(rnd.randint(3, 5)):
                branch_coral(rd, x + rnd.uniform(-20, 20), y, math.radians(-90 + rnd.uniform(-35, 35)), rnd.uniform(50, 80) * w / 1200,
                             9 * w / 1200, colour, 4, rnd)
        else:
            sea_fan(rd, x, y, rnd.uniform(120, 200) * w / 1200, rnd.choice([(180, 60, 140), (220, 100, 80), (140, 70, 190)]), rnd)
    sh = Image.new("RGBA", size, (0, 0, 0, 0))
    sh.putalpha(reef.getchannel("A").point(lambda a: a * 0.4))
    img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(10)), (10, 14))
    img.alpha_composite(reef)
    # Near fish: a few bright reef fish with gradient bodies and an eye.
    d = draw(img)
    for _ in range(int(w / 200)):
        fx, fy = rnd.uniform(0.05, 0.95) * w, rnd.uniform(0.55, 0.85) * h
        s = rnd.uniform(18, 30) * w / 1200
        body, stripe = rnd.choice([((255, 140, 40), (255, 255, 255)), ((40, 120, 255), (255, 220, 40)), ((255, 220, 40), (40, 40, 60))])
        flip = rnd.choice([-1, 1])
        d.ellipse((fx - s, fy - s * 0.55, fx + s, fy + s * 0.55), fill=body + (255,))
        d.polygon([(fx - flip * s * 0.85, fy), (fx - flip * s * 1.6, fy - s * 0.5), (fx - flip * s * 1.6, fy + s * 0.5)], fill=body + (255,))
        d.line((fx - flip * s * 0.1, fy - s * 0.5, fx - flip * s * 0.1, fy + s * 0.5), fill=stripe + (230,), width=max(2, int(s * 0.18)))
        d.ellipse((fx + flip * s * 0.55 - 3, fy - s * 0.15 - 3, fx + flip * s * 0.55 + 3, fy - s * 0.15 + 3), fill=(10, 10, 10, 255))
    # Bubbles.
    for _ in range(int(w / 30)):
        x, y = rnd.uniform(0, w), rnd.uniform(0.15, 0.9) * h
        for k in range(rnd.randint(3, 10)):
            r = rnd.uniform(3, 11) * w / 1200
            by = y - k * r * 3.4
            d.ellipse((x - r, by - r, x + r, by + r), outline=(220, 250, 255, 150), width=2)
            d.ellipse((x - r * 0.5, by - r * 0.55, x - r * 0.1, by - r * 0.15), fill=(255, 255, 255, 210))
            x += rnd.uniform(-5, 5)
    vignette(img, 0.55, (0, 8, 20))
    return img


# ================= PLANTS =================
def render_leaf(length, kind, colour, seed, light=(-0.5, -0.65, 0.6)):
    """A leaf as a curved surface lit from one side: raised halves either side of a grooved
    midrib, embossed lateral veins, a sheen, and darker towards the base."""
    Lh = int(length)
    widths = {"monstera": 0.86, "banana": 0.34, "philodendron": 0.7, "frond": 0.16}
    Wd = int(Lh * widths[kind]) + 4
    ys, xs = np.mgrid[0:Lh, 0:Wd].astype(np.float32)
    t = 1 - ys / (Lh - 1)  # 0 at the stem end (bottom), 1 at the tip
    c = Wd / 2
    if kind == "monstera":
        prof = np.clip(np.sin(np.pi * np.clip(t * 0.92 + 0.04, 0, 1)), 0, 1) ** 0.55
        prof *= 1 - 0.35 * np.exp(-((t - 0.02) / 0.08) ** 2)
    elif kind == "banana":
        prof = np.clip(np.sin(np.pi * np.clip(t, 0, 1)) * 3, 0, 1) ** 0.6
    elif kind == "philodendron":
        prof = np.clip(np.clip(np.sin(np.pi * (0.15 + 0.85 * t)), 0, 1) ** 0.7 * (1 + 0.25 * (1 - t)), 0, 1)
    else:
        prof = np.clip(np.sin(np.pi * np.clip(t, 0, 1)), 0, 1) ** 0.8
    half = np.maximum(1, prof * (Wd / 2 - 2))
    a = (xs - c) / half
    inside = (np.abs(a) <= 1) & (t > 0.01) & (t < 0.995)
    rnd = random.Random(seed)
    # Height field: two convex halves, a groove down the middle, veins as shallow ridges.
    vein_period = {"monstera": 0.085, "banana": 0.03, "philodendron": 0.1, "frond": 0.06}[kind]
    vein_slant = {"monstera": 0.5, "banana": 0.15, "philodendron": 0.6, "frond": 0.4}[kind]
    vein = np.cos((t + np.abs(a) * vein_slant * 0.3) / vein_period * 2 * math.pi)
    hgt = np.sqrt(np.clip(1 - a * a, 0, 1)) * 0.6 + np.abs(a) * 0.25 * (1 - np.abs(a)) - 0.25 * np.exp(-(a / 0.06) ** 2)
    hgt += 0.025 * smoothstep(0.7, 1.0, vein)
    hgt *= half / max(1.0, Wd / 2) * 40
    gy, gx = np.gradient(hgt)
    nz = np.ones_like(hgt)
    norm = np.sqrt(gx * gx + gy * gy + nz)
    lx, ly, lz = light
    ll = math.sqrt(lx * lx + ly * ly + lz * lz)
    ndl = np.clip((-gx * lx - gy * ly + nz * lz) / (norm * ll), 0, 1)
    spec = np.clip(ndl, 0, 1) ** 24 * 0.35
    tex = fbm((Wd, Lh), seed, base=max(6, Wd // 4), octaves=3)
    base_c = np.array(colour, np.float32)
    col = base_c[None, None, :] * (0.3 + 0.95 * ndl[..., None]) * (0.75 + 0.25 * t[..., None]) * (0.9 + 0.2 * tex[..., None])
    col += spec[..., None] * 255
    mid = np.exp(-(a / 0.035) ** 2) * (t > 0.02)
    col = col * (1 - mid[..., None] * 0.6) + mid[..., None] * 0.6 * np.minimum(255, base_c * 1.6 + 30)
    if kind == "monstera":
        # Splits from the edge in towards the midrib, curving with the veins, and holes.
        for k in range(8):
            tk = 0.18 + k * 0.095
            slit = np.abs(t - (tk + 0.06 * (np.abs(a) - 0.4))) < 0.012 + 0.008 * np.abs(a)
            inside &= ~(slit & (np.abs(a) > 0.42))
        for k in range(4):
            tk = 0.3 + k * 0.15
            hole = ((t - tk) / 0.035) ** 2 + ((np.abs(a) - 0.27) / 0.06) ** 2 < 1
            inside &= ~hole
    elif kind == "banana":
        for k in range(9):  # wind tears
            tk = rnd.uniform(0.15, 0.9)
            side = rnd.choice([-1, 1])
            tear = (np.abs(t - tk - 0.02 * np.abs(a)) < 0.004) & (a * side > 0.1)
            inside &= ~tear
    alpha = inside.astype(np.float32) * 255
    leaf = Image.fromarray(np.dstack([np.clip(col, 0, 255), alpha]).astype(np.uint8), "RGBA")
    return leaf.filter(ImageFilter.SMOOTH)


def fern(length, colour, seed):
    """A fern frond: many small leaflets along a gently curved stem."""
    Lh = int(length)
    out = Image.new("RGBA", (int(Lh * 0.8), Lh), (0, 0, 0, 0))
    d = ImageDraw.Draw(out, "RGBA")
    rnd = random.Random(seed)
    c = out.width / 2
    pts = [(c + Lh * 0.06 * math.sin(t * 2.2), Lh * (1 - t)) for t in np.linspace(0, 1, 40)]
    pinna = render_leaf(Lh * 0.26, "frond", colour, seed)
    for i, (px, py) in enumerate(pts[2:-1]):
        t = i / len(pts)
        s = 1 - t * 0.85
        for side in (-1, 1):
            p = pinna.resize((max(2, int(pinna.width * s)), max(2, int(pinna.height * s))))
            p = p.rotate(side * (-70 + t * 20), expand=True, resample=Image.BICUBIC)
            out.alpha_composite(p, (int(px - p.width / 2 + side * p.width * 0.32), int(py - p.height / 2)))
    d.line(pts, fill=tuple(int(v * 0.6) for v in colour) + (255,), width=max(2, Lh // 160))
    return out


def plants_scene(size, slots, seed):
    w, h = size
    rnd = random.Random(seed)
    bg = warp_fbm(size, seed, max(w, h) // 3, 5, 0.2)
    img = to_img(palette(bg, [(0, (4, 16, 8)), (0.6, (14, 40, 20)), (1, (30, 70, 34))]))
    bok = Image.new("RGB", size, "black")
    bd = ImageDraw.Draw(bok)
    for _ in range(int(w * h / 26000)):
        x, y, r = rnd.uniform(0, w), rnd.uniform(0, h), rnd.uniform(12, 46) * w / 1200
        c = rnd.choice([(90, 120, 60), (140, 150, 80), (70, 100, 60), (160, 160, 110)])
        bd.ellipse((x - r, y - r, x + r, y + r), fill=c)
    img = screen_add(img, bok.filter(ImageFilter.GaussianBlur(7)))
    greens = [(46, 110, 48), (64, 132, 56), (34, 92, 46), (82, 140, 62), (50, 116, 78), (96, 150, 60)]
    kinds = ["monstera", "monstera", "banana", "philodendron", "fern"]

    def near_edge():
        # Mostly round the edges and between the photos, where they'll be seen.
        side = rnd.random()
        if side < 0.3:
            return rnd.uniform(-0.12, 0.14) * w, rnd.uniform(-0.05, 1.05) * h
        if side < 0.6:
            return rnd.uniform(0.86, 1.12) * w, rnd.uniform(-0.05, 1.05) * h
        if side < 0.8:
            return rnd.uniform(0, 1) * w, rnd.uniform(-0.08, 0.1) * h
        return rnd.uniform(0, 1) * w, rnd.uniform(0.9, 1.08) * h

    area = (w * h) / (1200 * 1800)
    for depth, count, blur, dark in ((0, 30, 7, 0.45), (1, 24, 3, 0.7), (2, 20, 0, 1.0)):
        lay = layer(img)
        for _ in range(int(count * area)):
            kind = rnd.choice(kinds)
            col = tuple(int(v * dark) for v in rnd.choice(greens))
            s = rnd.uniform(0.28, 0.48) * min(w, h) * (1.4 if kind == "banana" else 1)
            leaf = fern(s * 1.2, col, rnd.randint(0, 99999)) if kind == "fern" else render_leaf(s, kind, col, rnd.randint(0, 99999))
            x, y = near_edge()
            # Point the leaf inwards, as if growing from outside the frame.
            ang = math.degrees(math.atan2(y - h / 2, x - w / 2)) + 90 + rnd.uniform(-35, 35)
            leaf = leaf.rotate(-ang, resample=Image.BICUBIC, expand=True)
            lay.alpha_composite(leaf, (int(x - leaf.width / 2), int(y - leaf.height / 2)))
        if blur:
            lay = lay.filter(ImageFilter.GaussianBlur(blur))
        sh = Image.new("RGBA", size, (0, 0, 0, 0))
        sh.putalpha(lay.getchannel("A").point(lambda a: a * 0.55))
        img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(14)), (10, 18))
        img.alpha_composite(lay)
    d = draw(img)
    for _ in range(int(w * h / 60000)):  # dew drops
        x, y, r = rnd.uniform(0, w), rnd.uniform(0, h), rnd.uniform(3, 6)
        d.ellipse((x - r, y - r, x + r, y + r), fill=(200, 230, 200, 60), outline=(230, 255, 230, 120))
        d.ellipse((x - r * 0.45, y - r * 0.6, x - r * 0.05, y - r * 0.2), fill=(255, 255, 255, 210))
    vignette(img, 0.55, (0, 8, 0))
    return img


# ================= OUTDOORS =================
def pine(d, x, base, height, colour, rnd, lit=None):
    """A spruce: ragged tiers of branches, narrower towards the tip."""
    tiers = 9
    width = height * 0.32
    for i in range(tiers):
        t = i / tiers
        y = base - height * 0.08 - height * 0.9 * t
        wd = width * (1 - t) ** 1.1
        pts = [(x - wd, y)]
        for k in range(7):  # ragged edge
            pts.append((x - wd + wd * k / 7, y - height * 0.11 * (k / 7) + rnd.uniform(-3, 3)))
        pts.append((x, y - height * 0.16))
        for k in range(7, -1, -1):
            pts.append((x + wd - wd * k / 7 + rnd.uniform(-3, 3), y - height * 0.11 * (k / 7)))
        d.polygon(pts, fill=colour)
        if lit:
            d.line(pts[len(pts) // 2:], fill=lit, width=2)
    d.line((x, base, x, base - height * 0.1), fill=colour, width=max(2, int(width * 0.08)))


def outdoors_scene(size, slots, seed):
    w, h = size
    rnd = random.Random(seed)
    ys = np.linspace(0, 1, h, dtype=np.float32)[:, None] * np.ones((1, w), np.float32)
    sky = palette(ys, [(0, (40, 80, 150)), (0.3, (120, 150, 200)), (0.5, (245, 190, 150)), (0.62, (255, 215, 170)), (1, (255, 225, 185))])
    cl = warp_fbm(size, seed, max(w, h) // 3, 6, 0.3)
    cmask = smoothstep(0.55, 0.85, cl) * (1 - smoothstep(0.3, 0.52, ys))
    under = smoothstep(0.55, 0.75, cl)
    ccol = np.array((255, 236, 220), np.float32) * (0.75 + 0.25 * under[..., None])
    sky = sky * (1 - cmask[..., None] * 0.85) + ccol * cmask[..., None] * 0.85
    img = to_img(sky)
    sun = (w * 0.66, h * 0.5)
    glow = Image.new("RGB", size, "black")
    ImageDraw.Draw(glow).ellipse((sun[0] - w * 0.3, sun[1] - w * 0.3, sun[0] + w * 0.3, sun[1] + w * 0.3), fill=(130, 90, 50))
    img = screen_add(img, glow.filter(ImageFilter.GaussianBlur(w * 0.09)))
    draw(img).ellipse((sun[0] - w * 0.035, sun[1] - w * 0.035, sun[0] + w * 0.035, sun[1] + w * 0.035), fill=(255, 248, 230, 255))
    haze_c = np.array((236, 205, 190), np.float32)
    ranges = [(0.5, 0.13, (120, 120, 150), 0.55), (0.58, 0.18, (95, 100, 125), 0.35), (0.66, 0.22, (75, 80, 90), 0.18),
              (0.74, 0.2, (55, 60, 62), 0.05)]
    yy = np.arange(h, dtype=np.float32)[:, None]
    for k, (base, height, colour, haze) in enumerate(ranges):
        # Skyline: big smooth shapes plus a little rocky detail (no spikes).
        big = noise1d(w, seed + 10 + k, max(80, w // (2 + k)), 3)
        detail = noise1d(w, seed + 40 + k, max(20, w // 30), 4)
        crest = smoothstep(0.1, 0.9, big) ** 1.2 * 0.85 + detail * 0.15
        top = (base - height * crest) * h
        mask = (yy >= top[None, :]).astype(np.float32)
        # Hill shading from a ridged height field: faces towards the sun are lit.
        # Gullies run downhill: ridged noise stretched tall, over a broader ridged base.
        gul = ridged((w, max(8, h // 4)), seed + 20 + k, base=max(16, w // (12 + 2 * k)), octaves=5)
        gul = np.asarray(Image.fromarray((gul * 255).astype(np.uint8)).resize((w, h), Image.BICUBIC), np.float32) / 255
        broad = ridged(size, seed + 30 + k, base=max(60, w // (4 + k)), octaves=3)
        hf = 0.55 * gul + 0.45 * broad
        hf = np.asarray(Image.fromarray((hf * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.2)), np.float32) / 255
        rock = fbm(size, seed + 60 + k, base=24, octaves=3)  # fine rock grain, not lit
        gy, gx = np.gradient(hf * 60)
        shade = np.clip(0.6 - gx * 1.3 - gy * 0.25, 0.15, 1.3)
        rgb = np.array(colour, np.float32)[None, None, :] * (shade * (0.88 + 0.24 * rock))[..., None]
        below = (yy - top[None, :]) / (height * h + 1)
        if k <= 2:  # snow on the upper slopes, brightest on lit faces
            snow = smoothstep(0.35, 0.0, below) * smoothstep(0.5, 0.75, hf) * smoothstep(0.4, 0.9, crest)[None, :]
            snow_col = np.array((245, 240, 238), np.float32) * np.clip(shade, 0.55, 1.1)[..., None] + np.array((-20, -10, 10))
            rgb = rgb * (1 - snow[..., None]) + snow_col * snow[..., None]
        rgb = rgb * (1 - haze) + haze_c * haze
        rng = Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8), "RGB").convert("RGBA")
        rng.putalpha(Image.fromarray((mask * 255).astype(np.uint8), "L").filter(ImageFilter.GaussianBlur(0.8)))
        img.alpha_composite(rng)
        fog = Image.new("RGBA", size, (0, 0, 0, 0))
        fy = (base + 0.03) * h
        ImageDraw.Draw(fog).rectangle((0, fy - h * 0.025, w, fy + h * 0.025), fill=(245, 225, 215, 120 - k * 20))
        img.alpha_composite(fog.filter(ImageFilter.GaussianBlur(h * 0.015)))
    lake_top = int(h * 0.82)
    refl = img.crop((0, int(h * 0.82) - (h - lake_top), w, lake_top)).transpose(Image.FLIP_TOP_BOTTOM).filter(ImageFilter.GaussianBlur(2))
    refl.alpha_composite(Image.new("RGBA", refl.size, (20, 40, 60, 100)))
    img.alpha_composite(refl, (0, lake_top))
    d = draw(img)
    for k, (yb, scale, colour, lit) in enumerate(((0.8, 0.55, (34, 54, 44), (70, 90, 60)), (0.86, 0.8, (18, 34, 26), (50, 70, 45)),
                                                 (0.96, 1.15, (8, 18, 14), None))):
        lay = layer(img)
        ld = ImageDraw.Draw(lay)
        x = -40
        while x < w + 40:
            th = rnd.uniform(0.09, 0.16) * h * scale
            if not (k == 0 and 0.25 * w < x < 0.75 * w and rnd.random() < 0.6):
                pine(ld, x, yb * h + rnd.uniform(-8, 8), th, colour + (255,), rnd, lit + (160,) if lit else None)
            x += th * rnd.uniform(0.22, 0.4)
        if k == 0:
            lay = lay.filter(ImageFilter.GaussianBlur(1.2))
        img.alpha_composite(lay)
    d = draw(img)
    for _ in range(6):  # birds
        bx, by_ = rnd.uniform(0.2, 0.8) * w, rnd.uniform(0.12, 0.35) * h
        s = rnd.uniform(6, 12) * w / 1200
        d.arc((bx - s, by_ - s / 2, bx, by_ + s / 2), 200, 340, fill=(40, 40, 50, 220), width=2)
        d.arc((bx, by_ - s / 2, bx + s, by_ + s / 2), 200, 340, fill=(40, 40, 50, 220), width=2)
    return img


# ================= the designs, per shape =================
def strip_slots(top, bottom, gap=40, x0=80, w=1040):
    return af.layout(top=top, bottom=bottom, gap=gap, x0=x0, w=w)


def title(img, xy, text, colour, size, font_name="PoiretOne.ttf", spacing=14, shadow_c=(0, 0, 0, 160)):
    d = draw(img)
    sh = layer(img)
    spaced_text(ImageDraw.Draw(sh), (xy[0] + 3, xy[1] + 4), text, font(font_name, size), shadow_c, spacing)
    img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(4)))
    spaced_text(draw(img), xy, text, font(font_name, size), rgba(colour), spacing)


def space(shape):
    w, h = shape
    if shape == STRIP:
        slots = strip_slots(380, 380)
        planets = [("rings", 860, 190, 300), ("earth", 170, 230, 230), ("moon", 1110, 1720, 120), ("gas", 60, 2550, 300),
                   ("mars", 1130, 3060, 150), ("ice", 260, 3420, 230)]
    elif shape == L:
        slots = [[400, 140, 600, 450], [1040, 140, 600, 450], [400, 640, 600, 450], [1040, 640, 600, 450]]
        planets = [("gas", 150, 330, 380), ("rings", 1720, 1060, 300), ("earth", 160, 920, 240), ("moon", 1720, 90, 110),
                   ("mars", 1000, 1150, 100)]
    else:
        slots = [[110, 360, 470, 620], [620, 360, 470, 620], [110, 1050, 470, 620], [620, 1050, 470, 620]]
        planets = [("rings", 900, 170, 260), ("earth", 170, 180, 230), ("gas", 60, 1730, 320), ("moon", 1130, 1720, 140),
                   ("mars", 600, 1020, 60)]
    img = space_scene(shape, slots, 401, planets)
    thin_frame(img, slots, (220, 230, 255, 230), 3, glow_colour=(120, 160, 255, 140))
    if shape == STRIP:
        title(img, (w / 2, 3460), "TO THE STARS", (230, 236, 255), 64)
    elif shape == P:
        title(img, (w / 2 + 120, 300), "TO THE STARS", (230, 236, 255), 56)
    else:
        title(img, (1020, 70), "TO THE STARS", (230, 236, 255), 52)
    return cut(img, slots, radius=8), slots, {}


def ocean(shape):
    w, h = shape
    if shape == STRIP:
        slots = strip_slots(300, 520)
    elif shape == L:
        slots = [[110, 120, 760, 470], [930, 120, 760, 470], [110, 650, 760, 380], [930, 650, 760, 380]]
    else:
        slots = [[110, 200, 470, 620], [620, 200, 470, 620], [110, 880, 470, 620], [620, 880, 470, 620]]
    img = ocean_scene(shape, slots, 501)
    thin_frame(img, slots, (230, 250, 255, 220), 3, glow_colour=(150, 230, 255, 120))
    if shape == STRIP:
        title(img, (w / 2, 160), "DEEP BLUE", (235, 250, 255), 80)
    elif shape == P:
        title(img, (w / 2, 110), "DEEP BLUE", (235, 250, 255), 70)
    else:
        title(img, (w / 2, 64), "DEEP BLUE", (235, 250, 255), 50)
    return cut(img, slots, radius=8), slots, {}


def plants(shape):
    w, h = shape
    if shape == STRIP:
        slots = strip_slots(260, 340, gap=60, x0=110, w=980)
    elif shape == L:
        slots = [[160, 150, 700, 430], [940, 150, 700, 430], [160, 640, 700, 430], [940, 640, 700, 430]]
    else:
        slots = [[150, 230, 430, 580], [620, 230, 430, 580], [150, 900, 430, 580], [620, 900, 430, 580]]
    img = plants_scene(shape, slots, 601)
    thin_frame(img, slots, (240, 245, 230, 240), 4, glow_colour=None)
    d = draw(img)
    if shape == STRIP:
        title(img, (w / 2, 3400), "WILD & GREEN", (235, 245, 225), 66)
    elif shape == P:
        title(img, (w / 2, 1640), "WILD & GREEN", (235, 245, 225), 66)
    else:
        title(img, (w / 2, 85), "WILD & GREEN", (235, 245, 225), 52)
    return cut(img, slots, radius=6), slots, {}


def outdoors(shape):
    w, h = shape
    if shape == STRIP:
        slots = strip_slots(160, 900, gap=36)
    elif shape == L:
        slots = [[90, 90, 520, 360], [640, 90, 520, 360], [1190, 90, 520, 360]]
    else:
        slots = [[110, 110, 470, 600], [620, 110, 470, 600]]
    if shape == STRIP:
        # The photos fill most of a strip, so the landscape goes in the bottom part and the sky
        # carries on above it.
        scene_h = 1500
        scene = outdoors_scene((w, scene_h), slots, 701)
        img = to_img(palette(np.linspace(0, 1, h - scene_h, dtype=np.float32)[:, None] * np.ones((1, w), np.float32),
                             [(0, (20, 50, 110)), (1, (40, 80, 150))]))
        img = img.crop((0, 0, w, h)) if img.height == h else Image.new("RGBA", (w, h))
        top = to_img(palette(np.linspace(0, 1, h - scene_h, dtype=np.float32)[:, None] * np.ones((1, w), np.float32),
                             [(0, (20, 50, 110)), (1, (40, 80, 150))]))
        img.alpha_composite(top)
        img.alpha_composite(scene, (0, h - scene_h))
    else:
        img = outdoors_scene(shape, slots, 701)
    thin_frame(img, slots, (255, 250, 240, 240), 4)
    if shape == STRIP:
        title(img, (w / 2, 3480), "THE GREAT OUTDOORS", (255, 250, 240), 54)
    elif shape == P:
        title(img, (w / 2, 1720), "THE GREAT OUTDOORS", (255, 250, 240), 54)
    else:
        title(img, (w / 2, 1140), "THE GREAT OUTDOORS", (255, 250, 240), 46)
    return cut(img, slots, radius=6), slots, {}


THEMES = [("Space", space), ("Ocean", ocean), ("Plants", plants), ("Outdoors", outdoors)]
STRIP_NUMBERS = {"Space": 41, "Ocean": 42, "Plants": 43, "Outdoors": 44}

if __name__ == "__main__":
    for name, fn in THEMES:
        img, slots, extra = fn(STRIP)
        n = STRIP_NUMBERS[name]
        img.save(os.path.join("frames", f"frame{n}.png"))
        with open(os.path.join("frames", f"frame{n}.json"), "w") as f:
            json.dump({"slots": slots, **extra}, f, indent=2)
        print(f"frame{n}: {name}")
