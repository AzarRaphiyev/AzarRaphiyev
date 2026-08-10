"""Exploration: find a background-segmentation rule for the source photo.

Writes candidate masks to tools/_debug/ so they can be inspected by eye before
the real pipeline commits to one.
"""
import os

import numpy as np
from PIL import Image
from scipy import ndimage

HERE = os.path.dirname(os.path.abspath(__file__))
DEBUG = os.path.join(HERE, "_debug")
os.makedirs(DEBUG, exist_ok=True)

# Head-and-shoulders crop, aspect-matched to the 300x340 dot grid (0.882 w:h).
CROP = (93, 55, 344, 340)  # left, top, right, bottom

src = Image.open(os.path.join(HERE, "source-photo.jpg")).convert("RGB")
print("source:", src.size)

crop = src.crop(CROP)
print("crop:", crop.size, "aspect", crop.size[0] / crop.size[1], "target", 300 / 340)
crop.save(os.path.join(DEBUG, "crop.png"))

grid = crop.resize((300, 340), Image.LANCZOS)
grid.save(os.path.join(DEBUG, "grid.png"))

arr = np.asarray(grid).astype(np.float32)

# The backdrop is a teal wall. Sample it from the top-left / top-right corners,
# which are wall in every plausible crop.
corners = np.concatenate([
    arr[0:40, 0:40].reshape(-1, 3),
    arr[0:40, -40:].reshape(-1, 3),
])
bg = np.median(corners, axis=0)
print("estimated bg rgb:", bg)

# A flat RGB distance drowns in the vignette (corners are the same hue, much
# darker). Normalise each pixel by its own brightness first so the test is on
# hue/chroma, not exposure.
def chroma(a):
    lum = a.sum(axis=-1, keepdims=True) + 1e-6
    return a / lum

cd = np.linalg.norm(chroma(arr) - chroma(bg[None, None, :]), axis=-1)
print("chroma distance: min %.4f max %.4f mean %.4f" % (cd.min(), cd.max(), cd.mean()))

for thr in (0.02, 0.03, 0.04, 0.05, 0.06, 0.08):
    m = cd > thr
    print("thr %.3f -> subject fraction %.3f" % (thr, m.mean()))
    Image.fromarray((m * 255).astype(np.uint8)).save(
        os.path.join(DEBUG, "mask_raw_%.3f.png" % thr)
    )

# Clean-up pass on the most promising threshold.
for thr in (0.03, 0.04, 0.05):
    m = cd > thr
    m = ndimage.binary_closing(m, structure=np.ones((7, 7)))
    m = ndimage.binary_fill_holes(m)
    lab, n = ndimage.label(m)
    if n:
        sizes = ndimage.sum(m, lab, range(1, n + 1))
        m = lab == (int(np.argmax(sizes)) + 1)
    m = ndimage.binary_opening(m, structure=np.ones((3, 3)))
    print("thr %.3f cleaned -> subject fraction %.3f (%d components)" % (thr, m.mean(), n))
    Image.fromarray((m * 255).astype(np.uint8)).save(
        os.path.join(DEBUG, "mask_clean_%.3f.png" % thr)
    )
