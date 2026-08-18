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
                      H-J typed by graders, M a hidden drift hash.
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

RAW_TAB = "Raw Submissions"
REGISTRY_TAB = "Question Registry"
LOG_TAB = "Sync Log"
GRADE_TAB_PREFIX = "Grade - "

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
    "REC": "Reconciliation",
    "TRN": "Transit",
    "CLI": "Climate",
    "ART": "Arts",
    "ROL": "Rolling & cycling",
    "WLK": "Walking",
    "HLT": "Healthcare access",
}

# Questions whose subject isn't the one their prefix implies. HFL-12 is the
# infrastructure funding gap, which finalize.py grades as Governance even though
# Homes for Living submitted it.
CATEGORY_OVERRIDE = {
    "HFL-12": "Governance",
}

# Ungraded: the "-GEN" per-topic comment boxes are free text with nothing to
# score, and the GEN-* questions are published unscored.
SKIP_LABELS = {"GEN-01", "GEN-02"}

# Tab order, so the sheet reads the way the scorecard does.
CATEGORY_ORDER = [
    "Housing", "Transit", "Walking", "Rolling & cycling", "Climate",
    "Arts", "Governance", "Reconciliation", "Healthcare access",
]

# Owner is hand-maintained and sits after the generated columns: who submitted
# the question, so a grader knows whom to ask. The script writes its header on a
# fresh sheet and never touches the values, including on --refresh. Anything
# further right must start at column M: J:L holds the per-category tally block.
REGISTRY_HEADERS = [
    "Label", "Category", "Question", "Type", "Graded", "Weight",
    "Raw columns", "Notes", "Owner",
]

GRADE_HEADERS = [
    "Key", "Candidate", "Municipality", "Label", "Question", "Answer", "Owner",
    "Grade", "Weight", "Rationale", "Grader", "Graded at", "Answer hash",
]

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
            f"{first + 1}-{last + 1}",
            notes,
        ])
    return rows


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
    """Percent format on the weight column, plus the per-category tally block."""
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
                        '=ARRAYFORMULA(IF($J$2:$J="","",COUNTIF($B$2:$B,$J$2:$J)))'}},
                    {"userEnteredValue": {"formulaValue":
                        '=ARRAYFORMULA(IF($J$2:$J="","",SUMIF($B$2:$B,$J$2:$J,$F$2:$F)))'}},
                ]},
            ],
            "fields": "userEnteredValue,userEnteredFormat.backgroundColor,"
                      "userEnteredFormat.textFormat,userEnteredFormat.wrapStrategy",
            "start": {"sheetId": sheet_id, "rowIndex": 0, "columnIndex": 9}}},
        {"repeatCell": {
            "range": {"sheetId": sheet_id, "startRowIndex": 1, "endRowIndex": row_count,
                      "startColumnIndex": 11, "endColumnIndex": 12},
            "cell": {"userEnteredFormat": {"numberFormat": {"type": "PERCENT", "pattern": "0%"}}},
            "fields": "userEnteredFormat.numberFormat"}},
        {"updateDimensionProperties": {
            "range": {"sheetId": sheet_id, "dimension": "COLUMNS", "startIndex": 2, "endIndex": 3},
            "properties": {"pixelSize": 460}, "fields": "pixelSize"}},
        {"updateDimensionProperties": {
            "range": {"sheetId": sheet_id, "dimension": "COLUMNS", "startIndex": 7, "endIndex": 8},
            "properties": {"pixelSize": 320}, "fields": "pixelSize"}},
    ]


def grade_tab_requests(sheet_id, row_count):
    """Validation, formats, widths, the hidden hash column and the edit warning."""
    body = {"sheetId": sheet_id, "startRowIndex": 1, "endRowIndex": row_count}
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
            "cell": {"userEnteredFormat": {"numberFormat": {"type": "PERCENT", "pattern": "0%"}}},
            "fields": "userEnteredFormat.numberFormat"}},
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


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true", help="print the plan, write nothing")
    ap.add_argument("--refresh", action="store_true",
                    help="also rewrite Question, Type, Raw columns and Notes on rows that "
                         "already exist, for when the form's wording or columns changed. "
                         "Category, Graded, Weight and Owner are hand-maintained and never "
                         "touched.")
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

    existing = {ws.title for ws in sh.worksheets()}
    wanted = [REGISTRY_TAB] + [GRADE_TAB_PREFIX + c for c in categories] + [LOG_TAB]
    missing = [t for t in wanted if t not in existing]
    print(f"\nTabs: {len(wanted)} wanted, {len(wanted) - len(missing)} present, "
          f"{len(missing)} to create")
    for t in missing:
        print(f"  + {t}")

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
        registry = sh.add_worksheet(REGISTRY_TAB, rows=max(len(rows) + 50, 200), cols=12)
        sh.batch_update({"requests": header_row_requests(registry.id, REGISTRY_HEADERS)
                         + registry_requests(registry.id, registry.row_count)})
        registry.update(rows, f"A2:H{len(rows) + 1}", value_input_option="USER_ENTERED")
        print(f"{REGISTRY_TAB}: created with {len(rows)} questions")
    else:
        listed = [r[0].strip() for r in registry.get_values("A2:A") if r and r[0].strip()]
        have = set(listed)
        new = [r for r in rows if r[0] not in have]
        if new:
            first = len(listed) + 2
            registry.update(new, f"A{first}:H{first + len(new) - 1}",
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
                # C-D and G-H only: B, E and F are the hand-maintained ones.
                updates.append({"range": f"C{line}:D{line}", "values": [[row[2], row[3]]]})
                updates.append({"range": f"G{line}:H{line}", "values": [[row[6], row[7]]]})
                refreshed += 1
            if updates:
                registry.batch_update(updates, value_input_option="USER_ENTERED")
        print(f"{REGISTRY_TAB}: {len(new)} question(s) appended, {len(listed)} already listed"
              + (f", {refreshed} refreshed" if args.refresh else ""))

    for category in categories:
        title = GRADE_TAB_PREFIX + category
        ws = sheet_by_title(sh, title)
        if ws is not None:
            print(f"{title}: already exists, left alone")
            continue
        ws = sh.add_worksheet(title, rows=GRADE_TAB_ROWS, cols=len(GRADE_HEADERS))
        sh.batch_update({"requests": header_row_requests(ws.id, GRADE_HEADERS)
                         + grade_tab_requests(ws.id, GRADE_TAB_ROWS)})
        print(f"{title}: created")

    log = sheet_by_title(sh, LOG_TAB)
    if log is None:
        log = sh.add_worksheet(LOG_TAB, rows=2000, cols=len(LOG_HEADERS))
        sh.batch_update({"requests": header_row_requests(log.id, LOG_HEADERS)})
        print(f"{LOG_TAB}: created")
    else:
        print(f"{LOG_TAB}: already exists, left alone")

    print("\nNext: set a Weight on every registry row (each category should total "
          "100%), then deploy scripts/questionnaire/appsscript/Code.gs.")


if __name__ == "__main__":
    main()
