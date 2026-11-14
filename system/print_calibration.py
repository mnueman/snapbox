#!/usr/bin/env python3
"""Prints a ruler sheet to measure how much of a borderless 4x6 the printer cuts off on each side.

Each edge has coloured 1 mm bands and numbered rulers (millimetres from the paper's edge, as sent).
The first number you can read on an edge is how many mm the printer cut off there. Enter the four
numbers in the booth's settings (PRINT_TRIM_MM in photobooth.py) so prints fit the paper exactly.

    python3 system/print_calibration.py            # print it (printer SELPHY)
    python3 system/print_calibration.py out.jpg    # just save it
"""
import subprocess
import sys
import tempfile

from PIL import Image, ImageDraw, ImageFont

W, H = 2400, 3600  # 4x6 inches at 600 dpi, as the booth sends it
MM = W / (4 * 25.4)  # pixels per millimetre
MAX_MM = 8
BANDS = [(235, 60, 60), (245, 150, 40), (240, 210, 40), (70, 180, 80), (60, 130, 230),
         (150, 80, 200), (120, 120, 120), (40, 40, 40)]
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def font(size):
    return ImageFont.truetype(FONT, size)


def make():
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)

    # Coloured bands, 1 mm each, from every edge inward (light, so the rulers read on top).
    for i in range(MAX_MM):  # outermost first; each inner one covers the middle again
        c = tuple(int(v + (255 - v) * 0.55) for v in BANDS[i])
        a = round(i * MM)
        d.rectangle((a, a, W - 1 - a, H - 1 - a), fill=c)
    b = round(MAX_MM * MM)
    d.rectangle((b, b, W - 1 - b, H - 1 - b), fill="white")

    f = font(30)
    small = font(26)

    def ruler(edge, pos):
        # Ticks every 0.5 mm going inward; numbers every mm, beside the tick.
        for half in range(1, MAX_MM * 2 + 1):
            depth = half * MM / 2
            whole = half % 2 == 0
            length = 70 if whole else 38
            width = 5 if whole else 3
            if edge in ("top", "bottom"):
                y = depth if edge == "top" else H - 1 - depth
                d.line((pos - length // 2, y, pos + length // 2, y), fill="black", width=width)
                if whole:  # odd numbers on one side, even on the other, so they don't touch
                    n = half // 2
                    if n % 2:
                        d.text((pos + length // 2 + 8, y), str(n), font=f, fill="black",
                               anchor="lm")
                    else:
                        d.text((pos - length // 2 - 8, y), str(n), font=f, fill="black",
                               anchor="rm")
            else:
                x = depth if edge == "left" else W - 1 - depth
                d.line((x, pos - length // 2, x, pos + length // 2), fill="black", width=width)
                if whole:
                    n = half // 2
                    if n % 2:
                        d.text((x, pos + length // 2 + 6), str(n), font=f, fill="black",
                               anchor="mt")
                    else:
                        d.text((x, pos - length // 2 - 6), str(n), font=f, fill="black",
                               anchor="mb")

    for edge in ("top", "bottom"):
        for frac in (0.2, 0.5, 0.8):
            ruler(edge, round(W * frac))
    for edge in ("left", "right"):
        for frac in (0.15, 0.5, 0.85):
            ruler(edge, round(H * frac))

    # Where the two strips get cut apart.
    cx = W // 2
    for y in range(round(MAX_MM * MM) + 20, H - round(MAX_MM * MM) - 20, 60):
        d.line((cx, y, cx, y + 30), fill=(200, 0, 0), width=4)

    # Which side is which, once it's printed.
    big = font(120)
    d.text((W // 2, H * 0.12), "TOP", font=big, fill="black", anchor="mm")
    d.text((W // 2, H * 0.88), "BOTTOM", font=big, fill="black", anchor="mm")
    d.text((W * 0.25, H / 2), "LEFT", font=font(100), fill="black", anchor="mm")
    d.text((W * 0.75, H / 2), "RIGHT", font=font(100), fill="black", anchor="mm")
    lines = ["PRINT CALIBRATION", "", "On each edge, the first number",
             "you can read = mm cut off there.", "Half-mm ticks between numbers.",
             "Red dashes: centre (strip cut)."]
    y = H * 0.30
    for line in lines:
        d.text((W // 2, y), line, font=font(56) if line == lines[0] else small, fill="black",
               anchor="mm")
        y += 90 if line == lines[0] else 50
    return img


def main():
    img = make()
    if len(sys.argv) > 1:
        img.save(sys.argv[1], quality=95)
        print(f"Saved {sys.argv[1]}")
        return
    with tempfile.NamedTemporaryFile(suffix=".jpg") as tmp:
        img.save(tmp.name, quality=95)
        result = subprocess.run(["lp", "-d", "SELPHY", "-o", "PageSize=Postcard.Borderless",
                                 tmp.name], capture_output=True, text=True)
    print(result.stdout.strip() or result.stderr.strip())
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
