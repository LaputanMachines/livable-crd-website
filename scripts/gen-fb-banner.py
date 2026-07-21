#!/usr/bin/env python3
"""Generate the Facebook-group banner from the brand logo SVG.

Run from repo root:  python3 scripts/gen-fb-banner.py
Output: assets/images/facebook-banner.png  (1640x856, FB group-cover size)

Theme matches the site hero (_sass): Inky-purple background + the same 16px
dot texture, the white brand logo with the camas mark in Kwetlal purple, the
A/B/C/F grade chips, and a Kwetlal bottom bar.

This box has no SVG rasteriser or numpy, so we hand-roll a minimal SVG path
renderer with Pillow: parse paths -> flatten beziers -> nonzero-winding
scanline fill at 3x supersample -> LANCZOS downscale for anti-aliasing.
The Lexend brand font (Google Fonts) is fetched to a cache on first run;
falls back to DejaVu-Bold offline.
"""
import os, re, math, urllib.request
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMG  = os.path.join(ROOT, "assets", "images")
LOGO_SVG = os.path.join(IMG, "brand", "logo-light.svg")

# ---- brand palette (from _sass/_variables.scss) -------------------------
INKY    = (0x22, 0x09, 0x40)   # #220940  hero / page-header background
KWETLAL = (0xD5, 0xAD, 0xFF)   # #D5ADFF  light brand accent
WHITE   = (255, 255, 255)
GRADE = {"A": (0x1b,0x7a,0x3d), "B": (0x2d,0x6a,0x9f),   # $grade-a..f
         "C": (0xb8,0x86,0x0b), "F": (0xc4,0x1e,0x3a)}

# ---- Lexend brand font (variable) ---------------------------------------
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

def font(sz, wght):
    f = ImageFont.truetype(_FONT, sz)
    try: f.set_variation_by_axes([wght])
    except Exception: pass
    return f

# ======================= tiny SVG path rasteriser ========================
def _cubic(p0, p1, p2, p3, n=24):
    out = []
    for i in range(1, n + 1):
        t = i / n; mt = 1 - t
        out.append((mt**3*p0[0] + 3*mt*mt*t*p1[0] + 3*mt*t*t*p2[0] + t**3*p3[0],
                    mt**3*p0[1] + 3*mt*mt*t*p1[1] + 3*mt*t*t*p2[1] + t**3*p3[1]))
    return out

def _quad(p0, p1, p2, n=20):
    out = []
    for i in range(1, n + 1):
        t = i / n; mt = 1 - t
        out.append((mt*mt*p0[0] + 2*mt*t*p1[0] + t*t*p2[0],
                    mt*mt*p0[1] + 2*mt*t*p1[1] + t*t*p2[1]))
    return out

def parse_path(d):
    """Return list of subpaths, each a list of (x,y) points (beziers flattened)."""
    tokens = re.findall(r'[MmLlHhVvCcSsQqTtZz]|[-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?', d)
    subpaths, cur = [], []
    i = 0; x = y = 0.0; start = (0.0, 0.0)
    cmd = None; prev_c2 = prev_q1 = None
    def num():
        nonlocal i
        v = float(tokens[i]); i += 1; return v
    while i < len(tokens):
        if tokens[i] in "MmLlHhVvCcSsQqTtZz":
            cmd = tokens[i]; i += 1
        if cmd in "Mm":
            nx, ny = num(), num()
            if cmd == 'm': nx += x; ny += y
            if cur: subpaths.append(cur)
            cur = [(nx, ny)]; x, y = nx, ny; start = (x, y)
            cmd = 'l' if cmd == 'm' else 'L'; prev_c2 = prev_q1 = None
        elif cmd in "Ll":
            nx, ny = num(), num()
            if cmd == 'l': nx += x; ny += y
            cur.append((nx, ny)); x, y = nx, ny; prev_c2 = prev_q1 = None
        elif cmd in "Hh":
            nx = num()
            if cmd == 'h': nx += x
            cur.append((nx, y)); x = nx; prev_c2 = prev_q1 = None
        elif cmd in "Vv":
            ny = num()
            if cmd == 'v': ny += y
            cur.append((x, ny)); y = ny; prev_c2 = prev_q1 = None
        elif cmd in "Cc":
            x1,y1,x2,y2,nx,ny = num(),num(),num(),num(),num(),num()
            if cmd == 'c': x1+=x;y1+=y;x2+=x;y2+=y;nx+=x;ny+=y
            cur += _cubic((x,y),(x1,y1),(x2,y2),(nx,ny))
            prev_c2 = (x2,y2); x,y = nx,ny; prev_q1 = None
        elif cmd in "Ss":
            x2,y2,nx,ny = num(),num(),num(),num()
            if cmd == 's': x2+=x;y2+=y;nx+=x;ny+=y
            x1,y1 = (2*x-prev_c2[0], 2*y-prev_c2[1]) if prev_c2 else (x,y)
            cur += _cubic((x,y),(x1,y1),(x2,y2),(nx,ny))
            prev_c2 = (x2,y2); x,y = nx,ny; prev_q1 = None
        elif cmd in "Qq":
            x1,y1,nx,ny = num(),num(),num(),num()
            if cmd == 'q': x1+=x;y1+=y;nx+=x;ny+=y
            cur += _quad((x,y),(x1,y1),(nx,ny))
            prev_q1 = (x1,y1); x,y = nx,ny; prev_c2 = None
        elif cmd in "Tt":
            nx,ny = num(),num()
            if cmd == 't': nx+=x;ny+=y
            x1,y1 = (2*x-prev_q1[0], 2*y-prev_q1[1]) if prev_q1 else (x,y)
            cur += _quad((x,y),(x1,y1),(nx,ny))
            prev_q1 = (x1,y1); x,y = nx,ny; prev_c2 = None
        elif cmd in "Zz":
            if cur: cur.append(start); subpaths.append(cur); cur = []
            x, y = start; prev_c2 = prev_q1 = None
    if cur: subpaths.append(cur)
    return subpaths

def rounded_rect_subpath(x, y, w, h, rx, n=16):
    rx = min(rx, w/2); ry = min(rx, h/2)
    pts = []
    def arc(cx, cy, a0, a1):
        for k in range(n + 1):
            a = a0 + (a1 - a0) * k / n
            pts.append((cx + rx*math.cos(a), cy + ry*math.sin(a)))
    arc(x+rx,   y+ry,   math.pi,     1.5*math.pi)
    arc(x+w-rx, y+ry,   1.5*math.pi, 2*math.pi)
    arc(x+w-rx, y+h-ry, 0,           0.5*math.pi)
    arc(x+rx,   y+h-ry, 0.5*math.pi, math.pi)
    pts.append(pts[0])
    return [pts]

def rasterize(subpaths, W, H, scale, tx, ty):
    """Nonzero-winding scanline fill -> 'L' alpha image at (W,H)."""
    edges = []
    for sp in subpaths:
        dp = [(px*scale + tx, py*scale + ty) for px, py in sp]
        for k in range(len(dp) - 1):
            (x0, y0), (x1, y1) = dp[k], dp[k+1]
            if y0 == y1: continue
            wind = 1 if y1 > y0 else -1
            if y0 > y1: x0, y0, x1, y1 = x1, y1, x0, y0
            edges.append((y0, y1, x0, (x1 - x0) / (y1 - y0), wind))
    img = Image.new("L", (W, H), 0); px = img.load()
    for yy in range(H):
        yc = yy + 0.5
        xs = [(x0 + (yc - y0) * dxdy, wind)
              for (y0, y1, x0, dxdy, wind) in edges if y0 <= yc < y1]
        if not xs: continue
        xs.sort(); wnum = 0
        for j in range(len(xs) - 1):
            wnum += xs[j][1]
            if wnum != 0:
                a = max(0, int(math.ceil(xs[j][0] - 0.5)))
                b = min(W - 1, int(math.floor(xs[j+1][0] - 0.5)))
                for xp in range(a, b + 1):
                    px[xp, yy] = 255
    return img

def render_svg_group(svg_text, keep, out_w, out_h, ss=3):
    """Render selected <path>/<rect> elements (by doc-order index) to an alpha mask."""
    _, _, vbw, vbh = [float(v) for v in
                      re.search(r'viewBox="([\d.\s-]+)"', svg_text).group(1).split()]
    W, H = out_w*ss, out_h*ss
    scale = min(W/vbw, H/vbh)
    tx = (W - vbw*scale)/2; ty = (H - vbh*scale)/2
    subs = []
    for idx, (tag, attrs) in enumerate(re.findall(r'<(path|rect)\b([^>]*)/?>', svg_text)):
        if idx not in keep: continue
        if tag == "path":
            subs += parse_path(re.search(r'\bd="([^"]+)"', attrs).group(1))
        else:
            g = lambda k: float(re.search(rf'\b{k}="([-\d.]+)"', attrs).group(1))
            rx = re.search(r'\brx="([-\d.]+)"', attrs)
            subs += rounded_rect_subpath(g("x"), g("y"), g("width"), g("height"),
                                         float(rx.group(1)) if rx else 0.0)
    return rasterize(subs, W, H, scale, tx, ty).resize((out_w, out_h), Image.LANCZOS)

# ============================ compose banner =============================
def build():
    Wb, Hb = 1640, 856   # Facebook group-cover recommended upload size
    banner = Image.new("RGBA", (Wb, Hb), INKY + (255,))

    # dot texture (matches assets/images/hero-texture.svg, 16px tile)
    tile = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    td = ImageDraw.Draw(tile)
    da = int(255 * 0.5 * 0.26)
    for cx, cy in [(2,2),(10,2),(6,10),(14,10)]:
        td.ellipse([cx-1, cy-1, cx+1, cy+1], fill=(255,255,255,da))
    tex = Image.new("RGBA", (Wb, Hb), (0,0,0,0))
    for yy in range(0, Hb, 16):
        for xx in range(0, Wb, 16):
            tex.paste(tile, (xx, yy), tile)
    banner = Image.alpha_composite(banner, tex)

    # depth: darken toward the bottom, a faint light wash top-left
    dov = Image.new("L", (Wb, Hb), 0); dp = dov.load()
    lov = Image.new("L", (Wb, Hb), 0); lp = lov.load()
    for yy in range(Hb):
        dval = min(58, int(42 * (yy / Hb) ** 1.6))
        for xx in range(0, Wb, 2):
            dp[xx, yy] = dval
            if xx+1 < Wb: dp[xx+1, yy] = dval
            r = ((xx/Wb)**2 + (yy/Hb)**2) ** 0.5
            lval = int(max(0, 14 * (1 - r/0.9)))
            lp[xx, yy] = lval
            if xx+1 < Wb: lp[xx+1, yy] = lval
    d_layer = Image.new("RGBA", (Wb, Hb), (0,0,0,255));       d_layer.putalpha(dov)
    l_layer = Image.new("RGBA", (Wb, Hb), (255,255,255,255)); l_layer.putalpha(lov)
    banner = Image.alpha_composite(banner, d_layer)
    banner = Image.alpha_composite(banner, l_layer).convert("RGB")
    draw = ImageDraw.Draw(banner)

    svg = open(LOGO_SVG).read()
    # element order in logo-light.svg: 0 wordmark, 1 L-rect, 2 house, 3 tree,
    # 4 rect, 5-8 camas burst.  Camas is recoloured Kwetlal; the rest white.
    white_idx = {0, 1, 2, 3, 4}
    camas_idx = {5, 6, 7, 8}

    logo_h = 376
    logo_w = int(round(logo_h * 1988 / 1546))   # preserve viewBox aspect
    g1, tag_h, g2, chip, g3, url_h = 42, 56, 34, 66, 34, 34
    block = logo_h + g1 + tag_h + g2 + chip + g3 + url_h
    top = (Hb - block)//2 - 12

    white_mask = render_svg_group(svg, white_idx, logo_w, logo_h)
    camas_mask = render_svg_group(svg, camas_idx, logo_w, logo_h)
    lx, ly = (Wb - logo_w)//2, top
    banner.paste(Image.new("RGB", (logo_w, logo_h), WHITE),   (lx, ly), white_mask)
    banner.paste(Image.new("RGB", (logo_w, logo_h), KWETLAL), (lx, ly), camas_mask)

    tcy = ly + logo_h + g1 + tag_h//2
    draw.text((Wb/2, tcy), "Capital Region Candidate Scorecard",
              font=font(50, 700), fill=WHITE, anchor="mm")

    letters = list("ABCF"); gap = 22
    total = len(letters)*chip + (len(letters)-1)*gap
    gx = (Wb - total)//2
    gy = tcy + tag_h//2 + g2
    fchip = font(40, 800)
    for i, L in enumerate(letters):
        x0 = gx + i*(chip+gap)
        draw.rounded_rectangle([x0, gy, x0+chip, gy+chip], radius=8, fill=GRADE[L])
        draw.text((x0+chip/2, gy+chip/2+1), L, font=fchip, fill=WHITE, anchor="mm")

    draw.text((Wb/2, gy+chip+g3+url_h//2), "livablecrd.ca",
              font=font(29, 600), fill=KWETLAL, anchor="mm")

    draw.rectangle([0, Hb-14, Wb, Hb], fill=KWETLAL)   # Kwetlal bottom bar

    out = os.path.join(IMG, "facebook-banner.png")
    banner.save(out, optimize=True)
    print("wrote", out, banner.size)


if __name__ == "__main__":
    build()
