#!/usr/bin/env python3
"""Collect every submitted question from the source tabs into one normalised list.

This is the shared data layer for tables.py, voting.py and append.py: it reads the
submission tabs, assigns each question a stable ID and an official category, and
flags near-duplicates. It does not write to the sheet - run it directly to preview
the categorisation before rebuilding anything.

Unlike the stdlib-only scripts in scripts/, this needs gspread (see requirements.txt).

Usage:
  QUESTIONNAIRE_SHEET_ID=... python3 scripts/questionnaire/aggregate.py
"""

import os
import sys
from collections import Counter

import gspread

MASTER = "All Refined Questions"
FIRST = 2  # data starts directly under the header row

CATEGORIES = [
    "General",
    "Transit",
    "Housing",
    "Climate",
    "Arts",
    "Rolling & cycling",
    "Walking",
    "Healthcare access",
    "Reconciliation",
    "Governance",
    "Housekeeping",  # internal only - not published on the scorecard
]

SOURCES = ["Form Responses 1", "HFL Questions", "Victori'Us Questions", "RUSH Questions"]

# The RUSH tab opens with a cover note sitting in the question column rather than a
# question. Matched case-insensitively on the prefix so the row is skipped by intent,
# not by a "does it end in a question mark" guess that could drop a real submission.
RUSH_PREAMBLE = "here are our questions"

HEADERS = [
    "ID", "Category", "Submitted topic", "Question", "Answers / options",
    "Question type", "Source", "Submitter", "Municipality scope", "Notes",
]

# Submitted topic string -> official category.
TOPIC_MAP = {
    "walking": "Walking",
    "transit": "Transit",
    "rolling/cycling": "Rolling & cycling",
    "housing": "Housing",
    "climate": "Climate",
    "housekeeping": "Housekeeping",
    "good governance": "Governance",
    "governance": "Governance",
    "healthcare": "Healthcare access",
    "arts": "Arts",
}

# Form-response rows where the submitted topic is wrong or ambiguous.
# Key = question ID, value = (official category, why). The reason is written into
# the Notes column so the recategorisation is auditable in the sheet.
FR_OVERRIDES = {
    "FR-04": ("General", "Submitted as Transit + Rolling/Cycling; cross-cutting mode-shift question."),
    "FR-06": ("Governance", "Submitted as Housing; amalgamation is a governance question."),
    "FR-14": ("Housing", "Submitted as Transit + Housing; parking minimums sit with land use."),
    "FR-17": ("Housekeeping", "Submitted as Walking; not a policy question."),
    "FR-35": ("Governance", "Submitted as Housing; municipal finance, not housing."),
    "FR-55": ("Reconciliation", "Submitted as Transit; primary subject is First Nations representation in governance."),
}

VU_OVERRIDES = {
    "VU-01": ("General", "Budget allocation across 14 priorities; cross-cutting, not arts-specific."),
}

# Near-duplicates worth resolving before the questionnaire is built.
DUPES = {
    "FR-13": "Overlaps HFL-05 (pre-zoning to OCP).",
    "HFL-05": "Overlaps FR-13 (pre-zoning to OCP).",
    "FR-14": "Overlaps FR-36, HFL-08, HFL-09 (parking minimums).",
    "FR-36": "Overlaps FR-14, HFL-08, HFL-09 (parking minimums).",
    "HFL-08": "Overlaps FR-14, FR-36, HFL-09 (parking minimums).",
    "HFL-09": "Duplicate question text of HFL-08 in the source tab; category differs.",
    "FR-03": "Overlaps FR-21 (free/subsidised youth transit).",
    "FR-21": "Overlaps FR-03 (free/subsidised youth transit).",
    "FR-23": "Overlaps FR-31 (fossil fuel sponsorship refusal).",
    "FR-31": "Overlaps FR-23 (fossil fuel sponsorship refusal).",
}

MUNICIPALITIES = {
    "Victoria", "Saanich", "Oak Bay", "Central Saanich", "Esquimalt",
    "Sidney", "Langford", "View Royal", "North Saanich", "Colwood",
}


def sheet_id():
    """The spreadsheet key. Kept out of source: the sheet holds submitter emails."""
    sid = os.environ.get("QUESTIONNAIRE_SHEET_ID")
    if not sid:
        sys.exit("FATAL: set QUESTIONNAIRE_SHEET_ID (the Google Sheet key).")
    return sid


def open_sheet():
    return gspread.oauth().open_by_key(sheet_id())


def clean(text):
    return " ".join(text.split()) if text else ""


def map_topic(topic):
    key = topic.strip().lower()
    if key in TOPIC_MAP:
        return TOPIC_MAP[key]
    for part in key.replace(",", " ").split():
        if part in TOPIC_MAP:
            return TOPIC_MAP[part]
    return ""


def build_rows(sh):
    """Return one normalised row per question, ordered FR-*, HFL-*, VU-*, RUSH-*.

    Source order is append-only on purpose: new tabs go on the end so their rows land
    below the existing ones, which is what lets append.py extend a sheet that is
    already being voted on without shifting anyone's row alignment.
    """
    rows = []

    fr = sh.worksheet("Form Responses 1").get_all_values()
    n = 0
    for r in fr[1:]:
        if not any(c.strip() for c in r) or not r[7].strip():
            continue
        n += 1
        qid = f"FR-{n:02d}"
        cat, note = FR_OVERRIDES.get(qid, (map_topic(r[4]), ""))
        notes = [x for x in (note, DUPES.get(qid), clean(r[8])) if x]
        rows.append([
            qid, cat, clean(r[4]), clean(r[7]), "", clean(r[6]),
            "Form Responses 1", clean(r[1]), clean(r[2]), " | ".join(notes),
        ])

    hfl = sh.worksheet("HFL Questions").get_all_values()
    n = 0
    for r in hfl[1:]:
        if not any(c.strip() for c in r) or not r[2].strip():
            continue
        n += 1
        qid = f"HFL-{n:02d}"
        subtopic = clean(r[1])
        muni = subtopic if subtopic in MUNICIPALITIES else ""
        is_infra = "asset-management" in r[2].lower() or "asset management" in r[2].lower()
        cat = "Governance" if is_infra else "Housing"
        note = ("Municipal infrastructure funding gap; filed under Governance not Housing."
                if is_infra else "")
        notes = [x for x in (note, DUPES.get(qid)) if x]
        rows.append([
            qid, cat, subtopic, clean(r[2]), clean(r[3]), "",
            "HFL Questions", "Homes for Living", muni, " | ".join(notes),
        ])

    vu = sh.worksheet("Victori'Us Questions").get_all_values()
    n = 0
    for r in vu[1:]:
        if not r[0].strip().isdigit():
            continue
        n += 1
        qid = f"VU-{n:02d}"
        cat, note = VU_OVERRIDES.get(qid, ("Arts", ""))
        notes = [x for x in (note, clean(r[5]) if len(r) > 5 else "") if x]
        # Scope is one value for the whole tab because the tab has no scope column.
        # The 2026-08-09 resubmission marked eleven of its twelve questions "All
        # municipalities" (VU-03 alone was submitted Victoria-only, and its Notes say
        # so), which is also what finalize.py already ships them as.
        rows.append([
            qid, cat, clean(r[1]), clean(r[2]), clean(r[3]),
            clean(r[4])[:120], "Victori'Us Questions", "Victori'Us (Erin)",
            "All municipalities", " | ".join(notes),
        ])

    rush = sh.worksheet("RUSH Questions").get_all_values()
    n = 0
    for r in rush[1:]:
        if not any(c.strip() for c in r) or not r[0].strip():
            continue
        if clean(r[0]).lower().startswith(RUSH_PREAMBLE):
            continue
        n += 1
        qid = f"RUSH-{n:02d}"
        topic = clean(r[2]) if len(r) > 2 else ""
        rows.append([
            qid, map_topic(topic), topic, clean(r[0]), "", "",
            "RUSH Questions", "RUSH Initiative", "", DUPES.get(qid, ""),
        ])

    return rows


def main():
    rows = build_rows(open_sheet())
    print(f"{len(rows)} questions (read-only preview - nothing written)\n")
    for cat, cnt in Counter(r[1] or "(uncategorised)" for r in rows).most_common():
        print(f"  {cat:20} {cnt}")
    flagged = [r[0] for r in rows if r[0] in DUPES]
    print(f"\nnear-duplicates flagged: {', '.join(flagged)}")


if __name__ == "__main__":
    main()
