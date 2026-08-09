#!/usr/bin/env python3
"""Generate the form logo for the Tally candidate questionnaire.

Run from repo root:  python3 scripts/gen-tally-logo.py
Output: assets/images/tally-logo.png  (512x512; Tally asks for a square, min 200)

The brand mark in Inky purple #220940 — the base colour of tally-header.png —
on the site page background #faf9fc ($color-bg), a faint lavender off-white.
Icon only: the wordmark is unreadable once Tally crops to a circle.

Tally masks the logo to a circle, so the mark is sized by its *diagonal*, not
its width: the corners of its bounding box sit at PAD of the circle's radius,
which leaves clear padding all the way round rather than only at the sides.

Reuses the SVG rasteriser and palette from gen-fb-banner.py.
"""
import argparse, importlib.util, os, re
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# gen-fb-banner has a hyphen in its name, so it can't be imported by name.
_spec = importlib.util.spec_from_file_location(
    "gen_fb_banner", os.path.join(ROOT, "scripts", "gen-fb-banner.py"))
fb = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fb)

INKY, WHITE = fb.INKY, fb.WHITE
PAGE_BG = (0xFA, 0xF9, 0xFC)   # $color-bg in _sass/_variables.scss
MARK_SVG = os.path.join(fb.IMG, "brand", "logo-mark.svg")

PAD = 0.66          # bounding-box corners as a fraction of the circle's radius


def _zero_origin(svg_text):
    """Rewrite a viewBox with a non-zero origin to start at 0 0.

    render_svg_group() reads only the viewBox width/height and ignores min-x /
    min-y, so logo-mark's `viewBox="10 35 2000 890"` would push the mark past
    the bottom-right of the canvas and clip it. Growing the box instead of
    translating keeps every path inside; the slack is cropped off below.
    """
    m = re.search(r'viewBox="([\d.\s-]+)"', svg_text)
    minx, miny, w, h = [float(v) for v in m.group(1).split()]
    return svg_text.replace(m.group(0),
                            'viewBox="0 0 %g %g"' % (minx + w, miny + h))


def build(size=512, on_inky=False):
    svg = _zero_origin(open(MARK_SVG).read())
    n_el = len(re.findall(r'<(?:path|rect)\b', svg))

    # Over-render, then crop to the ink: the true bounds of the mark aren't the
    # viewBox, and cropping is what makes the circle padding exact.
    canvas_w = size * 3
    canvas_h = int(canvas_w * 940 / 2030)
    mask = fb.render_svg_group(svg, set(range(n_el)), canvas_w, canvas_h)
    mask = mask.crop(mask.getbbox())

    w, h = mask.size
    a = w / h
    diag = PAD * size                      # = 2 * PAD * radius
    mw = int(round(diag * a / (a * a + 1) ** 0.5))
    mh = max(1, int(round(mw / a)))
    mask = mask.resize((mw, mh), Image.LANCZOS)

    bg, ink = (INKY, WHITE) if on_inky else (PAGE_BG, INKY)
    logo = Image.new("RGB", (size, size), bg)
    logo.paste(Image.new("RGB", (mw, mh), ink),
               ((size - mw) // 2, (size - mh) // 2), mask)

    out = os.path.join(fb.IMG,
                       "tally-logo-inky.png" if on_inky else "tally-logo.png")
    logo.save(out, optimize=True)
    print("wrote", out, logo.size, "mark %dx%d" % (mw, mh),
          "%.0f KB" % (os.path.getsize(out) / 1024))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--size", type=int, default=512,
                    help="square output size in px (default 512; Tally's minimum is 200)")
    ap.add_argument("--on-inky", action="store_true",
                    help="white mark on Inky instead of Inky mark on #faf9fc")
    a = ap.parse_args()
    build(a.size, a.on_inky)
