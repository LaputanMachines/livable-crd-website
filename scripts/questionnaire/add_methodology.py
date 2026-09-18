#!/usr/bin/env python3
"""Insert the registry's `Methodology` column, and repair what that moves.

Written for one event and kept as the record of it, like `resubmit.py`. On
2026-09-18 the committee wanted a column where a grader could describe, in their
own words, how a question is scored - beside the `Weight` that says what it is
worth, not appended past the tally block where the schema's own rule would have
put it.

Inserting a column in the middle of `Question Registry` is not a one-cell edit,
because two families of formula on the grading tabs look the registry up **by
column number**:

    Owner       =VLOOKUP($D2,'Question Registry'!$A:$I,9,FALSE)
    Max points  =VLOOKUP($D2,'Question Registry'!$A:$M,13,FALSE)

Google Sheets widens a VLOOKUP's *range* when a column is inserted inside it -
`$A:$I` becomes `$A:$J` - and never touches the column *number*. So after the
insert, `9` points at `Notes` instead of `Owner`, and `13` points at the tally
block's `Weight sum` instead of `Max points`. Neither errors. Every grading row
would quietly show a paragraph of internal commentary as the question's owner,
and every housing row would lose the maximum its score is divided by, changing
every housing grade and every housing percentage on the sheet.

So this does the insert and the repair in one run: 3,421 Owner lookups across
eight grading tabs, and 775 Max points lookups on `Grade - Housing`. Nothing
else on any grading tab is touched - no grade, no rationale, no hash.

The scripts that read the registry by position change with it, and are already
updated in this repository: `REGISTRY_HEADERS` and `REGISTRY_MAX_COLUMN` in
`grading_tabs.py`, `REGISTRY_READ_WIDTH` and `REGISTRY_OWNER_COLUMN` in
`appsscript/Code.gs`, and the `R_*` indexes in `../sync-questionnaire.py`, which
now also refuses to run at all unless the tab's header is the one it expects.

Order matters, and only in one direction. Run this first; the repository's copy
of `Code.gs` must then be pasted in and redeployed, because the *running* copy
writes the old `$A:$I,9` into every row it appends. `sync-questionnaire.py` in
CI fails loudly against either layout it does not recognise rather than
publishing the wrong column, so it is safe either side of the change.

Dry-run by default. It asserts the old layout before it writes anything: run it
twice and the second run stops rather than inserting a second column.

  python3 scripts/questionnaire/add_methodology.py            # preview
  python3 scripts/questionnaire/add_methodology.py --apply    # do it
"""

import argparse
import datetime
import json
import os
import sys

import gspread
from gspread.utils import ValueRenderOption

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from grading_tabs import (  # noqa: E402
    GRADE_TAB_PREFIX, HEADER_FORMAT, POINTS_CATEGORIES, REGISTRY_TAB,
    a1, column_i_formula, owner_formula, sheet_by_title,
)

# What the tab reads before this runs, and what it must read after. Taken from
# REGISTRY_HEADERS as it stood on either side of the change rather than derived,
# so a registry that has drifted some other way stops the run.
HEADERS_BEFORE = ["Label", "Category", "Question", "Type", "Graded", "Weight",
                  "Raw columns", "Notes", "Owner"]
HEADERS_AFTER = ["Label", "Category", "Question", "Type", "Graded", "Weight",
                 "Methodology", "Raw columns", "Notes", "Owner"]

# 0-based index the new column is inserted at: G, between Weight and Raw columns.
INSERT_AT = 6
NEW_HEADER = "Methodology"
NEW_WIDTH = 320


def grading_tabs(sh):
    return [ws for ws in sh.worksheets() if ws.title.startswith(GRADE_TAB_PREFIX)]


def repair_plan(sh):
    """{tab title: (owner lines, column I lines)} for every grading tab.

    Computed against the registry as it stands *after* the insert, which is why
    it is called after it: the formulas these compare against are the new ones.
    """
    plan = {}
    for ws in grading_tabs(sh):
        category = ws.title[len(GRADE_TAB_PREFIX):]
        values = ws.get_values("A2:I", value_render_option=ValueRenderOption.formula)
        owners, maxima = [], []
        for offset, row in enumerate(values, start=2):
            if not (row and str(row[0]).strip()):
                continue
            if (str(row[6]).strip() if len(row) > 6 else "") != owner_formula(offset):
                owners.append(offset)
            if category in POINTS_CATEGORIES and \
                    (str(row[8]).strip() if len(row) > 8 else "") != \
                    column_i_formula(category, offset):
                maxima.append(offset)
        plan[ws.title] = (owners, maxima)
    return plan


def write_block(sheet, column, lines, render):
    """Rewrite one column on the given lines, as a single contiguous update.

    A block rather than one update per row: 3,421 separate ranges is 3,421
    entries in a batch the API will not take. Rows inside the span that need no
    change are written back as themselves, read from the sheet first so nothing
    is invented.
    """
    if not lines:
        return 0
    first, last = min(lines), max(lines)
    current = sheet.get_values(f"{column}{first}:{column}{last}",
                               value_render_option=ValueRenderOption.formula)
    wanted = set(lines)
    block = []
    for offset in range(first, last + 1):
        existing = current[offset - first] if offset - first < len(current) else []
        block.append([render(offset) if offset in wanted
                      else (existing[0] if existing else "")])
    sheet.update(block, f"{column}{first}:{column}{last}",
                 value_input_option="USER_ENTERED")
    return len(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="write; default is a preview")
    ap.add_argument("--sheet-id", default=os.environ.get("QUESTIONNAIRE_SUBMISSIONS_SHEET_ID"))
    args = ap.parse_args()
    if not args.sheet_id:
        sys.exit("Set QUESTIONNAIRE_SUBMISSIONS_SHEET_ID.")

    sh = gspread.oauth().open_by_key(args.sheet_id)
    registry = sheet_by_title(sh, REGISTRY_TAB)
    if registry is None:
        sys.exit(f"No '{REGISTRY_TAB}' tab.")

    header = [str(h).strip() for h in registry.row_values(1)]
    print(f"{REGISTRY_TAB} header: {header}")

    if header[:len(HEADERS_AFTER)] == HEADERS_AFTER:
        print(f"\n'{NEW_HEADER}' is already there. Nothing to do.")
        return 0
    if header[:len(HEADERS_BEFORE)] != HEADERS_BEFORE:
        print(f"\nSTOPPING: expected the first {len(HEADERS_BEFORE)} columns to read "
              f"{HEADERS_BEFORE}. Something else has changed on this tab.")
        return 1

    print(f"\nWould insert '{NEW_HEADER}' at column {a1(INSERT_AT)}, between "
          f"Weight and Raw columns.")
    print(f"  Raw columns {a1(INSERT_AT)} -> {a1(INSERT_AT + 1)}, "
          f"Notes {a1(INSERT_AT + 1)} -> {a1(INSERT_AT + 2)}, "
          f"Owner {a1(INSERT_AT + 2)} -> {a1(INSERT_AT + 3)}")
    print(f"  the Category/Questions/Weight sum block J:L -> K:M, Max points M -> N")

    tabs = grading_tabs(sh)
    counts = {ws.title: len([r for r in ws.get_values("A2:A") if r and r[0].strip()])
              for ws in tabs}
    total = sum(counts.values())
    housing = sum(n for t, n in counts.items()
                  if t[len(GRADE_TAB_PREFIX):] in POINTS_CATEGORIES)
    print(f"\nWould then repair, because Sheets renumbers neither lookup:")
    print(f"  Owner      -> {owner_formula(2)}   on {total} row(s) across {len(tabs)} tab(s)")
    for title in sorted(counts):
        if counts[title]:
            print(f"      {title:28s} {counts[title]:5d}")
    print(f"  Max points -> {column_i_formula('Housing', 2)}   on {housing} housing row(s)")

    if not args.apply:
        print("\nPreview only. Re-run with --apply to write.")
        return 0

    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    directory = os.path.expanduser("~/livable-crd-backups")
    os.makedirs(directory, exist_ok=True)
    path = os.path.join(directory, f"submissions-tabs-{stamp}.json")
    with open(path, "w") as fh:
        json.dump({ws.title: ws.get_values() for ws in sh.worksheets()}, fh)
    print(f"\nBacked up to {path}")

    sh.batch_update({"requests": [
        {"insertDimension": {
            "range": {"sheetId": registry.id, "dimension": "COLUMNS",
                      "startIndex": INSERT_AT, "endIndex": INSERT_AT + 1},
            "inheritFromBefore": False}},
        {"updateCells": {
            "rows": [{"values": [{"userEnteredValue": {"stringValue": NEW_HEADER},
                                  "userEnteredFormat": HEADER_FORMAT}]}],
            "fields": "userEnteredValue,userEnteredFormat.backgroundColor,"
                      "userEnteredFormat.textFormat,userEnteredFormat.wrapStrategy",
            "start": {"sheetId": registry.id, "rowIndex": 0, "columnIndex": INSERT_AT}}},
        {"updateDimensionProperties": {
            "range": {"sheetId": registry.id, "dimension": "COLUMNS",
                      "startIndex": INSERT_AT, "endIndex": INSERT_AT + 1},
            "properties": {"pixelSize": NEW_WIDTH}, "fields": "pixelSize"}},
    ]})
    print(f"{REGISTRY_TAB}: '{NEW_HEADER}' inserted at {a1(INSERT_AT)}")

    plan = repair_plan(sh)
    for ws in tabs:
        owners, maxima = plan[ws.title]
        category = ws.title[len(GRADE_TAB_PREFIX):]
        wrote = write_block(ws, "G", owners, owner_formula)
        fixed = write_block(ws, "I", maxima,
                            lambda line: column_i_formula(category, line))
        print(f"{ws.title}: {wrote} Owner lookup(s) rewritten"
              + (f", {fixed} Max points lookup(s) rewritten" if fixed else ""))

    print("\nNext: paste appsscript/Code.gs into the sheet and cut a new deployment "
          "version. Until then the running copy writes the old Owner lookup into "
          "every row it appends.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
