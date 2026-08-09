#!/usr/bin/env python3
"""Generate the welcome image for the first page of the Tally questionnaire.

Run from repo root:  python3 scripts/gen-tally-welcome.py
Output: assets/images/tally-welcome.png  (2800x880)

In-form images run the full width of the form, so Tally recommends 1400px;
this renders 2x that for wide layouts and retina. Pass --width to change it —
the layout is a 1400x440 grid scaled to fit, so composition is size-independent.

Deliberately plain: the page background #faf9fc, the colour brand lockup, and
one line of Inky #220940 Lexend. No texture, no gradient, no second heading —
the cover already carries the title, and this sits directly above the intro
copy, where anything busier competes with the text the candidate has to read.

Reuses the SVG rasteriser, Lexend loader and palette from gen-fb-banner.py.
"""
import argparse, importlib.util, os, re
from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# gen-fb-banner has a hyphen in its name, so it can't be imported by name.
_spec = importlib.util.spec_from_file_location(
    "gen_fb_banner", os.path.join(ROOT, "scripts", "gen-fb-banner.py"))
fb = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fb)

INKY, KWETLAL = fb.INKY, fb.KWETLAL
PAGE_BG = (0xFA, 0xF9, 0xFC)          # $color-bg in _sass/_variables.scss
LIVABLE = (0x5C, 0x18, 0xA4)          # $livable-purple
LOGO_SVG = os.path.join(fb.IMG, "brand", "logo.svg")

LINE = "Tell voters where you stand."

GW, GH = 1400, 440                    # design grid; all dimensions below are in these units
SS = 2                                # supersample factor, collapsed on the final resize


def fill_groups(svg_text):
    """Map each element fill colour -> the set of element indices using it.

    Read from the file rather than hard-coded, so a logo edit that adds or
    reorders a path can't silently recolour half the mark.
    """
    groups = {}
    for idx, (_, attrs) in enumerate(re.findall(r'<(path|rect)\b([^>]*)/?>', svg_text)):
        m = re.search(r'fill="([^"]+)"', attrs)
        groups.setdefault((m.group(1) if m else "none").lower(), set()).add(idx)
    return groups


def build(out_w=GW * 2, out_h=None):
    out_h = out_h or int(round(out_w * GH / GW))
    S = (out_w / GW) * SS                       # grid unit -> working pixels
    Wp, Hp = int(round(GW * S)), int(round(GH * S))

    img = Image.new("RGB", (Wp, Hp), PAGE_BG)
    draw = ImageDraw.Draw(img)

    svg = open(LOGO_SVG).read()
    groups = fill_groups(svg)
    logo_h = int(round(210 * S))
    logo_w = int(round(logo_h * 1988 / 1546))   # preserve viewBox aspect

    f_line = fb.font(int(38 * S), 600)
    gap = int(46 * S)
    line_h = int(38 * S)
    block_h = logo_h + gap + line_h
    top = (Hp - block_h) // 2

    for hexcode, colour in (("#5c18a4", LIVABLE), ("#d5adff", KWETLAL)):
        idx = groups.get(hexcode)
        if not idx:
            continue
        mask = fb.render_svg_group(svg, idx, logo_w, logo_h)
        img.paste(Image.new("RGB", (logo_w, logo_h), colour),
                  ((Wp - logo_w) // 2, top), mask)

    draw.text((Wp / 2, top + logo_h + gap + line_h / 2), LINE,
              font=f_line, fill=INKY, anchor="mm")

    img = img.resize((out_w, out_h), Image.LANCZOS)
    out = os.path.join(fb.IMG, "tally-welcome.png")
    img.save(out, optimize=True)
    print("wrote", out, img.size, "%.0f KB" % (os.path.getsize(out) / 1024))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--width", type=int, default=GW * 2,
                    help="output width in px (default 2800; Tally recommends 1400)")
    a = ap.parse_args()
    build(a.width)
