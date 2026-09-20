#!/usr/bin/env python3
"""Bootstrap the grading tabs on the candidate submission sheet.

The submission sheet ("Submissions - 2026 Municipal Elections") is Tally's raw
dump: one row per candidate, one column per form field. Graders can't work in it
- multi-select questions sprawl across up to 17 columns, and Tally rewrites the
tab on every submission - so grading happens on separate tabs, one per scorecard
subject, in long form: one row per candidate per question.

This script creates the tabs and their structure. It does not move any data;
`appsscript/Code.gs`, running inside the spreadsheet, appends the rows as
submissions arrive.

Tabs created:

  Question Registry   One row per graded question: label, category, weight,
                      owner, and which raw columns hold its answer.
                      Hand-maintained after the first run; this is the single
                      source of truth for what gets graded and what each
                      question is worth.
  Grade - <Subject>   One per scorecard subject. A-G generated and protected,
                      H-J typed by graders, M a hidden drift hash. H holds a
                      letter on most subjects and a number on the two whose
                      partner org scores rather than grades: a number of points
                      out of the Max points in I on a POINTS_CATEGORIES subject,
                      and a 0-N score beside the ordinary weight in I on a
                      SCALE_CATEGORIES one.
  Category Grades     One row per candidate. One column per graded subject,
                      each starting as a weighted rollup of that subject's
                      question grades which a partner org can type their own
                      top-level letter over, and each followed by a checkbox
                      gating publication on the website. General and Healthcare
                      access have no graded question and so no grade column,
                      but do get a gate: their answers are published verbatim.
  Category Stats      The same grid as Category Grades, holding the figure each
                      letter was banded from rather than the letter. Nothing on
                      it is published; it is there so 99% and 85% can be told
                      apart when both read A.
  Sync Log            What the Apps Script did, and what it refused to do.

Idempotent: existing tabs are left alone, and the registry only gains rows for
labels it doesn't already list, so re-run it after new questions reach the form.

Usage:
  QUESTIONNAIRE_SUBMISSIONS_SHEET_ID=... python3 scripts/questionnaire/grading_tabs.py --dry-run
  QUESTIONNAIRE_SUBMISSIONS_SHEET_ID=... python3 scripts/questionnaire/grading_tabs.py
"""

import argparse
import datetime
import json
import os
import re
import sys

import gspread
from gspread.utils import ValueRenderOption

RAW_TAB = "2026 Municipal Elections"
REGISTRY_TAB = "Question Registry"
LOG_TAB = "Sync Log"
GRADE_TAB_PREFIX = "Grade - "
CATEGORY_TAB = "Category Grades"

# Letter grades the site can render. Mirrors VALID_GRADES in
# scripts/sync-candidates.py and the .grade-* classes in _sass/_components.scss.
VALID_GRADES = ["A", "B", "C", "C-", "F"]

# Raw-sheet columns identifying the candidate, 1-based. Code.gs repeats these;
# change both together.
COL_SUBMISSION_ID = 1
COL_SUBMITTED_AT = 3
COL_FIRST_NAME = 4
COL_LAST_NAME = 5
COL_MUNICIPALITY = 8

# Header prefix of a question column: "GEN-01: ...", "HFL-11-Victoria: ...".
LABEL_RE = re.compile(r"^([A-Z]{2,4}-(?:\d{2}|GEN)(?:-[A-Za-z]+)?):\s*(.*)$", re.S)

# Municipality-specific variants of one question ("HFL-11-Victoria"). A candidate
# answers exactly one, so all the variants collapse into a single graded question.
VARIANT_RE = re.compile(r"^([A-Z]{2,4}-\d{2})-[A-Za-z]+$")

# A multi-select question's option columns are the question's own text with
# " (the option text)" appended, so they are recognised by comparison against the
# shortest text in the block rather than by a regex: option text itself contains
# nested parentheses ("Small homes (< 500 sq. ft.)."), which no trailing-paren
# pattern survives. Code.gs uses the same rule.

# Label prefix -> scorecard subject, matching the categories in
# scripts/questionnaire/finalize.py and the ids in _data/subjects.yml.
PREFIX_CATEGORY = {
    "HFL": "Housing",
    "GOV": "Governance",
    # The reconciliation questions were folded into Governance with their codes
    # left as they were, so a REC-* label is a Governance question now. Existing
    # registry rows carry this in their hand-maintained Category cell; this map
    # only decides where a newly-discovered REC-* question would be proposed.
    "REC": "Governance",
    "TRN": "Transit",
    "CLI": "Climate",
    "ART": "Arts",
    "ROL": "Rolling & cycling",
    "WLK": "Walking",
    "HLT": "Healthcare access",
}

# Questions whose subject isn't the one their prefix implies. Empty today, and
# kept because the next one is a question of when rather than whether: the map
# is the seam a question moves through, and the last occupant (HFL-12, the
# infrastructure funding gap) needed a sheet migration to leave it. Homes for
# Living count HFL-12 towards the housing score in their own workbook, so it is
# Housing here too - see scripts/questionnaire/move_question.py.
CATEGORY_OVERRIDE = {}

# Ungraded: the "-GEN" per-topic comment boxes are free text with nothing to
# score, and the GEN-* questions are published unscored.
SKIP_LABELS = {"GEN-01", "GEN-02"}

# Categories whose graders type a number in H rather than a letter, and what
# that number is out of. Two partner orgs score rather than grade, and they do
# it differently enough that this is two maps and not one set.
#
# Housing - Homes for Living. Every question is worth a stated number of points,
# the municipality-specific ones are only asked where they apply, and the
# candidate gets one cumulative grade from their share of the points available
# to them. Column I holds that question's Max points, and housing questions
# carry no Weight at all: the points ARE the weighting, so the registry's
# per-category "should total 100%" check is skipped for them. A housing score
# can also be negative, and it is the only kind that can - see SCORE_FLOOR.
#
# Arts - Victori'us. Every question is scored 0-3 against their rubric and
# carries a Weight exactly as on a letter tab, and the topic grade is the
# weighted average of those scores read as a percentage. Column I is the same
# Weight lookup every letter tab has, the weights still have to total 100%, and
# the only thing that changes about the tab is what H means.
#
# Both are mirrored in appsscript/Code.gs and sync-questionnaire.py.
POINTS_CATEGORIES = {"Housing"}
SCALE_CATEGORIES = {"Arts": 3}
SCORED_CATEGORIES = POINTS_CATEGORIES | set(SCALE_CATEGORIES)

# The incumbent record: one more row on Grade - Housing, and the only row on any
# grading tab that is not a question anybody was asked.
#
# Homes for Living wanted a sitting councillor's actual record on housing scored
# alongside what they said they would do, so this row carries their judgement of
# the term itself. It is scored in points in column H like every other housing
# row, out of a Max points they set on its registry row, and it is fanned out
# ONLY to candidates the published roster calls incumbents - Code.gs reads
# _data/candidates.yml from this site's own repository to decide, because the
# submission sheet holds nothing that says who is sitting.
#
# What it is worth is not its points. RECORD_SHARE of the housing grade is the
# record and the rest is the questionnaire, whatever the two are scored out of,
# so the row cannot simply join the points total - see points_rollup_formula().
# A candidate with no scored record row is graded on the questionnaire alone, at
# 100%, which is every challenger and every incumbent nobody has scored yet.
#
# Mirrored in appsscript/Code.gs (RECORD_LABEL) and sync-questionnaire.py
# (RECORD_LABEL / RECORD_SHARE); the three change together.
RECORD_LABEL = "HFL-INC"
RECORD_CATEGORY = "Housing"
RECORD_SHARE = 0.3
RECORD_OWNER = "Homes for Living"
RECORD_QUESTION = (
    "Incumbent record: what this candidate has done on housing during their "
    "current term. Scored by Homes for Living, not answered by the candidate."
)
RECORD_TYPE = "record"
RECORD_NOTES = (
    f"Not a form question: no raw columns, and the row is only created for "
    f"candidates _data/candidates.yml lists as sitting incumbents. Worth "
    f"{RECORD_SHARE:.0%} of the housing grade on its own; the questionnaire "
    f"carries the other {1 - RECORD_SHARE:.0%}."
)

# Where each rubric's bands fall, as a share of what was available. Ascending,
# because MATCH with a 1 finds the last threshold at or below the value.
#
# They are deliberately not the same bands. Homes for Living have a C- running
# from 50% to 60%; Victori'us have no C- at all and put A a point higher, at
# 86%. Each is the org's own threshold table, as their own workbook states it.
POINTS_BANDS = [(0.0, "F"), (0.5, "C-"), (0.6, "C"), (0.7, "B"), (0.85, "A")]
SCALE_BANDS = [(0.0, "F"), (0.6, "C"), (0.7, "B"), (0.86, "A")]

# How a scale tab's Weight column is rendered. Two places, not the whole percent
# a letter tab shows, because it is what a grader and the website both read: the
# arts weights are sixths and fifteenths, and eight of them rounded to whole
# percents total 101%.
SCALE_WEIGHT_PATTERN = "0.00%"

# Tab order, so the sheet reads the way the scorecard does.
CATEGORY_ORDER = [
    "Housing", "Transit", "Walking", "Rolling & cycling", "Climate",
    "Arts", "Governance", "Healthcare access",
]

# Categories the questionnaire asks about but nobody grades: General is only the
# GEN-* free-text questions, and Healthcare access's one question is marked
# ungraded in the registry. They still need a publication gate, because their
# answers are published on the website verbatim, so Category Grades carries a
# deploy checkbox for each.
#
# A checkbox and NO grade column beside it, unlike every other category. There
# is nothing to roll up, and a grade column here would point categoryFormula()
# at a Grade tab with no graded rows in it. Code.gs tells the two kinds of
# header apart by CATEGORY_DEPLOY_SUFFIX rather than by position, so a lone gate
# column needs no change there.
UNGRADED_GATES = ["General", "Healthcare access"]

# Owner is hand-maintained and sits after the generated columns: who submitted
# the question, so a grader knows whom to ask. The script writes its header on a
# fresh sheet and never touches the values, including on --refresh. Anything
# further right must start at column M: J:L holds the per-category tally block.
REGISTRY_HEADERS = [
    "Label", "Category", "Question", "Type", "Graded", "Weight", "Methodology",
    "Raw columns", "Notes", "Owner",
]

# Where Owner sits, 1-based, for the lookup every grading row's column G holds.
# Named rather than written into the formula, because it has moved once already:
# Methodology was inserted beside Weight on 2026-09-18 and pushed it from I to J,
# and a VLOOKUP's column number is the one thing Sheets does NOT adjust when a
# column is inserted inside its range. See scripts/questionnaire/add_methodology.py.
REGISTRY_OWNER_COLUMN = 10

# Methodology: optional, hand-maintained, and read by nobody. Graders describe
# how a question is scored in their own words, beside the Weight that says what
# it is worth. Nothing generated is written into it and nothing published reads
# it; --refresh leaves it alone with Category, Graded, Weight and Owner.
REGISTRY_METHODOLOGY_COLUMN = 7

GRADE_HEADERS = [
    "Key", "Candidate", "Municipality", "Label", "Question", "Answer", "Owner",
    "Grade", "Weight", "Rationale", "Grader", "Graded at", "Answer hash",
]

# What H and I are called on a tab that takes a number in H. The columns
# themselves are the same two every grading tab has - no tab is a different
# width, and every hardcoded index in Code.gs, sync-questionnaire.py and this
# file keeps its meaning - only what a grader puts in them changes.
#
# A points tab renames both: H holds a number out of I rather than a letter
# weighted by I. A scale tab renames only H, and names the ceiling while it is
# there, because a bare "Score" above a column whose neighbour still reads
# "Weight" does not say what the number is out of.
POINTS_GRADE_HEADERS = ["Score", "Max points"]

# Registry column holding what a scored question is worth, 1-based. Sits past
# the J:L weight tally, in the "column M or beyond" the schema reserves for
# anything added after A:I.
REGISTRY_MAX_COLUMN = 14
MAX_POINTS_HEADER = "Max points"

LOG_HEADERS = ["Timestamp", "Trigger", "Event", "Detail"]

HEADER_FORMAT = {
    "backgroundColor": {"red": 0.9529412, "green": 0.9529412, "blue": 0.9529412},
    "textFormat": {"bold": True},
    "wrapStrategy": "CLIP",
}

# Columns the Apps Script owns on a grading tab, 0-based end-exclusive: A-G, plus
# the hidden hash in M. Graders get a warning if they type in them. Owner and
# Weight are lookups into the registry rather than copies, so correcting either
# there corrects every grading row at once.
GENERATED_COLUMNS = (0, 7)
HASH_COLUMN = 12

GRADE_COLUMN_WIDTHS = [
    (0, 1, 210),    # Key
    (1, 2, 170),    # Candidate
    (2, 3, 130),    # Municipality
    (3, 4, 80),     # Label
    (4, 5, 320),    # Question
    (5, 6, 420),    # Answer
    (6, 7, 200),    # Owner
    (7, 8, 70),     # Grade
    (8, 9, 80),     # Weight
    (9, 10, 420),   # Rationale
    (10, 11, 120),  # Grader
    (11, 12, 140),  # Graded at
]

GRADE_TAB_ROWS = 2000

# Category Grades: Key/Candidate/Municipality are written once by Code.gs, same
# as a grading tab's generated columns. The category columns after them start
# with a computed rollup but are meant to be typed over with a partner org's own
# call, so - unlike GENERATED_COLUMNS above - they carry no edit-warning protection.
CATEGORY_GENERATED_COLUMNS = (0, 3)

# Each category column is immediately followed by a checkbox column with this
# suffix, gating publication of that category's top-level grade and detailed
# scoring on the website. Code.gs matches on the same suffix to tell a grade
# column (gets a rollup formula) from a deploy-gate column (defaults to
# unchecked) when it appends a new candidate's row.
CATEGORY_DEPLOY_SUFFIX = " - Deploy to website"

# `Category Stats`: the same grid as `Category Grades`, holding the figure each
# letter was banded from rather than the letter.
#
# It exists because a band is a wide thing to be inside. Two candidates both
# reading A on housing can be 85% and 99%, and the tab that decides the grade
# cannot show the difference; somebody choosing between two A candidates wants
# it. Nothing here is published - sync-questionnaire.py does not read this tab -
# and nothing here gates anything, so it carries no deploy checkboxes.
#
# The three rubrics do not measure the same thing, and the tab cannot pretend
# otherwise: housing is a share of the points available, arts a share of the
# 0-3 scale, and a letter-graded subject a position on the A-F scale. See
# subject_ratio(). Two decimal places because that is the point of the tab.
STATS_TAB = "Category Stats"
STATS_PATTERN = "0.00%"


def is_graded(label):
    return not label.endswith("-GEN") and label not in SKIP_LABELS


def base_label(label):
    m = VARIANT_RE.match(label)
    return m.group(1) if m else label


def category_for(label):
    if label in CATEGORY_OVERRIDE:
        return CATEGORY_OVERRIDE[label]
    return PREFIX_CATEGORY.get(label.split("-")[0])


def question_blocks(header):
    """Contiguous column blocks per graded question, in sheet order.

    Returns [(label, first, last, [(index, text_after_label)])] with 0-based,
    end-inclusive indices. Municipality variants collapse into one block.
    """
    blocks = []
    for i, cell in enumerate(header):
        m = LABEL_RE.match((cell or "").strip())
        if not m:
            continue
        label = base_label(m.group(1))
        if not is_graded(label):
            continue
        if blocks and blocks[-1][0] == label:
            blocks[-1][2] = i
            blocks[-1][3].append((i, m.group(1), m.group(2)))
        else:
            blocks.append([label, i, i, [(i, m.group(1), m.group(2))]])
    return [tuple(b) for b in blocks]


def split_options(texts):
    """(question text, [option texts]) for one question's columns.

    The question's own column holds the wording; each option column repeats it
    with " (the option)" appended, so the shortest text is the question and
    anything extending it is an option. A column that extends nothing is a
    written follow-up part (GOV-01, CLI-01, ART-01), returned with the question.
    """
    base = min(texts, key=len)
    options, plain = [], []
    for t in texts:
        if t != base and t.startswith(base) and t.rstrip().endswith(")"):
            options.append(t[len(base):].strip().strip("()").strip())
        else:
            plain.append(t)
    return plain, options


def describe(cols, variants):
    """Question text, type and notes for one block's registry row."""
    # Option detection happens per municipality variant: HFL-12's five variants
    # each carry their own wording, so one shared base would match nothing.
    by_variant = {}
    for _, full_label, text in cols:
        by_variant.setdefault(full_label, []).append(" ".join(text.split()))

    options_per_variant, plain_parts = [], []
    for full_label, texts in by_variant.items():
        plain, options = split_options(texts)
        options_per_variant.append(len(options))
        if full_label == cols[0][1]:
            plain_parts = plain

    options = max(options_per_variant)

    kinds = []
    if variants > 1:
        kinds.append("variant")
    if options:
        kinds.append("multi")
    if len(plain_parts) > 1:
        kinds.append("pair")
    if not kinds:
        kinds.append("single")

    notes = []
    if variants > 1:
        notes.append(f"{variants} municipality variants, candidate answers one")
    if options:
        notes.append(f"{options} options")
    if len(plain_parts) > 1:
        notes.append(f"{len(plain_parts)} written parts, graded together")

    # The first column of the block carries the question itself.
    text = " ".join(cols[0][2].split())
    return text, ",".join(kinds), "; ".join(notes)


def registry_rows(header):
    """One row per graded question, ready to write under REGISTRY_HEADERS."""
    rows = []
    for label, first, last, cols in question_blocks(header):
        variants = len({full_label for _, full_label, _ in cols})
        text, kind, notes = describe(cols, variants)
        category = category_for(label)
        if not category:
            notes = "; ".join(filter(None, [notes, "UNMAPPED PREFIX - set the category by hand"]))
        rows.append([
            label,
            category or "",
            text,
            kind,
            "Yes",
            "",  # weight, set by hand
            "",  # methodology, set by hand
            f"{first + 1}-{last + 1}",
            notes,
        ])
    rows.append(record_registry_row())
    return rows


def record_registry_row():
    """The incumbent record's registry row: a graded row with no raw columns.

    Every other row on this tab describes columns of the form. This one
    describes nothing on it, because no candidate answered it - see
    RECORD_LABEL. Raw columns is therefore blank, and both readers know to
    expect that of this label alone: readRegistry() in Code.gs otherwise skips a
    row with no span, which is what keeps a half-filled registry row from
    quietly fanning empty answers out to every candidate.

    Max points is left blank on purpose. It is Homes for Living's number, the
    registry is where they type it, and seed_max_points() never fills a cell it
    was not given a figure for.
    """
    return [RECORD_LABEL, RECORD_CATEGORY, RECORD_QUESTION, RECORD_TYPE,
            "Yes", "", "", "", RECORD_NOTES]


def a1(col_index):
    """0-based column index to its A1 letters."""
    letters = ""
    n = col_index + 1
    while n:
        n, rem = divmod(n - 1, 26)
        letters = chr(65 + rem) + letters
    return letters


def sheet_by_title(sh, title):
    try:
        return sh.worksheet(title)
    except gspread.WorksheetNotFound:
        return None


def header_row_requests(sheet_id, headers, freeze=True):
    requests = [{
        "updateCells": {
            "rows": [{"values": [
                {"userEnteredValue": {"stringValue": h}, "userEnteredFormat": HEADER_FORMAT}
                for h in headers
            ]}],
            "fields": "userEnteredValue,userEnteredFormat.backgroundColor,"
                      "userEnteredFormat.textFormat,userEnteredFormat.wrapStrategy",
            "start": {"sheetId": sheet_id, "rowIndex": 0, "columnIndex": 0},
        }
    }]
    if freeze:
        requests.append({
            "updateSheetProperties": {
                "properties": {"sheetId": sheet_id, "gridProperties": {"frozenRowCount": 1}},
                "fields": "gridProperties.frozenRowCount",
            }
        })
    return requests


def registry_requests(sheet_id, row_count):
    """Percent format on the weight column, plus the per-category tally block.

    The tally block sits at K:M, one column right of where it started: inserting
    Methodology beside Weight moved it, and a registry built from scratch has to
    land where the live one now is.
    """
    body = {"sheetId": sheet_id, "startRowIndex": 1, "endRowIndex": row_count}
    weight = dict(body, startColumnIndex=5, endColumnIndex=6)
    return [
        {"repeatCell": {
            "range": weight,
            "cell": {"userEnteredFormat": {"numberFormat": {"type": "PERCENT", "pattern": "0%"}}},
            "fields": "userEnteredFormat.numberFormat"}},
        {"updateCells": {
            "rows": [
                {"values": [
                    {"userEnteredValue": {"stringValue": "Category"}, "userEnteredFormat": HEADER_FORMAT},
                    {"userEnteredValue": {"stringValue": "Questions"}, "userEnteredFormat": HEADER_FORMAT},
                    {"userEnteredValue": {"stringValue": "Weight sum"}, "userEnteredFormat": HEADER_FORMAT},
                ]},
                {"values": [
                    {"userEnteredValue": {"formulaValue":
                        '=SORT(UNIQUE(FILTER($B$2:$B,$B$2:$B<>"")))'}},
                    {"userEnteredValue": {"formulaValue":
                        '=ARRAYFORMULA(IF($K$2:$K="","",COUNTIF($B$2:$B,$K$2:$K)))'}},
                    {"userEnteredValue": {"formulaValue":
                        '=ARRAYFORMULA(IF($K$2:$K="","",SUMIF($B$2:$B,$K$2:$K,$F$2:$F)))'}},
                ]},
            ],
            "fields": "userEnteredValue,userEnteredFormat.backgroundColor,"
                      "userEnteredFormat.textFormat,userEnteredFormat.wrapStrategy",
            "start": {"sheetId": sheet_id, "rowIndex": 0, "columnIndex": 10}}},
        {"repeatCell": {
            "range": {"sheetId": sheet_id, "startRowIndex": 1, "endRowIndex": row_count,
                      "startColumnIndex": 12, "endColumnIndex": 13},
            "cell": {"userEnteredFormat": {"numberFormat": {"type": "PERCENT", "pattern": "0%"}}},
            "fields": "userEnteredFormat.numberFormat"}},
        {"updateDimensionProperties": {
            "range": {"sheetId": sheet_id, "dimension": "COLUMNS", "startIndex": 2, "endIndex": 3},
            "properties": {"pixelSize": 460}, "fields": "pixelSize"}},
        {"updateDimensionProperties": {
            "range": {"sheetId": sheet_id, "dimension": "COLUMNS", "startIndex": 6, "endIndex": 7},
            "properties": {"pixelSize": 320}, "fields": "pixelSize"}},
        {"updateDimensionProperties": {
            "range": {"sheetId": sheet_id, "dimension": "COLUMNS", "startIndex": 8, "endIndex": 9},
            "properties": {"pixelSize": 320}, "fields": "pixelSize"}},
    ]


def grade_headers_for(category):
    """The header row of one subject's grading tab."""
    headers = GRADE_HEADERS[:]
    if category in POINTS_CATEGORIES:
        headers[7:9] = POINTS_GRADE_HEADERS
    elif category in SCALE_CATEGORIES:
        headers[7] = f"Score / {SCALE_CATEGORIES[category]}"
    return headers


def grade_tab_requests(sheet_id, row_count, category=None):
    """Validation, formats, widths, the hidden hash column and the edit warning.

    A tab that takes a number in H is validated for a number: leaving the letter
    dropdown in place would invite a grader to type an A that nothing would ever
    read. What column I is validated as follows the rubric - whole points on a
    points tab, the same percentage every letter tab shows on a scale tab, whose
    I column is still a weight.
    """
    body = {"sheetId": sheet_id, "startRowIndex": 1, "endRowIndex": row_count}
    if category in SCORED_CATEGORIES:
        requests = score_validation_requests(sheet_id, row_count, category)
    else:
        requests = [
            {"setDataValidation": {
                "range": dict(body, startColumnIndex=7, endColumnIndex=8),
                "rule": {
                    "condition": {"type": "ONE_OF_LIST",
                                  "values": [{"userEnteredValue": g} for g in VALID_GRADES]},
                    "strict": True, "showCustomUi": True,
                    "inputMessage": "Letter grade: " + ", ".join(VALID_GRADES)}}},
            {"repeatCell": {
                "range": dict(body, startColumnIndex=8, endColumnIndex=9),
                "cell": {"userEnteredFormat": {
                    "numberFormat": {"type": "PERCENT", "pattern": "0%"}}},
                "fields": "userEnteredFormat.numberFormat"}},
        ]
    requests += [
        {"repeatCell": {
            "range": dict(body, startColumnIndex=4, endColumnIndex=6),
            "cell": {"userEnteredFormat": {"wrapStrategy": "WRAP", "verticalAlignment": "TOP"}},
            "fields": "userEnteredFormat.wrapStrategy,userEnteredFormat.verticalAlignment"}},
        {"repeatCell": {
            "range": dict(body, startColumnIndex=9, endColumnIndex=10),
            "cell": {"userEnteredFormat": {"wrapStrategy": "WRAP", "verticalAlignment": "TOP"}},
            "fields": "userEnteredFormat.wrapStrategy,userEnteredFormat.verticalAlignment"}},
        {"updateDimensionProperties": {
            "range": {"sheetId": sheet_id, "dimension": "COLUMNS",
                      "startIndex": HASH_COLUMN, "endIndex": HASH_COLUMN + 1},
            "properties": {"hiddenByUser": True}, "fields": "hiddenByUser"}},
        {"addProtectedRange": {
            "protectedRange": {
                "range": {"sheetId": sheet_id,
                          "startColumnIndex": GENERATED_COLUMNS[0],
                          "endColumnIndex": GENERATED_COLUMNS[1]},
                "description": "Written by the sync script. Edits are overwritten.",
                "warningOnly": True}}},
        {"addProtectedRange": {
            "protectedRange": {
                "range": {"sheetId": sheet_id,
                          "startColumnIndex": HASH_COLUMN, "endColumnIndex": HASH_COLUMN + 1},
                "description": "Answer drift hash. Written by the sync script.",
                "warningOnly": True}}},
    ]
    for start, end, width in GRADE_COLUMN_WIDTHS:
        requests.append({"updateDimensionProperties": {
            "range": {"sheetId": sheet_id, "dimension": "COLUMNS",
                      "startIndex": start, "endIndex": end},
            "properties": {"pixelSize": width}, "fields": "pixelSize"}})
    return requests


# What each housing question is worth, seeded into the registry's Max points
# column when it is blank.
#
# Taken from row 4 of the per-municipality tabs in Homes for Living's workbook,
# which is the row their own percentages are actually divided by. Their Questions
# and Cross Check tabs disagree with it - both put HFL-12 at 5, and Cross Check
# has Victoria at 54 + 11 = 66 rather than 65 - but every scoring tab that
# produced a real candidate percentage says 6, which is also what the question
# is worth on its face: "select up to two" of options scoring 5, 1, -2, 0 and 1.
# These figures reproduce their published totals (Girard 42/66, Brown 35/60).
#
# Seeded rather than demanded, and never overwritten: the numbers are Homes for
# Living's, and one they type over this is the one that counts.
SCORE_MAX_POINTS = {
    "HFL-01": 8, "HFL-02": 8, "HFL-03": 6, "HFL-04": 5, "HFL-05": 3,
    "HFL-06": 6, "HFL-07": 3, "HFL-08": 2, "HFL-09": 6, "HFL-10": 7,
    "HFL-11": 6, "HFL-12": 6,
}

# How wide column H stays for the incumbent record, which is NOT what that row
# is worth: its Max points is Homes for Living's to type, and the registry ships
# it blank. This only has to be wide enough that the obvious choice - a record
# scored out of ten - is not refused by a validation rule that predates it. A
# maximum above this is fine on the registry and is reported by --dry-run and by
# Grading > Check setup, because the column would then refuse the top of its own
# scale until this number is raised.
RECORD_CEILING = 10

# The widest column H is ever validated to without the registry having a say:
# enough for the seeded questions and for a record scored out of RECORD_CEILING.
# On a sheet that already exists, points_ceiling() reads what the registry
# actually says and widens this, because the numbers there are the partner org's
# and they change them - HFL-INC went from 8 to 29 the day after it shipped.
SCORE_CEILING = max(max(SCORE_MAX_POINTS.values()), RECORD_CEILING)

# Housing, and only housing, can score below zero. Homes for Living's rubric has
# options that cost a candidate points rather than earning none - HFL-12's five
# options score 5, 1, -2, 0 and 1 - so an answer can be worse than not answering,
# and their scoring has always said so. The other scored tab does not: Victori'us
# score 0-3 and nothing below, so a scale tab's floor stays 0.
#
# The floor mirrors the ceiling, for the reason the ceiling is a single number:
# validation runs down a whole column and cannot know which question a row holds,
# so it is a typo guard and not the rubric. What any one question can cost is
# Homes for Living's to decide as they score the row, the same way what it can
# earn is theirs; this only has to be wide enough never to refuse a score they
# meant to type.
SCORE_FLOOR = -SCORE_CEILING


def points_ceiling(registry):
    """How wide column H has to be on a points tab, read from the registry.

    Validation runs down a whole column and cannot know which question a row
    holds, so it is one number for the column: a typo guard, not the rubric. What
    it must never do is refuse a score somebody meant to type, and the only way
    to know how big that can be is to read the maxima the partner org has set.

    SCORE_CEILING is the floor of this rather than the answer. A maximum typed
    into the registry widens the column on the next run; one deleted from it does
    not narrow the column below what the seeded questions need, because a grader
    part-way through typing is worse served by a rule that tightens under them.

    Returns None when the registry cannot be read, which leaves the constant in
    charge - the same answer a from-scratch bootstrap gets.
    """
    if registry is None:
        return None
    try:
        values = registry.get_values(f"A2:{a1(REGISTRY_MAX_COLUMN - 1)}")
    except Exception:
        return None
    maxima = []
    for row in values:
        if len(row) < REGISTRY_MAX_COLUMN or \
                (row[1].strip() if len(row) > 1 else "") not in POINTS_CATEGORIES:
            continue
        try:
            maxima.append(abs(float(row[REGISTRY_MAX_COLUMN - 1].strip())))
        except ValueError:
            continue
    return max([SCORE_CEILING] + [int(m) if m == int(m) else m for m in maxima])


def max_points_formula(line):
    """Column I on a scored tab: what this row's question is worth.

    The same shape as the Weight lookup it replaces - a VLOOKUP into the
    registry rather than a copy, so correcting a maximum there corrects every
    candidate's row at once - just pointed at Max points instead. Mirrors
    maxPointsFormula() in appsscript/Code.gs; the two render the same string.
    """
    return (f"=IFERROR(VLOOKUP($D{line},'{REGISTRY_TAB}'"
            f"!$A:${a1(REGISTRY_MAX_COLUMN - 1)},{REGISTRY_MAX_COLUMN},FALSE),\"\")")


def owner_formula(line):
    """Column G on every grading tab: who wrote and grades this question.

    A VLOOKUP into the registry rather than a copy, like the two beside it, so
    correcting an owner there corrects every grading row at once. Mirrors the
    string writeRows() builds in appsscript/Code.gs.

    The column number comes from REGISTRY_OWNER_COLUMN rather than being written
    in, because inserting a column into the registry moves Owner and Sheets does
    not renumber a VLOOKUP when it widens its range.
    """
    return (f"=IFERROR(VLOOKUP($D{line},'{REGISTRY_TAB}'"
            f"!$A:${a1(REGISTRY_OWNER_COLUMN - 1)},{REGISTRY_OWNER_COLUMN},FALSE),\"\")")


def weight_formula(line):
    """Column I on a letter-graded tab, and on a scale tab: this question's
    share of its subject. Mirrors weightFormula() in appsscript/Code.gs."""
    return f"=IFERROR(VLOOKUP($D{line},'{REGISTRY_TAB}'!$A:$F,6,FALSE),\"\")"


def column_i_formula(category, line):
    """Column I: what the question is worth, in the units its tab grades in.

    A maximum on a points tab, and a weight on every other kind - which is to
    say a scale tab's column I is the one a letter tab has, untouched. The whole
    difference on a scale tab is in H.
    """
    return (max_points_formula(line) if category in POINTS_CATEGORIES
            else weight_formula(line))


def band_expression(ratio, bands):
    """A ratio banded into a letter, as a formula fragment.

    One shape for both rubrics, which is the point: the thresholds and the
    letters are the org's, and they disagree - Homes for Living's C- has no
    counterpart in the arts bands, and A starts a point higher there. Mirrors
    bandExpression() in appsscript/Code.gs; the two render the same string.
    """
    letters = ";".join(f'"{letter}"' for _, letter in bands)
    thresholds = ";".join(f"{threshold:g}" for threshold, _ in bands)
    return f'IFERROR(INDEX({{{letters}}},MATCH({ratio},{{{thresholds}}},1)),"")'


def points_rollup_formula(category, line):
    """Category Grades' cumulative letter for a points-scored category.

    Mirrors pointsCategoryFormula() in appsscript/Code.gs. Sum the scores,
    divide by what the questions that carry one were worth, and band the ratio
    at 85/70/60/50.

    The maximum is summed over the scored rows only, which is what makes one
    formula work for every municipality. A question a candidate was never asked
    - HFL-11 in Sooke, HFL-12 anywhere but the five - is fanned out to their tab
    regardless and never scored, so it leaves the total and the maximum alone,
    and they are graded out of the 54 they were actually asked rather than the
    66 somebody in Victoria was.

    The ratio is floored at 0 before it is banded, and that is not cosmetic: the
    scores can be negative (see SCORE_FLOOR), so a candidate can end below zero,
    and MATCH against a band table starting at 0 returns #N/A for anything under
    it. IFERROR would then leave the cell blank, which reads as "not graded yet"
    on a tab where blank means exactly that - the one candidate who has earned an
    F outright would be the one with no grade at all. MAX pins them to the bottom
    band instead. Nothing above 0 moves, and the published points and percentage
    are still the real ones: only the letter stops at F, which is where it stops
    anyway.

    The incumbent record is the one row that is not summed in with the rest. It
    carries RECORD_SHARE of the topic whatever it is scored out of, so the two
    shares are worked out separately and blended: the questionnaire's share of
    its own maximum, and the record's share of its own, weighted 70/30. Summing
    the record in with the questions would instead give it the share its points
    happen to be of the total, which is a different number on every candidate
    and none of them 30%.

    An unscored record leaves the maximum at 0, and the blend collapses to the
    questionnaire alone - which is the whole of the rule for a challenger, and
    the right reading for an incumbent nobody has scored yet. A record scored
    with no Max points beside it collapses the same way rather than dividing by
    zero and blanking the grade; Grading > Check setup reports it, and
    sync-questionnaire.py refuses to publish the subject until it is fixed.
    """
    return "=" + band_expression(points_ratio(category, line), POINTS_BANDS)


def points_ratio(category, line):
    """The share of the available points, as a formula fragment.

    Split out from the letter so `Category Stats` can publish the number the
    letter was banded from without a second implementation of it drifting from
    this one. Everything the docstring above says about the blend and the floor
    is this expression.
    """
    tab = f"'{GRADE_TAB_PREFIX}{category}'"
    where = f"{tab}!$B:$B,$B{line},{tab}!$C:$C,$C{line}"
    asked = f'{tab}!$D:$D,"<>{RECORD_LABEL}"'
    record = f'{tab}!$D:$D,"{RECORD_LABEL}"'
    scored = f'{tab}!$H:$H,"<>"'
    points = f"SUMIFS({tab}!$H:$H,{where},{asked})"
    maximum = f"SUMIFS({tab}!$I:$I,{where},{asked},{scored})"
    record_points = f"SUMIFS({tab}!$H:$H,{where},{record})"
    record_max = f"SUMIFS({tab}!$I:$I,{where},{record},{scored})"
    questionnaire = f"{points}/{maximum}"
    blended = (f"{1 - RECORD_SHARE:g}*{questionnaire}"
               f"+{RECORD_SHARE:g}*{record_points}/{record_max}")
    return f"MAX(IF({record_max}=0,{questionnaire},{blended}),0)"


def scale_rollup_formula(category, line):
    """Category Grades' cumulative letter for a category scored on a fixed scale.

    Mirrors scaleCategoryFormula() in appsscript/Code.gs. Victori'us score every
    arts question 0-3 and weight the questions against each other, so the topic
    grade is the weighted average of the scores read as a share of a straight 3,
    banded at 86/70/60.

    Two things are worth spelling out about the shape:

    The score is read through MATCH into {0;1;2;3} rather than multiplied
    directly, exactly as the letter rollup reads a letter through MATCH into
    {"F","C-","C","B","A"}. SUMPRODUCT evaluates the whole column, and a column
    of mostly-empty cells cannot be multiplied - one "" anywhere in it and the
    arithmetic is #VALUE! before the filter ever gets a say.

    ISNUMBER, not <>"", is what decides whether a row counts. Both keep the
    unscored rows out, and only ISNUMBER also keeps out a letter left behind
    from before the rubric changed: that row drops out of the weight it is
    divided by as well as the total, which is the same courtesy an ungraded row
    gets rather than a silent zero dragging the candidate down.
    """
    return "=" + band_expression(scale_ratio(category, line), SCALE_BANDS)


def scale_ratio(category, line):
    """The weighted average as a share of the scale, as a formula fragment.

    Split out for the same reason points_ratio() is: `Category Stats` shows this
    number, and it has to be this number and not one like it.
    """
    ceiling = SCALE_CATEGORIES[category]
    tab = f"'{GRADE_TAB_PREFIX}{category}'"
    score, weight = f"{tab}!$H$2:$H", f"{tab}!$I$2:$I"
    scale = ";".join(str(n) for n in range(ceiling + 1))
    rows = (f"({tab}!$B$2:$B=$B{line})*({tab}!$C$2:$C=$C{line})"
            f"*ISNUMBER({score})")
    earned = f"SUMPRODUCT({rows}*IFERROR(MATCH({score},{{{scale}}},0)-1,0)*{weight})"
    available = f"({ceiling}*SUMPRODUCT({rows}*{weight}))"
    return f"{earned}/{available}"


def letter_ratio(category, line):
    """Where a letter-graded subject's weighted average sits on the A-F scale.

    The letter rollup lives in Code.gs, because it is written once per candidate
    by the sync and never refreshed from here. Its ratio lives here as well as
    there, because `Category Stats` is written from both: by this script for the
    candidates already on the sheet, and by the sync for each new one. The two
    render the same string, and letters_ratio's shape is the letter formula's
    with the ROUND and the INDEX taken off.

    Divided by four because the scale is F=0 to A=4, so the weighted average is
    a position on it rather than a share of anything earned. That is a different
    measure from the two scored subjects' and the tab's header says so; what
    makes it worth showing is that it is the unrounded number the letter came
    from, and two candidates who both round to A do not generally share it.

    An N/A in the grade column matches nothing, scores 0 and still counts in the
    weight, exactly as it does in the letter. That is the existing rule about
    what N/A means, not a new one: only a blank cell drops a row out.
    """
    tab = f"'{GRADE_TAB_PREFIX}{category}'"
    scale = '{"F","C-","C","B","A"}'
    grade, weight = f"{tab}!$H$2:$H", f"{tab}!$I$2:$I"
    rows = (f"({tab}!$B$2:$B=$B{line})*({tab}!$C$2:$C=$C{line})"
            f'*({grade}<>"")')
    earned = f"SUMPRODUCT({rows}*IFERROR(MATCH({grade},{scale},0)-1,0)*{weight})"
    available = f"SUMPRODUCT({rows}*{weight})"
    return f"{earned}/{available}/{len(VALID_GRADES) - 1}"


def subject_ratio(category, line):
    """The figure behind one subject's letter, in whatever its rubric measures.

    Three rubrics, three meanings, one column on `Category Stats`: a share of
    the points available on a points subject, a share of the scale on a scale
    subject, and a position on the A-F scale on a letter-graded one. Mirrors
    subjectRatio() in appsscript/Code.gs.
    """
    if category in POINTS_CATEGORIES:
        return points_ratio(category, line)
    if category in SCALE_CATEGORIES:
        return scale_ratio(category, line)
    return letter_ratio(category, line)


def stats_formula(category, line):
    """One cell of `Category Stats`: the ratio, or blank where there is none.

    IFERROR rather than a floor, and deliberately: a candidate nobody has graded
    on this subject divides by zero, and a blank cell is the honest answer.
    Housing's own floor is inside points_ratio(), where the letter reads it too.
    """
    return f'=IFERROR({subject_ratio(category, line)},"")'


def rollup_formula(category, line):
    """Category Grades' cell for a category its graders score rather than grade."""
    return (points_rollup_formula(category, line) if category in POINTS_CATEGORIES
            else scale_rollup_formula(category, line))


def seed_max_points(registry):
    """Write the Max points header, and a maximum for any scored row missing one.

    The column sits at M because A:I is the schema both scripts read by position
    and J:L holds the per-category weight tally. Only ever fills a blank cell.
    """
    # The tab was created twelve columns wide, which is exactly the J:L tally
    # block and no more. Writing to M without widening it first fails with
    # "exceeds grid limits" rather than growing the sheet the way a paste would.
    if registry.col_count < REGISTRY_MAX_COLUMN:
        registry.add_cols(REGISTRY_MAX_COLUMN - registry.col_count)

    header = registry.row_values(1)
    if len(header) < REGISTRY_MAX_COLUMN or \
            str(header[REGISTRY_MAX_COLUMN - 1]).strip() != MAX_POINTS_HEADER:
        registry.update([[MAX_POINTS_HEADER]],
                        f"{a1(REGISTRY_MAX_COLUMN - 1)}1", value_input_option="RAW")
        registry.format(f"{a1(REGISTRY_MAX_COLUMN - 1)}1", HEADER_FORMAT)

    values = registry.get_values(f"A2:{a1(REGISTRY_MAX_COLUMN - 1)}")
    updates = []
    for offset, row in enumerate(values, start=2):
        label = row[0].strip() if row else ""
        category = row[1].strip() if len(row) > 1 else ""
        if category not in POINTS_CATEGORIES or label not in SCORE_MAX_POINTS:
            continue
        current = row[REGISTRY_MAX_COLUMN - 1].strip() \
            if len(row) >= REGISTRY_MAX_COLUMN else ""
        if current:
            continue
        updates.append({"range": f"{a1(REGISTRY_MAX_COLUMN - 1)}{offset}",
                        "values": [[SCORE_MAX_POINTS[label]]]})
    if updates:
        registry.batch_update(updates, value_input_option="USER_ENTERED")
    print(f"{REGISTRY_TAB}: {MAX_POINTS_HEADER} "
          + (f"seeded on {len(updates)} row(s)" if updates
             else "already set on every scored row"))


def record_report(registry):
    """What still has to be typed by hand before the incumbent record scores.

    Two cells, both Homes for Living's: the Max points the record is scored out
    of, and the Owner every grading row's column G looks up. Neither is written
    by this script - a maximum is the rubric and an owner is a claim about who
    graded it - so both are reported until they are there.

    Also reports any maximum wider than the column is validated to today. That is
    no longer a problem to fix by hand - points_ceiling() reads these same cells
    and widens the column on the next run - but it is worth saying which run has
    to happen before a grader can type the top of their own scale.
    """
    lines = []
    values = registry.get_values(f"A2:{a1(REGISTRY_MAX_COLUMN - 1)}")
    rows = {row[0].strip(): row for row in values if row and row[0].strip()}

    cell = lambda row, index: row[index].strip() if len(row) > index else ""
    row = rows.get(RECORD_LABEL)
    if row is None:
        lines.append(f"{RECORD_LABEL}: not on the registry yet, would be appended "
                     f"as a {RECORD_CATEGORY} row with no raw columns")
    else:
        maximum = cell(row, REGISTRY_MAX_COLUMN - 1)
        owner = cell(row, REGISTRY_OWNER_COLUMN - 1)
        lines.append(
            f"{RECORD_LABEL}: on the registry, {MAX_POINTS_HEADER} "
            + (f"{maximum}" if maximum
               else f"NOT SET - {RECORD_OWNER} type it, and no incumbent's "
                    f"housing grade counts the record until they do")
            + ", Owner " + (owner or f"NOT SET - put \"{RECORD_OWNER}\" there"))

    for label, row in sorted(rows.items()):
        maximum = cell(row, REGISTRY_MAX_COLUMN - 1)
        try:
            value = float(maximum)
        except ValueError:
            continue
        if value > SCORE_CEILING:
            lines.append(f"  {label}: {MAX_POINTS_HEADER} {maximum} is above the "
                         f"{SCORE_CEILING} column H is validated to by default. "
                         f"This run widens it to {int(value) if value == int(value) else value}; "
                         f"until it does, a grader cannot type the top of that scale.")
    return lines


def rows_needing_owner(sheet):
    """Rows on a grading tab whose column G is not the current Owner lookup.

    Every row on every tab, the day Methodology was inserted into the registry:
    Owner moved from column I to column J, and Sheets widened each VLOOKUP's
    range without renumbering it, so all of them quietly returned Notes instead.
    Code.gs writes column G only on rows it appends, by design, so nothing would
    ever have corrected them.

    Returns the line numbers, so the caller can rewrite one contiguous block.
    """
    values = sheet.get_values("A2:G", value_render_option=ValueRenderOption.formula)
    lines = []
    for offset, row in enumerate(values, start=2):
        if not (row and str(row[0]).strip()):
            continue
        current = str(row[6]).strip() if len(row) > 6 else ""
        if current != owner_formula(offset):
            lines.append(offset)
    return lines


def rows_needing_column_i(sheet, category):
    """Rows on a scored grading tab whose column I is not this rubric's lookup.

    Every row already on the housing tab, the first time this ran: the tab was
    filled with one row per candidate per question while column I still held the
    weight lookup every letter-graded tab uses. Code.gs writes the right formula
    only on rows it appends - by design, so a sync never overwrites a grader -
    so the rows that predate the rubric would keep pointing at a weight nobody
    sets.

    Nothing at all on a scale tab, and that is the rubric being honest rather
    than a check that does not apply: an arts row's column I is the weight
    lookup it always was, so the formula it should hold is the formula already
    in it. Only H changes there.
    """
    values = sheet.get_values("A2:I", value_render_option=ValueRenderOption.formula)
    lines = []
    for offset, row in enumerate(values, start=2):
        if not (row and str(row[0]).strip()):
            continue
        current = str(row[8]).strip() if len(row) > 8 else ""
        if current != column_i_formula(category, offset):
            lines.append(offset)
    return lines


def letters_left_in_scores(sheet):
    """Rows on a scale tab whose H still holds a letter rather than a score.

    Three of them on Grade - Arts when Victori'us' rubric arrived, from the pass
    that graded the first candidate in letters. They are left where they are:
    the new validation stops the next one being typed, and quietly deleting
    somebody's grading is worse than reporting it and letting them retype it as
    a score. Until they do, ISNUMBER in the rollup keeps those rows out of the
    grade entirely rather than scoring them zero.
    """
    values = sheet.get_values("A2:H")
    out = []
    for offset, row in enumerate(values, start=2):
        if not (row and str(row[0]).strip()):
            continue
        current = str(row[7]).strip() if len(row) > 7 else ""
        if not current:
            continue
        try:
            float(current)
        except ValueError:
            out.append((offset, str(row[1]).strip(), str(row[3]).strip(), current))
    return out


def contiguous_runs(lines):
    """[(first, last)] covering `lines` in runs of consecutive row numbers.

    So a caller can write scattered rows without touching what sits between
    them. A range write to Sheets fills every cell in the range, so the only
    safe way to leave a row alone is to keep it out of every range.
    """
    runs = []
    for line in sorted(set(lines)):
        if runs and line == runs[-1][1] + 1:
            runs[-1][1] = line
        else:
            runs.append([line, line])
    return [(first, last) for first, last in runs]


def align_scored_tab(sh, sheet, category, ceiling=None):
    """Point an existing grading tab's H, and its I, at what its rubric grades in.

    None of it is something the Apps Script can do for rows it has already
    written: rename the headers so a grader can see what the columns now hold,
    swap the letter dropdown on H for the rubric's number, and rewrite the
    lookup in I on every row that still points at the wrong one - which on a
    scale tab is none of them, because a weight is what it wanted all along.

    Scores already typed in H are untouched. So is anything in J-L.
    """
    headers = grade_headers_for(category)
    sheet.update([headers[7:9]], "H1:I1", value_input_option="RAW")
    sh.batch_update({"requests":
                     score_validation_requests(sheet.id, sheet.row_count, category,
                                               ceiling)})

    lines = rows_needing_column_i(sheet, category)
    if lines:
        # One write per run of consecutive rows, never one write spanning the
        # first to the last. This used to fill the gaps between them with "",
        # on the assumption that the rows needing a repoint were one block - true
        # the day the housing rubric arrived and every row on the tab wanted the
        # same change, and false ever since.
        #
        # On 2026-09-19 the rows needing it were the 24 HFL-INC rows, scattered
        # from row 80 to row 921, and the gap-filling blanked Max points on the
        # 818 question rows between them: every housing candidate in that span
        # lost their denominator, challengers went blank and incumbents came out
        # of the rollup graded on their record alone. Nothing was unrecoverable,
        # because column I is the same formula on every row of a points tab and
        # a second run rewrites it - but a write that clears cells it was never
        # asked to touch should not be possible in the first place.
        updates = [
            {"range": f"I{first}:I{last}",
             "values": [[column_i_formula(category, line)]
                        for line in range(first, last + 1)]}
            for first, last in contiguous_runs(lines)
        ]
        sheet.batch_update(updates, value_input_option="USER_ENTERED")
    print(f"{GRADE_TAB_PREFIX}{category}: headers set to "
          f"{', '.join(headers[7:9])}, "
          + (f"{len(lines)} row(s) repointed at {headers[8]}" if lines
             else f"every row already reads {headers[8]}"))

    if category in SCALE_CATEGORIES:
        stale = letters_left_in_scores(sheet)
        for line, candidate, label, value in stale:
            print(f"  row {line}: {candidate} {label} still reads {value!r}, "
                  f"which is a letter and not a score. Left alone; it counts "
                  f"towards nothing until somebody retypes it as "
                  f"0-{SCALE_CATEGORIES[category]}.")


def score_validation_requests(sheet_id, row_count, category, ceiling=None):
    """A whole number in H, and the format column I wants under this rubric.

    The range is the rubric's, not one range for every scored tab: a points tab
    is validated against the largest any one question is worth, and a scale tab
    against the top of its own scale, which is the only number a grader is ever
    allowed to type there.

    The floor is where the two rubrics differ most. A points tab accepts a
    negative score, because Homes for Living's options include ones that cost a
    candidate points; a scale tab does not, because 0 is the bottom of the
    Victori'us scale. See SCORE_FLOOR for why a points tab is validated against
    one floor rather than each question's own.

    Column I is a maximum on a points tab, so it loses the percent format every
    letter tab gives it. On a scale tab it is still a weight and keeps one, to
    two places rather than the whole percent a letter tab shows: the eight arts
    weights are sixths and fifteenths, and rounded to whole percents they read
    7 + 17 + 13 + 10 + 17 + 10 + 10 + 17, which is 101% of a topic. The
    questionnaire page already publishes them from the registry to two places,
    and the candidate pages take theirs from this column.
    """
    body = {"sheetId": sheet_id, "startRowIndex": 1, "endRowIndex": row_count}
    points = category in POINTS_CATEGORIES
    if points:
        # points_ceiling() when the caller had a registry to read; the constant
        # when it did not, which is a sheet being built from scratch.
        ceiling = ceiling or SCORE_CEILING
        floor = -ceiling
    else:
        ceiling, floor = SCALE_CATEGORIES[category], 0
    out_of = "this question's maximum" if points else f"{ceiling}"
    column_i = ({"type": "NUMBER", "pattern": "0"} if points
                else {"type": "PERCENT", "pattern": SCALE_WEIGHT_PATTERN})
    return [
        {"setDataValidation": {
            "range": dict(body, startColumnIndex=7, endColumnIndex=8),
            "rule": {
                "condition": {"type": "NUMBER_BETWEEN", "values": [
                    {"userEnteredValue": str(floor)},
                    {"userEnteredValue": str(ceiling)}]},
                "strict": True, "showCustomUi": False,
                "inputMessage": f"Score out of {out_of} "
                                f"({floor} to {ceiling}), or blank if it does "
                                f"not apply"}}},
        {"repeatCell": {
            "range": dict(body, startColumnIndex=8, endColumnIndex=9),
            "cell": {"userEnteredFormat": {"numberFormat": column_i}},
            "fields": "userEnteredFormat.numberFormat"}},
    ]


def refresh_scored_rollup(sh, categories):
    """Point Category Grades' scored columns at the scores instead of the letters.

    Those cells were written once, by the Apps Script, with the weighted-letter
    formula every other category uses, and it never re-touches a cell it has
    written: a partner org typing their own letter over the rollup is the
    intended override, and a sync that undid it would be a bug. That is exactly
    why a switch of rubric cannot come from a sync and has to come from here.

    A cell holding a letter somebody typed is left alone and reported, because
    it is the override the rule above exists to protect. Only a cell still
    holding a formula is rewritten.
    """
    sheet = sheet_by_title(sh, CATEGORY_TAB)
    if sheet is None:
        return
    header = [str(h).strip() for h in sheet.row_values(1)]
    values = sheet.get_values(f"A2:{a1(sheet.col_count - 1)}",
                              value_render_option=ValueRenderOption.formula)

    for category in categories:
        if category not in header:
            continue
        column = header.index(category)
        updates, typed = [], []
        for offset, row in enumerate(values, start=2):
            if not (row and str(row[0]).strip()):
                continue
            current = str(row[column]).strip() if len(row) > column else ""
            wanted = rollup_formula(category, offset)
            if current == wanted:
                continue
            if current and not current.startswith("="):
                typed.append(f"row {offset} ({row[1]}: {current})")
                continue
            updates.append({"range": f"{a1(column)}{offset}", "values": [[wanted]]})

        if updates:
            sheet.batch_update(updates, value_input_option="USER_ENTERED")
        print(f"{CATEGORY_TAB}: {category} rollup "
              + (f"repointed at the scores on {len(updates)} row(s)" if updates
                 else "already reads the scores")
              + (f"; left {len(typed)} typed grade(s) alone: {', '.join(typed)}"
                 if typed else ""))



def graded_categories(registry_values):
    """Categories with a Graded=Yes row, in CATEGORY_ORDER.

    Reads the registry as it actually stands, not the freshly-derived rows
    registry_rows() would propose: a category whose only question has since
    been hand-marked ungraded (Healthcare access, today) drops out here even
    though registry_rows() still calls it "Yes" for a from-scratch bootstrap.
    Code.gs's readRegistry() applies the same Graded=="yes" filter at sync
    time, so the two stay in agreement as the registry is hand-edited.
    """
    have = set()
    for r in registry_values:
        if len(r) >= 5 and str(r[1]).strip() and str(r[4]).strip().lower() == "yes":
            have.add(str(r[1]).strip())
    return [c for c in CATEGORY_ORDER if c in have]


def category_headers(categories):
    """The full Category Grades header row.

    Graded categories get a (grade, deploy) pair; the ungraded ones get a lone
    deploy checkbox, appended last so adding them never shifts a column that
    already holds data.
    """
    headers = ["Key", "Candidate", "Municipality"]
    for c in categories:
        headers += [c, c + CATEGORY_DEPLOY_SUFFIX]
    for c in UNGRADED_GATES:
        headers.append(c + CATEGORY_DEPLOY_SUFFIX)
    return headers


def missing_category_headers(existing, wanted):
    """Headers in `wanted` that `existing` does not already carry, in order.

    Compared by exact header text, which is what both Code.gs and
    sync-questionnaire.py match on. Only ever used to append: a header the sheet
    has and this script does not know about is somebody's own column and is left
    where it is.
    """
    have = {str(h).strip() for h in existing}
    return [h for h in wanted if h not in have]


def append_category_gates(sh, sheet, headers):
    """Add any missing Category Grades columns to a tab that already exists.

    The tab is created once, on the first run, and every run after that used to
    leave it alone entirely. That was fine while the column set was fixed, and
    stopped being fine the moment General and Healthcare access needed gates of
    their own: the tab was already full of graded rows, so recreating it was not
    an option and the columns had to arrive beside them.

    Additive only. Existing columns are never moved, renamed or removed, so a
    grade already typed and a box already ticked keep both their meaning and
    their position.
    """
    existing = sheet.row_values(1)
    missing = missing_category_headers(existing, headers)
    if not missing:
        print(f"{CATEGORY_TAB}: already has every column, left alone")
        return

    start = len(existing)
    if start + len(missing) > sheet.col_count:
        sheet.add_cols(start + len(missing) - sheet.col_count)

    sheet.update(
        [missing],
        f"{a1(start)}1:{a1(start + len(missing) - 1)}1",
        value_input_option="RAW",
    )

    requests = [{
        "repeatCell": {
            "range": {"sheetId": sheet.id, "startRowIndex": 0, "endRowIndex": 1,
                      "startColumnIndex": start, "endColumnIndex": start + len(missing)},
            "cell": {"userEnteredFormat": HEADER_FORMAT},
            "fields": "userEnteredFormat.backgroundColor,userEnteredFormat.textFormat,"
                      "userEnteredFormat.wrapStrategy",
        }
    }]
    for i, header in enumerate(missing):
        width = 70 if header.endswith(CATEGORY_DEPLOY_SUFFIX) else 100
        requests.append({"updateDimensionProperties": {
            "range": {"sheetId": sheet.id, "dimension": "COLUMNS",
                      "startIndex": start + i, "endIndex": start + i + 1},
            "properties": {"pixelSize": width}, "fields": "pixelSize"}})

    # Backfill the candidates already on the tab. Code.gs only ever writes a row
    # it has not seen before, so without this the new gates would sit blank and
    # unrendered on every existing row: an empty cell reads as unpublished, which
    # is right, but there would be no checkbox to tick to change that.
    #
    # Scoped to exactly the rows that hold a key, for the same reason Code.gs
    # scopes its own checkbox rule: a BOOLEAN rule applied to empty rows makes
    # Sheets auto-fill every one with FALSE and corrupts getLastRow().
    filled = len([k for k in sheet.col_values(1)[1:] if str(k).strip()])
    for i, header in enumerate(missing):
        if not header.endswith(CATEGORY_DEPLOY_SUFFIX) or not filled:
            continue
        requests.append({"repeatCell": {
            "range": {"sheetId": sheet.id, "startRowIndex": 1, "endRowIndex": 1 + filled,
                      "startColumnIndex": start + i, "endColumnIndex": start + i + 1},
            "cell": {"userEnteredValue": {"boolValue": False},
                     "dataValidation": {"condition": {"type": "BOOLEAN"}}},
            "fields": "userEnteredValue,dataValidation"}})

    sh.batch_update({"requests": requests})
    print(f"{CATEGORY_TAB}: appended {', '.join(missing)}"
          + (f", unchecked on {filled} existing row(s)" if filled else ""))


def stats_headers(categories):
    """`Category Stats` header row: the identity columns, then one per subject.

    No deploy checkboxes. Nothing on this tab is published or gates anything;
    it exists so a reader can tell 99% from 85% where both say A.
    """
    return ["Key", "Candidate", "Municipality"] + list(categories)


def stats_tab_requests(sheet_id, categories):
    """Widths, the percent format down every subject column, and the warning.

    The whole tab is generated, unlike `Category Grades`, where typing a letter
    over the rollup is the intended override. There is nothing here to override:
    a figure somebody typed over a formula would be a claim about arithmetic
    rather than a judgement, so all of it carries the edit warning.
    """
    requests = [
        {"updateDimensionProperties": {
            "range": {"sheetId": sheet_id, "dimension": "COLUMNS", "startIndex": 0, "endIndex": 1},
            "properties": {"pixelSize": 150}, "fields": "pixelSize"}},
        {"updateDimensionProperties": {
            "range": {"sheetId": sheet_id, "dimension": "COLUMNS", "startIndex": 1, "endIndex": 2},
            "properties": {"pixelSize": 170}, "fields": "pixelSize"}},
        {"updateDimensionProperties": {
            "range": {"sheetId": sheet_id, "dimension": "COLUMNS", "startIndex": 2, "endIndex": 3},
            "properties": {"pixelSize": 130}, "fields": "pixelSize"}},
        {"addProtectedRange": {
            "protectedRange": {
                "range": {"sheetId": sheet_id},
                "description": "Written by the sync script. Edits are overwritten.",
                "warningOnly": True}}},
    ]
    for i in range(len(categories)):
        column = 3 + i
        requests.append({"updateDimensionProperties": {
            "range": {"sheetId": sheet_id, "dimension": "COLUMNS",
                      "startIndex": column, "endIndex": column + 1},
            "properties": {"pixelSize": 100}, "fields": "pixelSize"}})
        requests.append({"repeatCell": {
            "range": {"sheetId": sheet_id, "startRowIndex": 1,
                      "startColumnIndex": column, "endColumnIndex": column + 1},
            "cell": {"userEnteredFormat": {
                "numberFormat": {"type": "PERCENT", "pattern": STATS_PATTERN}}},
            "fields": "userEnteredFormat.numberFormat"}})
    return requests


def sync_stats_tab(sh, categories):
    """Create `Category Stats` if it is missing, and keep it level with the grades.

    Every candidate on `Category Grades` gets a row here, and every row gets the
    formula for every subject. Both halves are additive and idempotent: a row is
    added for a key this tab does not carry, and a cell is rewritten only when it
    is a formula that is not the current one.

    A cell holding something typed is reported and left, the same courtesy
    refresh_scored_rollup() pays a partner org's own letter. Nothing here is
    meant to be typed over, but discovering that somebody did by overwriting it
    is not how this script finds out.
    """
    grades = sheet_by_title(sh, CATEGORY_TAB)
    if grades is None:
        print(f"{STATS_TAB}: no {CATEGORY_TAB} to mirror, skipped")
        return

    headers = stats_headers(categories)
    identity = [row[:3] for row in grades.get_values("A2:C")
                if row and str(row[0]).strip()]

    sheet = sheet_by_title(sh, STATS_TAB)
    if sheet is None:
        sheet = sh.add_worksheet(STATS_TAB, rows=GRADE_TAB_ROWS, cols=len(headers))
        sh.batch_update({"requests": header_row_requests(sheet.id, headers)
                         + stats_tab_requests(sheet.id, categories)})
        print(f"{STATS_TAB}: created with columns {', '.join(categories)}")
    else:
        missing = missing_category_headers(sheet.row_values(1), headers)
        if missing:
            print(f"{STATS_TAB}: missing column(s) {', '.join(missing)}; delete the "
                  f"tab and re-run to rebuild it")
            return

    header = [str(h).strip() for h in sheet.row_values(1)]
    existing = sheet.get_values(f"A2:{a1(len(header) - 1)}",
                                value_render_option=ValueRenderOption.formula)
    rows_by_key = {str(row[0]).strip(): (offset, row)
                   for offset, row in enumerate(existing, start=2)
                   if row and str(row[0]).strip()}

    updates, typed, added = [], [], 0
    line = max(len(existing) + 2, 2)
    for key, candidate, municipality in identity:
        key = str(key).strip()
        if key in rows_by_key:
            at, row = rows_by_key[key]
        else:
            at, row = line, []
            line += 1
            added += 1
            updates.append({"range": f"A{at}:C{at}",
                            "values": [[key, candidate, municipality]]})

        for column, category in enumerate(categories, start=3):
            current = str(row[column]).strip() if len(row) > column else ""
            wanted = stats_formula(category, at)
            if current == wanted:
                continue
            if current and not current.startswith("="):
                typed.append(f"row {at} ({candidate}, {category}: {current})")
                continue
            updates.append({"range": f"{a1(column)}{at}", "values": [[wanted]]})

    if updates:
        sheet.batch_update(updates, value_input_option="USER_ENTERED")
    print(f"{STATS_TAB}: {len(identity)} candidate(s), {added} row(s) added, "
          f"{len(updates) - added} cell(s) written"
          + (f"; left {len(typed)} typed value(s) alone: {', '.join(typed)}"
             if typed else ""))


def category_tab_requests(sheet_id, row_count, categories):
    """Widths and the identity-column edit warning.

    Category columns are deliberately left unprotected: a partner org
    overriding the computed rollup is the point, not a mistake to warn about.
    Each category is immediately followed by its own "<Category> - Deploy to
    website" checkbox, which gates publication of that category's top-level
    grade and detailed scoring - unchecked by default, flipped by hand.

    No checkbox validation is set here, and row_count is unused: applying a
    BOOLEAN rule to Google Sheets' still-empty template rows makes it
    auto-fill every one of them with FALSE, which corrupts getLastRow() into
    reporting the sheet as fully populated. ensureCategoryRows() in Code.gs
    applies the checkbox rule to only the exact rows it just wrote instead.
    """
    requests = [
        {"updateDimensionProperties": {
            "range": {"sheetId": sheet_id, "dimension": "COLUMNS", "startIndex": 0, "endIndex": 1},
            "properties": {"pixelSize": 150}, "fields": "pixelSize"}},
        {"updateDimensionProperties": {
            "range": {"sheetId": sheet_id, "dimension": "COLUMNS", "startIndex": 1, "endIndex": 2},
            "properties": {"pixelSize": 170}, "fields": "pixelSize"}},
        {"updateDimensionProperties": {
            "range": {"sheetId": sheet_id, "dimension": "COLUMNS", "startIndex": 2, "endIndex": 3},
            "properties": {"pixelSize": 130}, "fields": "pixelSize"}},
        {"addProtectedRange": {
            "protectedRange": {
                "range": {"sheetId": sheet_id,
                          "startColumnIndex": CATEGORY_GENERATED_COLUMNS[0],
                          "endColumnIndex": CATEGORY_GENERATED_COLUMNS[1]},
                "description": "Written by the sync script. Edits are overwritten.",
                "warningOnly": True}}},
    ]
    for i in range(len(categories)):
        grade_col = 3 + 2 * i
        deploy_col = grade_col + 1
        requests.append({"updateDimensionProperties": {
            "range": {"sheetId": sheet_id, "dimension": "COLUMNS",
                      "startIndex": grade_col, "endIndex": grade_col + 1},
            "properties": {"pixelSize": 100}, "fields": "pixelSize"}})
        requests.append({"updateDimensionProperties": {
            "range": {"sheetId": sheet_id, "dimension": "COLUMNS",
                      "startIndex": deploy_col, "endIndex": deploy_col + 1},
            "properties": {"pixelSize": 70}, "fields": "pixelSize"}})
    return requests


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true", help="print the plan, write nothing")
    ap.add_argument("--refresh", action="store_true",
                    help="also rewrite Question, Type, Raw columns and Notes on rows that "
                         "already exist, for when the form's wording or columns changed. "
                         "Category, Graded, Weight, Methodology and Owner are "
                         "hand-maintained and never touched.")
    ap.add_argument("--sheet-id", default=os.environ.get("QUESTIONNAIRE_SUBMISSIONS_SHEET_ID"),
                    help="submission sheet key (default: $QUESTIONNAIRE_SUBMISSIONS_SHEET_ID)")
    args = ap.parse_args()

    if not args.sheet_id:
        sys.exit("Set QUESTIONNAIRE_SUBMISSIONS_SHEET_ID or pass --sheet-id.")

    sh = gspread.oauth().open_by_key(args.sheet_id)
    raw = sh.worksheet(RAW_TAB)
    header = raw.get_values("1:1")[0]

    rows = registry_rows(header)
    categories = [c for c in CATEGORY_ORDER if any(r[1] == c for r in rows)]
    unmapped = sorted({r[0] for r in rows if not r[1]})

    print(f"{RAW_TAB}: {len(header)} columns")
    print(f"{len(rows)} graded questions across {len(categories)} subjects")
    for c in categories:
        labels = [r[0] for r in rows if r[1] == c]
        print(f"  {c:20s} {len(labels):2d}  {', '.join(labels)}")
    if unmapped:
        print(f"  UNMAPPED: {', '.join(unmapped)} - fix PREFIX_CATEGORY or set by hand")

    # Looked up here rather than with the other tabs below, because the points
    # rubric's summary line states the width its maxima require.
    cg_registry = sheet_by_title(sh, REGISTRY_TAB)
    width = points_ceiling(cg_registry) or SCORE_CEILING

    scored = [c for c in categories if c in SCORED_CATEGORIES]
    for c in scored:
        if c in POINTS_CATEGORIES:
            print(f"  {c} is scored in points: H is a score from {-width} "
                  f"to {width} out of I, negatives included, and the "
                  f"{CATEGORY_TAB} letter is banded from the two.")
        else:
            print(f"  {c} is scored 0-{SCALE_CATEGORIES[c]}: H is that score, I "
                  f"stays the question's weight, and the {CATEGORY_TAB} letter is "
                  f"banded from the weighted average of the two.")

    existing = {ws.title for ws in sh.worksheets()}
    wanted = ([REGISTRY_TAB] + [GRADE_TAB_PREFIX + c for c in categories]
              + [CATEGORY_TAB, STATS_TAB, LOG_TAB])
    missing = [t for t in wanted if t not in existing]
    print(f"\nTabs: {len(wanted)} wanted, {len(wanted) - len(missing)} present, "
          f"{len(missing)} to create")
    for t in missing:
        print(f"  + {t}")

    # Column-level preview for a tab that already exists. Without this the whole
    # Category Grades migration is invisible to --dry-run, which returns below
    # long before the code that would run it, and the one thing worth previewing
    # about a write to a tab full of grades is which columns it adds.
    cg_preview = sheet_by_title(sh, CATEGORY_TAB)
    if cg_preview is not None and cg_registry is not None:
        pending = missing_category_headers(
            cg_preview.row_values(1),
            category_headers(graded_categories(cg_registry.get_values("A2:E"))))
        print(f"\n{CATEGORY_TAB}: "
              + (f"{len(pending)} column(s) to append: {', '.join(pending)}"
                 if pending else "every column already present"))
        subjects = graded_categories(cg_registry.get_values("A2:E"))
        stats = sheet_by_title(sh, STATS_TAB)
        filled = len([k for k in cg_preview.col_values(1)[1:] if str(k).strip()])
        print(f"{STATS_TAB}: "
              + (f"would be created with {len(subjects)} subject column(s) and "
                 f"{filled} candidate row(s): {', '.join(subjects)}"
                 if stats is None
                 else f"exists; would be levelled with {CATEGORY_TAB}'s "
                      f"{filled} candidate row(s)"))
        for line in record_report(cg_registry):
            print(line)

    for category in scored:
        ws = sheet_by_title(sh, GRADE_TAB_PREFIX + category)
        if ws is None:
            continue
        expected = grade_headers_for(category)[7:9]
        have = [str(h).strip() for h in ws.row_values(1)[7:9]]
        print(f"{GRADE_TAB_PREFIX}{category}: H and I read {', '.join(have)}"
              + ("" if have == expected else f" and would become {', '.join(expected)}")
              + f", {len(rows_needing_column_i(ws, category))} row(s) to repoint "
                f"at {expected[1]}")
        for line, candidate, label, value in (letters_left_in_scores(ws)
                                              if category in SCALE_CATEGORIES else []):
            print(f"  row {line}: {candidate} {label} reads {value!r}, a letter "
                  f"on a tab that now scores 0-{SCALE_CATEGORIES[category]}. "
                  f"Left alone, and counts towards nothing until it is retyped.")

    if args.dry_run:
        print("\n--dry-run: nothing written.")
        return

    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    directory = os.path.expanduser("~/livable-crd-backups")
    os.makedirs(directory, exist_ok=True)
    path = os.path.join(directory, f"submissions-tabs-{stamp}.json")
    with open(path, "w") as fh:
        json.dump({ws.title: ws.get_values() for ws in sh.worksheets()}, fh)
    print(f"\nBacked up to {path}")

    # Registry first: the grading tabs' weight formulas point at it.
    registry = sheet_by_title(sh, REGISTRY_TAB)
    if registry is None:
        registry = sh.add_worksheet(REGISTRY_TAB, rows=max(len(rows) + 50, 200),
                                    cols=REGISTRY_MAX_COLUMN + 1)
        sh.batch_update({"requests": header_row_requests(registry.id, REGISTRY_HEADERS)
                         + registry_requests(registry.id, registry.row_count)})
        registry.update(rows, f"A2:I{len(rows) + 1}", value_input_option="USER_ENTERED")
        print(f"{REGISTRY_TAB}: created with {len(rows)} questions")
    else:
        listed = [r[0].strip() for r in registry.get_values("A2:A") if r and r[0].strip()]
        have = set(listed)
        new = [r for r in rows if r[0] not in have]
        if new:
            first = len(listed) + 2
            registry.update(new, f"A{first}:I{first + len(new) - 1}",
                            value_input_option="USER_ENTERED")
        refreshed = 0
        if args.refresh:
            by_label = {r[0]: r for r in rows}
            updates = []
            for offset, label in enumerate(listed):
                row = by_label.get(label)
                if not row:
                    continue
                line = offset + 2
                # C-D and H-I only: B, E, F, G and J are the hand-maintained ones.
                updates.append({"range": f"C{line}:D{line}", "values": [[row[2], row[3]]]})
                updates.append({"range": f"H{line}:I{line}", "values": [[row[7], row[8]]]})
                refreshed += 1
            if updates:
                registry.batch_update(updates, value_input_option="USER_ENTERED")
        print(f"{REGISTRY_TAB}: {len(new)} question(s) appended, {len(listed)} already listed"
              + (f", {refreshed} refreshed" if args.refresh else ""))

    # Before the grading tabs: their Max points lookups point at this column.
    # Only a points category has any; a scale category's questions are weighted
    # like every letter-graded one and want nothing in M.
    if [c for c in scored if c in POINTS_CATEGORIES]:
        seed_max_points(registry)
        for line in record_report(registry):
            print(line)

    # Read before the grading tabs, because their column H validation is sized
    # from it. Homes for Living's maxima are theirs to change, and the column has
    # to stay wide enough to accept whatever they set.
    ceiling = points_ceiling(registry)

    for category in categories:
        title = GRADE_TAB_PREFIX + category
        is_scored = category in SCORED_CATEGORIES
        headers = grade_headers_for(category)
        ws = sheet_by_title(sh, title)
        if ws is not None:
            if is_scored:
                align_scored_tab(sh, ws, category, ceiling)
            else:
                print(f"{title}: already exists, left alone")
            continue
        ws = sh.add_worksheet(title, rows=GRADE_TAB_ROWS, cols=len(headers))
        sh.batch_update({"requests": header_row_requests(ws.id, headers)
                         + grade_tab_requests(ws.id, GRADE_TAB_ROWS, category)})
        print(f"{title}: created")

    # Read back what the registry actually says now (including any hand edits,
    # e.g. Healthcare access marked ungraded) to decide which categories a
    # partner org gets a top-level grade column for.
    cg_categories = graded_categories(registry.get_values("A2:E"))
    cg_headers = category_headers(cg_categories)
    cg = sheet_by_title(sh, CATEGORY_TAB)
    if cg is None:
        cg = sh.add_worksheet(CATEGORY_TAB, rows=GRADE_TAB_ROWS, cols=len(cg_headers))
        sh.batch_update({"requests": header_row_requests(cg.id, cg_headers)
                         + category_tab_requests(cg.id, GRADE_TAB_ROWS, cg_categories)})
        print(f"{CATEGORY_TAB}: created with columns {', '.join(cg_categories)} "
              f"(each with a Deploy to website checkbox), plus a gate for "
              f"{', '.join(UNGRADED_GATES)}")
    else:
        append_category_gates(sh, cg, cg_headers)

    # Last, because it points at the score columns the steps above just made.
    if scored:
        refresh_scored_rollup(sh, scored)

    # After Category Grades, whose rows it mirrors and whose subjects it reads.
    sync_stats_tab(sh, cg_categories)

    log = sheet_by_title(sh, LOG_TAB)
    if log is None:
        log = sh.add_worksheet(LOG_TAB, rows=2000, cols=len(LOG_HEADERS))
        sh.batch_update({"requests": header_row_requests(log.id, LOG_HEADERS)})
        print(f"{LOG_TAB}: created")
    else:
        print(f"{LOG_TAB}: already exists, left alone")

    print("\nNext: set a Weight on every registry row that wants one - every "
          "category but " + ", ".join(sorted(POINTS_CATEGORIES)) + ", which wants "
          f"a {MAX_POINTS_HEADER} instead - each totalling 100%, then deploy "
          "scripts/questionnaire/appsscript/Code.gs. Until that deploy, no "
          f"{RECORD_LABEL} row is created for anybody: this script writes the "
          "registry row and the rollup, and the Apps Script is what fans the "
          "row out to the incumbents.")


if __name__ == "__main__":
    main()
