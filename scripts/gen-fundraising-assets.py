#!/usr/bin/env python3
"""Generate the fundraising social images for coalition partners.

Run from repo root:  python3 scripts/gen-fundraising-assets.py
Writes to assets/promo/:
  donate-square.png     1080x1080  Instagram / Facebook feed, dark treatment
  donate-landscape.png  1200x630   link cards, newsletters, slides, light

Both carry a QR code pointing at the site's own donate page (not the Action
Network URL directly) so the landing page still explains the contribution rules
before anyone gives, and so the destination can change without reprinting the
image.

Rendered with Pillow rather than SVG + a headless browser: these are raster
uploads, and this machine has no SVG rasteriser. Brand font is Lexend, cached
from Google Fonts on first run (DejaVu fallback offline).

Deps: pillow, segno.
"""
import os
import urllib.request

import segno
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BRAND = os.path.join(ROOT, "assets", "images", "brand")
OUT = os.path.join(ROOT, "assets", "promo")

DONATE_URL = "https://livablecrd.ca/donate/"
DONATE_TXT = "livablecrd.ca/donate"

# ---- brand palette (from _sass/_variables.scss) -------------------------
INKY = (0x22, 0x09, 0x40)      # #220940  hero / page-header background
PURPLE = (0x5C, 0x18, 0xA4)    # #5C18A4  primary brand colour
KWETLAL = (0xD5, 0xAD, 0xFF)   # #D5ADFF  light brand accent
WHITE = (255, 255, 255)
BG_LIGHT = (0xFA, 0xF9, 0xFC)  # site page background
MUTED = (0x56, 0x4A, 0x66)     # body copy on light surfaces

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


def font(sz, wght=600):
    f = ImageFont.truetype(_FONT, sz)
    try:
        f.set_variation_by_axes([wght])
    except Exception:
        pass
    return f


# ---- drawing helpers ----------------------------------------------------
def center(draw, cx, y, text, fnt, fill):
    """Draw `text` horizontally centred on cx with its cap-top at y."""
    l, t, r, b = draw.textbbox((0, 0), text, font=fnt)
    draw.text((cx - (r - l) / 2 - l, y - t), text, font=fnt, fill=fill)


def left(draw, x, y, text, fnt, fill):
    l, t, r, b = draw.textbbox((0, 0), text, font=fnt)
    draw.text((x - l, y - t), text, font=fnt, fill=fill)
    return r - l


def tracked(draw, cx, y, text, fnt, fill, track):
    """Letter-spaced text centred on cx. Pillow has no tracking, so lay the
    glyphs out one at a time and add `track` px after each."""
    widths = [draw.textlength(ch, font=fnt) for ch in text]
    total = sum(widths) + track * (len(text) - 1)
    _, t, _, _ = draw.textbbox((0, 0), text, font=fnt)
    x = cx - total / 2
    for ch, w in zip(text, widths):
        draw.text((x, y - t), ch, font=fnt, fill=fill)
        x += w + track


def paste_logo(img, name, box_h, cx, y):
    """Composite a transparent brand logo PNG scaled to `box_h` tall, centred
    on cx with its top at y. Returns the height consumed."""
    logo = Image.open(os.path.join(BRAND, name)).convert("RGBA")
    w = round(logo.width * box_h / logo.height)
    logo = logo.resize((w, box_h), Image.LANCZOS)
    img.paste(logo, (round(cx - w / 2), y), logo)
    return box_h


def qr_matrix(url):
    """QR modules as a list of rows of bools, no quiet zone. Error level Q so a
    partner can crop or overlay a little without breaking the scan."""
    return [list(row) for row in segno.make(url, error="q").matrix]


def draw_qr(draw, url, x, y, size, dark=INKY):
    """Draw a QR filling a `size` box at x,y, including a 4-module quiet zone.
    Module edges are snapped to whole pixels so no scanner sees a soft edge."""
    m = qr_matrix(url)
    border = 4
    total = len(m) + border * 2
    unit = size / total
    for r, row in enumerate(m):
        for c, on in enumerate(row):
            if not on:
                continue
            px = x + (c + border) * unit
            py = y + (r + border) * unit
            draw.rectangle([round(px), round(py),
                            round(px + unit) - 1, round(py + unit) - 1],
                           fill=dark)


# ---- copy ---------------------------------------------------------------
EYEBROW = "COMMUNITY FUNDED, NON-PARTISAN"
HEAD = ["Fund the questions", "candidates answer."]
SUB = ["Livable CRD is volunteer-run. Donations pay for the",
       "questionnaire, the grading, and the published scorecard."]
SCAN = "Scan to donate"
RULES = "Individual donations only. No corporate, union, or developer money."


def make_square():
    """1080x1080, Inky ground. The workhorse: Instagram and Facebook feeds."""
    W = H = 1080
    cx = W / 2
    img = Image.new("RGB", (W, H), INKY)
    d = ImageDraw.Draw(img)

    d.rectangle([0, 0, W, 13], fill=KWETLAL)
    d.rectangle([0, H - 26, W, H], fill=KWETLAL)

    paste_logo(img, "logo-light.png", 170, cx, 54)

    tracked(d, cx, 266, EYEBROW, font(23, 600), KWETLAL, 4)

    y = 318
    for line in HEAD:
        center(d, cx, y, line, font(62, 700), WHITE)
        y += 76

    y += 24
    for line in SUB:
        center(d, cx, y, line, font(24, 400), KWETLAL)
        y += 36

    # QR card. White ground gives the scanner the contrast it needs; the code
    # itself is Inky rather than black so it still reads as brand, not clip-art.
    card_w, card_h = 520, 376
    cx0, cy0 = cx - card_w / 2, 586
    d.rounded_rectangle([cx0, cy0, cx0 + card_w, cy0 + card_h],
                        radius=24, fill=WHITE)
    qr = 244
    draw_qr(d, DONATE_URL, cx - qr / 2, cy0 + 28, qr)
    center(d, cx, cy0 + 286, SCAN, font(25, 600), INKY)
    center(d, cx, cy0 + 322, DONATE_TXT, font(29, 700), PURPLE)

    center(d, cx, H - 80, RULES, font(20, 500), KWETLAL)
    return img


def make_landscape():
    """1200x630, light ground. Link previews, newsletter headers, slides: a
    two-column split so the copy stays readable at feed-thumbnail size."""
    W, H = 1200, 630
    img = Image.new("RGB", (W, H), BG_LIGHT)
    d = ImageDraw.Draw(img)

    d.rounded_rectangle([10, 10, W - 11, H - 11], radius=14,
                        outline=INKY, width=7)

    # right column: QR card, sized first so the text column knows its room
    card_w, card_h = 356, 424
    cx0, cy0 = W - 76 - card_w, (H - card_h) / 2
    d.rounded_rectangle([cx0, cy0, cx0 + card_w, cy0 + card_h],
                        radius=20, fill=WHITE, outline=KWETLAL, width=6)
    qr = 250
    qcx = cx0 + card_w / 2
    draw_qr(d, DONATE_URL, qcx - qr / 2, cy0 + 34, qr)
    center(d, qcx, cy0 + 310, SCAN, font(23, 600), INKY)
    center(d, qcx, cy0 + 346, DONATE_TXT, font(25, 700), PURPLE)

    # left column
    x = 76
    logo = Image.open(os.path.join(BRAND, "logo-dark.png")).convert("RGBA")
    lh = 104
    lw = round(logo.width * lh / logo.height)
    logo = logo.resize((lw, lh), Image.LANCZOS)
    img.paste(logo, (x, 74), logo)

    f = font(19, 600)
    widths = [d.textlength(ch, font=f) for ch in EYEBROW]
    xe = x
    _, t, _, _ = d.textbbox((0, 0), EYEBROW, font=f)
    for ch, w in zip(EYEBROW, widths):
        d.text((xe, 210 - t), ch, font=f, fill=PURPLE)
        xe += w + 3

    y = 254
    for line in ["Fund the questions", "candidates answer."]:
        left(d, x, y, line, font(48, 700), INKY)
        y += 60

    y += 14
    for line in ["Livable CRD is volunteer-run. Donations pay",
                 "to send the questionnaire, grade the answers,",
                 "and publish the scorecard before you vote."]:
        left(d, x, y, line, font(21, 400), MUTED)
        y += 31

    left(d, x, H - 116, "Individual donations only.", font(18, 600), INKY)
    left(d, x, H - 90, "No corporate, union, or developer money.",
         font(18, 400), MUTED)
    return img


def main():
    os.makedirs(OUT, exist_ok=True)
    for name, fn in (("donate-square.png", make_square),
                     ("donate-landscape.png", make_landscape)):
        path = os.path.join(OUT, name)
        fn().save(path, optimize=True)
        print("wrote", path, "(%d bytes)" % os.path.getsize(path))


if __name__ == "__main__":
    main()
