#!/usr/bin/env python3
"""Add newly-submitted questions to a sheet that is already being voted on.

tables.py and voting.py rebuild from scratch, which wipes every vote cast so far.
Once voting is under way that price is too high just to take three new questions,
so this script appends instead:

  - existing master rows are never rewritten, so hand edits to categories and
    question text survive;
  - new rows land *below* the last one, so no voter tab shifts out of alignment;
  - each voter tab gets the same new rows, unscored, with its existing votes intact.

It refuses to run if the IDs already in the master are not a prefix of the IDs
build_rows() produces now. That mismatch means rows were reordered, renumbered or
deleted at source - appending would silently pair votes with the wrong questions,
so the only safe answer is a full rebuild (and the lost votes that implies).

Only handles growth. Removing a question still needs tables.py + voting.py.

Usage:
  QUESTIONNAIRE_SHEET_ID=... python3 scripts/questionnaire/append.py [--dry-run]
"""

import re
import sys

from aggregate import FIRST, HEADERS, MASTER, build_rows, open_sheet
from tables import AGG_HEADERS, column_properties
from voting import (
    AGG_START_COL, STATUS_COL, STATUS_COLOURS, aggregate_formulas, check_voter_columns,
    col_letter, tab_name,
)
from voting import HEADERS as VOTE_HEADERS


def voter_order(sh, master):
    """The committee, in the order the master's own formulas already reference them.

    Read back rather than re-derived: the Comments column prefixes each entry with its
    voter, and appended rows should read the same way as the rows above them.
    Falls back to tab-name order if no aggregates have been written yet.
    """
    got = master.get_values(f"O{FIRST}:O{FIRST}", value_render_option="FORMULA")
    cell = got[0][0] if got and got[0] else ""
    found = list(dict.fromkeys(re.findall(r"'Vote - ([^']+)'!", cell)))
    if found:
        return found
    return sorted(ws.title[len("Vote - "):] for ws in sh.worksheets()
                  if ws.title.startswith("Vote - "))


def table_by_sheet(meta):
    return {s["properties"]["sheetId"]: s.get("tables", []) for s in meta["sheets"]}


def extend_table(tables, sheet_id, new_last, col_props=None):
    """Grow a table's range to new_last, leaving its columns where they are."""
    reqs = []
    for t in tables.get(sheet_id, []):
        rng = dict(t["range"])
        rng["endRowIndex"] = new_last
        table = {"tableId": t["tableId"], "range": rng}
        fields = "range"
        if col_props is not None:
            table["columnProperties"] = col_props
            fields = "range,columnProperties"
        reqs.append({"updateTable": {"table": table, "fields": fields}})
    return reqs


def restatus_formats(meta, master_id, new_last):
    """Repoint the master's Status colour rules at the longer range.

    Deleted highest-index-first (indices shift on delete), then re-added, so the tab
    ends up with exactly one rule per status rather than a duplicate set per run.
    """
    props = next(s for s in meta["sheets"] if s["properties"]["sheetId"] == master_id)
    mine = [
        i for i, cf in enumerate(props.get("conditionalFormats", []))
        if any(r.get("startColumnIndex") == STATUS_COL - 1 for r in cf.get("ranges", []))
    ]
    reqs = [{"deleteConditionalFormatRule": {"sheetId": master_id, "index": i}}
            for i in sorted(mine, reverse=True)]
    reqs += [{"addConditionalFormatRule": {"index": 0, "rule": {
        "ranges": [{"sheetId": master_id, "startRowIndex": FIRST - 1, "endRowIndex": new_last,
                    "startColumnIndex": STATUS_COL - 1, "endColumnIndex": STATUS_COL}],
        "booleanRule": {"condition": {"type": "TEXT_EQ", "values": [{"userEnteredValue": lbl}]},
                        "format": {"backgroundColor": {"red": r, "green": g, "blue": b}}},
    }}} for lbl, r, g, b in STATUS_COLOURS]
    return reqs


def main():
    dry_run = "--dry-run" in sys.argv[1:]

    sh = open_sheet()
    master = sh.worksheet(MASTER)

    desired = build_rows(sh)
    existing = [v for v in master.col_values(1)[FIRST - 1:] if v.strip()]

    have, want = existing, [r[0] for r in desired]
    if want[:len(have)] != have:
        drift = next((i for i, (a, b) in enumerate(zip(have, want)) if a != b), len(want))
        sys.exit(
            f"FATAL: master IDs are not a prefix of the current source tabs "
            f"(first mismatch at row {FIRST + drift}: master has "
            f"{have[drift] if drift < len(have) else '(nothing)'}, sources give "
            f"{want[drift] if drift < len(want) else '(nothing)'}).\n"
            f"Rows were reordered or removed at source. Appending would misalign votes - "
            f"rebuild with tables.py + voting.py instead, accepting the loss of votes."
        )

    new = desired[len(have):]
    if not new:
        print(f"nothing to append - master already holds all {len(have)} questions")
        return

    old_last = FIRST + len(have) - 1
    new_last = FIRST + len(desired) - 1
    voters = voter_order(sh, master)

    print(f"master holds {len(have)} questions (rows {FIRST}-{old_last})")
    print(f"appending {len(new)} at rows {old_last + 1}-{new_last}:")
    for r in new:
        print(f"  {r[0]:8} {r[1]:10} {r[3][:70]}")
    print(f"voter tabs: {', '.join(voters) or '(none found)'}")
    check_voter_columns(sh, voters)

    if dry_run:
        print("\n--dry-run: nothing written")
        return

    n_cols = len(HEADERS) + len(AGG_HEADERS)
    if master.row_count < new_last:
        master.resize(rows=new_last + 50, cols=max(master.col_count, n_cols))
    master.update(new, f"A{old_last + 1}", value_input_option="RAW")
    master.update([aggregate_formulas(voters, row) for row in range(old_last + 1, new_last + 1)],
                  f"{col_letter(AGG_START_COL)}{old_last + 1}", value_input_option="USER_ENTERED")
    print(f"wrote {len(new)} rows to {MASTER} (A-J) and their K-X aggregates")

    meta = sh.fetch_sheet_metadata()
    tables = table_by_sheet(meta)

    reqs = extend_table(tables, master.id, new_last, column_properties())
    reqs += restatus_formats(meta, master.id, new_last)
    sh.batch_update({"requests": reqs})
    print(f"extended the Questions table to row {new_last} and repointed Status colours")

    pulled = [[f"='{MASTER}'!A{r}", f"='{MASTER}'!B{r}", f"='{MASTER}'!D{r}"]
              for r in range(old_last + 1, new_last + 1)]
    for v in voters:
        ws = sh.worksheet(tab_name(v))
        if ws.row_count < new_last:
            ws.resize(rows=new_last + 20, cols=max(ws.col_count, len(VOTE_HEADERS)))
        ws.update(pulled, f"A{old_last + 1}", value_input_option="USER_ENTERED")
        sh.batch_update({"requests": extend_table(tables, ws.id, new_last)})
        print(f"  extended {tab_name(v)!r}")

    print("\nrun summary.py to repoint the Summary tab at the longer range")


if __name__ == "__main__":
    main()
