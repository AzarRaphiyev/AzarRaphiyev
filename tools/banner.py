"""Assemble the animated banner SVGs from the dithered portrait + logo clouds.

Run:  python banner.py
Out:  assets/banner-dark.svg, assets/banner-light.svg, tools/_data/*.npy
"""
import os

import numpy as np
from scipy.cluster.vq import kmeans2
from scipy.optimize import linear_sum_assignment

import logos
import portrait
from profile_data import HANDLE, PALETTE, ROWS, TITLE

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(os.path.dirname(HERE), "assets")
DATA = os.path.join(HERE, "_data")

# ---------------------------------------------------------------- canvas ----
W, H = 1180, 610
BAR = 40                      # title bar height
FRAME = (24, 66, 440, 522)    # portrait frame: x, y, w, h  (37.3% of width)
PAD = 14
GRID_W, GRID_H = portrait.GRID_W, portrait.GRID_H
CELL = 1.37
PX = FRAME[0] + PAD + (FRAME[2] - 2 * PAD - GRID_W * CELL) / 2.0
PY = FRAME[1] + PAD + (FRAME[3] - 2 * PAD - GRID_H * CELL) / 2.0

RX0, RX1 = 486, 1156          # info column
ADV = 0.6                     # monospace advance, in em

# ------------------------------------------------------------- animation ----
INTRO = 3.2                   # plays once
FADE_AT = 3.05                # intro -> loop crossfade
HOLD = 0.05                   # t=0 frame shows the finished portrait; see below
LOOP = 14.2
INTRO_GROUPS = 60
BANDS = 94
TRAVELLERS = 900
LOGO_SPAN = 155               # grid cells; drives how densely 900 dots read
DOT = 1.9                     # traveller dot size, grid cells
DRIFT = 0.42                  # fraction of the way to the logo centroid
NOISE = 4.0                   # per-dot jitter (grid cells) before grouping

# portrait 3.0 | 4 x 1.3 transitions | 3 x 2.0 logo holds  == 14.2s
_STOPS = [0.0, 3.0, 4.3, 6.3, 7.6, 9.6, 10.9, 12.9, 14.2]
KEYTIMES = [t / LOOP for t in _STOPS]


def _kt(values):
    return ";".join(("%.4g" % v).lstrip("0") if 0 < v < 1 else "%g" % v
                    for v in values)


KT = _kt(KEYTIMES)


# ------------------------------------------------------------------ dots ----
def capped_runs(ink, cap):
    """Horizontal ink runs, split so no run exceeds `cap` cells.

    Capping matters for the intro: a 40-cell run fading in as one unit reads as
    a horizontal streak, not as dots thickening.
    """
    out = []
    h, w = ink.shape
    for y in range(h):
        row = ink[y]
        x = 0
        while x < w:
            if not row[x]:
                x += 1
                continue
            s = x
            while x < w and row[x]:
                x += 1
            for a in range(s, x, cap):
                out.append((a, y, min(cap, x - a)))
    return out


def d_of(segs):
    """Run segments -> a single path `d`, in grid-cell units."""
    parts = []
    for x, y, n in segs:
        parts.append("M%d %dh%dv1h-%dz" % (x, y, n, n))
    return "".join(parts)


# --------------------------------------------------------------- metrics ----
def evenness(points, groups, n_groups, tiles=4):
    """Mean total-variation distance between each group's spatial spread and
    the whole portrait's. ~0 = scattered everywhere, ~0.7 = patchy."""
    tx = np.clip((points[:, 0] / GRID_W * tiles).astype(int), 0, tiles - 1)
    ty = np.clip((points[:, 1] / GRID_H * tiles).astype(int), 0, tiles - 1)
    tile = ty * tiles + tx
    glob = np.bincount(tile, minlength=tiles * tiles).astype(float)
    glob /= glob.sum()
    tot = 0.0
    for g in range(n_groups):
        sel = tile[groups == g]
        if len(sel) == 0:
            continue
        h = np.bincount(sel, minlength=tiles * tiles).astype(float)
        h /= h.sum()
        tot += 0.5 * np.abs(h - glob).sum()
    return tot / n_groups


def _grid_cells(shape):
    yy, xx = np.mgrid[0:shape[0], 0:shape[1]]
    return np.column_stack([xx.ravel() + 0.5, yy.ravel() + 0.5])


def straight_boundary(band):
    """Fraction of band-boundary edges that continue perfectly straight.

    Measured over the whole grid, not just inked cells: restricting it to ink
    makes the number track dot density instead of band geometry. Drift is a
    linear function of position, so quantising it *is* a square grid unless the
    assignment is jittered first -- axis-aligned tiles score near 1.0 here, an
    organic partition scores low.
    """
    total = matched = 0
    for b in (band, band.T):
        cur, nxt = b[:, :-1], b[:, 1:]
        edge = cur != nxt
        same = np.zeros_like(edge)
        same[1:] = edge[1:] & edge[:-1] & (cur[1:] == cur[:-1]) & (nxt[1:] == nxt[:-1])
        total += int(edge.sum())
        matched += int(same.sum())
    return matched / total if total else 0.0


# ------------------------------------------------------------------ text ----
def esc(s):
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def row_svg(label, value, y, p):
    """One info row: label, computed dotted leader, right-aligned value.

    textLength + lengthAdjust pins both ends regardless of which monospace font
    the visitor's browser actually resolves, so the leader never collides.
    """
    fs = 14
    lw = len(label) * fs * ADV
    vw = len(value) * fs * ADV
    x0 = RX0 + lw + 8
    x1 = RX1 - vw - 8

    out = [
        '<text x="%g" y="%g" class="lbl" textLength="%.1f" '
        'lengthAdjust="spacingAndGlyphs">%s</text>' % (RX0, y, lw, esc(label)),
        '<text x="%g" y="%g" class="val" text-anchor="end" textLength="%.1f" '
        'lengthAdjust="spacingAndGlyphs">%s</text>' % (RX1, y, vw, esc(value)),
    ]
    if x1 - x0 > 10:
        out.insert(1, '<line x1="%.1f" y1="%g" x2="%.1f" y2="%g" class="lead"/>'
                   % (x0, y - 4, x1, y - 4))
    return "".join(out)


def info_panel(p):
    parts = []
    y = 84
    parts.append('<text x="%g" y="%g" class="hdr">SYSTEM.INFO</text>' % (RX0, y))

    # Pulsing LIVE badge.
    parts.append(
        '<g><circle cx="%g" cy="%g" r="4" fill="#FF5F57">'
        '<animate attributeName="opacity" values="1;.2;1" dur="1.6s" '
        'repeatCount="indefinite"/></circle>'
        '<text x="%g" y="%g" class="live">LIVE</text></g>'
        % (RX1 - 44, y - 4, RX1, y)
    )

    # Handle pill.
    pill_w = (len(HANDLE) + 1) * 14 * ADV + 26
    parts.append(
        '<g><rect x="%g" y="%g" width="%.1f" height="26" rx="13" fill="%s" '
        'fill-opacity=".14" stroke="%s" stroke-opacity=".5"/>'
        '<text x="%g" y="%g" class="pill" textLength="%.1f" '
        'lengthAdjust="spacingAndGlyphs">@%s</text></g>'
        % (RX0, 100, pill_w, p["accent"], p["accent"],
           RX0 + 13, 118, (len(HANDLE) + 1) * 14 * ADV, esc(HANDLE))
    )

    y = 160
    for gi, group in enumerate(ROWS):
        if gi:
            parts.append('<line x1="%g" y1="%g" x2="%g" y2="%g" class="rule"/>'
                         % (RX0, y - 20, RX1, y - 20))
        for label, value in group:
            parts.append(row_svg(label, value, y, p))
            y += 23
        y += 16

    parts.append('<line x1="%g" y1="540" x2="%g" y2="540" class="rule"/>'
                 % (RX0, RX1))
    parts.append('<text x="%g" y="562" class="prompt">&gt; ready</text>' % RX0)
    parts.append(
        '<rect x="%g" y="551" width="8" height="14" fill="%s" fill-opacity=".7">'
        '<animate attributeName="opacity" values="1;1;0;0" keyTimes="0;.5;.5;1" '
        'dur="1.1s" repeatCount="indefinite"/></rect>'
        % (RX0 + 8 * 14 * ADV + 6, p["chrome"])
    )
    return "".join(parts)


# ----------------------------------------------------------------- build ----
def build(mode, rng):
    p = PALETTE[mode]
    ink, mask, stats = portrait.build(mode)

    # ---- intro layer: ~60 randomly interleaved groups -----------------------
    intro_segs = capped_runs(ink, 3)
    seg_pts = np.array([[x + n / 2.0, y + 0.5] for x, y, n in intro_segs])
    intro_g = rng.integers(0, INTRO_GROUPS, len(intro_segs))

    ev_random = evenness(seg_pts, intro_g, INTRO_GROUPS)
    # Control: the spatial grouping the brief warns against.
    ctrl = np.clip((seg_pts[:, 1] / GRID_H * INTRO_GROUPS).astype(int),
                   0, INTRO_GROUPS - 1)
    ev_spatial = evenness(seg_pts, ctrl, INTRO_GROUPS)

    # ---- loop layer: ~94 drift bands ---------------------------------------
    loop_segs = capped_runs(ink, 6)
    loop_pts = np.array([[x + n / 2.0, y + 0.5] for x, y, n in loop_segs])

    jitter = loop_pts + rng.normal(0, NOISE, loop_pts.shape)
    cent, band = kmeans2(jitter, BANDS, minit="++", seed=7, iter=24)
    cent_clean, _ = kmeans2(loop_pts, BANDS, minit="++", seed=7, iter=24)

    def nearest(pts, centroids):
        d = ((pts[:, None, :] - centroids[None, :, :]) ** 2).sum(-1)
        return d.argmin(1)

    cells = _grid_cells(ink.shape)
    shipped = nearest(cells + rng.normal(0, NOISE, cells.shape), cent)
    nonoise = nearest(cells, cent_clean)
    # The trap, built deliberately as a control: drift is linear in position, so
    # quantising it directly hands you axis-aligned tiles and a blocky dissolve.
    nx, ny = 10, 10
    gridtrap = (np.clip((cells[:, 0] / GRID_W * nx).astype(int), 0, nx - 1) * ny
                + np.clip((cells[:, 1] / GRID_H * ny).astype(int), 0, ny - 1))

    sb_noisy = straight_boundary(shipped.reshape(ink.shape))
    sb_clean = straight_boundary(nonoise.reshape(ink.shape))
    sb_grid = straight_boundary(gridtrap.reshape(ink.shape))

    # ---- logo clouds + optimal-transport chain ------------------------------
    clouds = logos.logo_clouds(TRAVELLERS, GRID_W, GRID_H, span=LOGO_SPAN, rng=rng)
    logo_c = clouds[0].mean(axis=0)

    # Ink coverage per logo: 900 dots spread over too wide a span stop reading
    # as a shape at all. ~0.09 was a loose haze; ~0.20 holds the silhouette.
    coverage = []
    for cloud in clouds:
        lo, hi = cloud.min(axis=0), cloud.max(axis=0)
        coverage.append(TRAVELLERS * DOT * DOT / float((hi - lo).prod()))

    # Seed the travellers from the portrait itself so they emerge out of it.
    pick = rng.choice(len(loop_pts), TRAVELLERS, replace=False)
    seed = loop_pts[pick]

    chain = [seed]
    for nxt in clouds:
        prev = chain[-1]
        cost = ((prev[:, None, :] - nxt[None, :, :]) ** 2).sum(-1)
        _, col = linear_sum_assignment(cost)
        chain.append(nxt[col])

    legs = chain + [seed]  # closes the loop back into the portrait
    ot_len = float(np.mean([np.linalg.norm(legs[i + 1] - legs[i], axis=1).mean()
                            for i in range(len(legs) - 1)]))

    # One position per keyTime: hold, travel, hold, travel, ... back to the face.
    waypoints = [chain[0], chain[0], chain[1], chain[1],
                 chain[2], chain[2], chain[3], chain[3], chain[0]]
    assert len(waypoints) == len(KEYTIMES)

    # ---- emit ---------------------------------------------------------------
    svg = []
    A = svg.append
    A('<svg xmlns="http://www.w3.org/2000/svg" '
      'xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 %d %d" '
      'width="%d" height="%d" role="img" aria-label="%s - Full-Stack Developer">'
      % (W, H, W, H, esc("Azar Rafiyev")))
    A('<title>Azar Rafiyev &#183; Full-Stack Developer</title>')
    A('<style>'
      'text{font-family:ui-monospace,SFMono-Regular,"SF Mono",Menlo,Consolas,'
      '"Liberation Mono",monospace;dominant-baseline:middle}'
      '.hdr{font-size:13px;letter-spacing:2.4px;fill:%(chrome)s}'
      '.live{font-size:12px;letter-spacing:1.6px;fill:#FF5F57;text-anchor:end}'
      '.pill{font-size:14px;fill:%(accent)s}'
      '.lbl{font-size:14px;fill:%(dim)s}'
      '.val{font-size:14px;fill:%(text)s}'
      '.tit{font-size:13px;fill:%(dim)s;text-anchor:middle}'
      '.cap{font-size:13px;letter-spacing:2.4px;fill:%(chrome)s}'
      '.prompt{font-size:13px;fill:%(dim)s}'
      '.lead{stroke:%(rule)s;stroke-width:1;stroke-dasharray:1 4}'
      '.rule{stroke:%(rule)s;stroke-width:1}'
      '</style>' % p)
    A('<defs><path id="t" d="M%g %gh%gv%gh-%gz"/></defs>'
      % (-DOT / 2, -DOT / 2, DOT, DOT, DOT))

    # window chrome
    A('<rect width="%d" height="%d" rx="14" fill="%s"/>' % (W, H, p["bg"]))
    A('<rect width="%d" height="%d" rx="14" fill="none" stroke="%s" '
      'stroke-opacity=".35"/>' % (W, H, p["rule"]))
    A('<line x1="0" y1="%d" x2="%d" y2="%d" class="rule"/>' % (BAR, W, BAR))
    for i, c in enumerate(("#FF5F57", "#FEBC2E", "#28C840")):
        A('<circle cx="%d" cy="%d" r="6" fill="%s"/>' % (26 + i * 20, BAR / 2, c))
    A('<text x="%d" y="%d" class="tit">%s</text>' % (W / 2, BAR / 2, esc(TITLE)))

    # portrait frame
    A('<text x="%d" y="56" class="cap">VISUAL.MAP</text>' % FRAME[0])
    A('<rect x="%d" y="%d" width="%d" height="%d" rx="10" fill="%s" '
      'stroke="%s" stroke-opacity=".55"/>'
      % (FRAME[0], FRAME[1], FRAME[2], FRAME[3], p["panel"], p["rule"]))

    A('<g transform="translate(%.2f,%.2f) scale(%g)" shape-rendering="crispEdges">'
      % (PX, PY, CELL))

    # intro: every group fades in somewhere different, all over the portrait
    A('<g fill="%s"><animate attributeName="opacity" values="1;0" '
      'begin="%gs" dur="0.15s" fill="freeze"/>' % (p["portrait"], FADE_AT))
    for g in range(INTRO_GROUPS):
        segs = [intro_segs[i] for i in np.nonzero(intro_g == g)[0]]
        if not segs:
            continue
        begin = 2.0 * g / INTRO_GROUPS
        A('<path opacity="0" d="%s"><animate attributeName="opacity" '
          'values="0;1" begin="%.3fs" dur="0.55s" fill="freeze"/></path>'
          % (d_of(segs), begin))
    A('</g>')

    # Loop layer. The opacity *attribute* is 1 and the animation that hides it
    # for the intro starts a beat late, at HOLD.
    #
    # That 50ms matters. Renderers that rasterise an SVG at animation time zero
    # -- which is how <img>-embedded SVG behaves in several contexts, and <img>
    # is exactly how GitHub renders a README banner -- take the attribute value.
    # With this group starting at opacity="0" the portrait frame came out blank
    # on the live profile page. Now t=0 is the finished portrait and the whole
    # animation is an enhancement on top of a banner that is already correct.
    A('<g fill="%s" opacity="1"><animate attributeName="opacity" values="0;0;1" '
      'keyTimes="0;%.4f;1" dur="%gs" begin="%gs" fill="freeze"/>'
      % (p["portrait"], (FADE_AT - HOLD) / (INTRO - HOLD), INTRO - HOLD, HOLD))
    for g in range(BANDS):
        idx = np.nonzero(band == g)[0]
        if not len(idx):
            continue
        segs = [loop_segs[i] for i in idx]
        c = loop_pts[idx].mean(axis=0)
        dx = (logo_c[0] - c[0]) * DRIFT
        dy = (logo_c[1] - c[1]) * DRIFT
        # Stagger so the bands do not leave as one slab.
        s = (g % 7) * 0.006
        kt = _kt([0, KEYTIMES[1] + s, KEYTIMES[2] + s,
                  KEYTIMES[7] - s, KEYTIMES[8]])
        A('<g><animateTransform attributeName="transform" type="translate" '
          'values="0 0;0 0;%.1f %.1f;%.1f %.1f;0 0" keyTimes="%s" dur="%gs" '
          'begin="%gs" repeatCount="indefinite"/>'
          '<animate attributeName="opacity" values="1;1;0;0;1" keyTimes="%s" '
          'dur="%gs" begin="%gs" repeatCount="indefinite"/>'
          '<path d="%s"/></g>'
          % (dx, dy, dx, dy, kt, LOOP, INTRO, kt, LOOP, INTRO, d_of(segs)))
    A('</g>')

    # travellers: one opacity animation for the whole swarm, positions per dot
    A('<g fill="%s" opacity="0"><animate attributeName="opacity" '
      'values="0;0;1;1;1;1;1;1;0" keyTimes="%s" dur="%gs" begin="%gs" '
      'repeatCount="indefinite"/>' % (p["accent"], KT, LOOP, INTRO))
    for i in range(TRAVELLERS):
        vals = ";".join("%.1f %.1f" % (w[i][0], w[i][1]) for w in waypoints)
        A('<use xlink:href="#t"><animateTransform attributeName="transform" '
          'type="translate" values="%s" keyTimes="%s" dur="%gs" begin="%gs" '
          'repeatCount="indefinite"/></use>' % (vals, KT, LOOP, INTRO))
    A('</g></g>')

    A(info_panel(p))
    A('</svg>')

    out = os.path.join(OUT, "banner-%s.svg" % mode)
    with open(out, "w", encoding="utf-8") as f:
        f.write("".join(svg))

    stats.update({
        "file": os.path.basename(out),
        "kb": round(os.path.getsize(out) / 1024.0, 1),
        "intro_segments": len(intro_segs),
        "loop_segments": len(loop_segs),
        "evenness_random": round(ev_random, 4),
        "evenness_spatial_control": round(ev_spatial, 4),
        "straight_boundary_shipped": round(sb_noisy, 4),
        "straight_boundary_kmeans_nonoise": round(sb_clean, 4),
        "straight_boundary_gridtrap_control": round(sb_grid, 4),
        "ot_mean_leg_cells": round(ot_len, 2),
        "logo_ink_coverage": [round(c, 3) for c in coverage],
    })
    np.save(os.path.join(DATA, "ink_%s.npy" % mode), ink)
    np.save(os.path.join(DATA, "mask_%s.npy" % mode), mask)
    np.save(os.path.join(DATA, "chain_%s.npy" % mode), np.stack(chain))
    return stats


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(DATA, exist_ok=True)
    for mode in ("dark", "light"):
        s = build(mode, np.random.default_rng(11))
        for k, v in s.items():
            print("  %-34s %s" % (k, v))
        print()
