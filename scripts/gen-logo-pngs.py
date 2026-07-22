#!/usr/bin/env python3
"""Rasterise the brand logo SVGs to transparent PNGs for partner downloads.

Run from repo root:  python3 scripts/gen-logo-pngs.py
Outputs (transparent background), in assets/images/brand/:
  logo-dark.png   logo-light.png   logo-mark.png

This box has no SVG rasteriser or numpy (see the branding-asset memo), so we
reuse the same pure-Pillow path renderer as gen-fb-banner.py: parse paths ->
flatten beziers -> nonzero-winding scanline fill at Nx supersample -> LANCZOS
downscale. Unlike the banner (single-colour masks), here we group elements by
their SVG `fill` and composite each colour, so full-colour logos come out right.
No font is needed, so the parser is copied rather than imported (importing the
banner script would trigger its Lexend web-font fetch).
"""
import os, re, math
from PIL import Image

ROOT  = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BRAND = os.path.join(ROOT, "assets", "images", "brand")

NAMED = {"white": (255, 255, 255), "black": (0, 0, 0)}

def parse_color(v):
    v = v.strip()
    if v.lower() in NAMED:
        return NAMED[v.lower()]
    if v.startswith("#") and len(v) == 7:
        return (int(v[1:3], 16), int(v[3:5], 16), int(v[5:7], 16))
    if v.startswith("#") and len(v) == 4:
        return tuple(int(c * 2, 16) for c in v[1:])
    return None   # e.g. "none" -> skip

# ======================= tiny SVG path rasteriser ========================
# (Same maths as scripts/gen-fb-banner.py.)
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

def _elem_subpaths(tag, attrs):
    if tag == "path":
        return parse_path(re.search(r'\bd="([^"]+)"', attrs).group(1))
    g = lambda k: float(re.search(rf'\b{k}="([-\d.]+)"', attrs).group(1))
    rx = re.search(r'\brx="([-\d.]+)"', attrs)
    return rounded_rect_subpath(g("x"), g("y"), g("width"), g("height"),
                                float(rx.group(1)) if rx else 0.0)

def render_svg(svg_text, out_w, out_h, ss=3):
    """Composite every <path>/<rect>, coloured by its own `fill`, onto a
    transparent RGBA image at (out_w, out_h). viewBox min-x/min-y honoured."""
    vbx, vby, vbw, vbh = [float(v) for v in
                          re.search(r'viewBox="([\d.\s-]+)"', svg_text).group(1).split()]
    W, H = out_w*ss, out_h*ss
    scale = min(W/vbw, H/vbh)
    tx = (W - vbw*scale)/2 - vbx*scale
    ty = (H - vbh*scale)/2 - vby*scale

    # group element subpaths by fill colour, preserving first-seen order
    groups = {}   # colour -> [subpaths...]
    for tag, attrs in re.findall(r'<(path|rect)\b([^>]*)/?>', svg_text):
        fm = re.search(r'\bfill="([^"]+)"', attrs)
        col = parse_color(fm.group(1)) if fm else None
        if col is None:
            continue
        groups.setdefault(col, []).extend(_elem_subpaths(tag, attrs))

    canvas = Image.new("RGBA", (out_w, out_h), (0, 0, 0, 0))
    for col, subs in groups.items():
        mask = rasterize(subs, W, H, scale, tx, ty).resize((out_w, out_h), Image.LANCZOS)
        solid = Image.new("RGBA", (out_w, out_h), col + (255,))
        canvas.paste(solid, (0, 0), mask)
    return canvas

# =============================== drive ===================================
SPECS = [
    ("logo-dark.svg",  "logo-dark.png",  1600),
    ("logo-light.svg", "logo-light.png", 1600),
    ("logo-mark.svg",  "logo-mark.png",  1600),
]

def build():
    for src, dst, out_w in SPECS:
        svg = open(os.path.join(BRAND, src)).read()
        vbx, vby, vbw, vbh = [float(v) for v in
                              re.search(r'viewBox="([\d.\s-]+)"', svg).group(1).split()]
        out_h = int(round(out_w * vbh / vbw))
        img = render_svg(svg, out_w, out_h)
        outp = os.path.join(BRAND, dst)
        img.save(outp, optimize=True)
        print("wrote", outp, img.size)

if __name__ == "__main__":
    build()
