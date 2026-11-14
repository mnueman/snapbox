#!/usr/bin/env python3
"""Checks that prints fit the paper, before trying it on paper.

PART 1, the booth's own code. Takes the print functions out of photobooth.py (print_corners,
fit_print, make_pair_print, make_sheet_print) and runs a test picture of every design shape on
this booth through them: strips (two to a sheet), landscape sheets (turned upright to print) and
portrait sheets. Each test picture is a grid of dots at known places; finding the dots in the
sheet sent to the printer shows exactly where every part of the design lands. Those positions are
checked against the measured paper edges (PRINT_TRIM_MM, PRINT_SLANT) and the bleed, worked out
here separately, not with the app's own corner maths. Also: nothing white anywhere on the sheet.

PART 2, the printer. A million simulated prints using what the ruler prints measured: each
edge's cut-off varies from print to print by what was seen between the 3 sheets (made larger, as
3 sheets can't show the full spread), our measurement may be off by its own uncertainty, and the
slant varies too. Scores how closely the design's edges meet the paper's edges, for a range of
bleeds, and finds the smallest bleed that leaves no gap on 99.9% of prints.

    python3 system/print_fit_sim.py
"""
import ast
import glob
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

APP = Path(__file__).resolve().parent.parent / "photobooth.py"
PAPER_MM = (100.0, 148.0)  # SELPHY postcard after tearing off the tabs (width, height)
PART1_TOL_MM = 0.05  # every dot and every edge within this of where it should be (~1 px)

# What the ruler prints measured (system/measure_calibration.py), booth-1's CP1500: 3 sheets,
# 5 photos (two sheets photographed twice, which shows how repeatable the measuring is: 0.018 mm).
MEASURED = {  # edge: (sheet-to-sheet spread seen, print-to-print spread once the measuring's own
    #                  is taken out, slant spread per mm)
    "top": (0.029, 0.022, 0.00067), "bottom": (0.036, 0.031, 0.00122),
    "left": (0.053, 0.050, 0.00055), "right": (0.056, 0.053, 0.00103),
}
SHEETS = 3
BIAS_SD = 0.02  # how far the self-check correction itself may be off
TEAR_SD = 0.03  # top/bottom: a tab doesn't tear exactly down the middle of the perforation
SPREAD_SAFETY = 1.5  # 3 sheets may understate the true spread: assume 1.5x what was seen
GAP_OK_MM = 0.05  # a gap this small can't be seen (and shows the design's edge colour anyway)


def load_print_code():
    tree = ast.parse(APP.read_text())
    want_fn = {"print_corners", "_perspective", "fit_print", "make_pair_print",
               "make_sheet_print", "image_kind"}
    want_var = {"STRIP_W", "STRIP_H", "PRINT_W", "PRINT_H", "PRINT_TRIM_MM", "PRINT_SLANT",
                "PRINT_BLEED_MM"}
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


# ------------------------------------------------------------------- part 1: the booth's code

FRACS = (0.015, 0.17, 0.33, 0.5, 0.67, 0.83, 0.985)


def dot_design(size):
    """Black, with a grid of 7x7 px white dots. Returns the picture and the dots' centres
    (distances from the top-left corner, so a pixel's centre is index + 0.5)."""
    w, h = size
    img = Image.new("RGB", size, (0, 0, 0))
    d = ImageDraw.Draw(img)
    pts = []
    for fy in FRACS:
        for fx in FRACS:
            x, y = round(fx * w), round(fy * h)
            d.rectangle((x - 3, y - 3, x + 3, y + 3), fill=(255, 255, 255))
            pts.append((x + 0.5, y + 0.5))
    return img, np.array(pts)


def homography(src, dst):
    """3x3 H with dst ~ H @ src, least squares over all points."""
    A = []
    for (x, y), (u, v) in zip(src, dst):
        A.append([x, y, 1, 0, 0, 0, -u * x, -u * y, -u])
        A.append([0, 0, 0, x, y, 1, -v * x, -v * y, -v])
    _, _, vt = np.linalg.svd(np.array(A))
    return vt[-1].reshape(3, 3) / vt[-1, -1]


def apply(H, pts):
    p = np.c_[pts, np.ones(len(pts))] @ H.T
    return p[:, :2] / p[:, 2:]


def find_dots(img, guesses, r=22):
    a = np.asarray(img.convert("L"), dtype=float)
    out = []
    for gx, gy in guesses:
        x0, y0 = int(gx) - r, int(gy) - r
        win = a[max(0, y0):y0 + 2 * r, max(0, x0):x0 + 2 * r]
        wgt = np.clip(win - 128, 0, None)
        if wgt.sum() == 0:
            out.append((np.nan, np.nan)); continue
        ys, xs = np.mgrid[0:win.shape[0], 0:win.shape[1]]
        out.append(((xs * wgt).sum() / wgt.sum() + max(0, x0) + 0.5,
                    (ys * wgt).sum() / wgt.sum() + max(0, y0) + 0.5))
    return np.array(out)


def spec_lines(ns):
    """The paper's edges and where the design's edges should be, in mm on the sheet sent,
    worked out here from the measurements (independently of the app's print_corners)."""
    t, s, b = ns["PRINT_TRIM_MM"], ns["PRINT_SLANT"], ns["PRINT_BLEED_MM"]
    W, H = 4 * 25.4, 6 * 25.4
    paper = {"top": lambda x: t["top"] + s["top"] * (x - W / 2),
             "bottom": lambda x: H - (t["bottom"] + s["bottom"] * (x - W / 2)),
             "left": lambda y: t["left"] + s["left"] * (y - H / 2),
             "right": lambda y: W - (t["right"] + s["right"] * (y - H / 2))}
    outward = {"top": -1, "bottom": 1, "left": -1, "right": 1}
    design = {e: (lambda f, o: (lambda u: f(u) + o * b))(f, outward[e]) for e, f in paper.items()}
    return paper, design


def check_shape(ns, kind, size):
    W, H = ns["PRINT_W"], ns["PRINT_H"]
    px_mm = W / (4 * 25.4)
    img, pts = dot_design(size)
    w, h = size
    if kind == "strip":
        before = ns["make_pair_print"](img, img)
        pre = np.r_[pts, pts + [w, 0]] * [W / (2 * w), H / h]
        design_box = (2 * w, h)
    else:
        before = ns["make_sheet_print"](img)
        if kind == "sheet":  # turned upright; which way is found from the dots below
            pre = np.c_[pts[:, 1], w - pts[:, 0]] * [W / h, H / w]
            alt = np.c_[h - pts[:, 1], pts[:, 0]] * [W / h, H / w]
        else:
            pre = pts * [W / w, H / h]
        design_box = size
    sent = ns["fit_print"](before)
    assert sent.size == (W, H), f"sheet sent is {sent.size}"

    # Where the app means each dot to go (its own corners), to find the dots.
    corners = np.array(ns["print_corners"]((W, H)))
    rect = np.array([(0, 0), (W, 0), (W, H), (0, H)], float)
    Hm = homography(rect, corners)
    if kind == "sheet":
        # Which way the sheet is turned: whichever puts the dots where they're found.
        found_a = find_dots(sent, apply(Hm, pre)); found_b = find_dots(sent, apply(Hm, alt))
        err_a = np.nanmax(np.hypot(*(found_a - apply(Hm, pre)).T))
        err_b = np.nanmax(np.hypot(*(found_b - apply(Hm, alt)).T))
        if err_b < err_a:
            pre = alt
    expect = apply(Hm, pre)
    found = find_dots(sent, expect)
    dot_err_mm = np.nanmax(np.hypot(*(found - expect).T)) / px_mm
    missing = int(np.isnan(found).any(axis=1).sum())

    # Independent check of the edges: the map from the whole picture (before fitting) to the
    # sheet, from the dots actually found; then where the picture's edges land vs the spec.
    Hf = homography(pre, found)
    paper, design = spec_lines(ns)
    edge_err, gap = {}, {}
    n = 50
    for e in ("top", "bottom", "left", "right"):
        u = np.linspace(0, W if e in ("top", "bottom") else H, n)
        if e == "top":
            pts_e = np.c_[u, np.zeros(n)]
        elif e == "bottom":
            pts_e = np.c_[u, np.full(n, H)]
        elif e == "left":
            pts_e = np.c_[np.zeros(n), u]
        else:
            pts_e = np.c_[np.full(n, W), u]
        land = apply(Hf, pts_e) / px_mm  # mm on the sheet sent
        if e in ("top", "bottom"):
            along, pos = land[:, 0], land[:, 1]
        else:
            along, pos = land[:, 1], land[:, 0]
        edge_err[e] = float(np.abs(pos - design[e](along)).max())
    join = None
    if kind == "strip":
        mid = apply(Hf, np.c_[np.full(n, W / 2), np.linspace(0, H, n)]) / px_mm
        centre = (paper["left"](mid[:, 1]) + paper["right"](mid[:, 1])) / 2
        join = float(np.abs(mid[:, 0] - centre).max())

    # Nothing white: a plain dark-red picture comes out dark red everywhere, edges included.
    plain = Image.new("RGB", size, (120, 20, 30))
    plain_in = (ns["make_pair_print"](plain, plain) if kind == "strip"
                else ns["make_sheet_print"](plain))
    pa = np.asarray(ns["fit_print"](plain_in), dtype=int)
    off_colour = int((np.abs(pa - [120, 20, 30]).max(axis=2) > 12).sum())
    return dot_err_mm, missing, edge_err, join, off_colour


def all_shapes(ns):
    root = APP.parent
    shapes = {}
    pats = [root / "frames" / "**" / "*.png", root / "gifts" / "**" / "*.png",
            Path.home() / "my-designs" / "**" / "*.png"]
    n_designs = 0
    for pat in pats:
        for f in glob.glob(str(pat), recursive=True):
            if "/fonts/" in f or not Path(f).with_suffix(".json").exists():
                continue
            with Image.open(f) as im:
                shapes.setdefault((ns["image_kind"](im.size), im.size), []).append(f)
            n_designs += 1
    saved = glob.glob(str(root / "strips" / "archive" / "*.jpg"))
    for f in saved:
        with Image.open(f) as im:
            shapes.setdefault((ns["image_kind"](im.size), im.size), [])
    return shapes, n_designs, len(saved)


def part1(ns):
    shapes, n_designs, n_saved = all_shapes(ns)
    print("PART 1: the booth's print code, every design shape")
    print(f"  {n_designs} designs + {n_saved} saved pictures = {len(shapes)} shapes to print")
    all_ok, worst = True, 0.0
    names = {"strip": "strips, 2 per sheet", "sheet": "landscape sheet, turned upright",
             "psheet": "portrait sheet"}
    for (kind, size), files in sorted(shapes.items()):
        dot_err, missing, edge_err, join, off = check_shape(ns, kind, size)
        w = max([dot_err] + list(edge_err.values()) + ([join] if join is not None else []))
        ok = w <= PART1_TOL_MM and missing == 0 and off == 0
        all_ok &= ok
        worst = max(worst, w)
        print(f"  {'PASS' if ok else 'FAIL'}  {names[kind]:31s} {size[0]}x{size[1]} "
              f"({len(files)} designs): dots {dot_err:.3f} mm, edges "
              + ", ".join(f"{e} {v:.3f}" for e, v in edge_err.items())
              + (f", strip join {join:.3f}" if join is not None else "")
              + (f", {missing} DOTS MISSING" if missing else "")
              + (f", {off} px NOT DESIGN COLOUR" if off else ", no white"))
    print(f"  => {'all pass' if all_ok else 'FAILED'}: worst {worst:.3f} mm "
          f"(pass mark {PART1_TOL_MM} mm)")
    return all_ok, worst


# --------------------------------------------------------------------- part 2: the printer

def simulate(ns, bleed, n, rng, safety=SPREAD_SAFETY):
    t = ns["PRINT_TRIM_MM"]
    W, H = 4 * 25.4, 6 * 25.4
    mag = (PAPER_MM[0] / (W - t["left"] - t["right"]) + PAPER_MM[1] / (H - t["top"] - t["bottom"])) / 2
    lens = {"top": W, "bottom": W, "left": H, "right": H}
    ends = []  # per edge: how far the design reaches past the paper at both corners (mm on paper)
    area = np.zeros(n)
    for e, (seen, real, slant) in MEASURED.items():
        # How far our numbers are off for this printer (fixed, unknown): the average of 3 sheets
        # and the self-check correction can both be a little off.
        mean_err = np.sqrt((seen / np.sqrt(SHEETS)) ** 2 + BIAS_SD ** 2)
        d_mid = rng.normal(0, mean_err, n)
        d_slant = rng.normal(0, slant / np.sqrt(SHEETS), n)
        # This print: the printer's own print-to-print spread, and the tear.
        d_mid += rng.normal(0, safety * real, n)
        if e in ("top", "bottom"):
            d_mid += rng.normal(0, TEAR_SD, n)
        d_slant += rng.normal(0, safety * slant, n)
        half = lens[e] / 2
        over = np.stack([bleed + d_mid - d_slant * half, bleed + d_mid + d_slant * half], 1) * mag
        ends.append(over)
        a, b = over[:, 0], over[:, 1]
        same = np.sign(a) == np.sign(b)
        mis = np.where(same, (np.abs(a) + np.abs(b)) / 2,
                       (a ** 2 + b ** 2) / (2 * (np.abs(a) + np.abs(b)) + 1e-12))
        area += mis * lens[e] * mag
    over = np.concatenate(ends, axis=1)  # (n, 8): every edge, both ends
    gap = np.clip(-over, 0, None).max(axis=1)
    reach = np.clip(over, 0, None).max(axis=1)
    fit = 1 - area / (PAPER_MM[0] * PAPER_MM[1])
    no_gap = gap <= GAP_OK_MM
    return {"fit": fit.mean(), "no_gap": no_gap.mean(),
            "within_05": (no_gap & (reach <= 0.5)).mean(),
            "within_075": (no_gap & (reach <= 0.75)).mean(),
            "lost_mean": over.clip(0).mean(), "lost_p999": np.percentile(reach, 99.9),
            "gap_p999": np.percentile(gap, 99.9)}


def part2(ns, n=1_000_000):
    rng = np.random.default_rng(7)
    print()
    print(f"PART 2: {n:,} simulated prints per row, from the ruler prints' measurements")
    print(f"  print-to-print spread assumed {SPREAD_SAFETY}x what was measured. A gap = the design")
    print(f"  stopping short of the paper's edge by over {GAP_OK_MM} mm somewhere (it would show the")
    print("  design's own edge colour carried on, never white).")
    print("  bleed  no gap     no gap and design  area fit  1-in-1000 worst:  design lost")
    print("                    lost <=0.5 / 0.75mm          gap    lost       (avg per edge)")
    best, rows = None, {}
    for bl in np.round(np.arange(0.0, 0.51, 0.05), 2):
        r = simulate(ns, bl, n, rng)
        rows[bl] = r
        mark = "  <- current" if abs(bl - ns["PRINT_BLEED_MM"]) < 1e-9 else ""
        print(f"  {bl:.2f}  {100 * r['no_gap']:8.3f}%  {100 * r['within_05']:8.3f}% "
              f"{100 * r['within_075']:8.3f}%  {100 * r['fit']:6.2f}%   {r['gap_p999']:.2f}  "
              f"{r['lost_p999']:.2f}mm     {r['lost_mean']:.2f}mm{mark}")
        if best is None and r["no_gap"] >= 0.999:
            best = bl
    if best is not None:
        r = rows[best]
        print(f"  => smallest bleed with no gap on >= 99.9% of prints: {best:.2f} mm: "
              f"{100 * r['no_gap']:.3f}% gap-free; {100 * r['within_05']:.2f}% also lose no more "
              f"than 0.5 mm of design anywhere; area fit {100 * r['fit']:.2f}%")
    print()
    print("  Check: if prints vary 2x as much as measured, at that bleed and the next ones up:")
    for bl in (best, best + 0.05, best + 0.1) if best is not None else ():
        r = simulate(ns, bl, n, rng, safety=2.0)
        print(f"    bleed {bl:.2f} mm: no gap {100 * r['no_gap']:.3f}%, area fit {100 * r['fit']:.2f}%")
    return best


def main():
    ns = load_print_code()
    print(f"Settings: cut-off {ns['PRINT_TRIM_MM']} mm, slant {ns['PRINT_SLANT']}, "
          f"bleed {ns['PRINT_BLEED_MM']} mm")
    print()
    ok, _ = part1(ns)
    part2(ns)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
