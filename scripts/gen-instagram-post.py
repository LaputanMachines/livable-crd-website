#!/usr/bin/env python3
"""Generate the square Instagram launch post for Livable CRD.

Run from repo root:  python3 scripts/gen-instagram-post.py
Writes assets/social/instagram-launch.png (1080x1080).

Uses the brand palette + Lexend font (cached from Google Fonts, DejaVu fallback)
and composites the white logo lockup on the Inky background, matching the
og-image / facebook-banner style.
"""
import os, urllib.request
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMG = os.path.join(ROOT, "assets", "images")
SOCIAL = os.path.join(ROOT, "assets", "social")

# ---- brand palette (from _sass/_variables.scss) -------------------------
INKY = (0x22, 0x09, 0x40)      # #220940  hero / page-header background
KWETLAL = (0xD5, 0xAD, 0xFF)   # #D5ADFF  light brand accent
WHITE = (255, 255, 255)
GRADES = [("A", (0x1b, 0x7a, 0x3d)), ("B", (0x2d, 0x6a, 0x9f)),
          ("C", (0xb8, 0x86, 0x0b)), ("F", (0xc4, 0x1e, 0x3a))]

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


def center(draw, cx, y, text, fnt, fill):
    l, t, r, b = draw.textbbox((0, 0), text, font=fnt)
    draw.text((cx - (r - l) / 2 - l, y), text, font=fnt, fill=fill)
    return b - t


def draw_arrow(draw, x, cy, length, color, weight=6):
    """Right-pointing arrow drawn as primitives (Lexend has no arrow glyph)."""
    x1 = x + length
    draw.line([(x, cy), (x1, cy)], fill=color, width=weight)
    head = length * 0.55
    draw.line([(x1 - head, cy - head * 0.6), (x1, cy)], fill=color, width=weight)
    draw.line([(x1 - head, cy + head * 0.6), (x1, cy)], fill=color, width=weight)


def draw_pill(draw, cx, y, text, fnt, pad_x=54, height=88, fill=KWETLAL, fg=INKY):
    l, t, r, b = draw.textbbox((0, 0), text, font=fnt)
    tw, th = r - l, b - t
    arrow_len = 40
    arrow_gap = 26
    content_w = tw + arrow_gap + arrow_len
    w = content_w + pad_x * 2
    x0 = cx - w / 2
    draw.rounded_rectangle([x0, y, x0 + w, y + height], radius=height / 2, fill=fill)
    tx = x0 + pad_x
    draw.text((tx - l, y + (height - th) / 2 - t), text, font=fnt, fill=fg)
    draw_arrow(draw, tx + tw + arrow_gap, y + height / 2, arrow_len, fg)
    return height


def make_instagram():
    S = 1080
    card = Image.new("RGB", (S, S), INKY)
    d = ImageDraw.Draw(card)
    cx = S // 2

    # Kwetlal accent bars, top and bottom.
    d.rectangle([0, 0, S, 16], fill=KWETLAL)
    d.rectangle([0, S - 28, S, S], fill=KWETLAL)

    # Brand logo: white vertical lockup on Inky, scaled by height.
    logo = Image.open(os.path.join(IMG, "brand", "logo-light.png")).convert("RGBA")
    lh = 300
    lw = round(logo.width * lh / logo.height)
    logo = logo.resize((lw, lh), Image.LANCZOS)

    eyebrow_font = font(30, 600)
    head_font = font(60, 700)
    sub_font = font(34, 400)
    chip_font = font(46, 700)
    cta_font = font(38, 700)

    eyebrow_txt = "N O W   L A U N C H I N G"
    head_lines = ["Capital Region", "Candidate Scorecard"]
    sub_lines = ["A non-partisan coalition grading candidates",
                 "on the issues that shape daily life."]
    cta_txt = "livablecrd.ca"

    def th(fnt, txt):
        l, t, r, b = d.textbbox((0, 0), txt, font=fnt)
        return b - t

    chip = 96
    cta_h = 88
    # gaps between stack elements
    g_eye, g_logo, g_head_line, g_head, g_sub_line, g_sub, g_chips = 34, 44, 12, 40, 10, 46, 46

    head_h = th(head_font, head_lines[0]) * len(head_lines) + g_head_line * (len(head_lines) - 1)
    sub_h = th(sub_font, sub_lines[0]) * len(sub_lines) + g_sub_line * (len(sub_lines) - 1)
    stack = (th(eyebrow_font, eyebrow_txt) + g_eye + lh + g_logo + head_h + g_head
             + sub_h + g_sub + chip + g_chips + cta_h)
    y = max(40, (S - stack) // 2)

    y += center(d, cx, y, eyebrow_txt, eyebrow_font, KWETLAL) + g_eye
    card.paste(logo, ((S - lw) // 2, y), logo)
    y += lh + g_logo
    for i, line in enumerate(head_lines):
        y += center(d, cx, y, line, head_font, WHITE)
        y += g_head_line if i < len(head_lines) - 1 else g_head
    for i, line in enumerate(sub_lines):
        y += center(d, cx, y, line, sub_font, KWETLAL)
        y += g_sub_line if i < len(sub_lines) - 1 else g_sub

    # grade chips row (letter-grade colours kept semantic, not rebranded)
    gap = 28
    total = len(GRADES) * chip + (len(GRADES) - 1) * gap
    x = cx - total // 2
    for letter, color in GRADES:
        d.rounded_rectangle([x, y, x + chip, y + chip], radius=20, fill=color)
        l, t, r, b = d.textbbox((0, 0), letter, font=chip_font)
        d.text((x + (chip - (r - l)) / 2 - l, y + (chip - (b - t)) / 2 - t),
               letter, font=chip_font, fill=WHITE)
        x += chip + gap
    y += chip + g_chips

    draw_pill(d, cx, y, cta_txt, cta_font, height=cta_h, fill=KWETLAL, fg=INKY)

    os.makedirs(SOCIAL, exist_ok=True)
    out = os.path.join(SOCIAL, "instagram-launch.png")
    card.save(out, optimize=True)
    print("wrote", out, card.size)


if __name__ == "__main__":
    make_instagram()
