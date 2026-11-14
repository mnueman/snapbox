#!/usr/bin/env python3
"""Checks that prints fit the paper, before trying it on paper.

Part 1, the booth's own code: takes the print functions out of photobooth.py (print_layout,
fit_print, make_pair_print, make_sheet_print) and runs every design on this booth, every shape
(strips two to a sheet, landscape sheets turned upright, portrait sheets), through them. Each test
picture carries thin marker lines at known places; finding them in the result gives exactly where
the design's edges, and the line between two strips, land on the sheet sent to the printer.

Part 2, the printer: many simulated prints, each with the printer's measured cut-off
(PRINT_TRIM_MM) plus the uncertainty of that measurement and print-to-print wobble, scoring how
closely the design's edges meet the paper's edges.

    python3 system/print_fit_sim.py
"""
import ast
import glob
import json
import os
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

APP = Path(__file__).resolve().parent.parent / "photobooth.py"
PAPER_MM = (100.0, 148.0)  # SELPHY postcard after tearing off the tabs (width, height)
TOL_MM = 0.05  # part 1 pass mark: a design edge within this of where it should be (~1 px)
RNG = np.random.default_rng(1)


def load_print_code():
    """The print functions and settings from photobooth.py, without starting the app."""
    tree = ast.parse(APP.read_text())
    want_fn = {"print_layout", "fit_print", "make_pair_print", "make_sheet_print", "image_kind"}
    want_var = {"STRIP_W", "STRIP_H", "PRINT_W", "PRINT_H", "PRINT_TRIM_MM", "PRINT_BLEED_MM"}
    body = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in want_fn:
            body.append(node)
        elif isinstance(node, ast.Assign):
            names = {t.id for t in node.targets if isinstance(t, ast.Name)}
            names |= {e.id for t in node.targets if isinstance(t, ast.Tuple) for e in t.elts}
            if names & want_var:
                body.append(node)
    ns = {"np": np, "Image": Image}
    exec(compile(ast.Module(body=body, type_ignores=[]), str(APP), "exec"), ns)
    missing = (want_fn | want_var) - set(ns)
    if missing:
        sys.exit(f"Not found in photobooth.py: {sorted(missing)}")
    return ns


# ---------------------------------------------------------------- part 1: the booth's code

MARKS = (0.11, 0.37, 0.83)  # where the marker lines go, as a fraction of the design (uneven, so
#                             a turned or flipped result can't be mistaken for the right one)


def marked(size):
    """A test design: black, with 3 thin white lines each way at known places."""
    w, h = size
    img = Image.new("RGB", size, (0, 0, 0))
    d = ImageDraw.Draw(img)
    for f in MARKS:
        x, y = round(f * w), round(f * h)
        d.rectangle((x - 2, 0, x + 2, h - 1), fill=(255, 255, 255))
        d.rectangle((0, y - 2, w - 1, y + 2), fill=(255, 255, 255))
    # Positions as distances from the picture's edge (a pixel's centre is index + 0.5).
    return img, [round(f * w) + 0.5 for f in MARKS], [round(f * h) + 0.5 for f in MARKS]


def line_centres(profile):
    """Sub-pixel centres of the bright lines in a 1-D brightness profile."""
    on = profile > 0.5 * profile.max()
    out, start = [], None
    for i, v in enumerate(np.r_[on, False]):
        if v and start is None:
            start = i
        elif not v and start is not None:
            seg = profile[start:i]
            out.append(float((np.arange(start, i) * seg).sum() / seg.sum()) + 0.5)
            start = None
    return out


def find_lines(out_img):
    """Centres of the marker lines in the sent sheet: (vertical lines' x, horizontal lines' y)."""
    a = np.asarray(out_img.convert("L"), dtype=float)
    h, w = a.shape
    # Away from the crossing lines: sample the middle of the gaps between them.
    cols = line_centres(np.median(a, axis=0))
    rows = line_centres(np.median(a, axis=1))
    return cols, rows


def fit_axis(design_pos, found):
    """Linear map design px -> sent px from matched marker lines; tries both directions."""
    best = None
    for cand in (found, found[::-1]):
        if len(cand) != len(design_pos):
            continue
        p = np.polyfit(design_pos, cand, 1)
        err = np.abs(np.polyval(p, design_pos) - cand).max()
        if best is None or err < best[1]:
            best = (p, err)
    return best


def check_layout(ns, kind, design_size):
    """Where a design of this shape lands on the sheet sent to the printer. Returns the design's
    four edges (and the strip join) in sent px, plus the worst marker-fit error."""
    W, H = ns["PRINT_W"], ns["PRINT_H"]
    img, xs, ys = marked(design_size)
    if kind == "strip":
        sent_in = ns["make_pair_print"](img, img)
        # The pair puts the second strip right of the first.
        dw = design_size[0]
        x_design = xs + [x + dw for x in xs]
        y_design = ys
        span = (0, 2 * dw, 0, design_size[1])
    else:
        sent_in = ns["make_sheet_print"](img)
        x_design, y_design = xs, ys
        span = (0, design_size[0], 0, design_size[1])
    sent = ns["fit_print"](sent_in)
    assert sent.size == (W, H), f"{kind}: sent sheet is {sent.size}, not {(W, H)}"
    cols, rows = find_lines(sent)
    turned = kind == "sheet"  # landscape sheets are turned upright: design x runs down the page
    if turned:
        px, ex = fit_axis(x_design, rows)
        py, ey = fit_axis(y_design, cols)
    else:
        px, ex = fit_axis(x_design, cols)
        py, ey = fit_axis(y_design, rows)
    x0, x1 = sorted(np.polyval(px, [span[0], span[1]]))
    y0, y1 = sorted(np.polyval(py, [span[2], span[3]]))
    if turned:  # design x became sent y
        x0, x1, y0, y1 = y0, y1, x0, x1
    join = np.polyval(px, design_size[0]) if kind == "strip" else None
    # Nothing white added around the design: send a plain dark-red design the same way and
    # check every pixel of the sheet is still that colour (edges included).
    plain = Image.new("RGB", design_size, (120, 20, 30))
    plain_in = (ns["make_pair_print"](plain, plain) if kind == "strip"
                else ns["make_sheet_print"](plain))
    pa = np.asarray(ns["fit_print"](plain_in), dtype=int)
    white_border = int((np.abs(pa - [120, 20, 30]).max(axis=2) > 12).sum())
    return {"left": x0, "right": x1, "top": y0, "bottom": y1, "join": join,
            "fit_err_px": max(ex, ey), "white_border_px": white_border}


def all_designs():
    root = APP.parent
    pats = [root / "frames" / "**" / "*.png", root / "gifts" / "**" / "*.png",
            Path.home() / "my-designs" / "**" / "*.png"]
    found = []
    for pat in pats:
        for f in glob.glob(str(pat), recursive=True):
            if "/fonts/" in f or not Path(f).with_suffix(".json").exists():
                continue
            try:
                with Image.open(f) as im:
                    found.append((f, im.size))
            except Exception:
                pass
    return sorted(found)


def part1(ns):
    W, H = ns["PRINT_W"], ns["PRINT_H"]
    px_mm = W / (4 * 25.4)
    t, b = ns["PRINT_TRIM_MM"], ns["PRINT_BLEED_MM"]
    # Where each edge should land: the measured cut-off, less the bleed.
    want = {"left": (t["left"] - b) * px_mm, "right": W - (t["right"] - b) * px_mm,
            "top": (t["top"] - b) * px_mm, "bottom": H - (t["bottom"] - b) * px_mm}
    paper_mid = (t["left"] * px_mm + W - t["right"] * px_mm) / 2

    designs = all_designs()
    by_shape = {}
    for f, size in designs:
        by_shape.setdefault((ns["image_kind"](size), size), []).append(f)
    archive = glob.glob(str(APP.parent / "strips" / "archive" / "*.jpg"))
    for f in archive:
        with Image.open(f) as im:
            by_shape.setdefault((ns["image_kind"](im.size), im.size), [])

    print("PART 1: the booth's print code, every design shape")
    print(f"  {len(designs)} designs + {len(archive)} saved pictures, "
          f"{len(by_shape)} different shapes")
    results, worst = {}, 0.0
    for (kind, size), files in sorted(by_shape.items()):
        r = check_layout(ns, kind, size)
        errs = {e: (r[e] - want[e]) / px_mm for e in want}
        if r["join"] is not None:
            errs["join"] = (r["join"] - paper_mid) / px_mm
        worst_here = max(abs(v) for v in errs.values())
        worst = max(worst, worst_here)
        ok = worst_here <= TOL_MM and r["white_border_px"] == 0 and r["fit_err_px"] < 0.5
        results[(kind, size)] = (r, errs, ok)
        name = {"strip": "strips, 2 per sheet", "sheet": "landscape sheet (turned upright)",
                "psheet": "portrait sheet"}[kind]
        print(f"  {'PASS' if ok else 'FAIL'}  {name:32s} {size[0]}x{size[1]}  "
              f"{len(files):3d} designs  edges off by at most {worst_here:.3f} mm"
              + (f"  (strip join {errs['join']:+.3f} mm)" if "join" in errs else "")
              + (f"  WHITE BORDER {r['white_border_px']} px" if r["white_border_px"] else ""))
    passed = sum(ok for *_, ok in results.values())
    print(f"  => {passed}/{len(results)} shapes pass; worst edge {worst:.3f} mm "
          f"(pass mark {TOL_MM} mm)")
    return results, passed == len(results)


# ---------------------------------------------------------------- part 2: the printer

def part2(ns, n=200_000):
    """Simulated prints. Each edge's real cut-off = measured + measurement error (fixed for the
    printer) + this print's wobble (paper shifting a little sideways / along, a tiny change of
    size, a slight twist). Scores where the design's edges meet the paper's edges."""
    t, bleed = ns["PRINT_TRIM_MM"], ns["PRINT_BLEED_MM"]
    W_mm, H_mm = 4 * 25.4, 6 * 25.4
    vis_w = W_mm - t["left"] - t["right"]
    vis_h = H_mm - t["top"] - t["bottom"]
    mag = (PAPER_MM[0] / vis_w + PAPER_MM[1] / vis_h) / 2  # sent mm -> paper mm

    def simulate(bleed, sd_measure, sd_shift, sd_twist_mm, n):
        # Error in each edge's cut-off for this printer (the measurement's own uncertainty).
        m = RNG.normal(0, sd_measure, (n, 4))
        # This print: shift across (x) and along (y), and a twist (opposite ends of an edge move
        # opposite ways by up to sd_twist_mm).
        sx = RNG.normal(0, sd_shift, n)
        sy = RNG.normal(0, sd_shift, n)
        tw = np.abs(RNG.normal(0, sd_twist_mm, n))
        # Positive = design reaches past the paper's edge (that much of the design is lost);
        # negative = a gap (the design's edge colour carried on, never white).
        left = bleed + m[:, 0] - sx
        right = bleed + m[:, 1] + sx
        top = bleed + m[:, 2] - sy
        bottom = bleed + m[:, 3] + sy
        e = np.stack([left, right, top, bottom], 1) * mag
        worst_gap = np.maximum(0, -(e - tw[:, None] * mag)).max(axis=1)  # twist: one end worse
        worst_loss = np.maximum(0, e + tw[:, None] * mag).max(axis=1)
        # Area score: how much of the paper and the design don't line up, as a share of the paper.
        lens = np.array([PAPER_MM[1], PAPER_MM[1], PAPER_MM[0], PAPER_MM[0]])
        misfit = (np.abs(e) + tw[:, None] * mag / 2) @ lens
        accuracy = 1 - misfit / (PAPER_MM[0] * PAPER_MM[1])
        perfect = (worst_gap <= 0.10) & (worst_loss <= 0.75)
        return {"accuracy": accuracy.mean(), "acc_p01": np.percentile(accuracy, 0.1),
                "no_gap": (worst_gap <= 0.10).mean(), "perfect": perfect.mean(),
                "loss_mean": np.maximum(0, e).mean(), "loss_p999": np.percentile(worst_loss, 99.9),
                "gap_p999": np.percentile(worst_gap, 99.9)}

    print()
    print(f"PART 2: {n:,} simulated prints per row (paper {PAPER_MM[0]:.0f}x{PAPER_MM[1]:.0f} mm)")
    print("  'Edges spot on' = no gap over 0.1 mm and no more than 0.75 mm of design lost, any edge.")
    print("  Gaps show the design's own edge colour carried on, never white.")
    rows = []
    for label, sdm, sds, tw in [
        ("perfectly repeatable printer      ", 0.00, 0.00, 0.00),
        ("measurement error only (0.08 mm)  ", 0.08, 0.00, 0.00),
        ("+ print wobble 0.10 mm, twist 0.05", 0.08, 0.10, 0.05),
        ("+ print wobble 0.15 mm, twist 0.10", 0.08, 0.15, 0.10),
        ("+ print wobble 0.25 mm, twist 0.15", 0.08, 0.25, 0.15),
    ]:
        r = simulate(bleed, sdm, sds, tw, n)
        rows.append((label, r))
        print(f"  {label}  area fit {100 * r['accuracy']:6.2f}%   edges spot on "
              f"{100 * r['perfect']:6.2f}%   no gap {100 * r['no_gap']:6.2f}%   "
              f"worst 1-in-1000: gap {r['gap_p999']:.2f} mm, design lost {r['loss_p999']:.2f} mm")

    print()
    print("  Bleed sweep (wobble 0.15 mm, twist 0.10, measurement 0.08):")
    for bl in (0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8):
        r = simulate(bl, 0.08, 0.15, 0.10, n)
        mark = "  <- current" if abs(bl - bleed) < 1e-9 else ""
        print(f"    bleed {bl:.1f} mm: area fit {100 * r['accuracy']:6.2f}%  edges spot on "
              f"{100 * r['perfect']:6.2f}%  no gap {100 * r['no_gap']:6.2f}%{mark}")
    return rows


def main():
    ns = load_print_code()
    print(f"Settings: cut-off {ns['PRINT_TRIM_MM']} mm, bleed {ns['PRINT_BLEED_MM']} mm")
    print()
    _, ok = part1(ns)
    part2(ns)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
