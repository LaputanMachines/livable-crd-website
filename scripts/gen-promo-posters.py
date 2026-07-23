#!/usr/bin/env python3
"""Generate printable promo posters for Livable CRD.

Run from repo root:  python3 scripts/gen-promo-posters.py
Writes two letter-size (8.5x11") portrait SVG posters to assets/promo/:
  poster-dark.svg   Inky background, light logo, bold treatment
  poster-light.svg  Light background, full-colour logo + topic icons

Each poster embeds a scannable QR code (https://livablecrd.ca) and the Lexend
brand font (base64 @font-face) so it renders on-brand even on machines without
Lexend installed. SVG stays sharp at any print size.

Deps: segno (pip install segno). No system tools required.

The committed PNG versions (assets/promo/*.png, 300dpi letter) are rendered from
these SVGs with headless Chrome — regenerate after editing:
  for f in poster-dark poster-light; do
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless \
      --disable-gpu --force-device-scale-factor=3 --window-size=850,1100 \
      --default-background-color=00000000 \
      --screenshot="assets/promo/$f.png" "file://$PWD/assets/promo/$f.svg"
  done
"""
import os
import re
import base64

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMG = os.path.join(ROOT, "assets", "images")
BRAND = os.path.join(IMG, "brand")
ICONS = os.path.join(BRAND, "icons")
OUT = os.path.join(ROOT, "assets", "promo")

URL = "https://livablecrd.ca"

# ---- brand palette (from _sass/_variables.scss) -------------------------
INKY = "#220940"      # Inky Purple  — deep background
PURPLE = "#5C18A4"    # Livable Purple — primary brand colour
KWETLAL = "#D5ADFF"   # Kwetlal Purple — light accent
WHITE = "#FFFFFF"
BG_LIGHT = "#FAF9FC"  # site page background

LEXEND_CACHE = os.path.join(os.path.expanduser("~"), ".cache",
                            "livable-crd", "Lexend-var.ttf")


# ---- embed helpers ------------------------------------------------------
def font_face():
    """Return a <style> block embedding the Lexend variable font, or an empty
    string (graceful fallback to system fonts) if the cache is missing."""
    if not os.path.exists(LEXEND_CACHE):
        print("Lexend cache missing; posters will fall back to system fonts.")
        return ""
    with open(LEXEND_CACHE, "rb") as fh:
        b64 = base64.b64encode(fh.read()).decode("ascii")
    return (
        '<defs><style type="text/css">@font-face{'
        'font-family:"Lexend";font-style:normal;font-weight:100 900;'
        'src:url("data:font/ttf;base64,%s") format("truetype");}'
        "</style></defs>" % b64
    )


def embed_svg(path, x, y, w, h):
    """Nest an external SVG file as an inner <svg> positioned at x,y sized w x h,
    preserving its own viewBox and aspect ratio (centered)."""
    with open(path, "r", encoding="utf-8") as fh:
        raw = fh.read()
    m = re.search(r"<svg\b([^>]*)>(.*)</svg>", raw, re.DOTALL)
    attrs, inner = m.group(1), m.group(2)
    vb = re.search(r'viewBox="([^"]*)"', attrs)
    viewbox = vb.group(1) if vb else "0 0 100 100"
    return (
        '<svg x="%s" y="%s" width="%s" height="%s" viewBox="%s" '
        'preserveAspectRatio="xMidYMid meet" overflow="visible">%s</svg>'
        % (x, y, w, h, viewbox, inner)
    )


def qr_group(dark, x, y, size):
    """Build a QR code <g> for URL. `dark` is the module colour. The code fills
    a `size` x `size` box at x,y with a built-in quiet zone."""
    import segno
    qr = segno.make(URL, error="q")
    matrix = list(qr.matrix)
    n = len(matrix)
    border = 4  # quiet-zone modules
    total = n + border * 2
    unit = size / total
    rects = []
    for r, row in enumerate(matrix):
        for c, val in enumerate(row):
            if val:
                px = x + (c + border) * unit
                py = y + (r + border) * unit
                rects.append('<rect x="%.3f" y="%.3f" width="%.3f" '
                             'height="%.3f"/>' % (px, py, unit, unit))
    return ('<g fill="%s" shape-rendering="crispEdges">%s</g>'
            % (dark, "".join(rects)))


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def text(x, y, s, size, fill, weight=600, anchor="middle", spacing=None):
    ls = ' letter-spacing="%s"' % spacing if spacing else ""
    return ('<text x="%s" y="%s" text-anchor="%s" font-family="Lexend, '
            'system-ui, sans-serif" font-weight="%s" font-size="%s" '
            'fill="%s"%s>%s</text>'
            % (x, y, anchor, weight, size, fill, ls, esc(s)))


# ---- posters ------------------------------------------------------------
# Letter portrait: viewBox units are 1/100 inch, so 850 x 1100 == 8.5" x 11".
W, H = 850, 1100
CX = W / 2

HEAD = ["Where do your", "candidates stand?"]
SUB = ["A non-partisan candidate scorecard for",
       "Capital Region municipal elections."]
TOPICS = "Transit · Housing · Arts · Climate · Walking · Cycling · Health"
SCAN = "Scan to see the scorecard"
URL_TXT = "livablecrd.ca"


def poster_dark():
    p = ['<svg xmlns="http://www.w3.org/2000/svg" width="8.5in" height="11in" '
         'viewBox="0 0 %d %d" role="img" '
         'aria-label="Livable CRD candidate scorecard poster">' % (W, H)]
    p.append(font_face())
    # background + accent bars
    p.append('<rect width="%d" height="%d" fill="%s"/>' % (W, H, INKY))
    p.append('<rect x="0" y="0" width="%d" height="18" fill="%s"/>' % (W, KWETLAL))
    p.append('<rect x="0" y="%d" width="%d" height="34" fill="%s"/>'
             % (H - 34, W, KWETLAL))

    # logo (light lockup)
    lw = 270
    lh = lw * 1546 / 1988
    p.append(embed_svg(os.path.join(BRAND, "logo-light.svg"),
                       CX - lw / 2, 76, lw, lh))

    # eyebrow
    p.append(text(CX, 334, "CAPITAL REGION MUNICIPAL ELECTIONS", 20,
                  KWETLAL, weight=600, spacing="3"))

    # headline
    hy = 400
    for line in HEAD:
        p.append(text(CX, hy, line, 58, WHITE, weight=700))
        hy += 68

    # subhead
    sy = hy - 2
    for line in SUB:
        p.append(text(CX, sy, line, 26, KWETLAL, weight=400))
        sy += 36

    # QR card
    card_w, card_h = 448, 410
    cx0 = CX - card_w / 2
    cy0 = 592
    p.append('<rect x="%s" y="%s" width="%s" height="%s" rx="20" fill="%s"/>'
             % (cx0, cy0, card_w, card_h, WHITE))
    qr_size = 286
    p.append(qr_group(INKY, CX - qr_size / 2, cy0 + 30, qr_size))
    p.append(text(CX, cy0 + 348, SCAN, 26, INKY, weight=600))
    p.append(text(CX, cy0 + 386, URL_TXT, 30, PURPLE, weight=700))

    # footer
    p.append(text(CX, H - 58, "Non-partisan · community-built · no endorsements",
                  20, KWETLAL, weight=500))
    p.append("</svg>")
    return "".join(p)


def poster_light():
    p = ['<svg xmlns="http://www.w3.org/2000/svg" width="8.5in" height="11in" '
         'viewBox="0 0 %d %d" role="img" '
         'aria-label="Livable CRD candidate scorecard poster">' % (W, H)]
    p.append(font_face())
    p.append('<rect width="%d" height="%d" fill="%s"/>' % (W, H, BG_LIGHT))
    # inky frame
    p.append('<rect x="16" y="16" width="%d" height="%d" fill="none" '
             'stroke="%s" stroke-width="8" rx="10"/>' % (W - 32, H - 32, INKY))

    # logo (full colour)
    lw = 252
    lh = lw * 1546 / 1988
    p.append(embed_svg(os.path.join(BRAND, "logo.svg"),
                       CX - lw / 2, 56, lw, lh))

    # eyebrow
    p.append(text(CX, 296, "CAPITAL REGION MUNICIPAL ELECTIONS", 20,
                  PURPLE, weight=600, spacing="3"))

    # headline
    hy = 356
    for line in HEAD:
        p.append(text(CX, hy, line, 54, INKY, weight=700))
        hy += 62

    # subhead
    sy = hy - 4
    for line in SUB:
        p.append(text(CX, sy, line, 24, "#564a66", weight=400))
        sy += 32

    # topic icons row (colour)
    icon = 72
    gap = 36
    names = ["home-icon-colour.svg", "camas-icon-colour.svg",
             "symbols-icon-colour.svg"]
    total = len(names) * icon + (len(names) - 1) * gap
    ix = CX - total / 2
    iy = sy + 4
    for nm in names:
        p.append(embed_svg(os.path.join(ICONS, nm), ix, iy, icon, icon))
        ix += icon + gap

    # QR card
    card_w, card_h = 452, 372
    cx0 = CX - card_w / 2
    cy0 = iy + icon + 22
    p.append('<rect x="%s" y="%s" width="%s" height="%s" rx="20" fill="%s" '
             'stroke="%s" stroke-width="6"/>'
             % (cx0, cy0, card_w, card_h, WHITE, KWETLAL))
    qr_size = 258
    p.append(qr_group(INKY, CX - qr_size / 2, cy0 + 28, qr_size))
    p.append(text(CX, cy0 + 316, SCAN, 24, INKY, weight=600))
    p.append(text(CX, cy0 + 350, URL_TXT, 28, PURPLE, weight=700))

    # footer
    p.append(text(CX, H - 52, "Non-partisan · community-built · no endorsements",
                  20, "#564a66", weight=500))
    p.append("</svg>")
    return "".join(p)


def main():
    os.makedirs(OUT, exist_ok=True)
    for name, fn in (("poster-dark.svg", poster_dark),
                     ("poster-light.svg", poster_light)):
        out = os.path.join(OUT, name)
        with open(out, "w", encoding="utf-8") as fh:
            fh.write(fn())
        print("wrote", out, "(%d bytes)" % os.path.getsize(out))


if __name__ == "__main__":
    main()
