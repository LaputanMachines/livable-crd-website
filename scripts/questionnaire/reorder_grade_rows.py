#!/usr/bin/env python3
"""Put a grading tab's rows back in registry order, one candidate at a time.

`syncAll` in `appsscript/Code.gs` appends: a candidate who submits gets their
whole block of questions written at the bottom of each `Grade - <Subject>` tab
in registry order, which reads well. A question that arrives later does not.
`move_question.py` appends the moved question's rows as one batch below every
candidate's block, so HFL-12 sits in a run of twenty-four rows at the bottom
instead of after each candidate's HFL-11, and a grader scrolling one candidate's
housing answers has to jump.

Nothing reads a grading tab positionally - `syncAll`, `onGradeEdit` and
`sync-questionnaire.py` all key on column A - so the fix is a pure reorder:
every row keeps its grade, rationale, grader, timestamp and answer hash, and
only the two lookup formulas (Owner in G, Weight or Max points in I) are
rebuilt, because both are keyed on the row they sit in.

A value write carries no cell format, and `Graded at` has no format of its own:
the column is left unformatted by `grading_tabs.py`, and each cell only becomes
a date because `onGradeEdit`'s `setValue(new Date())` formats the one cell it
touches. So a timestamp landing on a row whose old occupant was never graded
arrives as a bare serial number - 46277.17805 rather than 9/12/2026 - with the
value right and the format missing. `--apply` sets DATE on every `Graded at`
cell that holds a number and lacks it, whether or not anything moved, so a
second run repairs a tab an earlier one left like that.

Candidates stay in the order they first appear; within a candidate, questions
are sorted into `Question Registry` order. A label the registry doesn't list
sorts to the end of its candidate's block and is reported.

Read-only unless --apply is passed, and every tab is dumped to
~/livable-crd-backups/ before the first write.

Usage:
  QUESTIONNAIRE_SUBMISSIONS_SHEET_ID=... python3 scripts/questionnaire/reorder_grade_rows.py Housing
  QUESTIONNAIRE_SUBMISSIONS_SHEET_ID=... python3 scripts/questionnaire/reorder_grade_rows.py Housing --apply
"""

import argparse
import datetime
import json
import os
import sys

import gspread
from gspread.utils import ValueRenderOption

from grading_tabs import (
    CATEGORY_ORDER, GRADE_HEADERS, GRADE_TAB_PREFIX, REGISTRY_TAB, a1,
    column_i_formula, grade_headers_for, sheet_by_title,
)
from move_question import owner_formula

# Registry columns, 1-based.
R_LABEL, R_CATEGORY = 1, 2

# Grading tab columns, 1-based. Mirrors GRADE_HEADERS.
G_KEY, G_CANDIDATE, G_LABEL, G_OWNER, G_WEIGHT, G_GRADED_AT = 1, 2, 4, 7, 9, 12

# What a formatted `Graded at` cell carries. Anything else on a cell holding a
# timestamp is the missing-format case above.
DATE_FORMATS = {"DATE", "DATE_TIME"}

WIDTH = len(GRADE_HEADERS)


def backup(sh):
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    directory = os.path.expanduser("~/livable-crd-backups")
    os.makedirs(directory, exist_ok=True)
    path = os.path.join(directory, f"submissions-tabs-{stamp}.json")
    with open(path, "w") as fh:
        json.dump({ws.title: ws.get_values() for ws in sh.worksheets()}, fh)
    return path


def registry_order(registry_values, category):
    """Labels of `category`, in the order the registry lists them."""
    order = []
    for row in registry_values[1:]:
        if not row:
            continue
        if row[R_CATEGORY - 1].strip() == category:
            label = row[R_LABEL - 1].strip()
            if label and label not in order:
                order.append(label)
    return order


def rebuilt(row, line, category):
    """One row rewritten for the line it is about to land on.

    Everything is carried across verbatim except G and I, which are VLOOKUPs
    keyed on `$D<line>` and so have to follow the row rather than be copied.
    """
    cell = lambda i: row[i] if i < len(row) else ""
    out = [cell(i) for i in range(WIDTH)]
    out[G_OWNER - 1] = owner_formula(line)
    out[G_WEIGHT - 1] = column_i_formula(category, line)
    return out


def undated(sh, tab, last_line):
    """Lines whose `Graded at` holds a number that isn't formatted as a date."""
    col = a1(G_GRADED_AT - 1)
    meta = sh.fetch_sheet_metadata({
        "ranges": [f"'{tab.title}'!{col}2:{col}{last_line}"],
        "fields": "sheets(data(rowData(values("
                  "effectiveValue(numberValue),effectiveFormat(numberFormat)))))",
    })
    data = meta["sheets"][0].get("data", [{}])[0].get("rowData", [])
    lines = []
    for i, row in enumerate(data, start=2):
        cell = (row.get("values") or [{}])[0]
        if "numberValue" not in cell.get("effectiveValue", {}):
            continue
        fmt = cell.get("effectiveFormat", {}).get("numberFormat", {})
        if fmt.get("type") not in DATE_FORMATS:
            lines.append(i)
    return lines


def date_format_requests(sheet_id, lines):
    return [
        {"repeatCell": {
            "range": {"sheetId": sheet_id, "startRowIndex": line - 1, "endRowIndex": line,
                      "startColumnIndex": G_GRADED_AT - 1, "endColumnIndex": G_GRADED_AT},
            "cell": {"userEnteredFormat": {"numberFormat": {"type": "DATE"}}},
            "fields": "userEnteredFormat.numberFormat"}}
        for line in lines
    ]


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("category", help="the subject whose tab to reorder, e.g. Housing")
    ap.add_argument("--apply", action="store_true",
                    help="do it. Without this the script prints the plan and writes nothing.")
    ap.add_argument("--sheet-id", default=os.environ.get("QUESTIONNAIRE_SUBMISSIONS_SHEET_ID"),
                    help="submission sheet key (default: $QUESTIONNAIRE_SUBMISSIONS_SHEET_ID)")
    args = ap.parse_args()

    if not args.sheet_id:
        sys.exit("Set QUESTIONNAIRE_SUBMISSIONS_SHEET_ID or pass --sheet-id.")
    if args.category not in CATEGORY_ORDER:
        sys.exit(f"{args.category!r} is not one of {', '.join(CATEGORY_ORDER)}.")

    sh = gspread.oauth().open_by_key(args.sheet_id)

    registry = sheet_by_title(sh, REGISTRY_TAB)
    tab = sheet_by_title(sh, GRADE_TAB_PREFIX + args.category)
    if registry is None:
        sys.exit(f'No "{REGISTRY_TAB}" tab.')
    if tab is None:
        sys.exit(f'No "{GRADE_TAB_PREFIX}{args.category}" tab.')

    labels = registry_order(registry.get_values(), args.category)
    if not labels:
        sys.exit(f"{REGISTRY_TAB} lists no {args.category} question.")

    values = tab.get_values(value_render_option=ValueRenderOption.formula)
    expected = grade_headers_for(args.category)
    if not values or [c.strip() for c in values[0][:WIDTH]] != expected:
        sys.exit(f"{GRADE_TAB_PREFIX}{args.category}: header is not the expected "
                 f"{', '.join(expected)}. Refusing to touch it.")

    rows = [(i, row) for i, row in enumerate(values[1:], start=2)
            if any(str(c).strip() for c in row)]
    blank = [i for i, row in rows if not str(row[G_KEY - 1]).strip()]
    if blank:
        sys.exit(f"{GRADE_TAB_PREFIX}{args.category}: row(s) "
                 f"{', '.join(map(str, blank))} have no Key. Refusing to reorder.")

    # Candidates in the order they first appear; questions in registry order.
    seen, candidates, unknown = {}, [], set()
    for i, row in rows:
        key = str(row[G_KEY - 1]).split("|")[0]
        if key not in seen:
            seen[key] = len(candidates)
            candidates.append(key)
    def sort_key(item):
        i, row = item
        key = str(row[G_KEY - 1]).split("|")[0]
        label = str(row[G_LABEL - 1]).strip()
        if label not in labels:
            unknown.add(label)
            return (seen[key], len(labels), i)
        return (seen[key], labels.index(label), i)

    ordered = sorted(rows, key=sort_key)
    moves = [(old, new) for new, (old, _) in enumerate(ordered, start=2) if old != new]

    print(f'{GRADE_TAB_PREFIX}{args.category}: {len(rows)} row(s), '
          f'{len(candidates)} candidate(s), question order '
          f'{" ".join(labels)}')
    if unknown:
        print(f"  not in the registry, sorted to the end of each block: "
              f"{', '.join(sorted(unknown))}")
    stale = undated(sh, tab, len(values))
    if stale:
        print(f"  {len(stale)} Graded at cell(s) hold a timestamp with no date "
              f"format: {', '.join(f'{a1(G_GRADED_AT - 1)}{line}' for line in stale[:12])}"
              + (" ..." if len(stale) > 12 else ""))

    if not moves:
        print("  already in order.")
        if not stale:
            print("  Nothing to do.")
            return
        if not args.apply:
            print("\nNothing written. Re-run with --apply to set the date format(s).")
            return
        print(f"\nBacked up to {backup(sh)}")
        sh.batch_update({"requests": date_format_requests(tab.id, stale)})
        print(f"{GRADE_TAB_PREFIX}{args.category}: {len(stale)} date format(s) set")
        return

    by_old = dict(rows)
    print(f"  {len(moves)} row(s) move:")
    for old, new in moves[:12]:
        row = by_old[old]
        print(f"    row {old:4d} -> {new:4d}  {str(row[G_KEY - 1]):24s} "
              f"{str(row[G_CANDIDATE - 1])}")
    if len(moves) > 12:
        print(f"    ... and {len(moves) - 12} more")

    first, last = min(n for _, n in moves), max(n for _, n in moves)
    block = [rebuilt(row, line, args.category)
             for line, (_, row) in enumerate(ordered, start=2)
             if first <= line <= last]
    rng = f"A{first}:{a1(WIDTH - 1)}{last}"
    print(f"  rewriting {rng} ({len(block)} row(s)); "
          f"Owner and {grade_headers_for(args.category)[8]} re-derived for "
          f"their new row numbers")

    if not args.apply:
        print("\nNothing written. Re-run with --apply to do it.")
        return

    print(f"\nBacked up to {backup(sh)}")
    tab.update(block, rng, value_input_option="USER_ENTERED")
    print(f"{GRADE_TAB_PREFIX}{args.category}: {len(block)} row(s) rewritten, "
          f"{len(moves)} of them moved")

    # After the values, not before: a Graded at cell that had no date format
    # keeps none through the write, and one that moves onto an unformatted cell
    # loses the format it had. Re-read rather than reuse `stale` from the plan.
    now_stale = undated(sh, tab, len(values))
    if now_stale:
        sh.batch_update({"requests": date_format_requests(tab.id, now_stale)})
        print(f"{GRADE_TAB_PREFIX}{args.category}: {len(now_stale)} date format(s) set")
    print("\nNext: Grading > Check setup in the sheet. Nothing should be "
          "appended or flagged - the keys did not change.")


if __name__ == "__main__":
    main()
