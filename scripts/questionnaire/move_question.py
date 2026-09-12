#!/usr/bin/env python3
"""Move one question's grading rows from one subject's tab to another.

A question's subject is the `Category` cell on its `Question Registry` row, and
changing that cell alone is not enough. `syncAll` in `appsscript/Code.gs` keys
rows per tab, so a question that changes category appends a fresh batch of blank
rows to its new `Grade - <Subject>` tab and abandons whatever graders typed on
the old one - the answers, the grades, the rationales and the drift hashes all
stay behind on a tab nothing reads any more.

This script does the move properly: it carries the grade, rationale, grader,
timestamp and answer hash across, re-derives the Owner and Weight lookups for
the row numbers they land on, deletes the rows it copied, and rebalances the
weights of whatever is left behind in the old category.

Written for HFL-12, the infrastructure funding gap. Homes for Living count it
towards the housing score in their own workbook and hand back one cumulative
housing grade, so scoring it as Governance here put the same answer in the wrong
subject and left our housing percentages unable to match theirs.

Read-only unless --apply is passed, and every tab is dumped to
~/livable-crd-backups/ before the first write.

Usage:
  QUESTIONNAIRE_SUBMISSIONS_SHEET_ID=... python3 scripts/questionnaire/move_question.py HFL-12 --to Housing
  QUESTIONNAIRE_SUBMISSIONS_SHEET_ID=... python3 scripts/questionnaire/move_question.py HFL-12 --to Housing --apply
"""

import argparse
import datetime
import json
import os
import sys

import gspread

from grading_tabs import (
    CATEGORY_ORDER, GRADE_HEADERS, GRADE_TAB_PREFIX, POINTS_CATEGORIES,
    REGISTRY_TAB, a1, column_i_formula, sheet_by_title, weight_formula,
)

# Registry columns, 1-based, for the two cells this script writes.
R_LABEL, R_CATEGORY, R_WEIGHT = 1, 2, 6

# Grading tab columns, 1-based. Mirrors GRADE_HEADERS.
G_LABEL, G_OWNER, G_GRADE, G_WEIGHT, G_HASH = 4, 7, 8, 9, 13


def owner_formula(line):
    return f"=IFERROR(VLOOKUP($D{line},'{REGISTRY_TAB}'!$A:$I,9,FALSE),\"\")"


def moved_row(row, line, category):
    """One source row rewritten for the line it is about to land on.

    A-F and the hash come across untouched: they are the candidate, the question
    and the answer, and none of that changed. G and I are lookups keyed on the
    row they sit in, so they are rebuilt rather than copied - and I is rebuilt
    against the units the destination grades in, a maximum on a points tab and a
    weight on every other kind. H and J-L are the grader's work and are the
    whole reason this is a move and not a re-sync.

    H is carried across as it stands, which for a question moving between tabs
    that grade in different units is a value landing in a cell that now wants a
    different one. Nothing is dropped on the way: the only question this has had
    to move, HFL-12, had no grade typed on any of its rows, and silently
    discarding a grader's work would be worse than landing it somewhere visible.
    """
    cell = lambda i: row[i] if i < len(row) else ""
    out = [cell(i) for i in range(6)]                    # key .. answer
    out.append(owner_formula(line))                      # owner
    out.append(cell(7))                                  # grade or score
    out.append(column_i_formula(category, line))         # weight or max points
    out += [cell(9), cell(10), cell(11)]                 # rationale, grader, graded at
    out.append(cell(12))                                 # answer hash
    return out


def backup(sh):
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    directory = os.path.expanduser("~/livable-crd-backups")
    os.makedirs(directory, exist_ok=True)
    path = os.path.join(directory, f"submissions-tabs-{stamp}.json")
    with open(path, "w") as fh:
        json.dump({ws.title: ws.get_values() for ws in sh.worksheets()}, fh)
    return path


def delete_rows_requests(sheet_id, lines):
    """One deleteDimension per row, bottom-up so earlier indices stay valid."""
    return [
        {"deleteDimension": {"range": {
            "sheetId": sheet_id, "dimension": "ROWS",
            "startIndex": line - 1, "endIndex": line}}}
        for line in sorted(lines, reverse=True)
    ]


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("label", help="question label to move, e.g. HFL-12")
    ap.add_argument("--to", required=True, help="the category it should belong to")
    ap.add_argument("--apply", action="store_true",
                    help="do it. Without this the script prints the plan and writes nothing.")
    ap.add_argument("--sheet-id", default=os.environ.get("QUESTIONNAIRE_SUBMISSIONS_SHEET_ID"),
                    help="submission sheet key (default: $QUESTIONNAIRE_SUBMISSIONS_SHEET_ID)")
    args = ap.parse_args()

    if not args.sheet_id:
        sys.exit("Set QUESTIONNAIRE_SUBMISSIONS_SHEET_ID or pass --sheet-id.")
    if args.to not in CATEGORY_ORDER:
        sys.exit(f"{args.to!r} is not one of {', '.join(CATEGORY_ORDER)}.")

    sh = gspread.oauth().open_by_key(args.sheet_id)

    registry = sheet_by_title(sh, REGISTRY_TAB)
    if registry is None:
        sys.exit(f'No "{REGISTRY_TAB}" tab.')
    registry_values = registry.get_values()

    line_for_label, category = None, None
    for i, row in enumerate(registry_values[1:], start=2):
        if row and row[R_LABEL - 1].strip() == args.label:
            line_for_label = i
            category = row[R_CATEGORY - 1].strip()
    if not line_for_label:
        sys.exit(f"{REGISTRY_TAB} lists no {args.label}.")
    if category == args.to:
        sys.exit(f"{args.label} is already in {args.to}; nothing to move.")

    source = sheet_by_title(sh, GRADE_TAB_PREFIX + category)
    target = sheet_by_title(sh, GRADE_TAB_PREFIX + args.to)
    if source is None or target is None:
        sys.exit(f'Need both "{GRADE_TAB_PREFIX}{category}" and "{GRADE_TAB_PREFIX}{args.to}".')

    # Only a points category's questions trade their weight for a maximum. A
    # scale category weights its questions exactly as a letter-graded one does,
    # so a question moving into Arts keeps its weight and joins that category's
    # 100%.
    points = args.to in POINTS_CATEGORIES
    width = len(GRADE_HEADERS)

    moving = [(i, row) for i, row in enumerate(source.get_values()[1:], start=2)
              if len(row) >= G_LABEL and row[G_LABEL - 1].strip() == args.label]
    graded = [i for i, row in moving if len(row) >= G_GRADE and row[G_GRADE - 1].strip()]

    # What is left in the old category once the question goes, and what each of
    # those is then worth. A letter-graded category's weights have to total 100%
    # or Code.gs's setup check complains, and dropping a question from six to
    # five without touching them leaves it at 86%.
    staying = [i for i, row in enumerate(registry_values[1:], start=2)
               if row and row[R_CATEGORY - 1].strip() == category
               and row[R_LABEL - 1].strip() != args.label]
    reweight = category not in POINTS_CATEGORIES and staying

    print(f"{args.label}: {category} -> {args.to}")
    print(f"  {GRADE_TAB_PREFIX}{category}: {len(moving)} row(s) to move, "
          f"{len(graded)} of them already graded")
    for i, row in moving[:5]:
        print(f"    row {i:4d}  {row[1]} ({row[2]})  grade={row[G_GRADE - 1] or '-'!r}")
    if len(moving) > 5:
        print(f"    ... and {len(moving) - 5} more")
    first = max(len(target.get_values()) + 1, 2)
    print(f"  {GRADE_TAB_PREFIX}{args.to}: appending {len(moving)} row(s) at row {first}"
          + (", with Max points in column I" if points else ""))
    print(f"  {REGISTRY_TAB} row {line_for_label}: Category {category!r} -> {args.to!r}"
          + (", Weight cleared (scored in points; set its Max points instead)"
             if points else ""))
    if reweight:
        print(f"  {REGISTRY_TAB}: {len(staying)} remaining {category} row(s) "
              f"reweighted to =1/{len(staying)}")

    if not args.apply:
        print("\nNothing written. Re-run with --apply to do it.")
        return

    print(f"\nBacked up to {backup(sh)}")

    values = [moved_row(row, first + n, args.to) for n, (_, row) in enumerate(moving)]
    if values:
        target.update(values, f"A{first}:{a1(width - 1)}{first + len(values) - 1}",
                      value_input_option="USER_ENTERED")
        sh.batch_update({"requests": delete_rows_requests(source.id, [i for i, _ in moving])})
        print(f"{GRADE_TAB_PREFIX}{args.to}: {len(values)} row(s) appended at {first}")
        print(f"{GRADE_TAB_PREFIX}{category}: {len(moving)} row(s) deleted")

    updates = [{"range": f"B{line_for_label}", "values": [[args.to]]}]
    if points:
        updates.append({"range": f"F{line_for_label}", "values": [[""]]})
    for line in staying:
        updates.append({"range": f"F{line}", "values": [[f"=1/{len(staying)}"]]})
    registry.batch_update(updates, value_input_option="USER_ENTERED")
    print(f"{REGISTRY_TAB}: category set"
          + (f", {len(staying)} weight(s) rebalanced" if reweight else ""))

    print("\nNext: Grading > Sync now in the sheet, then Grading > Check setup.")


if __name__ == "__main__":
    main()
