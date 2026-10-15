#!/usr/bin/env python3
"""Render Livable CRD marketing images sized for Google Ads.

Run from repo root:  python3 scripts/gen-google-ads-images.py
Outputs in assets/promo/google-ads/, three concepts in three sizes each:

  Landscape 1.91:1  1200x628   (Google min 600x314)
  Square    1:1     1200x1200  (Google min 300x300)
  Portrait  4:5     960x1200   (Google min 480x600)

  images-compare-*    two made-up scorecards side by side, no copy
  images-issues-*     the questionnaire's subject icons with grade chips, no copy
  images-headline-*   a short headline over one made-up scorecard

Google asks for little or no overlaid text (keep it well under a fifth of the
frame) and may crop up to 5% from any edge, so copy and key shapes stay inside
a centred safe area. The scorecards are illustrations: grey bars stand in for
names and answers so no real candidate is shown or implied.

Everything is drawn at 2x and LANCZOS-downscaled. The subject icons are the
site's stroke SVGs (assets/images/icons/); this file carries a small stroke
renderer for them because the fill-only rasteriser in gen-logo-pngs.py does
not draw strokes or arcs.
"""
import math, os, re, urllib.request
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT  = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ICONS = os.path.join(ROOT, "assets", "images", "icons")
OUT   = os.path.join(ROOT, "assets", "promo", "google-ads")

INKY     = (0x22, 0x09, 0x40)   # #220940  hero background
PURPLE   = (0x5C, 0x18, 0xA4)   # #5C18A4  primary brand colour
KWETLAL  = (0xD5, 0xAD, 0xFF)   # #D5ADFF  light brand accent
WHITE    = (255, 255, 255)
BG_LIGHT = (0xFA, 0xF9, 0xFC)   # site page background
TINT     = (0xF1, 0xE8, 0xFF)   # icon tile behind subject icons
BAR      = (0xEC, 0xE7, 0xF2)   # placeholder text bars
BAR_DARK = (0xCF, 0xC5, 0xDD)
GRADE = {"A": (0x1b, 0x7a, 0x3d), "B": (0x2d, 0x6a, 0x9f),   # $grade-a..f
         "C": (0xb8, 0x86, 0x0b), "F": (0xc4, 0x1e, 0x3a)}

SIZES = {"landscape": (1200, 628), "square": (1200, 1200), "portrait": (960, 1200)}
S = 2   # supersample factor

# ------------------------------- fonts -----------------------------------
LEXEND_URL = ("https://raw.githubusercontent.com/google/fonts/main/"
              "ofl/lexend/Lexend%5Bwght%5D.ttf")
LEXEND_CACHE = os.path.join(os.path.expanduser("~"), ".cache",
                            "livable-crd", "Lexend-var.ttf")
DEJAVU = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def _lexend_path():
    if os.path.exists(LEXEND_CACHE):
        return LEXEND_CACHE
    try:
        os.makedirs(os.path.dirname(LEXEND_CACHE), exist_ok=True)
        urllib.request.urlretrieve(LEXEND_URL, LEXEND_CACHE)
        return LEXEND_CACHE
    except Exception as e:
        print("Lexend fetch failed (%s); falling back to DejaVu" % e)
        return DEJAVU


_FONT = _lexend_path()


def font(sz, wght=600):
    f = ImageFont.truetype(_FONT, round(sz))
    try:
        f.set_variation_by_axes([wght])
    except Exception:
        pass
    return f


def text_center(draw, box, text, fnt, fill):
    """Centre `text` optically inside box (x0, y0, x1, y1)."""
    l, t, r, b = draw.textbbox((0, 0), text, font=fnt)
    x = (box[0] + box[2]) / 2 - (r - l) / 2 - l
    y = (box[1] + box[3]) / 2 - (b - t) / 2 - t
    draw.text((x, y), text, font=fnt, fill=fill)


# ---------------------- stroke icon renderer -----------------------------
def _arc(p0, rx, ry, phi, large, sweep, p1, n=16):
    """SVG endpoint arc -> points (excluding p0)."""
    if rx == 0 or ry == 0:
        return [p1]
    cp, sp = math.cos(math.radians(phi)), math.sin(math.radians(phi))
    dx, dy = (p0[0] - p1[0]) / 2, (p0[1] - p1[1]) / 2
    x1p, y1p = cp * dx + sp * dy, -sp * dx + cp * dy
    rx, ry = abs(rx), abs(ry)
    lam = x1p**2 / rx**2 + y1p**2 / ry**2
    if lam > 1:
        rx, ry = rx * math.sqrt(lam), ry * math.sqrt(lam)
    num = rx*rx*ry*ry - rx*rx*y1p*y1p - ry*ry*x1p*x1p
    den = rx*rx*y1p*y1p + ry*ry*x1p*x1p
    co = math.sqrt(max(0, num / den)) * (-1 if large == sweep else 1)
    cxp, cyp = co * rx * y1p / ry, -co * ry * x1p / rx
    cx = cp * cxp - sp * cyp + (p0[0] + p1[0]) / 2
    cy = sp * cxp + cp * cyp + (p0[1] + p1[1]) / 2
    ang = lambda ux, uy, vx, vy: math.atan2(ux*vy - uy*vx, ux*vx + uy*vy)
    t1 = ang(1, 0, (x1p - cxp) / rx, (y1p - cyp) / ry)
    dt = ang((x1p - cxp) / rx, (y1p - cyp) / ry, (-x1p - cxp) / rx, (-y1p - cyp) / ry)
    if not sweep and dt > 0:
        dt -= 2 * math.pi
    elif sweep and dt < 0:
        dt += 2 * math.pi
    pts = []
    for i in range(1, n + 1):
        t = t1 + dt * i / n
        x, y = rx * math.cos(t), ry * math.sin(t)
        pts.append((cp * x - sp * y + cx, sp * x + cp * y + cy))
    return pts


def _bez(pts, n=16):
    out = []
    for i in range(1, n + 1):
        t = i / n
        if len(pts) == 4:
            p0, p1, p2, p3 = pts; mt = 1 - t
            out.append((mt**3*p0[0] + 3*mt*mt*t*p1[0] + 3*mt*t*t*p2[0] + t**3*p3[0],
                        mt**3*p0[1] + 3*mt*mt*t*p1[1] + 3*mt*t*t*p2[1] + t**3*p3[1]))
        else:
            p0, p1, p2 = pts; mt = 1 - t
            out.append((mt*mt*p0[0] + 2*mt*t*p1[0] + t*t*p2[0],
                        mt*mt*p0[1] + 2*mt*t*p1[1] + t*t*p2[1]))
    return out


def parse_path(d):
    """Return a list of (points, closed) polylines."""
    toks = re.findall(r'[A-Za-z]|[-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?', d)
    i, cmd = 0, None
    x = y = 0.0
    start = (0.0, 0.0)
    prev_ctrl = None
    lines, cur = [], []

    def num():
        nonlocal i
        v = float(toks[i]); i += 1
        return v

    def flag():
        # arc flags may be packed ("0 0 1" or "001")
        nonlocal i
        t = toks[i]
        if len(t) > 1 and t[0] in "01" and not t.startswith(("0.", "1.")):
            toks[i] = t[1:]
            return int(t[0])
        i += 1
        return int(float(t))

    while i < len(toks):
        if re.match(r'[A-Za-z]', toks[i]):
            cmd = toks[i]; i += 1
        rel = cmd.islower()
        c = cmd.upper()
        ox, oy = (x, y) if rel else (0.0, 0.0)
        if c == "M":
            if len(cur) > 1:
                lines.append((cur, False))
            x, y = num() + ox, num() + oy
            start, cur = (x, y), [(x, y)]
            cmd = "l" if rel else "L"
            prev_ctrl = None
        elif c == "Z":
            if cur:
                lines.append((cur, True))
            cur = [start]; x, y = start
            prev_ctrl = None
        elif c == "L":
            x, y = num() + ox, num() + oy; cur.append((x, y)); prev_ctrl = None
        elif c == "H":
            x = num() + ox; cur.append((x, y)); prev_ctrl = None
        elif c == "V":
            y = num() + oy; cur.append((x, y)); prev_ctrl = None
        elif c in "CS":
            if c == "C":
                c1 = (num() + ox, num() + oy)
            else:
                c1 = (2*x - prev_ctrl[0], 2*y - prev_ctrl[1]) if prev_ctrl else (x, y)
            c2 = (num() + ox, num() + oy)
            p = (num() + ox, num() + oy)
            cur += _bez([(x, y), c1, c2, p]); prev_ctrl = c2; x, y = p
        elif c == "Q":
            c1 = (num() + ox, num() + oy); p = (num() + ox, num() + oy)
            cur += _bez([(x, y), c1, p]); prev_ctrl = None; x, y = p
        elif c == "A":
            rx, ry, phi = num(), num(), num()
            large, sweep = flag(), flag()
            p = (num() + ox, num() + oy)
            cur += _arc((x, y), rx, ry, phi, large, sweep, p); x, y = p
            prev_ctrl = None
        else:
            raise ValueError("unsupported path command " + cmd)
    if len(cur) > 1:
        lines.append((cur, False))
    return lines


def render_icon(name, size, color, stroke=2.0):
    """Draw a 24x24 stroke icon at `size` px, round caps/joins, on transparent."""
    svg = open(os.path.join(ICONS, name + ".svg")).read()
    k = size / 24 * 4                       # 4x supersample inside the icon
    big = size * 4
    mask = Image.new("L", (big, big), 0)
    d = ImageDraw.Draw(mask)
    w = max(1, round(stroke * k))
    r = w / 2

    def cap(p):
        d.ellipse([p[0] - r, p[1] - r, p[0] + r, p[1] + r], fill=255)

    num = lambda a, key: float(re.search(rf'\b{key}="([-\d.]+)"', a).group(1)) \
        if re.search(rf'\b{key}="', a) else 0.0
    for tag, a in re.findall(r'<(path|circle|rect|line)\b([^>]*)/?>', svg):
        if tag == "path":
            for pts, closed in parse_path(re.search(r'\bd="([^"]+)"', a).group(1)):
                P = [(px * k, py * k) for px, py in pts]
                if closed:
                    P.append(P[0])
                d.line(P, fill=255, width=w, joint="curve")
                for p in P:
                    cap(p)
        elif tag == "circle":
            cx, cy, rr = num(a, "cx") * k, num(a, "cy") * k, num(a, "r") * k
            d.ellipse([cx - rr - r, cy - rr - r, cx + rr + r, cy + rr + r], fill=255)
            d.ellipse([cx - rr + r, cy - rr + r, cx + rr - r, cy + rr - r], fill=0)
        elif tag == "rect":
            x0, y0 = num(a, "x") * k, num(a, "y") * k
            x1, y1 = x0 + num(a, "width") * k, y0 + num(a, "height") * k
            d.rounded_rectangle([x0 - r, y0 - r, x1 + r, y1 + r],
                                radius=num(a, "rx") * k + r, fill=255)
            d.rounded_rectangle([x0 + r, y0 + r, x1 - r, y1 - r],
                                radius=max(0, num(a, "rx") * k - r), fill=0)
        elif tag == "line":
            P = [(num(a, "x1") * k, num(a, "y1") * k), (num(a, "x2") * k, num(a, "y2") * k)]
            d.line(P, fill=255, width=w); cap(P[0]); cap(P[1])
    mask = mask.resize((size, size), Image.LANCZOS)
    out = Image.new("RGBA", (size, size), color + (0,))
    out.putalpha(mask)
    return out


# ------------------------------ pieces -----------------------------------
def dots(img, color=(255, 255, 255), alpha=34, step=16 * S, r=1.2 * S):
    """The site hero's dot texture (assets/images/hero-texture.svg)."""
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for row, y in enumerate(range(0, img.height + step, step // 2)):
        off = 0 if row % 2 == 0 else step // 2
        for x in range(off, img.width + step, step):
            d.ellipse([x - r, y - r, x + r, y + r], fill=color + (alpha,))
    img.alpha_composite(layer)


def chip(d, x, y, size, letter, radius=None):
    d.rounded_rectangle([x, y, x + size, y + size],
                        radius=radius or size * 0.22, fill=GRADE[letter])
    text_center(d, (x, y, x + size, y + size), letter, font(size * 0.56, 700), WHITE)


def shadowed(card, blur):
    """Return card on a canvas padded for a soft drop shadow."""
    pad = blur * 3
    sh = Image.new("RGBA", (card.width + 2 * pad, card.height + 2 * pad), (0, 0, 0, 0))
    a = Image.new("L", sh.size, 0)
    a.paste(card.getchannel("A").point(lambda v: v * 0.45), (pad, pad + blur // 2))
    a = a.filter(ImageFilter.GaussianBlur(blur))
    sh.paste(Image.new("RGBA", sh.size, (10, 2, 25, 255)), (0, 0), a)
    sh.alpha_composite(card, (pad, pad))
    return sh


ROW_ICONS = ["housing", "transit", "climate", "walking", "rolling-cycling"]


def scorecard(cw, overall, grades, bar_lengths):
    """A made-up candidate scorecard, `cw` px wide (already supersampled)."""
    k = cw / 520
    pad, av, row_h = 34 * k, 92 * k, 74 * k
    head_h = av
    ch = round(pad + head_h + 30 * k + 2 * k + 14 * k + len(grades) * row_h + pad - 14 * k)
    card = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    d = ImageDraw.Draw(card)
    d.rounded_rectangle([0, 0, cw - 1, ch - 1], radius=30 * k, fill=WHITE)

    # header: avatar, name/municipality bars, overall grade
    x0, y0 = pad, pad
    d.ellipse([x0, y0, x0 + av, y0 + av], fill=TINT)
    hx, hy, hr = x0 + av / 2, y0 + av * 0.38, av * 0.17
    d.ellipse([hx - hr, hy - hr, hx + hr, hy + hr], fill=PURPLE)
    sw = av * 0.56
    d.pieslice([hx - sw / 2, y0 + av * 0.62, hx + sw / 2, y0 + av * 1.18],
               180, 360, fill=PURPLE)
    # clip shoulders to the avatar circle
    m = Image.new("L", card.size, 0)
    ImageDraw.Draw(m).ellipse([x0, y0, x0 + av, y0 + av], fill=255)
    outside = Image.new("L", card.size, 255)
    outside.paste(0, (0, 0), m)
    sub = Image.new("RGBA", card.size, WHITE + (255,))
    region = [round(x0), round(y0 + av * 0.85), round(x0 + av), round(y0 + av * 1.2)]
    card.paste(sub.crop(region), region[:2], outside.crop(region))
    d = ImageDraw.Draw(card)

    bx = x0 + av + 24 * k
    d.rounded_rectangle([bx, y0 + 18 * k, bx + 220 * k, y0 + 44 * k], radius=13 * k, fill=BAR_DARK)
    d.rounded_rectangle([bx, y0 + 58 * k, bx + 140 * k, y0 + 76 * k], radius=9 * k, fill=BAR)
    big = 92 * k
    chip(d, cw - pad - big, y0, big, overall)

    # divider
    dy = y0 + head_h + 30 * k
    d.line([(pad, dy), (cw - pad, dy)], fill=BAR, width=max(1, round(2 * k)))

    # subject rows
    tile, small = 54 * k, 54 * k
    y = dy + 2 * k + 14 * k
    for icon, g, bl in zip(ROW_ICONS, grades, bar_lengths):
        cy = y + row_h / 2 - 7 * k
        d.rounded_rectangle([pad, cy - tile / 2, pad + tile, cy + tile / 2], radius=14 * k, fill=TINT)
        ic = render_icon(icon, round(tile * 0.6), PURPLE)
        card.alpha_composite(ic, (round(pad + (tile - ic.width) / 2), round(cy - ic.height / 2)))
        d = ImageDraw.Draw(card)
        lx = pad + tile + 22 * k
        d.rounded_rectangle([lx, cy - 9 * k, lx + bl * k, cy + 9 * k], radius=9 * k, fill=BAR)
        chip(d, cw - pad - small, cy - small / 2, small, g)
        y += row_h
    return card


CARD_GOOD = ("A", "AABAB", [250, 200, 230, 170, 210])
CARD_MIXED = ("C", "CBFCB", [190, 240, 160, 220, 180])


def place(img, piece, cx, cy, angle=0):
    if angle:
        piece = piece.rotate(angle, resample=Image.BICUBIC, expand=True)
    img.alpha_composite(piece, (round(cx - piece.width / 2), round(cy - piece.height / 2)))


# ------------------------------ concepts ---------------------------------
def make_compare(kind):
    W, H = (v * S for v in SIZES[kind])
    img = Image.new("RGBA", (W, H), INKY + (255,))
    dots(img)
    if kind == "landscape":
        cw = round(H * 0.74)
        a, b = scorecard(cw, *CARD_GOOD), scorecard(cw, *CARD_MIXED)
        place(img, shadowed(b, 18 * S), W * 0.66, H * 0.53, -4)
        place(img, shadowed(a, 18 * S), W * 0.34, H * 0.50, 4)
    else:
        cw = round(W * (0.56 if kind == "square" else 0.64))
        a, b = scorecard(cw, *CARD_GOOD), scorecard(cw, *CARD_MIXED)
        place(img, shadowed(b, 18 * S), W * 0.63, H * 0.55, -5)
        place(img, shadowed(a, 18 * S), W * 0.39, H * 0.47, 4)
    return img


ISSUE_ICONS = ["housing", "transit", "climate", "walking", "rolling-cycling",
               "arts", "governance", "healthcare-access", "general"]
ISSUE_GRADES = "ABACBAFBA"


def issue_tile(size, icon, grade):
    t = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(t)
    d.rounded_rectangle([0, 0, size - 1, size - 1], radius=size * 0.16, fill=WHITE)
    # icon sits up and left of centre so the grade chip in the corner clears it
    ic = render_icon(icon, round(size * 0.42), PURPLE, stroke=1.8)
    t.alpha_composite(ic, (round(size * 0.42 - ic.width / 2), round(size * 0.42 - ic.height / 2)))
    d = ImageDraw.Draw(t)
    c = size * 0.26
    chip(d, size * 0.68, size * 0.68, c, grade)
    return t


def make_issues(kind):
    W, H = (v * S for v in SIZES[kind])
    img = Image.new("RGBA", (W, H), BG_LIGHT + (255,))
    dots(img, color=PURPLE, alpha=26)
    cols, rows, n = {"landscape": (4, 2, 8), "square": (3, 3, 9), "portrait": (3, 3, 9)}[kind]
    gap = 26 * S
    safe_w, safe_h = W * 0.84, H * (0.74 if kind == "portrait" else 0.84)
    size = int(min((safe_w - gap * (cols - 1)) / cols, (safe_h - gap * (rows - 1)) / rows))
    gw, gh = cols * size + (cols - 1) * gap, rows * size + (rows - 1) * gap
    ox = (W - gw) / 2
    oy = (H - gh) / 2 - (H * 0.06 if kind == "portrait" else 0)
    for i in range(n):
        r, c = divmod(i, cols)
        tile = shadowed(issue_tile(size, ISSUE_ICONS[i], ISSUE_GRADES[i]), 8 * S)
        pad = (tile.width - size) // 2
        img.alpha_composite(tile, (round(ox + c * (size + gap)) - pad,
                                   round(oy + r * (size + gap)) - pad))
    if kind == "portrait":   # grade scale under the grid fills the 4:5 frame
        d = ImageDraw.Draw(img)
        cs, cg = 96 * S, 26 * S
        x = (W - (4 * cs + 3 * cg)) / 2
        y = oy + gh + (H - (oy + gh) - cs) / 2
        for L in "ABCF":
            chip(d, x, y, cs, L); x += cs + cg
    return img


HEADLINE = ["Know where they", "stand before you vote."]
SUBLINE = "Capital Region municipal election · Oct. 17"


def make_headline(kind):
    W, H = (v * S for v in SIZES[kind])
    img = Image.new("RGBA", (W, H), INKY + (255,))
    dots(img)
    d = ImageDraw.Draw(img)
    if kind == "landscape":
        tx, hs = W * 0.075, 46 * S
        hf, sf = font(hs, 700), font(hs * 0.42, 500)
        y = H * 0.30
        for line in HEADLINE:
            d.text((tx, y), line, font=hf, fill=WHITE); y += hs * 1.2
        d.text((tx, y + hs * 0.35), SUBLINE, font=sf, fill=KWETLAL)
        d.rounded_rectangle([tx, H * 0.30 - 34 * S, tx + 90 * S, H * 0.30 - 26 * S],
                            radius=4 * S, fill=KWETLAL)
        card = scorecard(round(H * 0.70), *CARD_GOOD)
        place(img, shadowed(card, 18 * S), W * 0.765, H * 0.51, -4)
    else:
        hs = (62 if kind == "square" else 56) * S
        hf, sf = font(hs, 700), font(hs * 0.42, 500)
        y = H * 0.09
        for line in HEADLINE:
            text_center(d, (0, y, W, y + hs), line, hf, WHITE); y += hs * 1.2
        text_center(d, (0, y + hs * 0.2, W, y + hs * 0.2 + hs * 0.5), SUBLINE, sf, KWETLAL)
        cw = round(W * (0.58 if kind == "square" else 0.70))
        card = scorecard(cw, *CARD_GOOD)
        top = y + hs * 1.15
        place(img, shadowed(card, 18 * S), W / 2, top + (H - top) / 2 + 10 * S, 0)
    return img


def calendar(w):
    """A tear-off calendar page for election day, `w` px wide."""
    h = round(w * 1.12)
    cal = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(cal)
    rad, band = w * 0.12, h * 0.30
    d.rounded_rectangle([0, 0, w - 1, h - 1], radius=rad, fill=WHITE)
    d.rounded_rectangle([0, 0, w - 1, band + rad], radius=rad, fill=PURPLE)
    d.rectangle([0, band, w - 1, band + rad], fill=WHITE)
    text_center(d, (0, band * 0.30, w, band), "OCT", font(band * 0.42, 700), WHITE)
    text_center(d, (0, band, w, h - h * 0.04), "17", font(h * 0.48, 700), INKY)
    # binder rings poking over the top edge
    rw, rh = w * 0.06, h * 0.10
    for fx in (0.22, 0.78):
        cx = w * fx
        d.rounded_rectangle([cx - rw / 2, -1, cx + rw / 2, rh], radius=rw / 2, fill=INKY)
    return cal


BALLOT = "ACBF"   # made-up grades beside the made-up names


def ballot(cw):
    """A made-up ballot: empty marking boxes, name bars, a grade beside each.
    The boxes stay unmarked so the picture never looks like a voting tip."""
    k = cw / 520
    pad, row_h = 36 * k, 86 * k
    head = 60 * k
    ch = round(pad + head + 24 * k + len(BALLOT) * row_h + pad - 16 * k)
    card = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    d = ImageDraw.Draw(card)
    d.rounded_rectangle([0, 0, cw - 1, ch - 1], radius=28 * k, fill=WHITE)
    d.rounded_rectangle([pad, pad, pad + 230 * k, pad + 26 * k], radius=13 * k, fill=BAR_DARK)
    d.rounded_rectangle([pad, pad + 40 * k, pad + 150 * k, pad + 56 * k], radius=8 * k, fill=BAR)
    dy = pad + head + 12 * k
    d.line([(pad, dy), (cw - pad, dy)], fill=BAR, width=max(1, round(2 * k)))
    box, sz = 40 * k, 58 * k
    y = dy + 12 * k
    for g, bl in zip(BALLOT, [240, 190, 260, 210]):
        cy = y + row_h / 2
        d.rounded_rectangle([pad, cy - box / 2, pad + box, cy + box / 2], radius=8 * k,
                            outline=PURPLE, width=max(2, round(4 * k)))
        lx = pad + box + 26 * k
        d.rounded_rectangle([lx, cy - 10 * k, lx + bl * k, cy + 10 * k], radius=10 * k, fill=BAR)
        chip(d, cw - pad - sz, cy - sz / 2, sz, g)
        y += row_h
    return card


def make_vote(kind):
    W, H = (v * S for v in SIZES[kind])
    img = Image.new("RGBA", (W, H), KWETLAL + (255,))
    dots(img, color=PURPLE, alpha=40)
    if kind == "landscape":
        b = ballot(round(W * 0.44))
        c = calendar(round(H * 0.46))
        place(img, shadowed(b, 16 * S), W * 0.60, H * 0.50, -3)
        place(img, shadowed(c, 14 * S), W * 0.27, H * 0.47, 6)
    else:
        b = ballot(round(W * 0.62))
        c = calendar(round(W * 0.30))
        place(img, shadowed(b, 18 * S), W * 0.57, H * 0.60, -3)
        place(img, shadowed(c, 16 * S), W * 0.25, H * 0.25, 7)
    return img


def save(img, name):
    W, H = img.width // S, img.height // S
    out = img.convert("RGB").resize((W, H), Image.LANCZOS)
    path = os.path.join(OUT, name)
    out.save(path, optimize=True)
    print(f"wrote {os.path.relpath(path, ROOT)} {out.size} {os.path.getsize(path) / 1024:.0f} KB")


def build():
    os.makedirs(OUT, exist_ok=True)
    for concept, fn in [("compare", make_compare), ("issues", make_issues),
                        ("headline", make_headline)]:
        for kind in SIZES:
            save(fn(kind), f"images-{concept}-{kind}.png")
    for kind in ("landscape", "square"):
        save(make_vote(kind), f"images-vote-{kind}.png")


if __name__ == "__main__":
    build()
