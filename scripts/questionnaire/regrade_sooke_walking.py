#!/usr/bin/env python3
"""Revisit three Sooke rows on the Walking tab.

Written for one event and kept as the record of it, like `reset_unsure_rows.py`.

On 2026-09-23 the coalition went back over the Sooke answers to WLK-02 and
WLK-04 on `Grade - Walking`:

- WLK-04 asks about car free streets in a downtown, main street or village
  centre. Sooke's centre is a single stretch of Highway 14, which the province
  controls, so the municipality has no street of that kind it could close on
  its own. The two Sooke candidates who answered N/A had been graded F as
  sidestepping; both rows are now blank with a rationale, as Highlands already
  was. One of the two had also explained the choice in the WLK-GEN comment box,
  which the F had not taken into account. The Sooke candidates who answered Yes
  keep their letters, because they took a position.
- One WLK-02 answer went from B to A. The question asks for the one change the
  candidate would commit to, and the answer names a single trail the
  municipality can build itself after placing the worst danger on the provincial
  highway.

These are cells a person typed, so nothing is guessed: each row must still hold
the label and answer it is listed under, and the grade it is changing from. Any
row that has moved or changed stops the run before anything is written. A row
already at its new grade and rationale is reported and skipped, so re-running is
safe.

Dry-run by default.

  python3 scripts/questionnaire/regrade_sooke_walking.py            # preview
  python3 scripts/questionnaire/regrade_sooke_walking.py --apply    # do it
"""

import argparse
import datetime
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import apply_rubric as ar  # noqa: E402

TAB = "Grade - Walking"
GRADER = "vp@bettertransityyj.ca"

K, LAB, ANS, GR, RAT = 0, 3, 5, 7, 9

# Key: (label, answer starts with, grade before, grade after, rationale).
# A blank grade after means ungraded, which drops the row out of the rollup;
# never N/A, which scores as F there.
CHANGES = {
    "EqANaxl|WLK-04": (
        "WLK-04", "N/A", "F", "",
        "Chose not applicable, and explained in the closing comments that the "
        "downtown is a single stretch of provincial highway with commercial "
        "space barely a block off it, so closing road connections is not "
        "workable yet, while naming Shields Road and a few others as future "
        "candidates for pedestrian priority or partial closure. That is a "
        "reasoned account of local conditions rather than a dodge, so the row "
        "is left ungraded instead of failed."
    ),
    "Nqg8vJp|WLK-04": (
        "WLK-04", "N/A", "F", "",
        "Selected not applicable on pedestrian priority and car free streets. "
        "The main street through the Sooke town centre is a provincial highway "
        "the municipality cannot close on its own, so the question does not "
        "fairly apply here and no grade is given."
    ),
    "EqANaxl|WLK-02": (
        "WLK-02", "The biggest walking safety concerns", "B", "A",
        "Places the worst walking danger on the highway stretch between "
        "Whiffin Spit and Ed McGregor Park, is candid that the province "
        "controls it and has resisted fixes there, and commits instead to the "
        "Grant Road West multi use trail. The question asks for one change and "
        "this names one the municipality can deliver on its own, which is the "
        "commitment the question is after."
    ),
}


def find(sheet_id):
    """(rows to write, rows already done). Exits on any surprise."""
    rows = ar.fetch_tab(sheet_id, TAB)
    if rows is None:
        sys.exit(f"no tab {TAB!r}, or it is not shared")

    todo, done, seen = {}, [], set()
    for i, row in enumerate(rows[1:], start=2):
        row = row + [""] * (13 - len(row))
        key = row[K].strip()
        if key not in CHANGES:
            continue
        seen.add(key)
        label, answer, before, after, text = CHANGES[key]
        if row[LAB].strip() != label:
            sys.exit(f"{key} is on {row[LAB]!r}, not {label}. Nothing written.")
        if not row[ANS].strip().startswith(answer):
            sys.exit(f"{key} now answers {row[ANS][:60]!r}, not {answer!r}. "
                     f"Nothing written.")
        grade = row[GR].strip()
        if grade == after and row[RAT].strip() == text:
            done.append(key)
            continue
        if grade != before:
            sys.exit(f"{key} holds grade {grade!r}, not {before!r}. Somebody "
                     f"has changed it since. Nothing written.")
        todo[key] = i

    missing = sorted(set(CHANGES) - seen)
    if missing:
        sys.exit(f"not on {TAB!r}: {missing}. Nothing written.")
    return todo, done


def write(sh, todo, graded_at):
    ws = ar.worksheet_by_title(sh, TAB)
    live = ws.col_values(K + 1)
    updates = []
    for key, row in todo.items():
        if row > len(live) or live[row - 1].strip() != key:
            sys.exit(f"row {row} of {TAB!r} now holds "
                     f"{live[row - 1].strip()!r}, not {key!r}. The tab moved; "
                     f"nothing written.")
        _label, _answer, _before, after, text = CHANGES[key]
        updates.append({"range": f"H{row}", "values": [[after]]})
        updates.append({"range": f"J{row}", "values": [[text]]})
        updates.append({"range": f"K{row}", "values": [[GRADER]]})
        updates.append({"range": f"L{row}", "values": [[graded_at]]})
    ws.batch_update(updates, value_input_option="USER_ENTERED")
    print(f"wrote {len(todo)} row(s) on {TAB}")


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

    todo, done = find(args.sheet_id)
    for key, row in sorted(todo.items(), key=lambda kv: kv[1]):
        _label, _answer, before, after, text = CHANGES[key]
        print(f"  row {row} {key}: grade {before!r} -> {after or 'blank'!r}")
        print(f"    {text[:96]}...")
    if done:
        print(f"  {len(done)} row(s) already changed, left alone: "
              f"{', '.join(sorted(done))}")

    print(f"{len(todo)} row(s) to change, grader {GRADER}, "
          f"graded at {graded_at}")
    if not todo:
        return
    if not args.apply:
        print("dry run; pass --apply to write")
        return

    import gspread  # imported late: only the write path needs it installed

    sh = gspread.oauth().open_by_key(args.sheet_id)
    stamp = datetime.datetime.now().strftime("%Y%m%dT%H%M%S")
    print(f"backup: {ar.backup(sh, stamp)}")
    write(sh, todo, graded_at)


if __name__ == "__main__":
    main()
