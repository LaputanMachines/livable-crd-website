#!/usr/bin/env python3
"""Correct spelling slips in one candidate's submitted answers, at their request.

Written for one event and kept as the record of it, like `reset_unsure_rows.py`.

David Gauthier (Esquimalt, submission 9Naz17Q) writes English as a second
language and asked the coalition to fix the typos in his written answers. That
is a narrow licence and this script keeps to it: misspellings, a wrong word that
is plainly the neighbouring one ("then"/"than", "polls"/"poles"), doubled
spaces, and a proper noun's capitals. Grammar, tone, word order and argument are
left exactly as he wrote them, so nothing here changes what any answer says or
what a grader read. Every change is listed in EDITS, in full, so the correction
is auditable against the backup taken before the write.

The edits land on the raw Tally tab, not on the grading tabs, because the raw
tab is the authority. `syncAll()` in appsscript/Code.gs rebuilds each grading
tab's Answer from it and would revert a grade-tab edit on its next run. Once
this has been applied, run the sheet's Grading menu -> sync: the corrected text
is copied onto the grading rows, the changed cells are tinted as drift, and the
grades already typed are left alone for a human to glance at.

Nothing but the answer cells is touched: no column is added, renamed or moved,
and no other candidate's row is read or written.

Dry-run by default.

  python3 scripts/questionnaire/fix_answer_typos.py            # preview
  python3 scripts/questionnaire/fix_answer_typos.py --apply    # do it
"""

import argparse
import csv
import datetime
import io
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import apply_rubric as ar  # noqa: E402

RAW_TAB = "2026 Municipal Elections"
SUBMISSION_ID = "9Naz17Q"
CANDIDATE = "David Gauthier"

# Raw-tab columns, 0-based, as sync-questionnaire.py numbers them.
RAW_SUBMISSION_ID = 0
RAW_FIRST_NAME = 3
RAW_LAST_NAME = 4

# Header prefix of a question column. Same pattern as sync-questionnaire.py's
# LABEL_RE and grading_tabs.py's; change all three together.
LABEL_RE = re.compile(r"^([A-Z]{2,4}-(?:\d{2}|GEN)(?:-[A-Za-z]+)?):\s*(.*)$", re.S)

# label -> [(what is there now, what replaces it)]. Each `old` has to appear
# exactly once in exactly one of that label's cells or the run stops: these are
# cells a person typed and a substring that matches twice, or matches a cell
# nobody expected, means the answer is not the one this list was written
# against. A pair whose `old` is already gone is reported and skipped, so
# re-running after a partial run is safe.
EDITS = {
    "GEN-GEN": [("to be apart of", "to be a part of")],
    "HFL-04": [
        ("a varients of", "a variance of"),
        ("muncipalities", "municipalities"),
    ],
    # Doubled space, not a word: "provincial  legislation".
    "HFL-10": [("provincial  legislation", "provincial legislation")],
    "REC-02": [("inclusitivty", "inclusivity")],
    "TRN-GEN": [
        ("these  transit", "these transit"),
        ("the skytrain in Van", "the SkyTrain in Van"),
    ],
    "CLI-11": [
        ("strait of hormuz", "Strait of Hormuz"),
        ("more prevalent then mass", "more prevalent than mass"),
        ("in it's own way", "in its own way"),
    ],
    "CLI-GEN": [("things get  examined", "things get examined")],
    "ART-05": [
        ("recogciliation", "reconciliation"),
        ("rescrictions", "restrictions"),
        ("oppurtunities", "opportunities"),
    ],
    # "design or the roads" - the slip is o for f, and "of" is the only reading
    # the rest of the sentence allows.
    "ROL-04": [("layout & design or the roads", "layout & design of the roads")],
    "ROL-GEN": [("more then a thousand", "more than a thousand")],
    "WLK-02": [("archie browning arena", "Archie Browning Arena")],
    "WLK-05": [
        ("We only use to have", "We only used to have"),
        ("polls at the entrances", "poles at the entrances"),
        ("to cross walks around schools", "to crosswalks around schools"),
        ("to strength awareness", "to strengthen awareness"),
        ("consideration/prioritizes", "consideration/priorities"),
    ],
    "WLK-06": [
        ("archie browning arena", "Archie Browning Arena"),
        ("the side walks/medians", "the sidewalks/medians"),
    ],
}


def a1(col_index):
    """0-based column index to its A1 letters. Mirrors grading_tabs.py's a1()."""
    letters = ""
    n = col_index + 1
    while n:
        n, rem = divmod(n - 1, 26)
        letters = chr(65 + rem) + letters
    return letters


def fetch_raw(sheet_id, timeout=120):
    """The raw tab as a list of rows, header first.

    The first header cell is checked because gviz answers a request for a
    missing tab with the spreadsheet's first sheet rather than an error, and a
    renamed tab would otherwise be edited as if it were this one.
    """
    params = {"tqx": "out:csv", "sheet": RAW_TAB, "headers": "1"}
    url = ar.GVIZ.format(id=sheet_id) + "?" + urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        if e.code in (401, 403, 404):
            sys.exit(f"cannot read {RAW_TAB!r}: HTTP {e.code}")
        raise
    rows = list(csv.reader(io.StringIO(body)))
    if not rows or not rows[0] or rows[0][0].strip() != "Submission ID":
        sys.exit(f"{RAW_TAB!r} does not start with a Submission ID column. "
                 f"Nothing written.")
    return rows


def locate(rows):
    """(sheet row number, the row) for the one submission this is written for."""
    found = [(i, r) for i, r in enumerate(rows[1:], start=2)
             if r and r[RAW_SUBMISSION_ID].strip() == SUBMISSION_ID]
    if len(found) != 1:
        sys.exit(f"{len(found)} rows carry submission {SUBMISSION_ID}, expected "
                 f"1. Nothing written.")
    number, row = found[0]
    name = " ".join(x.strip() for x in (row[RAW_FIRST_NAME], row[RAW_LAST_NAME]))
    if name != CANDIDATE:
        sys.exit(f"submission {SUBMISSION_ID} is {name!r}, not {CANDIDATE!r}. "
                 f"Nothing written.")
    return number, row


def columns_for(header):
    """label -> the 0-based indexes of every column headed with that label.

    A select-all question spends one column on the joined answer and one per
    option, all under the same label, so a label rarely means one column.
    """
    out = {}
    for i, cell in enumerate(header):
        match = LABEL_RE.match(cell.strip())
        if match:
            out.setdefault(match.group(1), []).append(i)
    return out


def plan(rows):
    """The cells to rewrite: [(label, sheet row, column index, old text, new
    text, [(old, new) applied])]. Exits on any surprise."""
    header = rows[0]
    number, row = locate(rows)
    by_label = columns_for(header)

    out, skipped = [], []
    for label, pairs in EDITS.items():
        if label not in by_label:
            sys.exit(f"no column headed {label} on {RAW_TAB!r}. Nothing written.")
        cells = {i: row[i] if i < len(row) else "" for i in by_label[label]}

        target, applied, done = None, [], []
        for old, new in pairs:
            hit = [i for i, text in cells.items() if text.count(old) == 1]
            more = [i for i, text in cells.items() if text.count(old) > 1]
            if more:
                sys.exit(f"{label}: {old!r} appears more than once in "
                         f"{a1(more[0])}{number}. Nothing written.")
            if not hit:
                # Already corrected, or the answer has changed underneath this
                # list. Those are told apart by the replacement being there.
                if any(new in text for text in cells.values()):
                    done.append((old, new))
                    continue
                sys.exit(f"{label}: {old!r} is not in the answer and neither is "
                         f"{new!r}. The answer has changed. Nothing written.")
            if len(hit) > 1:
                sys.exit(f"{label}: {old!r} is in {len(hit)} of that label's "
                         f"columns. Nothing written.")
            if target is not None and hit[0] != target:
                sys.exit(f"{label}: edits land in two different columns, "
                         f"{a1(target)} and {a1(hit[0])}. Nothing written.")
            target = hit[0]
            applied.append((old, new))

        if done:
            skipped.append((label, done))
        if not applied:
            continue
        before = cells[target]
        after = before
        for old, new in applied:
            after = after.replace(old, new)
        out.append((label, number, target, before, after, applied))
    return out, skipped


def context(text, needle, width=44):
    """The needle with a little of the sentence either side, for the preview."""
    at = text.find(needle)
    start, end = max(0, at - width), min(len(text), at + len(needle) + width)
    return ("..." if start else "") + text[start:end] + ("..." if end < len(text) else "")


def write(sheet_id, edits):
    import gspread  # imported late: only the write path needs it installed

    sh = gspread.oauth().open_by_key(sheet_id)
    stamp = datetime.datetime.now().strftime("%Y%m%dT%H%M%S")
    print(f"backup: {ar.backup(sh, stamp)}")

    ws = ar.worksheet_by_title(sh, RAW_TAB)
    updates = []
    for _label, number, column, before, after, _applied in edits:
        live = ws.cell(number, column + 1).value or ""
        if live != before:
            sys.exit(f"{a1(column)}{number} has changed since it was read. "
                     f"Nothing further written.")
        updates.append({"range": f"{a1(column)}{number}", "values": [[after]]})
    ws.batch_update(updates, value_input_option="RAW")
    print(f"rewrote {len(updates)} answer cell(s) on {RAW_TAB}")
    print("now run the sheet's Grading menu -> sync so the grading tabs pick "
          "the corrected text up")


def main():
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--sheet-id", default=ar.default_sheet_id())
    p.add_argument("--apply", action="store_true", help="write to the sheet")
    args = p.parse_args()

    if not args.sheet_id:
        sys.exit("no sheet id: set QUESTIONNAIRE_SUBMISSIONS_SHEET_ID")

    edits, skipped = plan(fetch_raw(args.sheet_id))
    for label, done in skipped:
        for old, new in done:
            print(f"  {label}: {old!r} -> {new!r} already applied, left alone")
    for label, number, column, before, after, applied in edits:
        print(f"  {label} at {a1(column)}{number}")
        for old, new in applied:
            print(f"    {old!r} -> {new!r}")
            print(f"      {context(before, old)}")

    changes = sum(len(applied) for *_, applied in edits)
    print(f"{changes} correction(s) in {len(edits)} answer cell(s), "
          f"{CANDIDATE} ({SUBMISSION_ID})")
    if not edits:
        return
    if not args.apply:
        print("dry run; pass --apply to write")
        return
    write(args.sheet_id, edits)


if __name__ == "__main__":
    main()
