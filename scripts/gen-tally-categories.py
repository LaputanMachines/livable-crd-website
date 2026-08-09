#!/usr/bin/env python3
"""Generate the topic-grid images for the Tally questionnaire.

Run from repo root:
    python3 scripts/gen-tally-categories.py                    -> categories.png
    python3 scripts/gen-tally-categories.py --set housekeeping -> housekeeping.png
Output: assets/tally/  (2800x800 for a two-row set, 2800x448 for one row)

An icon-and-label grid on the page background #faf9fc with Inky #220940
labels, sized 2x Tally's recommended 1400px in-form width; --width to change
it. Canvas height follows the row count, so every set shares one set of metrics.

`categories` is the ten graded topics, read from _data/subjects.yml so the
graphic and the scorecard can't drift apart. The other three have no entry
there and define their icons inline below: `housekeeping` is the internal
block (HK-01, HK-02), never scored, never published bar one answer; 
`info` is the pre-start briefing, and `conduct` summarises the code of
conduct page.

The icons need a *stroke* renderer, which gen-fb-banner.py's fill rasteriser
doesn't do: they're 24x24 Feather-style outlines (`stroke="currentColor"`,
round caps and joins) built from arcs and circles the fill parser doesn't
handle either. So this file carries its own small path parser (arcs and
circles included) and strokes the flattened polylines with Pillow at 4x,
then downsamples. Only the palette and the Lexend loader come from
gen-fb-banner.py.
"""
import argparse, importlib.util, math, os, re
import yaml
from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Every Tally asset lands here, separate from the site's own images.
OUT_DIR = os.path.join(ROOT, "assets", "tally")
os.makedirs(OUT_DIR, exist_ok=True)

# gen-fb-banner has a hyphen in its name, so it can't be imported by name.
_spec = importlib.util.spec_from_file_location(
    "gen_fb_banner", os.path.join(ROOT, "scripts", "gen-fb-banner.py"))
fb = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fb)

INKY = fb.INKY
LIVABLE = (0x5C, 0x18, 0xA4)          # $livable-purple
PAGE_BG = (0xFA, 0xF9, 0xFC)          # $color-bg in _sass/_variables.scss

ICON_DIR = os.path.join(fb.IMG, "icons")
SUBJECTS = os.path.join(ROOT, "_data", "subjects.yml")

# Questionnaire categories, in the order finalize.py ships them. Housekeeping
# is internal-only and has no subject entry, so it can't appear here by
# accident; every other name must resolve against subjects.yml.
CATEGORIES = ["General", "Walking", "Rolling & cycling", "Transit", "Housing",
              "Climate", "Arts", "Healthcare access", "Reconciliation",
              "Governance"]
LABELS = {"All categories / General": "General"}   # full name is too long to set

# The Housekeeping block: HK-01 and HK-02 in finalize.py. It's the internal
# category: neither question is graded, and only "why you're running" is ever
# published. It has no entry in subjects.yml and no icon in assets/images/icons,
# by design, so its icons are inline here rather than added to the site's set,
# where they'd read as scorecard topics.
HOUSEKEEPING = [
    ("Campaign viability",
     '<svg viewBox="0 0 24 24"><path d="M23 6l-9 9-5-5-8 8"/>'
     '<path d="M17 6h6v6"/></svg>'),
    ("Fundraising",
     '<svg viewBox="0 0 24 24"><path d="M12 1v22"/>'
     '<path d="M17.5 5H9.75a3.75 3.75 0 0 0 0 7.5h4.5a3.75 3.75 0 0 1 0 7.5H6"/></svg>'),
    ("Why you’re running",
     '<svg viewBox="0 0 24 24"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 '
     '2-2h14a2 2 0 0 1 2 2z"/><path d="M8 9h8M8 13h5"/></svg>'),
]

# The info page, distilled to the eight things a candidate needs to know before
# starting. Wording follows that page; QUESTION_COUNT is stated there too, so it
# has to be updated by hand when the shipping set changes size.
QUESTION_COUNT = 70
INFO = [
    ("%d questions" % QUESTION_COUNT,
     '<svg viewBox="0 0 24 24"><path d="M8 6h13M8 12h13M8 18h13"/>'
     '<path d="M3.5 6h.01M3.5 12h.01M3.5 18h.01"/></svg>'),
    ("Grouped by category",
     '<svg viewBox="0 0 24 24"><rect x="3" y="3" width="7" height="7" rx="1"/>'
     '<rect x="14" y="3" width="7" height="7" rx="1"/>'
     '<rect x="3" y="14" width="7" height="7" rx="1"/>'
     '<rect x="14" y="14" width="7" height="7" rx="1"/></svg>'),
    ("Every one optional",
     '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/>'
     '<path d="M8.5 12.5l2.5 2.5 4.5-5"/></svg>'),
    ("N/A or decline",
     '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/>'
     '<path d="M8 12h8"/></svg>'),
    ("Room to elaborate",
     '<svg viewBox="0 0 24 24"><path d="M12 20h9"/>'
     '<path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4z"/></svg>'),
    ("Saved as you go",
     '<svg viewBox="0 0 24 24"><path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11'
     'a2 2 0 0 1-2 2z"/><path d="M17 21v-8H7v8"/><path d="M7 3v5h8"/></svg>'),
    ("Grades with rationale",
     '<svg viewBox="0 0 24 24"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12'
     'a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/><path d="M16 13H8M16 17H8M10 9H8"/></svg>'),
    ("Answers published",
     '<svg viewBox="0 0 24 24"><path d="M1 12s4-7 11-7 11 7 11 7-4 7-11 7-11-7-11-7z"/>'
     '<circle cx="12" cy="12" r="3"/></svg>'),
]

# The code of conduct (/code-of-conduct/), reduced to the five things a
# candidate needs from it before they start typing. Three of the five are
# reassurances rather than prohibitions, in the same proportion the page gives
# them: the rule is easy to misread as a rule about opinions, and a graphic
# that led with the bans would invite exactly that reading.
#
# Labels are kept to ~16 characters. The renderer shrinks any label too wide for
# its column, so a long one here would render smaller than its neighbours and
# break the even type size every other set has. "Not graded" leans on the
# struck-through eye beside it to carry the unpublished half.
CONDUCT = [
    ("Disagree freely",
     '<svg viewBox="0 0 24 24"><path d="M14 9a2 2 0 0 1-2 2H6l-4 4V4a2 2 0 0 1 '
     '2-2h8a2 2 0 0 1 2 2z"/><path d="M18 9h2a2 2 0 0 1 2 2v11l-4-4h-6a2 2 0 0 '
     '1-2-2v-1"/></svg>'),
    ("Not the person",
     '<svg viewBox="0 0 24 24"><path d="M16 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>'
     '<circle cx="8.5" cy="7" r="4"/><path d="M18 8l5 5M23 8l-5 5"/></svg>'),
    ("Not graded",
     '<svg viewBox="0 0 24 24"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 '
     '0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 '
     '11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/>'
     '<path d="M1 1l22 22"/></svg>'),
    ("Chance to revise",
     '<svg viewBox="0 0 24 24"><path d="M1 4v6h6"/>'
     '<path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10"/></svg>'),
    ("You stay listed",
     '<svg viewBox="0 0 24 24"><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6'
     'a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/>'
     '<rect x="8" y="2" width="8" height="4" rx="1"/>'
     '<path d="M9 14l2 2 4-4"/></svg>'),
]

SETS = {"categories": 5, "housekeeping": 3, "info": 4, "conduct": 5}   # name -> columns

GW = 1400                             # design grid width; all dimensions are in these units
SS = 4                                # supersample factor, collapsed on the final resize


# ======================= stroked-SVG icon renderer =======================
def _cubic(p0, p1, p2, p3, n=16):
    return [(( 1-t)**3*p0[0] + 3*(1-t)**2*t*p1[0] + 3*(1-t)*t*t*p2[0] + t**3*p3[0],
             (1-t)**3*p0[1] + 3*(1-t)**2*t*p1[1] + 3*(1-t)*t*t*p2[1] + t**3*p3[1])
            for t in [i/n for i in range(1, n+1)]]


def _quad(p0, p1, p2, n=14):
    return [((1-t)**2*p0[0] + 2*(1-t)*t*p1[0] + t*t*p2[0],
             (1-t)**2*p0[1] + 2*(1-t)*t*p1[1] + t*t*p2[1])
            for t in [i/n for i in range(1, n+1)]]


def _arc(p0, rx, ry, phi_deg, large, sweep, p1, n=24):
    """SVG elliptical arc, endpoint -> centre parameterisation (F.6.5)."""
    (x1, y1), (x2, y2) = p0, p1
    if rx == 0 or ry == 0 or (x1, y1) == (x2, y2):
        return [p1]
    phi = math.radians(phi_deg)
    cos_p, sin_p = math.cos(phi), math.sin(phi)
    dx, dy = (x1 - x2) / 2, (y1 - y2) / 2
    x1p, y1p = cos_p*dx + sin_p*dy, -sin_p*dx + cos_p*dy
    rx, ry = abs(rx), abs(ry)
    lam = (x1p/rx)**2 + (y1p/ry)**2
    if lam > 1:
        rx, ry = rx*math.sqrt(lam), ry*math.sqrt(lam)
    num = rx*rx*ry*ry - rx*rx*y1p*y1p - ry*ry*x1p*x1p
    den = rx*rx*y1p*y1p + ry*ry*x1p*x1p
    co = math.sqrt(max(0.0, num/den)) * (-1 if large == sweep else 1)
    cxp, cyp = co*rx*y1p/ry, -co*ry*x1p/rx
    cx = cos_p*cxp - sin_p*cyp + (x1+x2)/2
    cy = sin_p*cxp + cos_p*cyp + (y1+y2)/2

    def ang(ux, uy, vx, vy):
        d = (math.hypot(ux, uy) * math.hypot(vx, vy)) or 1.0
        a = math.acos(max(-1.0, min(1.0, (ux*vx + uy*vy) / d)))
        return -a if ux*vy - uy*vx < 0 else a

    t1 = ang(1, 0, (x1p-cxp)/rx, (y1p-cyp)/ry)
    dt = ang((x1p-cxp)/rx, (y1p-cyp)/ry, (-x1p-cxp)/rx, (-y1p-cyp)/ry)
    if not sweep and dt > 0:
        dt -= 2*math.pi
    elif sweep and dt < 0:
        dt += 2*math.pi
    out = []
    for i in range(1, n+1):
        t = t1 + dt*i/n
        out.append((cos_p*rx*math.cos(t) - sin_p*ry*math.sin(t) + cx,
                    sin_p*rx*math.cos(t) + cos_p*ry*math.sin(t) + cy))
    return out


_TOK = re.compile(r'[MmLlHhVvCcSsQqTtAaZz]|[-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?')


def parse_path(d):
    """Flatten a path to [(points, closed)]. Feather subset, arcs included."""
    tk = _TOK.findall(d)
    subs, cur = [], []
    i = 0; x = y = 0.0; sx = sy = 0.0
    cmd = None; c2 = q1 = None

    def num():
        nonlocal i
        v = float(tk[i]); i += 1; return v

    while i < len(tk):
        if tk[i] in "MmLlHhVvCcSsQqTtAaZz":
            cmd = tk[i]; i += 1
            if cmd in "Zz":
                if cur:
                    subs.append((cur, True)); cur = []
                x, y = sx, sy; c2 = q1 = None
                continue
        rel = cmd.islower()
        if cmd in "Mm":
            nx, ny = num(), num()
            if rel: nx += x; ny += y
            if cur: subs.append((cur, False))
            cur = [(nx, ny)]; x, y = nx, ny; sx, sy = x, y
            cmd = 'l' if rel else 'L'; c2 = q1 = None
        elif cmd in "LlHhVv":
            if cmd in "Ll":
                nx, ny = num(), num()
                if rel: nx += x; ny += y
            elif cmd in "Hh":
                nx = num() + (x if rel else 0); ny = y
            else:
                ny = num() + (y if rel else 0); nx = x
            cur.append((nx, ny)); x, y = nx, ny; c2 = q1 = None
        elif cmd in "CcSs":
            if cmd in "Cc":
                x1, y1, x2, y2, nx, ny = (num(), num(), num(), num(), num(), num())
                if rel: x1 += x; y1 += y; x2 += x; y2 += y; nx += x; ny += y
            else:
                x2, y2, nx, ny = num(), num(), num(), num()
                if rel: x2 += x; y2 += y; nx += x; ny += y
                x1, y1 = (2*x - c2[0], 2*y - c2[1]) if c2 else (x, y)
            cur += _cubic((x, y), (x1, y1), (x2, y2), (nx, ny))
            c2 = (x2, y2); q1 = None; x, y = nx, ny
        elif cmd in "QqTt":
            if cmd in "Qq":
                x1, y1, nx, ny = num(), num(), num(), num()
                if rel: x1 += x; y1 += y; nx += x; ny += y
            else:
                nx, ny = num(), num()
                if rel: nx += x; ny += y
                x1, y1 = (2*x - q1[0], 2*y - q1[1]) if q1 else (x, y)
            cur += _quad((x, y), (x1, y1), (nx, ny))
            q1 = (x1, y1); c2 = None; x, y = nx, ny
        elif cmd in "Aa":
            rx, ry, rot, la, sw, nx, ny = (num(), num(), num(), num(),
                                           num(), num(), num())
            if rel: nx += x; ny += y
            cur += _arc((x, y), rx, ry, rot, int(la), int(sw), (nx, ny))
            c2 = q1 = None; x, y = nx, ny
        else:                                   # stray numbers, no live command
            i += 1
    if cur:
        subs.append((cur, False))
    return subs


def _ellipse_pts(cx, cy, rx, ry, n=48):
    return [(cx + rx*math.cos(2*math.pi*k/n), cy + ry*math.sin(2*math.pi*k/n))
            for k in range(n + 1)]


def icon_shapes(svg_text):
    """Every drawable in the icon as [(points, closed)], in viewBox units."""
    out = []
    for tag, attrs in re.findall(r'<(path|circle|rect|line)\b([^>]*)/?>', svg_text):
        g = lambda k, dflt=0.0: (float(m.group(1))
                                 if (m := re.search(rf'\b{k}="([-\d.]+)"', attrs))
                                 else dflt)
        if tag == "path":
            out += parse_path(re.search(r'\bd="([^"]+)"', attrs).group(1))
        elif tag == "circle":
            out.append((_ellipse_pts(g("cx"), g("cy"), g("r"), g("r")), True))
        elif tag == "line":
            out.append(([(g("x1"), g("y1")), (g("x2"), g("y2"))], False))
        else:
            x, y, w, h, r = g("x"), g("y"), g("width"), g("height"), g("rx")
            r = min(r, w/2, h/2)
            if r:
                pts = []
                for cx, cy, a0 in ((x+w-r, y+r, -math.pi/2), (x+w-r, y+h-r, 0),
                                   (x+r, y+h-r, math.pi/2), (x+r, y+r, math.pi)):
                    pts += [(cx + r*math.cos(a0 + math.pi/2*k/8),
                             cy + r*math.sin(a0 + math.pi/2*k/8)) for k in range(9)]
                pts.append(pts[0])
                out.append((pts, True))
            else:
                out.append(([(x, y), (x+w, y), (x+w, y+h), (x, y+h), (x, y)], True))
    return out


def render_icon(svg, size, stroke=2.0, ss=SS):
    """Stroke a 24x24 icon (SVG source text) to an alpha mask at (size, size)."""
    vb = re.search(r'viewBox="([\d.\s-]+)"', svg).group(1).split()
    minx, miny, vbw, vbh = [float(v) for v in vb]
    W = int(round(size * ss))
    k = W / max(vbw, vbh)
    sw = max(1, int(round(stroke * k)))
    r = sw / 2

    mask = Image.new("L", (W, W), 0)
    d = ImageDraw.Draw(mask)
    for pts, closed in icon_shapes(svg):
        p = [((px - minx) * k, (py - miny) * k) for px, py in pts]
        if closed and p[0] != p[-1]:
            p.append(p[0])
        if len(p) > 1:
            d.line(p, fill=255, width=sw, joint="curve")
        # Pillow rounds joins but butts the ends; Feather icons are round-capped.
        if not closed:
            for cx, cy in (p[0], p[-1]):
                d.ellipse([cx-r, cy-r, cx+r, cy+r], fill=255)
    return mask.resize((size, size), Image.LANCZOS)


# ============================== compose ==================================
def items_for(which):
    """[(label, svg source)] for a set; subject icons come off disk."""
    if which == "housekeeping":
        return list(HOUSEKEEPING)
    if which == "info":
        return list(INFO)
    if which == "conduct":
        return list(CONDUCT)
    by_name = {s["name"]: s for s in yaml.safe_load(open(SUBJECTS))}
    out = []
    for name in CATEGORIES:
        s = by_name.get(name)
        if s is None:                       # tolerate "Rolling & cycling" etc.
            s = next(v for k, v in by_name.items() if k.endswith(name))
        out.append((LABELS.get(s["name"], s["name"]),
                    open(os.path.join(ICON_DIR, s["icon"])).read()))
    return out


def build(which="categories", out_w=GW * 2):
    items = items_for(which)
    cols = SETS[which]
    rows = -(-len(items) // cols)
    S = out_w / GW                          # grid unit -> output pixels

    icon_px = int(round(86 * S))
    label_sz = int(28 * S)
    icon_gap = 22 * S
    row_gap = 40 * S
    row_h = icon_px + icon_gap + label_sz + row_gap
    pad = 44 * S                            # above the first icon, below the last label

    # Height follows the row count rather than a fixed grid, so a one-row set
    # isn't padded out with the dead space a two-row set needs.
    Wp = out_w
    Hp = int(round(rows * row_h - row_gap + 2 * pad))

    img = Image.new("RGB", (Wp, Hp), PAGE_BG)
    draw = ImageDraw.Draw(img)

    # No heading: the form's own question text says what this is, and a second
    # title would just repeat it.
    grid_top = pad
    side = 70 * S
    col_w = (Wp - 2 * side) / cols

    for i, (label, svg) in enumerate(items):
        cx = side + col_w * (i % cols) + col_w / 2
        cy = grid_top + row_h * (i // cols)

        mask = render_icon(svg, icon_px)
        img.paste(Image.new("RGB", (icon_px, icon_px), LIVABLE),
                  (int(cx - icon_px / 2), int(cy)), mask)

        sz = label_sz
        f = fb.font(sz, 500)
        while draw.textlength(label, font=f) > col_w - 14 * S and sz > 20 * S:
            sz -= max(1, int(S))
            f = fb.font(sz, 500)
        draw.text((cx, cy + icon_px + icon_gap + label_sz / 2), label,
                  font=f, fill=INKY, anchor="mm")

    out = os.path.join(OUT_DIR, "%s.png" % which)
    img.save(out, optimize=True)
    print("wrote", out, img.size, "%d items" % len(items),
          "%.0f KB" % (os.path.getsize(out) / 1024))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--set", dest="which", default="categories", choices=list(SETS),
                    help="which grid to build (default categories)")
    ap.add_argument("--width", type=int, default=GW * 2,
                    help="output width in px (default 2800; Tally recommends 1400)")
    a = ap.parse_args()
    build(a.which, a.width)
