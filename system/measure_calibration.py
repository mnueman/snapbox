#!/usr/bin/env python3
"""Measures a photo of a printed calibration sheet (system/print_calibration.py), tabs still on.

Finds the sheet's inner rectangle (where the coloured bands meet the white middle, 8 mm in from
every edge of the picture as sent), works out the photo's perspective from its four corners, then
walks along each edge and finds, in millimetres of the picture as sent:
  top / bottom: the perforation (where the tab tears off),
  left / right: the paper's edge.
Checks itself against the band boundaries at 3-7 mm, which the perspective fit doesn't use.

    python3 system/measure_calibration.py PHOTO.jpg [PHOTO2.jpg ...]

The photo must be roughly straight on, the whole sheet in view, TOP at the top, on a dark surface.
"""
import json
import sys

import numpy as np
from PIL import Image, ImageOps

W_MM, H_MM = 4 * 25.4, 6 * 25.4
INNER = 8.0  # mm: the white middle starts here
EDGE_SKIP_MM = 7.0  # stay this far from rulers and corners when walking an edge
RULERS = {"top": [0.2, 0.5, 0.8], "bottom": [0.2, 0.5, 0.8],
          "left": [0.15, 0.5, 0.85], "right": [0.15, 0.5, 0.85]}


def load(path):
    im = ImageOps.exif_transpose(Image.open(path)).convert("RGB")
    return np.asarray(im, dtype=np.float32)


def bilinear(img, x, y):
    h, w = img.shape[:2]
    x = np.clip(x, 0, w - 1.001); y = np.clip(y, 0, h - 1.001)
    x0 = np.floor(x).astype(int); y0 = np.floor(y).astype(int)
    fx = (x - x0)[..., None]; fy = (y - y0)[..., None]
    a = img[y0, x0]; b = img[y0, x0 + 1]; c = img[y0 + 1, x0]; d = img[y0 + 1, x0 + 1]
    return (a * (1 - fx) + b * fx) * (1 - fy) + (c * (1 - fx) + d * fx) * fy


def white_middle(img):
    """Mask (1/4 size) of the sheet's white middle: bright, colourless, connected to the centre."""
    small = img[::4, ::4]
    g = small.mean(axis=2)
    sat = small.max(axis=2) - small.min(axis=2)
    h, w = g.shape
    centre = g[h // 3:2 * h // 3, w // 3:2 * w // 3]
    paper = np.percentile(centre, 80)
    # Shadows and glare: compare each spot with the brightest paper near it, not the whole photo.
    B = 24
    hb, wb = h // B, w // B
    blocks = g[:hb * B, :wb * B].reshape(hb, B, wb, B).transpose(0, 2, 1, 3).reshape(hb, wb, -1)
    local = np.percentile(blocks, 95, axis=2)
    pad = np.pad(local, 1, mode="edge")  # each block: the brightest of it and its neighbours
    local = np.max([pad[i:i + hb, j:j + wb] for i in range(3) for j in range(3)], axis=0)
    illum = np.asarray(Image.fromarray(local.astype(np.float32)).resize((w, h), Image.BILINEAR))
    mask = (g > 0.88 * illum) & (g > 0.45 * paper) & (sat < 40)
    region = np.zeros_like(mask)
    region[h // 2 - 3:h // 2 + 3, w // 2 - 3:w // 2 + 3] = True
    region &= mask
    # Grow from the centre through the mask until it stops changing.
    for _ in range(4000):
        grown = region.copy()
        grown[1:] |= region[:-1]; grown[:-1] |= region[1:]
        grown[:, 1:] |= region[:, :-1]; grown[:, :-1] |= region[:, 1:]
        grown &= mask
        if (grown == region).all():
            break
        region = grown
    return region, paper


def robust_line(u, v):
    """Fits v = a*u + b to the points most of which lie on one straight line (RANSAC), ignoring
    the rest (ticks, labels, a patch where the white middle spilled over)."""
    rng = np.random.default_rng(0)
    best, best_n = None, -1
    for _ in range(400):
        i, j = rng.choice(len(u), 2, replace=False)
        if abs(u[j] - u[i]) < len(u) / 4:
            continue
        a = (v[j] - v[i]) / (u[j] - u[i]); b = v[i] - a * u[i]
        n = (np.abs(a * u + b - v) < 1.5).sum()
        if n > best_n:
            best, best_n = (a, b), n
    keep = np.abs(best[0] * u + best[1] - v) < 1.5
    for _ in range(3):
        p = np.polyfit(u[keep], v[keep], 1)
        keep = np.abs(np.polyval(p, u) - v) < 1.2
    p = np.polyfit(u[keep], v[keep], 1)
    return p, np.median(np.abs(np.polyval(p, u[keep]) - v[keep])), keep.sum()


def inner_edges(img, region):
    """Sub-pixel points along the inner rectangle's four sides (full-size px), and fitted lines."""
    g = img.mean(axis=2)
    rows = np.where(region.any(axis=1))[0]
    cols = np.where(region.any(axis=0))[0]
    r0, r1 = rows.min(), rows.max(); c0, c1 = cols.min(), cols.max()
    lines = {}
    for side in ("top", "bottom", "left", "right"):
        us, vs = [], []
        if side in ("top", "bottom"):
            span = range(c0 + (c1 - c0) // 20, c1 - (c1 - c0) // 20)
        else:
            span = range(r0 + (r1 - r0) // 20, r1 - (r1 - r0) // 20)
        for i in span:
            line = region[:, i] if side in ("top", "bottom") else region[i, :]
            idx = np.where(line)[0]
            if len(idx) == 0:
                continue
            e = (idx.min() if side in ("top", "left") else idx.max()) * 4
            # Refine at full size: steepest brightness change within +-10 px.
            lo, hi = e - 10, e + 11
            u = i * 4 + 1.5
            if side in ("top", "bottom"):
                prof = g[lo:hi, int(u) - 2:int(u) + 3].mean(axis=1)
            else:
                prof = g[int(u) - 2:int(u) + 3, lo:hi].mean(axis=0)
            if len(prof) < 21:
                continue
            grad = np.abs(np.diff(prof))
            k = grad.argmax()
            if 1 <= k < len(grad) - 1:
                a, b, c = grad[k - 1], grad[k], grad[k + 1]
                k = k + 0.5 * (a - c) / (a - 2 * b + c) if (a - 2 * b + c) != 0 else k
            us.append(u); vs.append(lo + k + 0.5)
        us, vs = np.array(us), np.array(vs)
        p, err, n = robust_line(us, vs)
        lines[side] = (p, err, n)
    return lines


def corner(h_line, v_line):
    """Where y = a*x + b (top/bottom) meets x = c*y + d (left/right)."""
    (a, b), (c, d) = h_line, v_line
    y = (a * d + b) / (1 - a * c)
    return np.array([c * y + d, y])


def homography(src, dst):
    A = []
    for (x, y), (u, v) in zip(src, dst):
        A.append([x, y, 1, 0, 0, 0, -u * x, -u * y, -u])
        A.append([0, 0, 0, x, y, 1, -v * x, -v * y, -v])
    _, _, vt = np.linalg.svd(np.array(A))
    return vt[-1].reshape(3, 3) / vt[-1, -1]


def to_photo(H, x_mm, y_mm):
    p = np.stack([x_mm, y_mm, np.ones_like(x_mm)], axis=-1) @ H.T
    return p[..., 0] / p[..., 2], p[..., 1] / p[..., 2]


def profile(img, H, edge, along_mm, depth_mm, width_mm=1.2):
    """Colour along `depth_mm` (from that edge inward) at `along_mm`, averaged over width_mm."""
    offs = np.linspace(-width_mm / 2, width_mm / 2, 9)
    A, D = np.meshgrid(along_mm + offs, depth_mm)  # (depth, offsets)
    if edge == "top":
        x, y = A, D
    elif edge == "bottom":
        x, y = A, H_MM - D
    elif edge == "left":
        x, y = D, A
    else:
        x, y = W_MM - D, A
    px, py = to_photo(H, x, y)
    rgb = bilinear(img, px, py)
    return rgb  # (depth, offsets, 3)


def find_perforation(rgb, depth):
    """The perforation: a thin line brighter and greyer than the bands either side."""
    g = rgb.mean(axis=2)
    sat = rgb.max(axis=2) - rgb.min(axis=2)
    # Dashed line: on each sample line, how much brighter than its surroundings (0.6 mm either side)
    step = depth[1] - depth[0]
    n = int(round(0.6 / step))
    k = np.ones(2 * n + 1) / (2 * n + 1)
    lift = np.stack([g[:, j] - np.convolve(g[:, j], k, mode="same") for j in range(g.shape[1])], 1)
    score = np.clip(lift, 0, None) * (sat < 45)
    score = np.sort(score, axis=1)[:, -4:].mean(axis=1)  # the brightest few: dashes, not gaps
    valid = (depth > 2.5) & (depth < 7.6)
    i = np.where(valid)[0][score[valid].argmax()]
    win = np.arange(max(0, i - 6), min(len(depth), i + 7))
    w = score[win]
    return float((depth[win] * w).sum() / w.sum()), float(score[i])


def find_paper_edge(rgb, depth):
    """The paper's edge: where the dark background ends."""
    g = np.median(rgb.mean(axis=2), axis=1)
    bg = np.percentile(g[depth < 0.5], 20)
    paper = np.median(g[(depth > 4.2) & (depth < 4.8)])  # the blue band, well inside
    thr = (bg + paper) / 2
    above = np.where((g > thr) & (depth < 4.5))[0]
    if len(above) == 0:
        return float("nan"), 0.0
    i = above[0]
    if i == 0:
        return float(depth[0]), float(paper - bg)
    d0, d1 = depth[i - 1], depth[i]
    x = d0 + (thr - g[i - 1]) / (g[i] - g[i - 1]) * (d1 - d0)
    return float(x), float(paper - bg)


def band_check(rgb, depth, avoid):
    """Where the band boundaries at 4, 5, 6 and 7 mm really are (colour changes), as found the
    same way as everything else: an independent check of the whole measurement. Skips any within
    0.4 mm of `avoid` (the perforation or paper edge)."""
    prof = np.median(rgb, axis=1)  # (depth, 3)
    grad = np.abs(np.gradient(prof, axis=0)).sum(axis=1)
    found = {}
    for mm in (4.0, 5.0, 6.0, 7.0):
        if abs(mm - avoid) < 0.45:
            continue
        win = np.where(np.abs(depth - mm) < 0.3)[0]
        i = win[grad[win].argmax()]
        if 1 <= i < len(grad) - 1:
            a, b, c = grad[i - 1], grad[i], grad[i + 1]
            off = 0.5 * (a - c) / (a - 2 * b + c) if (a - 2 * b + c) != 0 else 0.0
        else:
            off = 0.0
        found[mm] = float(depth[i] + off * (depth[1] - depth[0]))
    return found


def local_offset(rgb, depth):
    """How far off this spot's map is, from the two strongest band edges right next to it: light
    grey | dark grey at 7 mm, dark grey | white at 8 mm. A sheet that isn't quite flat, or the
    lens, bends the paper's edge and these bands alike, so this takes the bend out."""
    g = np.median(rgb.mean(axis=2), axis=1)
    grad = np.gradient(g)
    step = depth[1] - depth[0]
    found = []
    for mm, sign in ((7.0, -1), (8.0, 1)):
        win = np.where(np.abs(depth - mm) < 0.35)[0]
        gg = sign * grad[win]
        i = win[gg.argmax()]
        a, b, c = sign * grad[i - 1], sign * grad[i], sign * grad[i + 1]
        off = 0.5 * (a - c) / (a - 2 * b + c) if (a - 2 * b + c) != 0 else 0.0
        found.append(depth[i] + off * step - mm)
    return float(np.mean(found))


def measure(path, verbose=True):
    img = load(path)
    region, paper = white_middle(img)
    lines = inner_edges(img, region)
    TL = corner(lines["top"][0], lines["left"][0]); TR = corner(lines["top"][0], lines["right"][0])
    BL = corner(lines["bottom"][0], lines["left"][0]); BR = corner(lines["bottom"][0], lines["right"][0])
    src = [(INNER, INNER), (W_MM - INNER, INNER), (W_MM - INNER, H_MM - INNER), (INNER, H_MM - INNER)]
    H = homography(src, [TL, TR, BR, BL])
    depth = np.arange(-1.5, 8.6, 0.01)
    out = {"photo": path, "line_fit_px": {s: round(float(l[1]), 2) for s, l in lines.items()},
           "line_points": {s: int(l[2]) for s, l in lines.items()},
           "edges": {}}
    for edge in ("top", "bottom", "left", "right"):
        length = W_MM if edge in ("top", "bottom") else H_MM
        rulers = [f * length for f in RULERS[edge]]
        vals, checks, along = [], [], []
        for a in np.arange(EDGE_SKIP_MM + 6, length - EDGE_SKIP_MM - 6 + 0.01, 1.0):
            if any(abs(a - r) < EDGE_SKIP_MM for r in rulers):
                continue
            rgb = profile(img, H, edge, a, depth)
            if edge in ("top", "bottom"):
                v, sig = find_perforation(rgb, depth)
            else:
                v, sig = find_paper_edge(rgb, depth)
            if not np.isfinite(v):
                continue
            off = local_offset(rgb, depth)
            if abs(off) > 0.6:  # couldn't see the bands properly here
                continue
            v -= off
            chk = {mm: d - off for mm, d in band_check(rgb, depth, v + off).items()}
            vals.append(v); along.append(a); checks.append(chk)
        vals, checks, along = np.array(vals), np.array(checks), np.array(along)
        # Robust: drop odd samples (a speck, a shadow, the next sheet showing): first anything far
        # from the median, then anything more than 0.2 mm off the line through the rest.
        keep = np.abs(vals - np.median(vals)) < 0.6
        for _ in range(3):
            p = np.polyfit(along[keep], vals[keep], 1)
            keep = np.abs(np.polyval(p, along) - vals) < 0.2
        p = np.polyfit(along[keep], vals[keep], 1)
        out.setdefault("raw", {})[edge] = (along.tolist(), vals.tolist())
        mid = float(np.polyval(p, length / 2))
        ends = np.polyval(p, [along[keep].min(), along[keep].max()])
        out["edges"][edge] = {
            "cut_mm": round(mid, 3),                        # at the middle of the edge
            "twist_mm": round(float(ends[1] - ends[0]), 3),  # change over the measured stretch
            # Slant: change per 100 mm along the edge (left to right / top to bottom).
            "slant_per_100mm": round(float(p[0]) * 100, 4),
            "scatter_mm": round(float(np.std(vals[keep] - np.polyval(p, along[keep]))), 3),
            "samples": int(keep.sum()),
            # Band boundaries found vs where they are: should be 0.000.
            "check_off_mm": {str(mm): round(float(np.median([c[mm] for c in checks if mm in c]) - mm), 3)
                             for mm in (4.0, 5.0, 6.0, 7.0)
                             if sum(mm in c for c in checks) >= 5},
        }
    if verbose:
        print(f"{path}: inner-rectangle line fits (median px off): {out['line_fit_px']} "
              f"points used {out['line_points']}")
        for e, r in out["edges"].items():
            print(f"  {e:6s} cut {r['cut_mm']:5.2f} mm  (twist end-to-end {r['twist_mm']:+.2f}, "
                  f"scatter {r['scatter_mm']:.2f}, {r['samples']} samples; "
                  f"band edges off by {r['check_off_mm']})")
    return out


if __name__ == "__main__":
    results = [measure(p) for p in sys.argv[1:]]
    if len(results) > 1:
        print()
        for e in ("top", "bottom", "left", "right"):
            v = np.array([r["edges"][e]["cut_mm"] for r in results])
            sl = np.array([r["edges"][e]["slant_per_100mm"] for r in results])
            print(f"{e:6s} mean {v.mean():.3f} mm   sheet-to-sheet sd {v.std(ddof=1):.3f} mm   "
                  f"values {np.round(v, 2).tolist()}   slant per 100 mm {sl.mean():+.3f} "
                  f"(sd {sl.std(ddof=1):.3f})")
        offs = [o for r in results for e in r["edges"].values() for o in e["check_off_mm"].values()]
        print(f"self-check: band edges found {np.mean(offs):+.3f} mm off on average "
              f"(sd {np.std(offs):.3f}, {len(offs)} checks): subtract that from the cut-offs")
    print(json.dumps(results))
