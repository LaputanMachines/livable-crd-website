#!/usr/bin/env python3
"""Generate the header (cover) image for the Tally candidate questionnaire.

Run from repo root:  python3 scripts/gen-tally-header.py
Output: assets/tally/header.png  (3000x1000 by default)

Tally asks for a cover "at least 1500 pixels wide" and states no upper bound,
and the cover's aspect ratio changes with the window width — so this renders at
2x that minimum and keeps the content in a centred band that survives the crop.
Pass --width to change it; the layout is a 1500x500 grid scaled to fit, so the
composition is identical at any size.

Same theme as the site hero and the Facebook banner: Inky-purple background,
16px dot texture, the white brand logo with the camas mark in Kwetlal purple,
and a Kwetlal bottom bar. The lockup is horizontal rather than stacked, because
a tall lockup is the first thing a wide crop eats.

The SVG rasteriser, the Lexend loader and the palette all come from
gen-fb-banner.py; this script only composes. Everything is drawn at 2x the
output and downsampled, so type and logo edges stay clean.
"""
import argparse, importlib.util, os
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

INKY, KWETLAL, WHITE = fb.INKY, fb.KWETLAL, fb.WHITE
IMG = fb.IMG

TITLE    = "Candidate Questionnaire"
SUBTITLE = "Capital Region municipal election  ·  livablecrd.ca"

GW, GH = 1500, 500         # design grid; every dimension below is in these units
SS = 2                     # supersample factor, collapsed on the final resize


def background(Wp, Hp, S):
    """Inky base + hero dot texture + bottom darken + top-left light wash."""
    img = Image.new("RGBA", (Wp, Hp), INKY + (255,))

    tile_px = max(1, int(round(16 * S)))
    tile = Image.new("RGBA", (tile_px, tile_px), (0, 0, 0, 0))
    td = ImageDraw.Draw(tile)
    da = int(255 * 0.5 * 0.26)
    for cx, cy in [(2, 2), (10, 2), (6, 10), (14, 10)]:
        cx, cy, r = cx * S, cy * S, 1 * S
        td.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(255, 255, 255, da))
    tex = Image.new("RGBA", (Wp, Hp), (0, 0, 0, 0))
    for yy in range(0, Hp, tile_px):
        for xx in range(0, Wp, tile_px):
            tex.paste(tile, (xx, yy), tile)
    img = Image.alpha_composite(img, tex)

    # Both overlays are smooth gradients, so build them small and let LANCZOS
    # do the interpolation — a per-pixel loop at 6000x2000 costs ~40s for an
    # identical result.
    gw, gh = 120, 60
    dov = Image.new("L", (1, gh)); dp = dov.load()
    for yy in range(gh):
        dp[0, yy] = min(58, int(42 * (yy / gh) ** 1.6))
    lov = Image.new("L", (gw, gh)); lp = lov.load()
    for yy in range(gh):
        for xx in range(gw):
            r = ((xx / gw) ** 2 + (yy / gh) ** 2) ** 0.5
            lp[xx, yy] = int(max(0, 14 * (1 - r / 0.9)))

    dark  = Image.new("RGBA", (Wp, Hp), (0, 0, 0, 255))
    dark.putalpha(dov.resize((Wp, Hp), Image.BICUBIC))
    light = Image.new("RGBA", (Wp, Hp), (255, 255, 255, 255))
    light.putalpha(lov.resize((Wp, Hp), Image.BICUBIC))
    img = Image.alpha_composite(img, dark)
    return Image.alpha_composite(img, light).convert("RGB")


def build(out_w=GW * 2, out_h=None):
    out_h = out_h or int(round(out_w * GH / GW))
    S = (out_w / GW) * SS                 # grid unit -> working pixels
    Wp, Hp = int(round(GW * S)), int(round(GH * S))

    header = background(Wp, Hp, S)
    draw = ImageDraw.Draw(header)

    # Element order in logo-light.svg: 0 wordmark, 1 L-rect, 2 house, 3 tree,
    # 4 rect, 5-8 camas burst. Camas is recoloured Kwetlal, the rest stay white.
    svg = open(fb.LOGO_SVG).read()
    logo_h = int(round(238 * S))
    logo_w = int(round(logo_h * 1988 / 1546))          # preserve viewBox aspect

    # The lockup fills the canvas rather than hiding in a safe centre band. That
    # relies on the form's custom CSS showing the cover whole:
    #
    #   .tally-form-cover     { background-color: #220940; height: auto !important; }
    #   .tally-form-cover img { object-fit: contain !important; max-height: 280px; }
    #
    # Tally's default is to scale the cover to the box width and centre-crop, which
    # on a wide viewport shows only the middle 3/N of a 3:1 image — content this
    # size gets clipped and renders oversized. Shrink it back to roughly 30% of the
    # canvas height if that CSS ever comes off.
    margin, gap, rule_w = 120 * S, 50 * S, max(1, int(round(3 * S)))
    fixed = logo_w + gap + rule_w + gap
    title_sz, sub_sz = int(58 * S), int(25 * S)
    while title_sz > 40 * S:
        f_title, f_sub = fb.font(title_sz, 700), fb.font(sub_sz, 500)
        text_w = max(draw.textlength(TITLE, font=f_title),
                     draw.textlength(SUBTITLE, font=f_sub))
        if fixed + text_w <= Wp - 2 * margin:
            break
        title_sz -= int(2 * S)
        sub_sz = max(int(22 * S), int(title_sz * 0.41))

    block_w = fixed + text_w
    x = int((Wp - block_w) / 2)
    cy = int(Hp // 2 - 5 * S)                     # optical centre, above the bar

    ly = cy - logo_h // 2
    white_mask = fb.render_svg_group(svg, {0, 1, 2, 3, 4}, logo_w, logo_h)
    camas_mask = fb.render_svg_group(svg, {5, 6, 7, 8}, logo_w, logo_h)
    header.paste(Image.new("RGB", (logo_w, logo_h), WHITE),   (x, ly), white_mask)
    header.paste(Image.new("RGB", (logo_w, logo_h), KWETLAL), (x, ly), camas_mask)

    rx = int(x + logo_w + gap)
    rule_h = int(logo_h * 0.72)
    rule = Image.new("RGBA", (rule_w, rule_h), KWETLAL + (150,))
    header.paste(rule, (rx, cy - rule_h // 2), rule)

    tx = int(rx + rule_w + gap)
    line_gap = int(title_sz * 0.34)
    t_top = cy - (title_sz + line_gap + sub_sz) // 2
    draw.text((tx, t_top), TITLE, font=f_title, fill=WHITE, anchor="la")
    draw.text((tx, t_top + title_sz + line_gap), SUBTITLE,
              font=f_sub, fill=KWETLAL, anchor="la")

    bar = int(round(12 * S))
    draw.rectangle([0, Hp - bar, Wp, Hp], fill=KWETLAL)      # Kwetlal bottom bar

    header = header.resize((out_w, out_h), Image.LANCZOS)
    out = os.path.join(OUT_DIR, "header.png")
    header.save(out, optimize=True)
    print("wrote", out, header.size,
          "%.0f KB" % (os.path.getsize(out) / 1024))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--width", type=int, default=GW * 2,
                    help="output width in px (default 3000; Tally's minimum is 1500)")
    a = ap.parse_args()
    build(a.width)
