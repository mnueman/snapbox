#!/usr/bin/env python3
"""Makes the boot splash: the Snapbox name plate on leatherette, with a shine that sweeps across
the chrome and a red lamp that glows. Writes a Plymouth theme (pictures + script) to a folder;
system/setup-splash.sh installs it.

    python3 system/make_splash.py OUT_DIR [PANEL_W PANEL_H [ROTATION]]

The pictures are drawn for the screen as it is mounted and then turned to the panel's own
orientation, the same way the app turns its screens (ROTATION: screen_rotation.txt).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import numpy as np  # noqa: E402
from PIL import Image, ImageDraw, ImageFilter  # noqa: E402

import looks  # noqa: E402
from looks import SS, Pen  # noqa: E402


def panel_turn(rotation, pw, ph):
    """PIL degrees to turn a screen picture onto the panel (photobooth.py: to_panel_rotation)."""
    if ph > pw:
        return {0: -90, 180: 90, -90: 180, 90: 0}[rotation]
    return rotation


def turn(img, deg):
    return img.rotate(deg, expand=True) if deg else img


def turn_box(box, deg, w, h):
    """Where a box (x, y, bw, bh) on the w x h screen picture ends up once it's turned."""
    x, y, bw, bh = box
    deg %= 360
    if deg == 90:
        return (y, w - (x + bw), bh, bw)
    if deg == 270:
        return (h - (y + bh), x, bh, bw)
    if deg == 180:
        return (w - (x + bw), h - (y + bh), bw, bh)
    return box


def build(out, pw, ph, rotation):
    out.mkdir(parents=True, exist_ok=True)
    deg = panel_turn(rotation, pw, ph)
    w, h = (ph, pw) if deg % 180 else (pw, ph)  # the screen as you look at it
    k = h / 480.0

    # --- the still picture: leatherette, the chrome name plate, a little engraved line
    p = Pen(w, h)
    p.img.paste(looks._leather(w * SS, h * SS, k), (0, 0))
    p.d = ImageDraw.Draw(p.img, "RGBA")
    pw_, ph_ = min(w - 80 * k, 470 * k), 190 * k
    plate = ((w - pw_) / 2, (h - ph_) / 2 - 14 * k, (w + pw_) / 2, (h + ph_) / 2 - 14 * k)
    p.shadows([(plate, 14 * k, 12 * k, 8 * k, 0.75)])
    looks._metal(p, plate, looks.CHROME, 14 * k)
    p.rrect(plate, 14 * k, outline=(84, 86, 87, 255), width=1.2 * k)
    p.rrect((plate[0] + 2 * k, plate[1] + 2 * k, plate[2] - 2 * k, plate[3] - 2 * k), 12 * k, outline=(255, 255, 255, 170), width=1 * k)
    for sx, sy, ang in ((plate[0] + 14 * k, plate[1] + 14 * k, 30), (plate[2] - 14 * k, plate[1] + 14 * k, -40),
                        (plate[0] + 14 * k, plate[3] - 14 * k, 110), (plate[2] - 14 * k, plate[3] - 14 * k, 70)):
        looks._screw(p, sx, sy, 4.2 * k, ang)
    size = 112 * k
    script = looks.font("Yellowtail.ttf", size)
    while p.text_w("Snapbox", script) > pw_ - 110 * k:
        size -= 2 * k
        script = looks.font("Yellowtail.ttf", size)
    tw = p.text_w("Snapbox", script)
    dot_r = size * 0.14
    tx = (w - tw - dot_r * 2 - 8 * k) / 2
    ty = plate[1] + ph_ * 0.44
    p.text((tx, ty + 1.6 * k), "Snapbox", script, (255, 255, 255, 210), "lm")
    p.text((tx, ty), "Snapbox", script, looks.ENGRAVE, "lm")
    dot = (tx + tw + 8 * k + dot_r, ty - size * 0.22)
    p.shadows([((dot[0] - dot_r, dot[1] - dot_r, dot[0] + dot_r, dot[1] + dot_r), dot_r, 2 * k, 1.5 * k, 0.5)])
    p.paste(looks._disc(p.s(dot_r * 2), (255, 140, 140), (216, 35, 42), (130, 16, 22)), (dot[0] - dot_r, dot[1] - dot_r))
    looks._engraved(p, (w / 2, plate[3] - 30 * k), "AUTOMATIC · 35", looks.font(looks.BC_S, 17 * k), "mm", 6 * k, k=k)
    p.text((w / 2, plate[3] + 46 * k), "LOADING FILM", looks.font(looks.BC_S, 15 * k), (200, 201, 199, 255), "mm", 5 * k)
    bg = p.done().convert("RGB")

    # --- the same picture with the plate cut out: it goes on top, so the shine only shows on the chrome
    mask = bg.convert("RGBA")
    hole = Image.new("L", (w * SS, h * SS), 255)
    ImageDraw.Draw(hole).rounded_rectangle(tuple(round(v * SS) for v in plate), radius=round(14 * k * SS), fill=0)
    mask.putalpha(hole.resize((w, h), Image.LANCZOS))

    # --- the shine: a soft slanted band of light
    sw, sh = round(270 * k), round(ph_ + 8 * k)  # wide enough that its own edges are invisible
    yy, xx = np.mgrid[0:sh, 0:sw].astype(np.float32)
    across = xx - sw / 2 + (yy - sh / 2) * 0.38          # slanted
    alpha = np.exp(-(across / (20 * k)) ** 2) * 150 + np.exp(-(across / (46 * k)) ** 2) * 60
    shine = np.dstack([np.full((sh, sw, 3), 255, np.float32), np.clip(alpha, 0, 255)]).astype(np.uint8)
    shine = Image.fromarray(shine, "RGBA")
    shine_y = plate[1] - 4 * k
    start = (plate[0] - sw, shine_y, sw, sh)
    end = (plate[2], shine_y, sw, sh)

    # --- the red lamp's glow
    gs = round(dot_r * 7)
    glow = Image.new("RGBA", (gs, gs), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse((gs * 0.26, gs * 0.26, gs * 0.74, gs * 0.74), fill=(255, 60, 66, 210))
    glow = glow.filter(ImageFilter.GaussianBlur(dot_r * 0.9))
    glow_box = (dot[0] - gs / 2, dot[1] - gs / 2, gs, gs)

    turn(bg, deg).save(out / "bg.png")
    turn(mask, deg).save(out / "mask.png")
    turn(shine, deg).save(out / "shine.png")
    turn(glow, deg).save(out / "glow.png")
    s0, s1, gb = (turn_box(b, deg, w, h) for b in (start, end, glow_box))

    (out / "snapbox.plymouth").write_text(
        "[Plymouth Theme]\nName=Snapbox\nDescription=The Snapbox name plate with a moving shine\n"
        "ModuleName=script\n\n[script]\nImageDir=/usr/share/plymouth/themes/snapbox\n"
        "ScriptFile=/usr/share/plymouth/themes/snapbox/snapbox.script\n")
    (out / "snapbox.script").write_text(f"""# Made by system/make_splash.py: don't edit, run it again.
Window.SetBackgroundTopColor(0.07, 0.07, 0.07);
Window.SetBackgroundBottomColor(0.07, 0.07, 0.07);
bg_image = Image("bg.png");
ox = Window.GetX() + (Window.GetWidth() - bg_image.GetWidth()) / 2;
oy = Window.GetY() + (Window.GetHeight() - bg_image.GetHeight()) / 2;
bg = Sprite(bg_image);
bg.SetPosition(ox, oy, 0);
shine = Sprite(Image("shine.png"));
shine.SetPosition(ox + {s0[0]:.1f}, oy + {s0[1]:.1f}, 1);
mask = Sprite(Image("mask.png"));
mask.SetPosition(ox, oy, 2);
glow = Sprite(Image("glow.png"));
glow.SetPosition(ox + {gb[0]:.1f}, oy + {gb[1]:.1f}, 3);
tick = 0;
fun refresh ()
{{
    # 50 times a second: the shine crosses the plate in about 1.3 s, rests, and goes again
    tick++;
    p = (tick % 150) / 65;
    if (p > 1) p = 1;
    e = p * p * (3 - 2 * p);
    shine.SetPosition(ox + {s0[0]:.1f} + ({s1[0]:.1f} - {s0[0]:.1f}) * e, oy + {s0[1]:.1f} + ({s1[1]:.1f} - {s0[1]:.1f}) * e, 1);
    glow.SetOpacity(0.55 + 0.45 * Math.Sin(tick / 14));
}}
Plymouth.SetRefreshFunction(refresh);
""")
    return bg, mask, shine, glow, start, end, glow_box, (w, h)


if __name__ == "__main__":
    out = Path(sys.argv[1])
    pw, ph = (int(sys.argv[2]), int(sys.argv[3])) if len(sys.argv) > 3 else (480, 640)
    rotation = int(sys.argv[4]) if len(sys.argv) > 4 else 180
    bg, mask, shine, glow, start, end, glow_box, (w, h) = build(out, pw, ph, rotation)
    # A preview of three moments, as you'd see them on the screen.
    frames = []
    for t in (0.25, 0.55, 0.85):
        f = bg.convert("RGBA")
        x = start[0] + (end[0] - start[0]) * t
        layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        layer.alpha_composite(shine, (max(0, round(x)), round(start[1]))) if 0 <= x <= w - shine.width else None
        f.alpha_composite(layer)
        f.alpha_composite(mask)
        f.alpha_composite(glow, (round(glow_box[0]), round(glow_box[1])))
        frames.append(f.convert("RGB"))
    sheet = Image.new("RGB", (w * 3 + 20, h), "white")
    for i, f in enumerate(frames):
        sheet.paste(f, (i * (w + 10), 0))
    sheet.save(out / "preview.png")
    print(f"Splash for a {pw}x{ph} panel (screen setting {rotation}) written to {out}")
