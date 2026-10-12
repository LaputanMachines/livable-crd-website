#!/usr/bin/env python3
"""Render Livable CRD logo assets sized for Google Ads.

Run from repo root:  python3 scripts/gen-google-ads-logos.py
Outputs (PNG, opaque background) in assets/promo/google-ads/:

  Square logo, 1:1, 1200x1200 (Google min 128x128)
    logo-square-white.png        full-colour stacked logo on white
    logo-square-inky.png         white + Kwetlal logo on Inky
    logo-square-mark-white.png   icon-only mark on white (reads at small sizes)
  Landscape logo, 4:1, 1200x300 (Google min 512x128)
    logo-landscape-white.png     mark beside stacked wordmark, on white
    logo-landscape-inky.png      same, white + Kwetlal on Inky

Google Ads (Performance Max, responsive display, Demand Gen, Search business
logo) accepts PNG/JPG up to 5120 KB. Google may crop near the edges or show a
square logo inside a circle, so artwork stays inside a centred safe area.

The SVG rasteriser is borrowed from gen-logo-pngs.py (pure Pillow; this box
has no SVG CLI tools).
"""
import importlib.util, os, re
from PIL import Image

ROOT  = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BRAND = os.path.join(ROOT, "assets", "images", "brand")
OUT   = os.path.join(ROOT, "assets", "promo", "google-ads")

_spec = importlib.util.spec_from_file_location(
    "gen_logo_pngs", os.path.join(ROOT, "scripts", "gen-logo-pngs.py"))
_glp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_glp)
render_svg = _glp.render_svg

WHITE  = (255, 255, 255)
INKY   = (0x22, 0x09, 0x40)   # #220940
LIVABLE = "#5C18A4"

# In logo.svg (viewBox 0 0 1988 1546) the mark ends near y=910 and the
# wordmark starts at y=965; split between them to get the two parts.
SPLIT_Y = 935 / 1546
RENDER_W = 3200   # oversample, then LANCZOS down to final size


def logo_svg(on_dark):
    svg = open(os.path.join(BRAND, "logo.svg")).read()
    # Dark backgrounds: Livable Purple parts go white, camas stays Kwetlal.
    return svg.replace(f'fill="{LIVABLE}"', 'fill="white"') if on_dark else svg


def render_full(on_dark):
    svg = logo_svg(on_dark)
    vbw, vbh = [float(v) for v in
                re.search(r'viewBox="([\d.\s-]+)"', svg).group(1).split()][2:]
    return render_svg(svg, RENDER_W, int(round(RENDER_W * vbh / vbw)))


def trim(img):
    return img.crop(img.getbbox())


def fit(img, max_w, max_h):
    s = min(max_w / img.width, max_h / img.height)
    return img.resize((max(1, round(img.width * s)), max(1, round(img.height * s))),
                      Image.LANCZOS)


def place_center(canvas, img):
    canvas.paste(img, ((canvas.width - img.width) // 2,
                       (canvas.height - img.height) // 2), img)


def split(full):
    y = round(full.height * SPLIT_Y)
    return trim(full.crop((0, 0, full.width, y))), trim(full.crop((0, y, full.width, full.height)))


def square(full, bg, box):
    canvas = Image.new("RGBA", (1200, 1200), bg + (255,))
    place_center(canvas, fit(trim(full), box, box))
    return canvas


def landscape(full, bg):
    W, H = 1200, 300
    mark, word = split(full)
    content_h = 204                       # ~68% of height; safe from edge crops
    mark = fit(mark, 10_000, content_h)
    word = fit(word, 10_000, round(content_h * 0.9))
    gap = 56
    total_w = mark.width + gap + word.width
    if total_w > W * 0.86:                # keep side margins
        s = W * 0.86 / total_w
        mark = fit(mark, round(mark.width * s), H)
        word = fit(word, round(word.width * s), H)
        gap = round(gap * s)
        total_w = mark.width + gap + word.width
    canvas = Image.new("RGBA", (W, H), bg + (255,))
    x = (W - total_w) // 2
    canvas.paste(mark, (x, (H - mark.height) // 2), mark)
    # bottom-align the wordmark with the mark's baseline, like the stacked logo
    canvas.paste(word, (x + mark.width + gap, (H + mark.height) // 2 - word.height), word)
    return canvas


def save(img, name):
    path = os.path.join(OUT, name)
    img.convert("RGB").save(path, optimize=True)
    kb = os.path.getsize(path) / 1024
    print(f"wrote {os.path.relpath(path, ROOT)} {img.size} {kb:.0f} KB")


def build():
    os.makedirs(OUT, exist_ok=True)
    colour, light = render_full(False), render_full(True)
    mark, _ = split(colour)

    # Square: logo diagonal stays inside the inscribed circle (circle crops).
    save(square(colour, WHITE, 860), "logo-square-white.png")
    save(square(light, INKY, 860), "logo-square-inky.png")
    canvas = Image.new("RGBA", (1200, 1200), WHITE + (255,))
    place_center(canvas, fit(mark, 960, 960))
    save(canvas, "logo-square-mark-white.png")

    save(landscape(colour, WHITE), "logo-landscape-white.png")
    save(landscape(light, INKY), "logo-landscape-inky.png")


if __name__ == "__main__":
    build()
