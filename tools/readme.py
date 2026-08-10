"""Generate README.md. Every URL is computed here -- never hand-edit the output."""
import base64
import os
import urllib.parse

from simpleicons.all import icons

from profile_data import HANDLE, PALETTE

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

REPO = "%s/%s" % (HANDLE, HANDLE)
RAW = "https://raw.githubusercontent.com/%s" % REPO
D, L = PALETTE["dark"], PALETTE["light"]

# Swap this for a self-hosted fork once Vercel is deployed -- see README-SETUP.md.
# The shared public instance is what returns "API rate limit exceeded".
STATS_HOST = "https://github-readme-stats.vercel.app"

LINKS = {
    "LinkedIn": "https://www.linkedin.com/in/azer-rafiyev",
    "Portfolio": "https://raphiyev.vercel.app",
    "Gmail": "mailto:raphiyev@gmail.com",
}


def hexes(pal):
    return {k: v.lstrip("#") for k, v in pal.items()}


def stats_url(pal, path="api", **extra):
    p = hexes(pal)
    q = {
        "username": HANDLE,
        "hide_border": "true",
        "border_radius": "14",
        "bg_color": p["bg"],
        "title_color": p["chrome"],
        "text_color": p["text"],
        "icon_color": p["portrait"],
    }
    q.update(extra)
    return "%s/%s?%s" % (STATS_HOST, path, urllib.parse.urlencode(q))


def streak_url(pal):
    p = hexes(pal)
    q = {
        "user": HANDLE,
        "hide_border": "true",
        "border_radius": "14",
        "background": p["bg"],
        "stroke": p["rule"],
        "ring": p["portrait"],
        "fire": p["accent"],
        "currStreakNum": p["text"],
        "sideNums": p["text"],
        "currStreakLabel": p["chrome"],
        "sideLabels": p["chrome"],
        "dates": p["dim"],
    }
    return "https://streak-stats.demolab.com?" + urllib.parse.urlencode(q)


def badge(label, slug, pal, embed=False):
    """shields.io badge in the profile background colour.

    LinkedIn's named logo only renders on its brand blue #0A66C2 -- on any
    custom colour the glyph silently vanishes and you are left with bare text
    (measured: no <image> element in the response). Embedding the same official
    glyph as a base64 data-URI keeps it themed.
    """
    p = hexes(pal)
    if embed:
        svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
               'fill="#%s"><path d="%s"/></svg>' % (p["portrait"], icons.get(slug).path))
        logo = "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()
        q = "style=for-the-badge&logo=" + urllib.parse.quote(logo, safe="")
    else:
        q = "style=for-the-badge&logo=%s&logoColor=%s" % (slug, p["portrait"])
    return "https://img.shields.io/badge/%s-%s?%s" % (label, p["bg"], q)


def picture(dark, light, alt, width=None):
    w = ' width="%s"' % width if width else ""
    return (
        '<picture>\n'
        '  <source media="(prefers-color-scheme: dark)" srcset="%s" />\n'
        '  <source media="(prefers-color-scheme: light)" srcset="%s" />\n'
        '  <img alt="%s" src="%s"%s />\n'
        '</picture>' % (dark, light, alt, dark, w)
    )


def build():
    out = ['<div align="center">', ""]

    # --- banner ------------------------------------------------------------
    out += [picture("%s/main/assets/banner-dark.svg" % RAW,
                    "%s/main/assets/banner-light.svg" % RAW,
                    "Azar Rafiyev - Full-Stack Developer", width="100%"), "", "<br />", ""]

    # --- stats -------------------------------------------------------------
    out += [picture(streak_url(D), streak_url(L), "GitHub streak", width="100%"), ""]

    # The two github-readme-stats cards stay commented out until STATS_HOST
    # points at a self-hosted fork. The shared public instance is not merely
    # rate-limited -- as of this build it answers 503 DEPLOYMENT_PAUSED, so the
    # cards render as broken-image alt text. See SETUP.md step 3.
    #
    # hide_rank=true: the rank is stars-weighted, so a newer account with real
    # work in coursework and client repos gets scored as if it had shipped
    # nothing. The contribution counts are the honest part of that card.
    out += [
        "<!-- STATS: uncomment once STATS_HOST in tools/readme.py points at your",
        "     own Vercel instance and you have re-run `python tools/readme.py`. -->",
        "<!--",
        picture(stats_url(D, show_icons="true", hide_rank="true"),
                stats_url(L, show_icons="true", hide_rank="true"),
                "GitHub stats", width="49%"),
        picture(stats_url(D, path="api/top-langs", layout="compact", langs_count="8"),
                stats_url(L, path="api/top-langs", layout="compact", langs_count="8"),
                "Top languages", width="49%"),
        "-->",
        "",
        "<br />",
        "",
    ]

    # --- snake --------------------------------------------------------------
    # Live: the `output` branch exists and both SVGs return 200. Do not enable
    # this before the Action has run green -- the branch does not exist until
    # then, and GitHub caches the 404 for hours.
    out += [picture("%s/output/snake-dark.svg" % RAW,
                    "%s/output/snake-light.svg" % RAW,
                    "Contribution snake", width="100%"), "", "<br />", ""]

    # --- badges ------------------------------------------------------------
    parts = [
        '<a href="%s"><img src="%s" alt="LinkedIn" /></a>'
        % (LINKS["LinkedIn"], badge("LinkedIn", "linkedin", D, embed=True)),
        '<a href="%s"><img src="%s" alt="Portfolio" /></a>'
        % (LINKS["Portfolio"], badge("Portfolio", "vercel", D)),
        '<a href="%s"><img src="%s" alt="Email" /></a>'
        % (LINKS["Gmail"], badge("Gmail", "gmail", D)),
    ]
    out += ["&nbsp;&nbsp;\n".join(parts), "", "</div>", ""]

    text = "\n".join(out)
    with open(os.path.join(ROOT, "README.md"), "w", encoding="utf-8") as f:
        f.write(text)
    return text


if __name__ == "__main__":
    t = build()
    print(t)
    print("\n--- %d bytes" % len(t.encode()))
