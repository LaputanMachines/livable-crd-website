#!/usr/bin/env python3
"""Generate the topic-grid images for the Tally questionnaire.

Run from repo root:
    python3 scripts/gen-tally-categories.py                    -> categories.png
    python3 scripts/gen-tally-categories.py --set general      -> general.png
Output: assets/tally/  (2800x800 for a two-row set, 2800x448 for one row)

An icon-and-label grid on the page background #faf9fc with Inky #220940
labels, sized 2x Tally's recommended 1400px in-form width; --width to change
it. Canvas height follows the row count, so every set shares one set of metrics.

Only `categories` reads _data/subjects.yml, so that graphic and the scorecard
can't drift apart. Every other set defines its icons inline below, because each
one describes the questions in a single block rather than a topic: `general` is
GEN-01 and GEN-02, `walking` is WLK-01 to WLK-04, `housekeeping` is the
internal block (HK-01, HK-02), never scored and never published bar one answer,
`info` is the pre-start briefing, and `conduct` summarises the code of conduct
page.

The icons need a *stroke* renderer, which gen-fb-banner.py's fill rasteriser
doesn't do: they're 24x24 Feather-style outlines (`stroke="currentColor"`,
round caps and joins) built from arcs and circles the fill parser doesn't
handle either. So this file carries its own small path parser (arcs and
circles included) and strokes the flattened polylines with Pillow at 4x,
then downsamples. Only the palette and the Lexend loader come from
gen-fb-banner.py.
"""
import argparse, importlib.util, math, os, re
import yaml
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

INKY = fb.INKY
LIVABLE = (0x5C, 0x18, 0xA4)          # $livable-purple
PAGE_BG = (0xFA, 0xF9, 0xFC)          # $color-bg in _sass/_variables.scss

# Deliberately not $grade-a (#1b7a3d), the only green the site owns. That one is
# the colour of an A on the scorecard, and _variables.scss keeps the grade ramp
# semantic on purpose: "they convey data, not brand identity." Ten topic icons
# wearing it on the page that follows a candidate's submission is a sentence
# nobody meant to write. This is a brighter UI-tick green that reads as done
# rather than as a grade.
CHECK_GREEN = (0x16, 0xA3, 0x4A)

ICON_DIR = os.path.join(fb.IMG, "icons")
SUBJECTS = os.path.join(ROOT, "_data", "subjects.yml")

# Questionnaire categories, in the order finalize.py ships them. Housekeeping
# is internal-only and has no subject entry, so it can't appear here by
# accident; every other name must resolve against subjects.yml.
CATEGORIES = ["General", "Walking", "Rolling & cycling", "Transit", "Housing",
              "Climate", "Arts", "Healthcare access", "Reconciliation",
              "Governance"]
LABELS = {"All categories / General": "General"}   # full name is too long to set

# The General block: GEN-01 and GEN-02 in finalize.py. Both are cross-cutting
# rather than tied to one topic, which is what the first tile says; the other
# two are the questions themselves, a single forced choice and a forced
# trade-off. General does have a subjects.yml entry, but its icon there is the
# scorecard clipboard, which says "topic" and not "the two questions in this
# block", so this set defines its icons inline like every other set here.
GENERAL = [
    ("Cross-cutting",
     '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"/>'
     '<path d="M16.24 7.76l-2.12 6.36-6.36 2.12 2.12-6.36z"/></svg>'),
    ("One policy change",
     '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"/>'
     '<circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/></svg>'),
    ("$10M to allocate",
     '<svg viewBox="0 0 24 24"><path d="M21.21 15.89A10 10 0 1 1 8 2.83"/>'
     '<path d="M22 12A10 10 0 0 0 12 2v10z"/></svg>'),
]

# The Walking block: WLK-01 to WLK-04 in finalize.py, one tile per question in
# the order candidates meet them. WLK-01 is the adopted mode-shift targets, so
# it reuses the trending-up arrow the Housekeeping set gives to campaign
# viability: the two graphics are separate section breaks and never share a
# screen, and the arrow means the same thing in both.
WALKING = [
    ("Mode-shift targets",
     '<svg viewBox="0 0 24 24"><path d="M23 6l-9 9-5-5-8 8"/>'
     '<path d="M17 6h6v6"/></svg>'),
    ("Pedestrian safety",
     '<svg viewBox="0 0 24 24"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94'
     'a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>'
     '<path d="M12 9v4"/><path d="M12 17h.01"/></svg>'),
    ("Sidewalk funding",
     '<svg viewBox="0 0 24 24"><line x1="6" y1="20" x2="6" y2="15"/>'
     '<line x1="12" y1="20" x2="12" y2="10"/>'
     '<line x1="18" y1="20" x2="18" y2="4"/></svg>'),
    # A slashed car is the obvious icon and it loses to the stroke weight: the
    # body is 8 grid units tall against a 2-unit stroke, wheels small enough to
    # clear it fill in solid, and the slash then crosses all of it. Two figures
    # would be the easy alternative and it's taken, by reconciliation.svg, which
    # a candidate has already seen in categories.png. So: the place the question
    # actually names, a downtown or main street or village centre.
    ("Car-free streets",
     '<svg viewBox="0 0 24 24"><path d="M1 6L1 22 8 18 16 22 23 18 23 2 16 6 8 2z"/>'
     '<line x1="8" y1="2" x2="8" y2="18"/>'
     '<line x1="16" y1="6" x2="16" y2="22"/></svg>'),
]

# The Rolling & cycling block: ROL-01 to ROL-05. ROL-04 is `change="Unchanged"`
# and lives in the master sheet, so there was no text here to build a tile from.
ROLLING = [
    ("Missing links",
     '<svg viewBox="0 0 24 24"><path d="M15 7h3a5 5 0 0 1 0 10h-3"/>'
     '<path d="M9 7H6a5 5 0 0 0 0 10h3"/>'
     '<line x1="8.5" y1="12" x2="10.5" y2="12"/>'
     '<line x1="13.5" y1="12" x2="15.5" y2="12"/></svg>'),
    ("Physical protection",
     '<svg viewBox="0 0 24 24"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>'
     '</svg>'),
    ("No downgrades",
     '<svg viewBox="0 0 24 24"><path d="M7.86 2h8.28L22 7.86v8.28L16.14 22H7.86L2 16.14'
     'V7.86L7.86 2z"/><line x1="15" y1="9" x2="9" y2="15"/>'
     '<line x1="9" y1="9" x2="15" y2="15"/></svg>'),
    # ROL-05 is ungraded, but unlike HSG-10 it asks about a record rather than a
    # personal circumstance, so it earns a tile where the tenure question didn't.
    ("Your record",
     '<svg viewBox="0 0 24 24"><circle cx="12" cy="8" r="7"/>'
     '<path d="M8.21 13.89L7 23l5-3 5 3-1.21-9.12"/></svg>'),
]

# The Transit block: TRN-01 to TRN-05. TRN-04 is `change="Unchanged"`, so it has
# no tile for the same reason ROL-04 doesn't.
TRANSIT = [
    ("Fares and passes",
     '<svg viewBox="0 0 24 24"><rect x="1" y="4" width="22" height="16" rx="2"/>'
     '<line x1="1" y1="10" x2="23" y2="10"/></svg>'),
    ("Parking to bus lanes",
     '<svg viewBox="0 0 24 24"><path d="M17 1l4 4-4 4"/>'
     '<path d="M3 11V9a4 4 0 0 1 4-4h14"/><path d="M7 23l-4-4 4-4"/>'
     '<path d="M21 13v2a4 4 0 0 1-4 4H3"/></svg>'),
    ("Transit priority",
     '<svg viewBox="0 0 24 24"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/></svg>'),
    ("New connections",
     '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="4"/>'
     '<line x1="1" y1="12" x2="8" y2="12"/>'
     '<line x1="16" y1="12" x2="23" y2="12"/></svg>'),
]

# The Housing block: HSG-01 to HSG-11, the biggest in the questionnaire. These
# labels are given rather than derived - they came in as a per-question tagging
# of the block, which is why they read as tags ("OCP", "Plan") where the other
# sets read as phrases. Two rows of four.
#
# The source list had ten entries for eight labels: "Approvals" and "OCP" each
# appeared twice, once per question carrying that tag. Duplicates are dropped
# here - two identical tiles in one grid read as a rendering fault, not as two
# questions - and the order is first appearance in that list.
HOUSING = [
    # The one glyph here from a family already in use: reconciliation.svg is two
    # figures and the Conduct set has a figure with an x. All three mean people,
    # and no two share a section break, so the resemblance is the point rather
    # than a collision.
    ("Housing need",
     '<svg viewBox="0 0 24 24"><path d="M16 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>'
     '<circle cx="8.5" cy="7" r="4"/><line x1="20" y1="8" x2="20" y2="14"/>'
     '<line x1="23" y1="11" x2="17" y2="11"/></svg>'),
    ("Displacement",
     '<svg viewBox="0 0 24 24"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/>'
     '<path d="M16 17l5-5-5-5"/><line x1="21" y1="12" x2="9" y2="12"/></svg>'),
    ("Approvals",
     '<svg viewBox="0 0 24 24"><path d="M9 11l3 3L22 4"/>'
     '<path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/></svg>'),
    ("OCP",
     '<svg viewBox="0 0 24 24"><rect x="3" y="3" width="18" height="18" rx="2"/>'
     '<line x1="3" y1="9" x2="21" y2="9"/>'
     '<line x1="9" y1="21" x2="9" y2="9"/></svg>'),
    ("Housing types",
     '<svg viewBox="0 0 24 24"><path d="M2 21h20"/>'
     '<path d="M3 21v-7l4-3 4 3v7"/>'
     '<rect x="14" y="8" width="7" height="13" rx="1"/>'
     '<path d="M16.5 12h2M16.5 16h2"/></svg>'),
    ("Policy",
     '<svg viewBox="0 0 24 24"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/>'
     '<path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/>'
     '</svg>'),
    ("Non-market housing",
     '<svg viewBox="0 0 24 24"><circle cx="7.5" cy="16.5" r="5"/>'
     '<path d="M11 13L21 3"/><path d="M16.5 7.5l2.5 2.5"/>'
     '<path d="M19 5l2.5 2.5"/></svg>'),
    ("Plan",
     '<svg viewBox="0 0 24 24"><path d="M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1'
     '-5-2-8-2-4 1-4 1z"/><line x1="4" y1="22" x2="4" y2="15"/></svg>'),
]

# The Climate block: CLI-01 to CLI-11, six tiles for the five questions whose
# text is in finalize.py plus CLI-06. Four have no tile and all four are
# `change="Unchanged"`: CLI-05 (a zoning amendment, per Michael's note), CLI-07
# (the one Claude marked first to cut), and CLI-09 to CLI-11, the three that
# arrived after voting closed and are ungraded. Five unlabelled questions is the
# widest gap of any set here. Worth pulling their text from the sheet and
# checking whether any deserves a tile before this ships.
CLIMATE = [
    ("Climate priority",
     '<svg viewBox="0 0 24 24"><path d="M14 14.76V3.5a2.5 2.5 0 0 0-5 0v11.26'
     'a4.5 4.5 0 1 0 5 0z"/></svg>'),
    ("Fossil fuel ads",
     '<svg viewBox="0 0 24 24"><rect x="2" y="3" width="20" height="14" rx="2"/>'
     '<line x1="8" y1="21" x2="16" y2="21"/>'
     '<line x1="12" y1="17" x2="12" y2="21"/></svg>'),
    ("Lobbying register",
     '<svg viewBox="0 0 24 24"><path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/>'
     '<path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/></svg>'),
    # Scales, because CLI-04 is literally about joining a lawsuit. The Arts set
    # wants a balance too, for ART-07's trade-off, and doesn't get one: a court
    # is the more specific claim on the metaphor.
    ("Cost recovery",
     '<svg viewBox="0 0 24 24"><path d="M12 3v18"/><path d="M5 7h14"/>'
     '<path d="M8 21h8"/><path d="M5 7l-3 6a3 3 0 0 0 6 0z"/>'
     '<path d="M19 7l3 6a3 3 0 0 1-6 0z"/></svg>'),
    ("Heat and wildfire",
     '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="5"/>'
     '<line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/>'
     '<line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/>'
     '<line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/>'
     '<line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/>'
     '<line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/>'
     '<line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/></svg>'),
    ("Data centres",
     '<svg viewBox="0 0 24 24"><rect x="2" y="2" width="20" height="8" rx="2"/>'
     '<rect x="2" y="14" width="20" height="8" rx="2"/>'
     '<line x1="6" y1="6" x2="6.4" y2="6"/>'
     '<line x1="6" y1="18" x2="6.4" y2="18"/></svg>'),
]

# The Arts block: ART-01 to ART-07. ART-03 and ART-07 share the "Cultural
# spaces" tile - the implementation framework and the redevelopment trade-off
# are both about keeping venues - which is what frees a tile for ART-06's
# budget question.
ARTS = [
    ("Economic strategy",
     '<svg viewBox="0 0 24 24"><rect x="2" y="7" width="20" height="14" rx="2"/>'
     '<path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16"/></svg>'),
    ("First-year action",
     '<svg viewBox="0 0 24 24"><rect x="3" y="4" width="18" height="18" rx="2"/>'
     '<line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/>'
     '<line x1="3" y1="10" x2="21" y2="10"/></svg>'),
    ("Cultural spaces",
     '<svg viewBox="0 0 24 24"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/>'
     '<circle cx="12" cy="10" r="3"/></svg>'),
    ("Permitting barriers",
     '<svg viewBox="0 0 24 24"><path d="M22 3H2l8 9.46V19l4 2v-8.54L22 3z"/></svg>'),
    # Two icons here are second uses, both where the meaning carries over intact:
    # the dollar sign is Housekeeping's fundraising tile, and the pie chart is
    # the General set's $10M split. Money and a budget share mean the same thing
    # in all four places, and the graphics are separate section breaks.
    ("Funding venues",
     '<svg viewBox="0 0 24 24"><path d="M12 1v22"/>'
     '<path d="M17.5 5H9.75a3.75 3.75 0 0 0 0 7.5h4.5a3.75 3.75 0 0 1 0 7.5H6"/></svg>'),
    ("Budget priority",
     '<svg viewBox="0 0 24 24"><path d="M21.21 15.89A10 10 0 1 1 8 2.83"/>'
     '<path d="M22 12A10 10 0 0 0 12 2v10z"/></svg>'),
]

# The Governance block: GOV-01, GOV-02 and the per-municipality GOV-03. Not one
# tile per question, because GOV-01 asks two unrelated things in one block and
# GOV-02 is a second helping of its first half. Split by subject instead:
# regional delivery (GOV-01 part 1 and GOV-02), amalgamation (GOV-01 part 2,
# published unscored per its note), and the funding gap (GOV-03).
GOVERNANCE = [
    ("Shared services",
     '<svg viewBox="0 0 24 24"><circle cx="18" cy="5" r="3"/>'
     '<circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/>'
     '<line x1="8.59" y1="13.51" x2="15.42" y2="17.49"/>'
     '<line x1="15.41" y1="6.51" x2="8.59" y2="10.49"/></svg>'),
    ("Amalgamation",
     '<svg viewBox="0 0 24 24"><circle cx="18" cy="18" r="3"/>'
     '<circle cx="6" cy="6" r="3"/><path d="M6 21V9a9 9 0 0 0 9 9"/></svg>'),
    ("Infrastructure gap",
     '<svg viewBox="0 0 24 24"><path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 '
     '1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91'
     'a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/></svg>'),
]

# Healthcare access and Reconciliation share one section break: HLT-01 and
# REC-01 are the only questions in either category, and a section break per
# question would be two graphics for two questions.
#
# The only set that takes its icons off disk rather than defining them inline.
# Everywhere else an inline icon is the point, because the tile stands for a
# question and the subject icon would say "topic" instead. Here the tile stands
# for a topic, because the category is one question wide, so borrowing the
# subject icon is what keeps this graphic and categories.png saying the same
# thing. It also keeps me from inventing Indigenous iconography for REC-01:
# reconciliation.svg is the project's own choice and this defers to it.
#
# REC-01 is `change="Unchanged"`, so its text lives in the master sheet rather
# than finalize.py. The label follows aggregate.py's note on FR-55: "primary
# subject is First Nations representation in governance." Check it against the
# sheet before this ships.
HEALTH_REC = [
    ("Primary care clinics", "healthcare-access.svg"),
    ("First Nations representation", "reconciliation.svg"),
]

# The Housekeeping block: HK-01 and HK-02 in finalize.py. It's the internal
# category: neither question is graded, and only "why you're running" is ever
# published. It has no entry in subjects.yml and no icon in assets/images/icons,
# by design, so its icons are inline here rather than added to the site's set,
# where they'd read as scorecard topics.
HOUSEKEEPING = [
    ("Campaign viability",
     '<svg viewBox="0 0 24 24"><path d="M23 6l-9 9-5-5-8 8"/>'
     '<path d="M17 6h6v6"/></svg>'),
    ("Fundraising",
     '<svg viewBox="0 0 24 24"><path d="M12 1v22"/>'
     '<path d="M17.5 5H9.75a3.75 3.75 0 0 0 0 7.5h4.5a3.75 3.75 0 0 1 0 7.5H6"/></svg>'),
    ("Why you’re running",
     '<svg viewBox="0 0 24 24"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 '
     '2-2h14a2 2 0 0 1 2 2z"/><path d="M8 9h8M8 13h5"/></svg>'),
]

# The info page, distilled to the eight things a candidate needs to know before
# starting. Wording follows that page; QUESTION_COUNT is stated there too, so it
# has to be updated by hand when the shipping set changes size.
QUESTION_COUNT = 70
INFO = [
    ("%d questions" % QUESTION_COUNT,
     '<svg viewBox="0 0 24 24"><path d="M8 6h13M8 12h13M8 18h13"/>'
     '<path d="M3.5 6h.01M3.5 12h.01M3.5 18h.01"/></svg>'),
    ("Grouped by category",
     '<svg viewBox="0 0 24 24"><rect x="3" y="3" width="7" height="7" rx="1"/>'
     '<rect x="14" y="3" width="7" height="7" rx="1"/>'
     '<rect x="3" y="14" width="7" height="7" rx="1"/>'
     '<rect x="14" y="14" width="7" height="7" rx="1"/></svg>'),
    ("Every one optional",
     '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/>'
     '<path d="M8.5 12.5l2.5 2.5 4.5-5"/></svg>'),
    ("N/A or decline",
     '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/>'
     '<path d="M8 12h8"/></svg>'),
    ("Room to elaborate",
     '<svg viewBox="0 0 24 24"><path d="M12 20h9"/>'
     '<path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4z"/></svg>'),
    ("Saved as you go",
     '<svg viewBox="0 0 24 24"><path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11'
     'a2 2 0 0 1-2 2z"/><path d="M17 21v-8H7v8"/><path d="M7 3v5h8"/></svg>'),
    ("Grades with rationale",
     '<svg viewBox="0 0 24 24"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12'
     'a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/><path d="M16 13H8M16 17H8M10 9H8"/></svg>'),
    ("Answers published",
     '<svg viewBox="0 0 24 24"><path d="M1 12s4-7 11-7 11 7 11 7-4 7-11 7-11-7-11-7z"/>'
     '<circle cx="12" cy="12" r="3"/></svg>'),
]

# The code of conduct (/code-of-conduct/), reduced to the five things a
# candidate needs from it before they start typing. Three of the five are
# reassurances rather than prohibitions, in the same proportion the page gives
# them: the rule is easy to misread as a rule about opinions, and a graphic
# that led with the bans would invite exactly that reading.
#
# Labels are kept to ~16 characters. The renderer shrinks any label too wide for
# its column, so a long one here would render smaller than its neighbours and
# break the even type size every other set has. "Not graded" leans on the
# struck-through eye beside it to carry the unpublished half.
CONDUCT = [
    ("Disagree freely",
     '<svg viewBox="0 0 24 24"><path d="M14 9a2 2 0 0 1-2 2H6l-4 4V4a2 2 0 0 1 '
     '2-2h8a2 2 0 0 1 2 2z"/><path d="M18 9h2a2 2 0 0 1 2 2v11l-4-4h-6a2 2 0 0 '
     '1-2-2v-1"/></svg>'),
    ("Not the person",
     '<svg viewBox="0 0 24 24"><path d="M16 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>'
     '<circle cx="8.5" cy="7" r="4"/><path d="M18 8l5 5M23 8l-5 5"/></svg>'),
    ("Not graded",
     '<svg viewBox="0 0 24 24"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 '
     '0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 '
     '11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/>'
     '<path d="M1 1l22 22"/></svg>'),
    ("Chance to revise",
     '<svg viewBox="0 0 24 24"><path d="M1 4v6h6"/>'
     '<path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10"/></svg>'),
    ("You stay listed",
     '<svg viewBox="0 0 24 24"><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6'
     'a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/>'
     '<rect x="8" y="2" width="8" height="4" rx="1"/>'
     '<path d="M9 14l2 2 4-4"/></svg>'),
]

SETS = {"categories": 5, "complete": 5, "general": 3, "walking": 4,
        "rolling": 4, "transit": 4, "housing": 4, "climate": 3,
        "arts": 3, "health-rec": 2, "governance": 3,
        "housekeeping": 3, "info": 4, "conduct": 5}             # name -> columns

# Sets whose icons get a green tick badged onto them. `complete` is the ten
# topics again, ticked off, for the Thank you page: the same grid the candidate
# met at the start, now finished. Reusing it is the point, so it reads as the
# progress bar filling rather than as a new graphic.
CHECKED = {"complete"}

GW = 1400                             # design grid width; all dimensions are in these units
SS = 4                                # supersample factor, collapsed on the final resize


# ======================= stroked-SVG icon renderer =======================
def _cubic(p0, p1, p2, p3, n=16):
    return [(( 1-t)**3*p0[0] + 3*(1-t)**2*t*p1[0] + 3*(1-t)*t*t*p2[0] + t**3*p3[0],
             (1-t)**3*p0[1] + 3*(1-t)**2*t*p1[1] + 3*(1-t)*t*t*p2[1] + t**3*p3[1])
            for t in [i/n for i in range(1, n+1)]]


def _quad(p0, p1, p2, n=14):
    return [((1-t)**2*p0[0] + 2*(1-t)*t*p1[0] + t*t*p2[0],
             (1-t)**2*p0[1] + 2*(1-t)*t*p1[1] + t*t*p2[1])
            for t in [i/n for i in range(1, n+1)]]


def _arc(p0, rx, ry, phi_deg, large, sweep, p1, n=24):
    """SVG elliptical arc, endpoint -> centre parameterisation (F.6.5)."""
    (x1, y1), (x2, y2) = p0, p1
    if rx == 0 or ry == 0 or (x1, y1) == (x2, y2):
        return [p1]
    phi = math.radians(phi_deg)
    cos_p, sin_p = math.cos(phi), math.sin(phi)
    dx, dy = (x1 - x2) / 2, (y1 - y2) / 2
    x1p, y1p = cos_p*dx + sin_p*dy, -sin_p*dx + cos_p*dy
    rx, ry = abs(rx), abs(ry)
    lam = (x1p/rx)**2 + (y1p/ry)**2
    if lam > 1:
        rx, ry = rx*math.sqrt(lam), ry*math.sqrt(lam)
    num = rx*rx*ry*ry - rx*rx*y1p*y1p - ry*ry*x1p*x1p
    den = rx*rx*y1p*y1p + ry*ry*x1p*x1p
    co = math.sqrt(max(0.0, num/den)) * (-1 if large == sweep else 1)
    cxp, cyp = co*rx*y1p/ry, -co*ry*x1p/rx
    cx = cos_p*cxp - sin_p*cyp + (x1+x2)/2
    cy = sin_p*cxp + cos_p*cyp + (y1+y2)/2

    def ang(ux, uy, vx, vy):
        d = (math.hypot(ux, uy) * math.hypot(vx, vy)) or 1.0
        a = math.acos(max(-1.0, min(1.0, (ux*vx + uy*vy) / d)))
        return -a if ux*vy - uy*vx < 0 else a

    t1 = ang(1, 0, (x1p-cxp)/rx, (y1p-cyp)/ry)
    dt = ang((x1p-cxp)/rx, (y1p-cyp)/ry, (-x1p-cxp)/rx, (-y1p-cyp)/ry)
    if not sweep and dt > 0:
        dt -= 2*math.pi
    elif sweep and dt < 0:
        dt += 2*math.pi
    out = []
    for i in range(1, n+1):
        t = t1 + dt*i/n
        out.append((cos_p*rx*math.cos(t) - sin_p*ry*math.sin(t) + cx,
                    sin_p*rx*math.cos(t) + cos_p*ry*math.sin(t) + cy))
    return out


_TOK = re.compile(r'[MmLlHhVvCcSsQqTtAaZz]|[-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?')


def parse_path(d):
    """Flatten a path to [(points, closed)]. Feather subset, arcs included."""
    tk = _TOK.findall(d)
    subs, cur = [], []
    i = 0; x = y = 0.0; sx = sy = 0.0
    cmd = None; c2 = q1 = None

    def num():
        nonlocal i
        v = float(tk[i]); i += 1; return v

    while i < len(tk):
        if tk[i] in "MmLlHhVvCcSsQqTtAaZz":
            cmd = tk[i]; i += 1
            if cmd in "Zz":
                if cur:
                    subs.append((cur, True)); cur = []
                x, y = sx, sy; c2 = q1 = None
                continue
        rel = cmd.islower()
        if cmd in "Mm":
            nx, ny = num(), num()
            if rel: nx += x; ny += y
            if cur: subs.append((cur, False))
            cur = [(nx, ny)]; x, y = nx, ny; sx, sy = x, y
            cmd = 'l' if rel else 'L'; c2 = q1 = None
        elif cmd in "LlHhVv":
            if cmd in "Ll":
                nx, ny = num(), num()
                if rel: nx += x; ny += y
            elif cmd in "Hh":
                nx = num() + (x if rel else 0); ny = y
            else:
                ny = num() + (y if rel else 0); nx = x
            cur.append((nx, ny)); x, y = nx, ny; c2 = q1 = None
        elif cmd in "CcSs":
            if cmd in "Cc":
                x1, y1, x2, y2, nx, ny = (num(), num(), num(), num(), num(), num())
                if rel: x1 += x; y1 += y; x2 += x; y2 += y; nx += x; ny += y
            else:
                x2, y2, nx, ny = num(), num(), num(), num()
                if rel: x2 += x; y2 += y; nx += x; ny += y
                x1, y1 = (2*x - c2[0], 2*y - c2[1]) if c2 else (x, y)
            cur += _cubic((x, y), (x1, y1), (x2, y2), (nx, ny))
            c2 = (x2, y2); q1 = None; x, y = nx, ny
        elif cmd in "QqTt":
            if cmd in "Qq":
                x1, y1, nx, ny = num(), num(), num(), num()
                if rel: x1 += x; y1 += y; nx += x; ny += y
            else:
                nx, ny = num(), num()
                if rel: nx += x; ny += y
                x1, y1 = (2*x - q1[0], 2*y - q1[1]) if q1 else (x, y)
            cur += _quad((x, y), (x1, y1), (nx, ny))
            q1 = (x1, y1); c2 = None; x, y = nx, ny
        elif cmd in "Aa":
            rx, ry, rot, la, sw, nx, ny = (num(), num(), num(), num(),
                                           num(), num(), num())
            if rel: nx += x; ny += y
            cur += _arc((x, y), rx, ry, rot, int(la), int(sw), (nx, ny))
            c2 = q1 = None; x, y = nx, ny
        else:                                   # stray numbers, no live command
            i += 1
    if cur:
        subs.append((cur, False))
    return subs


def _ellipse_pts(cx, cy, rx, ry, n=48):
    return [(cx + rx*math.cos(2*math.pi*k/n), cy + ry*math.sin(2*math.pi*k/n))
            for k in range(n + 1)]


def icon_shapes(svg_text):
    """Every drawable in the icon as [(points, closed)], in viewBox units."""
    out = []
    for tag, attrs in re.findall(r'<(path|circle|rect|line)\b([^>]*)/?>', svg_text):
        g = lambda k, dflt=0.0: (float(m.group(1))
                                 if (m := re.search(rf'\b{k}="([-\d.]+)"', attrs))
                                 else dflt)
        if tag == "path":
            out += parse_path(re.search(r'\bd="([^"]+)"', attrs).group(1))
        elif tag == "circle":
            out.append((_ellipse_pts(g("cx"), g("cy"), g("r"), g("r")), True))
        elif tag == "line":
            out.append(([(g("x1"), g("y1")), (g("x2"), g("y2"))], False))
        else:
            x, y, w, h, r = g("x"), g("y"), g("width"), g("height"), g("rx")
            r = min(r, w/2, h/2)
            if r:
                pts = []
                for cx, cy, a0 in ((x+w-r, y+r, -math.pi/2), (x+w-r, y+h-r, 0),
                                   (x+r, y+h-r, math.pi/2), (x+r, y+r, math.pi)):
                    pts += [(cx + r*math.cos(a0 + math.pi/2*k/8),
                             cy + r*math.sin(a0 + math.pi/2*k/8)) for k in range(9)]
                pts.append(pts[0])
                out.append((pts, True))
            else:
                out.append(([(x, y), (x+w, y), (x+w, y+h), (x, y+h), (x, y)], True))
    return out


def render_icon(svg, size, stroke=2.0, ss=SS):
    """Stroke a 24x24 icon (SVG source text) to an alpha mask at (size, size)."""
    vb = re.search(r'viewBox="([\d.\s-]+)"', svg).group(1).split()
    minx, miny, vbw, vbh = [float(v) for v in vb]
    W = int(round(size * ss))
    k = W / max(vbw, vbh)
    sw = max(1, int(round(stroke * k)))
    r = sw / 2

    mask = Image.new("L", (W, W), 0)
    d = ImageDraw.Draw(mask)
    for pts, closed in icon_shapes(svg):
        p = [((px - minx) * k, (py - miny) * k) for px, py in pts]
        if closed and p[0] != p[-1]:
            p.append(p[0])
        if len(p) > 1:
            d.line(p, fill=255, width=sw, joint="curve")
        # Pillow rounds joins but butts the ends; Feather icons are round-capped.
        if not closed:
            for cx, cy in (p[0], p[-1]):
                d.ellipse([cx-r, cy-r, cx+r, cy+r], fill=255)
    return mask.resize((size, size), Image.LANCZOS)


def check_badge(size, ss=SS):
    """A green tick disc, RGBA, for badging onto the corner of an icon."""
    W = int(round(size * ss))
    im = Image.new("RGBA", (W, W), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    # A page-background ring first, so the disc reads as sitting on top of the
    # icon rather than tangled in it. Every topic icon has strokes running into
    # its bottom-right corner and without the ring they touch the disc.
    ring = W * 0.085
    d.ellipse([0, 0, W - 1, W - 1], fill=PAGE_BG + (255,))
    d.ellipse([ring, ring, W - 1 - ring, W - 1 - ring], fill=CHECK_GREEN + (255,))

    sw = max(1, int(round(W * 0.10)))
    pts = [(W * 0.31, W * 0.53), (W * 0.44, W * 0.66), (W * 0.71, W * 0.37)]
    d.line(pts, fill=(255, 255, 255, 255), width=sw, joint="curve")
    for px, py in (pts[0], pts[-1]):        # round caps, as in render_icon
        d.ellipse([px - sw/2, py - sw/2, px + sw/2, py + sw/2],
                  fill=(255, 255, 255, 255))
    return im.resize((size, size), Image.LANCZOS)


# ============================== compose ==================================
def items_for(which):
    """[(label, svg source)] for a set; subject icons come off disk."""
    if which == "general":
        return list(GENERAL)
    if which == "walking":
        return list(WALKING)
    if which == "rolling":
        return list(ROLLING)
    if which == "transit":
        return list(TRANSIT)
    if which == "housing":
        return list(HOUSING)
    if which == "climate":
        return list(CLIMATE)
    if which == "arts":
        return list(ARTS)
    if which == "governance":
        return list(GOVERNANCE)
    if which == "health-rec":
        return [(label, open(os.path.join(ICON_DIR, f)).read())
                for label, f in HEALTH_REC]
    if which == "housekeeping":
        return list(HOUSEKEEPING)
    if which == "info":
        return list(INFO)
    if which == "conduct":
        return list(CONDUCT)
    # `categories` and `complete` are the same ten topics; only the tick differs.
    by_name = {s["name"]: s for s in yaml.safe_load(open(SUBJECTS))}
    out = []
    for name in CATEGORIES:
        s = by_name.get(name)
        if s is None:                       # tolerate "Rolling & cycling" etc.
            s = next(v for k, v in by_name.items() if k.endswith(name))
        out.append((LABELS.get(s["name"], s["name"]),
                    open(os.path.join(ICON_DIR, s["icon"])).read()))
    return out


def build(which="categories", out_w=GW * 2):
    items = items_for(which)
    cols = SETS[which]
    rows = -(-len(items) // cols)
    S = out_w / GW                          # grid unit -> output pixels

    icon_px = int(round(86 * S))
    label_sz = int(28 * S)
    icon_gap = 22 * S
    row_gap = 40 * S
    row_h = icon_px + icon_gap + label_sz + row_gap
    pad = 44 * S                            # above the first icon, below the last label

    # Height follows the row count rather than a fixed grid, so a one-row set
    # isn't padded out with the dead space a two-row set needs.
    Wp = out_w
    Hp = int(round(rows * row_h - row_gap + 2 * pad))

    img = Image.new("RGB", (Wp, Hp), PAGE_BG)
    draw = ImageDraw.Draw(img)

    # No heading: the form's own question text says what this is, and a second
    # title would just repeat it.
    grid_top = pad
    side = 70 * S
    col_w = (Wp - 2 * side) / cols

    for i, (label, svg) in enumerate(items):
        cx = side + col_w * (i % cols) + col_w / 2
        cy = grid_top + row_h * (i // cols)

        mask = render_icon(svg, icon_px)
        img.paste(Image.new("RGB", (icon_px, icon_px), LIVABLE),
                  (int(cx - icon_px / 2), int(cy)), mask)

        # Overhanging the corner rather than tucked inside it: the icons don't
        # share a common bounding box (the bike fills its viewBox, the clipboard
        # doesn't), so an inset badge would sit at a different distance from
        # every one of them. Hung off the box, they line up.
        if which in CHECKED:
            bs = max(1, int(round(icon_px * 0.44)))
            badge = check_badge(bs)
            img.paste(badge, (int(round(cx + icon_px / 2 - bs * 0.70)),
                              int(round(cy + icon_px - bs * 0.70))), badge)

        sz = label_sz
        f = fb.font(sz, 500)
        while draw.textlength(label, font=f) > col_w - 14 * S and sz > 20 * S:
            sz -= max(1, int(S))
            f = fb.font(sz, 500)
        draw.text((cx, cy + icon_px + icon_gap + label_sz / 2), label,
                  font=f, fill=INKY, anchor="mm")

    out = os.path.join(OUT_DIR, "%s.png" % which)
    img.save(out, optimize=True)
    print("wrote", out, img.size, "%d items" % len(items),
          "%.0f KB" % (os.path.getsize(out) / 1024))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--set", dest="which", default="categories", choices=list(SETS),
                    help="which grid to build (default categories)")
    ap.add_argument("--width", type=int, default=GW * 2,
                    help="output width in px (default 2800; Tally recommends 1400)")
    a = ap.parse_args()
    build(a.which, a.width)
