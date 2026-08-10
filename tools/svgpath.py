"""Minimal SVG path parser -> flattened polygons.

svgpathtools chokes on the compact number packing simple-icons uses
("1.7474s.012" and friends), so the subset we actually need is parsed here.
Supports M/m L/l H/h V/v C/c S/s Q/q T/t A/a Z/z.
"""
import math
import re

_NUM = re.compile(r"[-+]?(?:\d*\.\d+(?:[eE][-+]?\d+)?|\d+\.?(?:[eE][-+]?\d+)?)")
_CMD = re.compile(r"[MmLlHhVvCcSsQqTtAaZz]")

_ARGC = {"M": 2, "L": 2, "H": 1, "V": 1, "C": 6, "S": 4, "Q": 4, "T": 2, "A": 7, "Z": 0}


def _tokenize(d):
    """Yield (command_letter, [floats]) with implicit-repeat expanded."""
    i, n = 0, len(d)
    cmd = None
    while i < n:
        ch = d[i]
        if ch in " ,\t\r\n":
            i += 1
            continue
        if _CMD.match(ch):
            cmd = ch
            i += 1
            if cmd in "Zz":
                yield "Z", []
                cmd = None
            continue
        if cmd is None:
            raise ValueError("number before any command at %d" % i)

        want = _ARGC[cmd.upper()]
        args = []
        while len(args) < want:
            while i < n and d[i] in " ,\t\r\n":
                i += 1
            # Arc flags are single digits and may be packed without separators.
            if cmd in "Aa" and len(args) in (3, 4):
                args.append(float(d[i]))
                i += 1
                continue
            m = _NUM.match(d, i)
            if not m:
                raise ValueError("expected number at %d in %r" % (i, d[i:i + 12]))
            args.append(float(m.group()))
            i = m.end()
        yield cmd, args
        # An implicit repeat of M is L (m -> l).
        if cmd == "M":
            cmd = "L"
        elif cmd == "m":
            cmd = "l"


def _cubic(p0, p1, p2, p3, steps):
    out = []
    for k in range(1, steps + 1):
        t = k / steps
        u = 1 - t
        x = u**3 * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t**3 * p3[0]
        y = u**3 * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t**3 * p3[1]
        out.append((x, y))
    return out


def _arc(p0, rx, ry, phi_deg, large, sweep, p1, steps):
    """Endpoint -> centre parameterisation, per the SVG spec appendix."""
    if p0 == p1:
        return []
    rx, ry = abs(rx), abs(ry)
    if rx == 0 or ry == 0:
        return [p1]

    phi = math.radians(phi_deg)
    cos_p, sin_p = math.cos(phi), math.sin(phi)
    dx2, dy2 = (p0[0] - p1[0]) / 2.0, (p0[1] - p1[1]) / 2.0
    x1 = cos_p * dx2 + sin_p * dy2
    y1 = -sin_p * dx2 + cos_p * dy2

    lam = (x1 * x1) / (rx * rx) + (y1 * y1) / (ry * ry)
    if lam > 1:
        s = math.sqrt(lam)
        rx, ry = rx * s, ry * s

    num = rx * rx * ry * ry - rx * rx * y1 * y1 - ry * ry * x1 * x1
    den = rx * rx * y1 * y1 + ry * ry * x1 * x1
    co = math.sqrt(max(0.0, num / den)) if den else 0.0
    if large == sweep:
        co = -co
    cx1 = co * rx * y1 / ry
    cy1 = -co * ry * x1 / rx
    cx = cos_p * cx1 - sin_p * cy1 + (p0[0] + p1[0]) / 2.0
    cy = sin_p * cx1 + cos_p * cy1 + (p0[1] + p1[1]) / 2.0

    def ang(ux, uy, vx, vy):
        d = math.hypot(ux, uy) * math.hypot(vx, vy)
        c = max(-1.0, min(1.0, (ux * vx + uy * vy) / d)) if d else 1.0
        a = math.acos(c)
        return -a if ux * vy - uy * vx < 0 else a

    th0 = ang(1, 0, (x1 - cx1) / rx, (y1 - cy1) / ry)
    dth = ang((x1 - cx1) / rx, (y1 - cy1) / ry, (-x1 - cx1) / rx, (-y1 - cy1) / ry)
    if not sweep and dth > 0:
        dth -= 2 * math.pi
    elif sweep and dth < 0:
        dth += 2 * math.pi

    out = []
    for k in range(1, steps + 1):
        th = th0 + dth * k / steps
        x = cos_p * rx * math.cos(th) - sin_p * ry * math.sin(th) + cx
        y = sin_p * rx * math.cos(th) + cos_p * ry * math.sin(th) + cy
        out.append((x, y))
    return out


def flatten(d, curve_steps=16, arc_steps=24):
    """Return a list of closed polygons (each a list of (x, y))."""
    polys, cur = [], []
    cx = cy = sx = sy = 0.0
    prev_ctrl = None
    prev_cmd = ""

    def close():
        nonlocal cur
        if len(cur) > 2:
            polys.append(cur)
        cur = []

    for cmd, a in _tokenize(d):
        rel = cmd.islower()
        up = cmd.upper()

        if up == "Z":
            if cur:
                cur.append((sx, sy))
            close()
            cx, cy = sx, sy
        elif up == "M":
            close()
            cx, cy = (cx + a[0], cy + a[1]) if rel else (a[0], a[1])
            sx, sy = cx, cy
            cur = [(cx, cy)]
        elif up == "L":
            cx, cy = (cx + a[0], cy + a[1]) if rel else (a[0], a[1])
            cur.append((cx, cy))
        elif up == "H":
            cx = cx + a[0] if rel else a[0]
            cur.append((cx, cy))
        elif up == "V":
            cy = cy + a[0] if rel else a[0]
            cur.append((cx, cy))
        elif up in ("C", "S"):
            if up == "C":
                p1 = (cx + a[0], cy + a[1]) if rel else (a[0], a[1])
                p2 = (cx + a[2], cy + a[3]) if rel else (a[2], a[3])
                p3 = (cx + a[4], cy + a[5]) if rel else (a[4], a[5])
            else:
                if prev_cmd in ("C", "S") and prev_ctrl is not None:
                    p1 = (2 * cx - prev_ctrl[0], 2 * cy - prev_ctrl[1])
                else:
                    p1 = (cx, cy)
                p2 = (cx + a[0], cy + a[1]) if rel else (a[0], a[1])
                p3 = (cx + a[2], cy + a[3]) if rel else (a[2], a[3])
            cur.extend(_cubic((cx, cy), p1, p2, p3, curve_steps))
            prev_ctrl = p2
            cx, cy = p3
        elif up in ("Q", "T"):
            if up == "Q":
                q = (cx + a[0], cy + a[1]) if rel else (a[0], a[1])
                p3 = (cx + a[2], cy + a[3]) if rel else (a[2], a[3])
            else:
                if prev_cmd in ("Q", "T") and prev_ctrl is not None:
                    q = (2 * cx - prev_ctrl[0], 2 * cy - prev_ctrl[1])
                else:
                    q = (cx, cy)
                p3 = (cx + a[0], cy + a[1]) if rel else (a[0], a[1])
            # Quadratic -> cubic.
            p1 = (cx + 2.0 / 3 * (q[0] - cx), cy + 2.0 / 3 * (q[1] - cy))
            p2 = (p3[0] + 2.0 / 3 * (q[0] - p3[0]), p3[1] + 2.0 / 3 * (q[1] - p3[1]))
            cur.extend(_cubic((cx, cy), p1, p2, p3, curve_steps))
            prev_ctrl = q
            cx, cy = p3
        elif up == "A":
            p1 = (cx + a[5], cy + a[6]) if rel else (a[5], a[6])
            cur.extend(_arc((cx, cy), a[0], a[1], a[2], int(a[3]), int(a[4]),
                            p1, arc_steps))
            cx, cy = p1
            prev_ctrl = None

        if up not in ("C", "S", "Q", "T"):
            prev_ctrl = None
        prev_cmd = up

    close()
    return polys
