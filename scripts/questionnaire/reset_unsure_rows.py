#!/usr/bin/env python3
"""Reset the rows where Unsure was graded C before the policy changed.

Written for one event and kept as the record of it, like `add_methodology.py`.

`rubrics.py` has graded Unsure as a blank since 2026-09-13, on the reasoning
that an absent position is not a weak yes and should drop out of the category
rollup rather than score against a candidate. That decision was taken on CLI-04
and UNSURE_GRADE says so. Rows typed C before it were left alone at the time,
which left two questions grading the same word two ways depending on the week
the row happened to be graded.

On 2026-09-20 the remaining Unsure rows on GOV-02 and WLK-04 were graded, and
the coalition chose to bring the older rows into line rather than publish a
question whose answer depends on when it was looked at. That is what this does,
and it is the only thing it does.

These are cells a person typed, so nothing is guessed: the row must still hold
the label it is listed under, the answer must still be Unsure, and the grade
must still be the C this was asked to clear. Any row that has moved or changed
stops the run before anything is written. A row already reset is reported and
skipped, so re-running is safe.

Dry-run by default.

  python3 scripts/questionnaire/reset_unsure_rows.py            # preview
  python3 scripts/questionnaire/reset_unsure_rows.py --apply    # do it
"""

import argparse
import datetime
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import apply_rubric as ar  # noqa: E402

ANSWER = "Unsure"
CLEARING = "C"
GRADER = "vp@bettertransityyj.ca"

K, LAB, ANS, GR, RAT = 0, 3, 5, 7, 9

# One entry per row, because a blank cell says nothing on its own and whoever
# reads the sheet needs to know the blank was chosen rather than missed.
# Keyed on the row Key; the tab and label are carried so a row cannot be
# written on the strength of its Key alone.
RESETS = {
    "9NoVzkG|GOV-02": (
        "Grade - Governance", "GOV-02",
        "Answered unsure on a regional service that would design, build and "
        "maintain local infrastructure shared across the region. An unsure "
        "states no position, so the row is left out of the grade rather than "
        "scored as partial support."
    ),
    "BE0ojzN|GOV-02": (
        "Grade - Governance", "GOV-02",
        "Undecided on pooling the design, construction and upkeep of local "
        "infrastructure into a regional service. Nothing was committed either "
        "way, so the row carries no letter and drops out of the category "
        "grade."
    ),
    "M17jPLE|GOV-02": (
        "Grade - Governance", "GOV-02",
        "No position taken on the shared regional service. Uncertainty is "
        "read as neither support nor opposition, so the grade cell is left "
        "blank."
    ),
    "1WBEQBl|WLK-04": (
        "Grade - Walking", "WLK-04",
        "Answered unsure on expanding pedestrian priority and car free "
        "streets in the town centre. An unsure withholds a position rather "
        "than opposing the change, so the row is left out of the grade."
    ),
    "2jVpz2g|WLK-04": (
        "Grade - Walking", "WLK-04",
        "Undecided on whether to expand pedestrian priority and car free "
        "streets. Nothing was committed for or against, so no letter is "
        "written and the row drops out of the category grade."
    ),
}


def tabs():
    order = []
    for tab, _label, _text in RESETS.values():
        if tab not in order:
            order.append(tab)
    return order


def find(sheet_id, tab, graded_at):
    """(rows to write, rows already reset) for one tab. Exits on any surprise."""
    rows = ar.fetch_tab(sheet_id, tab)
    if rows is None:
        sys.exit(f"no tab {tab!r}, or it is not shared")

    wanted = {k: v for k, v in RESETS.items() if v[0] == tab}
    todo, done, seen = {}, [], set()
    for i, row in enumerate(rows[1:], start=2):
        row = row + [""] * (13 - len(row))
        key = row[K].strip()
        if key not in wanted:
            continue
        seen.add(key)
        _tab, label, text = wanted[key]
        if row[LAB].strip() != label:
            sys.exit(f"{key} is on {row[LAB]!r}, not {label}. Nothing written.")
        if " ".join(row[ANS].split()).rstrip(".") != ANSWER:
            sys.exit(f"{key} now answers {row[ANS]!r}, not {ANSWER!r}. "
                     f"Nothing written.")
        grade = row[GR].strip()
        if not grade and row[RAT].strip():
            done.append(key)
            continue
        if grade != CLEARING:
            sys.exit(f"{key} holds grade {grade!r}, not {CLEARING!r}. Somebody "
                     f"has changed it since. Nothing written.")
        todo[key] = (i, text)

    missing = sorted(set(wanted) - seen)
    if missing:
        sys.exit(f"not on {tab!r}: {missing}. Nothing written.")
    return todo, done


def write(sh, tab, todo, graded_at):
    ws = ar.worksheet_by_title(sh, tab)
    live = ws.col_values(K + 1)
    updates = []
    for key, (row, text) in todo.items():
        if row > len(live) or live[row - 1].strip() != key:
            sys.exit(f"row {row} of {tab!r} now holds "
                     f"{live[row - 1].strip()!r}, not {key!r}. The tab moved; "
                     f"nothing further written.")
        updates.append({"range": f"H{row}", "values": [[""]]})
        updates.append({"range": f"J{row}", "values": [[text]]})
        updates.append({"range": f"K{row}", "values": [[GRADER]]})
        updates.append({"range": f"L{row}", "values": [[graded_at]]})
    ws.batch_update(updates, value_input_option="USER_ENTERED")
    print(f"reset {len(todo)} row(s) on {tab}")


def main():
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--sheet-id", default=ar.default_sheet_id())
    p.add_argument("--date", help="Graded at, YYYY-MM-DD; default today")
    p.add_argument("--apply", action="store_true", help="write to the sheet")
    args = p.parse_args()

    if not args.sheet_id:
        sys.exit("no sheet id: set QUESTIONNAIRE_SUBMISSIONS_SHEET_ID")

    day = (datetime.date.fromisoformat(args.date) if args.date
           else datetime.date.today())
    graded_at = f"{day.month}/{day.day}/{day.year}"

    plan = {}
    for tab in tabs():
        todo, done = find(args.sheet_id, tab, graded_at)
        plan[tab] = todo
        for key, (row, text) in sorted(todo.items(), key=lambda kv: kv[1][0]):
            print(f"  {tab} row {row} {key}: grade {CLEARING!r} -> blank")
            print(f"    {text[:96]}...")
        if done:
            print(f"  {len(done)} row(s) on {tab} already reset, left alone: "
                  f"{', '.join(sorted(done))}")

    total = sum(len(t) for t in plan.values())
    print(f"{total} row(s) to reset, grader {GRADER}, graded at {graded_at}")
    if not total:
        return
    if not args.apply:
        print("dry run; pass --apply to write")
        return

    import gspread  # imported late: only the write path needs it installed

    sh = gspread.oauth().open_by_key(args.sheet_id)
    stamp = datetime.datetime.now().strftime("%Y%m%dT%H%M%S")
    print(f"backup: {ar.backup(sh, stamp)}")
    for tab, todo in plan.items():
        if todo:
            write(sh, tab, todo, graded_at)


if __name__ == "__main__":
    main()
