#!/usr/bin/env python3
"""Generate social/OG image and favicons from the brand logo.

Run from repo root:  python3 scripts/gen-social-assets.py
Regenerate whenever assets/images/logo.jpg or the brand changes.
"""
import os
from PIL import Image, ImageDraw, ImageFont, ImageChops

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMG = os.path.join(ROOT, "assets", "images")

INDIGO = (46, 27, 93)        # sampled from logo badge (#2e1b5d)
BG = (250, 250, 248)         # site $color-bg #fafaf8
TEXT = (17, 17, 17)          # $color-text
MUTED = (74, 74, 74)         # $color-muted
GRADES = [("A", (27, 122, 61)), ("B", (45, 106, 159)),
          ("C", (184, 134, 11)), ("F", (196, 30, 58))]

FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_REG = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


def f(path, size):
    return ImageFont.truetype(path, size)


def center_text(draw, cx, y, text, font, fill):
    l, t, r, b = draw.textbbox((0, 0), text, font=font)
    draw.text((cx - (r - l) / 2, y), text, font=font, fill=fill)
    return b - t


def logo_crop():
    im = Image.open(os.path.join(IMG, "logo.jpg")).convert("RGB")
    bg = Image.new("RGB", im.size, (255, 255, 255))
    diff = ImageChops.difference(im, bg).convert("L")
    bbox = diff.point(lambda p: 255 if p > 30 else 0).getbbox()
    return im.crop(bbox)


def make_og():
    W, H = 1200, 630
    card = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(card)
    # top accent bar (brand indigo)
    d.rectangle([0, 0, W, 12], fill=INDIGO)

    # logo, scaled to ~600px wide
    logo = logo_crop()
    lw = 600
    lh = round(logo.height * lw / logo.width)
    logo = logo.resize((lw, lh), Image.LANCZOS)
    card.paste(logo, ((W - lw) // 2, 90))

    cx = W // 2
    y = 90 + lh + 50
    y += center_text(d, cx, y, "Capital Region Candidate Scorecard",
                     f(FONT_BOLD, 52), INDIGO) + 24
    center_text(d, cx, y, "See where municipal election candidates stand",
                f(FONT_REG, 30), MUTED)

    # grade chips row near bottom
    chip, gap = 72, 22
    total = len(GRADES) * chip + (len(GRADES) - 1) * gap
    x = cx - total // 2
    cy = H - 130
    gf = f(FONT_BOLD, 40)
    for letter, color in GRADES:
        d.rounded_rectangle([x, cy, x + chip, cy + chip], radius=14, fill=color)
        l, t, r, b = d.textbbox((0, 0), letter, font=gf)
        d.text((x + (chip - (r - l)) / 2 - l, cy + (chip - (b - t)) / 2 - t),
               letter, font=gf, fill="white")
        x += chip + gap

    out = os.path.join(IMG, "og-image.png")
    card.save(out, optimize=True)
    print("wrote", out, card.size)


def make_favicons():
    # Brand monogram: white "LC" on indigo rounded square. Crisp at any size.
    base = 512
    icon = Image.new("RGBA", (base, base), (0, 0, 0, 0))
    d = ImageDraw.Draw(icon)
    d.rounded_rectangle([0, 0, base, base], radius=96, fill=INDIGO)
    mf = f(FONT_BOLD, 250)
    txt = "LC"
    l, t, r, b = d.textbbox((0, 0), txt, font=mf)
    d.text((base / 2 - (r - l) / 2 - l, base / 2 - (b - t) / 2 - t),
           txt, font=mf, fill="white")

    for size, name in [(32, "favicon-32x32.png"),
                       (16, "favicon-16x16.png"),
                       (180, "apple-touch-icon.png")]:
        icon.resize((size, size), Image.LANCZOS).save(os.path.join(IMG, name))
        print("wrote", name)
    # multi-res .ico
    icon.save(os.path.join(IMG, "favicon.ico"),
              sizes=[(16, 16), (32, 32), (48, 48)])
    print("wrote favicon.ico")


if __name__ == "__main__":
    make_og()
    make_favicons()
