#!/usr/bin/env python3
"""Generate the "go back" pointer image for the Tally questionnaire.

Run from repo root:  python3 scripts/gen-tally-back.py
Output: assets/tally/back.png  (2800x250)

A curved arrow sweeping up into the top-left corner, with one line of Lexend
beside it. Unlike every other in-form graphic here it is not decoration or a
section break: it points at a control. Tally puts its back arrow above the form
body at the left, so the tip has to sit near this image's own top-left corner
and aim off the edge, which is what fixes the whole composition - arrow hard
left, text to its right, and a strip short enough that the tip stays close to
the control it means.

That also means the size it renders at matters more than it does elsewhere. The
arrow fills nearly the whole strip rather than sitting in it as a tile-sized
icon: at in-form width a glyph drawn to the 86-unit tile metric reads as another
topic icon, and a candidate scanning the page has no reason to follow it.

The strip is half the height it started at. The arrow is drawn wide and shallow
rather than scaled down to suit, because the short version of this image is the
one where shrinking hurts: an arrow that loses half its height next to type that
keeps all of its own stops being the thing the eye follows and becomes a bullet
beside the sentence. Widening it holds its length, and a long flat sweep is the
more natural gesture in a strip this shape anyway.

Reuses the stroked-SVG renderer from gen-tally-categories.py, and the Lexend
loader and palette that file takes from gen-fb-banner.py, so the arrow is drawn
by the same code and in the same weight as the icons on every other page.
"""
import argparse, importlib.util, os
from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Every Tally asset lands here, separate from the site's own images.
OUT_DIR = os.path.join(ROOT, "assets", "tally")
os.makedirs(OUT_DIR, exist_ok=True)


def _load(name):
    """Import a sibling script by path; the hyphens block a normal import."""
    spec = importlib.util.spec_from_file_location(
        name.replace("-", "_"), os.path.join(ROOT, "scripts", "%s.py" % name))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

cat = _load("gen-tally-categories")
fb = cat.fb

INKY = cat.INKY
LIVABLE = cat.LIVABLE
PAGE_BG = cat.PAGE_BG

LINE = "Click here to go back at any time"

# Drawn in a 170x100 box rather than the icons' square 24, for two reasons: the
# arrowhead needs a fractional-unit tip to sit near 45 degrees and the 24-grid
# would round it into a visible kink, and the strip is far wider than it is tall,
# so the arrow has to be too. render_icon reads the viewBox, so it scales the
# same way the icons do.
#
# The shaft leaves the bottom right running almost flat, then lifts into the
# corner: a gesture rather than the shortest path, because a straight diagonal
# reads as "over there" and a candidate follows it to the edge of the image and
# stops, while a curve keeps the eye moving past the corner, which is where the
# control actually is. The bow is deliberately shallow - the first draft turned
# through most of a right angle and read as a hook, an object in its own right,
# instead of as a direction.
#
# The head is one three-point polyline through the tip, not two strokes meeting
# there, so render_icon's round join closes it the way the Feather icons close
# their corners.
ARROW = ('<svg viewBox="0 0 170 100">'
         '<path d="M164 84 C112 94, 56 54, 15 16"/>'
         '<path d="M21 38.2 L15 16 L37.6 20.3"/>'
         '</svg>')

VB_W, VB_H = 170, 100                 # the arrow's viewBox, needed to place it

# Lighter than the icons' 2-in-24 as a fraction of the glyph it draws. The tile
# glyphs are read at a glance in a row of six; this one is read alone and several
# times their size, where the Feather ratio thickens into a slab.
STROKE = 12.0

GW, GH = 1400, 125                    # design grid; all dimensions below are in these units
ARROW_W = 178                         # the arrow's width; its height follows the viewBox
# Tighter than the topic grids' 70, and for a reason those don't have: every
# unit of margin here is a unit between the tip and the control it points at.
SIDE = 56
GAP = 46                              # arrow to text
TEXT_SZ = 56


def build(out_w=GW * 2):
    S = out_w / GW                              # grid unit -> output pixels
    Wp, Hp = int(round(GW * S)), int(round(GH * S))

    img = Image.new("RGB", (Wp, Hp), PAGE_BG)
    draw = ImageDraw.Draw(img)

    # render_icon always returns a square mask, scaled to the viewBox's longer
    # side, so a viewBox wider than it is tall leaves the bottom of that square
    # empty. Centre the drawn height, not the square it arrives in, or the arrow
    # hangs off the top of the strip.
    aw = int(round(ARROW_W * S))
    ah = aw * VB_H / VB_W
    ax = int(round(SIDE * S))
    ay = int(round((Hp - ah) / 2))
    mask = cat.render_icon(ARROW, aw, stroke=STROKE)
    img.paste(Image.new("RGB", (aw, aw), LIVABLE), (ax, ay), mask)

    # Shrink to fit rather than wrap: two lines beside the arrow would put the
    # second one below the tip, and the sentence is short enough that it never
    # has to.
    tx = int(round((SIDE + ARROW_W + GAP) * S))
    avail = Wp - tx - int(round(SIDE * S))
    sz = int(TEXT_SZ * S)
    f = fb.font(sz, 500)
    while draw.textlength(LINE, font=f) > avail and sz > int(28 * S):
        sz -= max(1, int(S))
        f = fb.font(sz, 500)
    draw.text((tx, Hp / 2), LINE, font=f, fill=INKY, anchor="lm")

    out = os.path.join(OUT_DIR, "back.png")
    img.save(out, optimize=True)
    print("wrote", out, img.size, "%.0f KB" % (os.path.getsize(out) / 1024))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--width", type=int, default=GW * 2,
                    help="output width in px (default 2800; Tally recommends 1400)")
    a = ap.parse_args()
    build(a.width)
