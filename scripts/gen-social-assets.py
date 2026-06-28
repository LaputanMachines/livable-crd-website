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


def draw_pill(draw, cx, y, text, font, pad_x=40, height=66,
              fill=INDIGO, fg="white"):
    """Filled, fully-rounded call-to-action button centered on cx."""
    l, t, r, b = draw.textbbox((0, 0), text, font=font)
    tw, th = r - l, b - t
    w = tw + pad_x * 2
    x0 = cx - w / 2
    draw.rounded_rectangle([x0, y, x0 + w, y + height],
                           radius=height / 2, fill=fill)
    draw.text((cx - tw / 2 - l, y + (height - th) / 2 - t),
              text, font=font, fill=fg)
    return height


def make_og():
    W, H = 1200, 630
    card = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(card)
    cx = W // 2
    # top accent bar (brand indigo)
    d.rectangle([0, 0, W, 12], fill=INDIGO)

    # logo wordmark, scaled to ~480px wide
    logo = logo_crop()
    lw = 480
    lh = round(logo.height * lw / logo.width)
    logo = logo.resize((lw, lh), Image.LANCZOS)

    head_font = f(FONT_BOLD, 50)
    sub_font = f(FONT_REG, 28)
    cta_font = f(FONT_BOLD, 30)
    head_txt = "Capital Region Candidate Scorecard"
    sub_txt = "See where candidates stand before you vote"
    cta_txt = "View the scorecard at livablecrd.ca  →"  # explicit CTA

    def text_h(font, txt):
        l, t, r, b = d.textbbox((0, 0), txt, font=font)
        return b - t

    # Vertically center the whole stack (logo, heading, subtitle, grade chips, CTA).
    chip = 64
    cta_h = 66
    g_logo, g_head, g_sub, g_chips = 38, 18, 32, 34
    stack = (lh + g_logo + text_h(head_font, head_txt) + g_head
             + text_h(sub_font, sub_txt) + g_sub + chip + g_chips + cta_h)
    y = max(40, (H - stack) // 2)

    card.paste(logo, ((W - lw) // 2, y))
    y += lh + g_logo
    y += center_text(d, cx, y, head_txt, head_font, INDIGO) + g_head
    y += center_text(d, cx, y, sub_txt, sub_font, MUTED) + g_sub

    # grade chips row
    gap = 20
    total = len(GRADES) * chip + (len(GRADES) - 1) * gap
    x = cx - total // 2
    gf = f(FONT_BOLD, 36)
    for letter, color in GRADES:
        d.rounded_rectangle([x, y, x + chip, y + chip], radius=14, fill=color)
        l, t, r, b = d.textbbox((0, 0), letter, font=gf)
        d.text((x + (chip - (r - l)) / 2 - l, y + (chip - (b - t)) / 2 - t),
               letter, font=gf, fill="white")
        x += chip + gap
    y += chip + g_chips

    # call-to-action button
    draw_pill(d, cx, y, cta_txt, cta_font, height=cta_h)

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
