"""Trace the three brand logos from their official simple-icons path data.

Nothing here is hand-drawn: the outlines come straight out of the simple-icons
package (24x24 viewBox), get flattened to polygons, rasterised, and then
stratified-sampled into an even point cloud.
"""
import numpy as np
from matplotlib.path import Path as MplPath
from simpleicons.all import icons

import svgpath

LOGOS = ["nextdotjs", "nestjs", "postgresql"]


def _mpl_path(d):
    """Flatten an SVG path string into a matplotlib compound Path."""
    verts, codes = [], []
    for poly in svgpath.flatten(d):
        verts.append(poly[0])
        codes.append(MplPath.MOVETO)
        for p in poly[1:]:
            verts.append(p)
            codes.append(MplPath.LINETO)
        codes[-1] = MplPath.CLOSEPOLY
    return MplPath(np.asarray(verts), np.asarray(codes))


def rasterise(slug, res=360):
    """Return a boolean (res, res) mask of the filled logo."""
    icon = icons.get(slug)
    if icon is None:
        raise KeyError(slug)
    path = _mpl_path(icon.path)
    # simple-icons paths live in a 0..24 viewBox.
    step = 24.0 / res
    ys, xs = np.mgrid[0:res, 0:res]
    pts = np.column_stack([
        (xs.ravel() + 0.5) * step,
        (ys.ravel() + 0.5) * step,
    ])
    inside = path.contains_points(pts).reshape(res, res)
    return inside


def sample_points(mask, count, rng):
    """Stratified jittered sample of `count` points from a boolean mask.

    Jittered-grid rather than uniform-random: a uniform draw clumps, and clumps
    read as noise once the dots are only ~1.6px across.
    """
    res = mask.shape[0]
    area = int(mask.sum())
    spacing = np.sqrt(area / float(count))

    pts = []
    n = int(np.ceil(res / spacing))
    for gy in range(n):
        for gx in range(n):
            for _ in range(4):  # a few jitter attempts per stratum
                x = (gx + rng.random()) * spacing
                y = (gy + rng.random()) * spacing
                ix, iy = int(x), int(y)
                if 0 <= ix < res and 0 <= iy < res and mask[iy, ix]:
                    pts.append((x, y))
                    break
    pts = np.asarray(pts, dtype=np.float64)

    if len(pts) > count:
        pts = pts[rng.choice(len(pts), count, replace=False)]
    elif len(pts) < count:  # top up from anywhere inside
        iy, ix = np.nonzero(mask)
        extra = rng.choice(len(iy), count - len(pts), replace=False)
        top = np.column_stack([ix[extra] + rng.random(len(extra)),
                               iy[extra] + rng.random(len(extra))])
        pts = np.vstack([pts, top])
    return pts


def logo_clouds(count, grid_w, grid_h, span, rng):
    """Point clouds for every logo, mapped into portrait-grid coordinates.

    Each logo is scaled so its *own* bounding box fills `span`, which keeps the
    three shapes optically the same size instead of the same nominal size.
    """
    clouds = []
    for slug in LOGOS:
        mask = rasterise(slug)
        pts = sample_points(mask, count, rng)
        res = mask.shape[0]
        pts = pts / res  # -> 0..1

        lo, hi = pts.min(axis=0), pts.max(axis=0)
        extent = (hi - lo).max()
        pts = (pts - (lo + hi) / 2.0) / extent * span
        pts[:, 0] += grid_w / 2.0
        pts[:, 1] += grid_h / 2.0
        clouds.append(pts)
    return clouds
