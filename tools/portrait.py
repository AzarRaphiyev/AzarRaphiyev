"""Photo -> 1-bit dithered dot grid, with background segmentation for dark mode."""
import os

import numpy as np
from PIL import Image, ImageEnhance, ImageFilter, ImageOps
from scipy import ndimage

HERE = os.path.dirname(os.path.abspath(__file__))

GRID_W, GRID_H = 300, 340
CROP = (93, 55, 344, 340)          # head + shoulders, aspect-matched to the grid
BG_THRESHOLD = 0.05                # chroma distance; see 01_explore_mask.py
# Dark mode lands on the brief's ~17k. Light mode cannot: it keeps the backdrop
# and the photo's hair/jumper crush to solid black, so thinning to 17k either
# posterises the midtones into flat slabs (high gamma) or hollows out the face.
# 35k measured better on both counts, and costs little file size because solid
# regions collapse into long horizontal runs.
TARGET_DOTS = {"dark": 17000, "light": 35000}


def _prepared_gray(img):
    """Contrast pipeline from the brief: autocontrast -> 1.3x -> unsharp."""
    g = img.convert("L")
    g = ImageOps.autocontrast(g, cutoff=1)
    g = ImageEnhance.Contrast(g).enhance(1.3)
    g = g.filter(ImageFilter.UnsharpMask(radius=3, percent=140, threshold=0))
    return np.asarray(g).astype(np.float64) / 255.0


def subject_mask(rgb):
    """Boolean mask of the sitter, separated from the flat backdrop.

    A plain RGB distance drowns in the vignette (the corners are the same hue,
    just darker), so the test is on chroma after dividing out brightness.
    """
    a = rgb.astype(np.float64)
    corners = np.concatenate([a[0:40, 0:40].reshape(-1, 3), a[0:40, -40:].reshape(-1, 3)])
    bg = np.median(corners, axis=0)

    def chroma(x):
        return x / (x.sum(axis=-1, keepdims=True) + 1e-6)

    dist = np.linalg.norm(chroma(a) - chroma(bg[None, None, :]), axis=-1)
    m = dist > BG_THRESHOLD
    m = ndimage.binary_closing(m, structure=np.ones((7, 7)))
    m = ndimage.binary_fill_holes(m)
    lab, n = ndimage.label(m)
    if n:
        sizes = ndimage.sum(m, lab, range(1, n + 1))
        m = lab == (int(np.argmax(sizes)) + 1)
    return ndimage.binary_opening(m, structure=np.ones((3, 3)))


def dither(density, mask=None):
    """1-bit Floyd-Steinberg in serpentine order.

    `density` is the probability of ink per cell. Where `mask` is False the cell
    can never take ink *and* accumulated error is hard-cleared, so error
    diffusion cannot bleed a halo across the segmentation edge.
    """
    h, w = density.shape
    buf = density.astype(np.float64).copy()
    if mask is not None:
        buf[~mask] = 0.0
    out = np.zeros((h, w), dtype=bool)

    for y in range(h):
        cols = range(w) if y % 2 == 0 else range(w - 1, -1, -1)
        fwd = 1 if y % 2 == 0 else -1
        for x in cols:
            if mask is not None and not mask[y, x]:
                buf[y, x] = 0.0
                continue
            old = buf[y, x]
            new = 1.0 if old >= 0.5 else 0.0
            out[y, x] = new > 0
            err = old - new
            for dx, dy, k in ((fwd, 0, 7 / 16), (-fwd, 1, 3 / 16),
                              (0, 1, 5 / 16), (fwd, 1, 1 / 16)):
                nx, ny = x + dx, y + dy
                if 0 <= nx < w and 0 <= ny < h:
                    if mask is not None and not mask[ny, nx]:
                        continue          # hard clear at the mask edge
                    buf[ny, nx] += err * k
    return out


def _fit_gamma(density, mask, target):
    """Find the tone curve that lands the dot count on target."""
    lo, hi = 0.15, 24.0
    for _ in range(40):
        mid = (lo + hi) / 2
        n = np.clip(density, 0, 1) ** mid
        if mask is not None:
            n = n * mask
        if n.sum() > target:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def build(mode, target=None, photo="source-photo.jpg"):
    """Return (ink, mask, stats) for 'dark' or 'light'."""
    target = TARGET_DOTS[mode] if target is None else target
    src = Image.open(os.path.join(HERE, photo)).convert("RGB")
    crop = src.crop(CROP).resize((GRID_W, GRID_H), Image.LANCZOS)
    rgb = np.asarray(crop)
    gray = _prepared_gray(crop)
    mask = subject_mask(rgb)

    if mode == "dark":
        # Light dots on a dark panel: ink follows the *lit* part of the sitter.
        # Drawing ink at dark pixels here is exactly what makes dark mode read
        # as a photo negative.
        density, use_mask = gray, mask
    else:
        # Dark dots on a light panel: ink follows the dark part of the photo,
        # backdrop included.
        density, use_mask = 1.0 - gray, None

    gamma = _fit_gamma(density, use_mask, target)
    shaped = np.clip(density, 0, 1) ** gamma
    ink = dither(shaped, use_mask)

    stats = {
        "mode": mode,
        "gamma": round(gamma, 4),
        "dots": int(ink.sum()),
        "subject_fraction": round(float(mask.mean()), 4),
        "ink_fraction": round(float(ink.mean()), 4),
    }
    return ink, mask, stats


def runs(ink):
    """Horizontal runs of ink as (x, y, length) in grid cells."""
    out = []
    h, w = ink.shape
    for y in range(h):
        row = ink[y]
        x = 0
        while x < w:
            if row[x]:
                s = x
                while x < w and row[x]:
                    x += 1
                out.append((s, y, x - s))
            else:
                x += 1
    return out


if __name__ == "__main__":
    os.makedirs(os.path.join(HERE, "_debug"), exist_ok=True)
    for mode in ("dark", "light"):
        ink, mask, stats = build(mode)
        print(stats, "runs:", len(runs(ink)))
        img = np.where(ink, 0, 255).astype(np.uint8) if mode == "light" \
            else np.where(ink, 255, 0).astype(np.uint8)
        Image.fromarray(img).resize((GRID_W * 2, GRID_H * 2), Image.NEAREST).save(
            os.path.join(HERE, "_debug", "portrait_%s.png" % mode))
