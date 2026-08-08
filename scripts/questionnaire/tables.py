#!/usr/bin/env python3
"""Rebuild the 'All Refined Questions' tab as a native Google Sheets table.

  Questions  A1:X<last>  header row 1, data from row 2. A-J question data, K-X
                         vote aggregates (values written by voting.py once voter
                         tabs exist).

Counts and roll-ups live on the Summary tab - see summary.py.

Tables give per-column sort/filter, banded rows, and enforced column types - the
Category column becomes a real dropdown, so the taxonomy cannot drift.

Destructive: clears the tab and rewrites it from the source tabs. Safe to re-run,
but see README.md before doing it once voting is under way.

Usage:
  QUESTIONNAIRE_SHEET_ID=... python3 scripts/questionnaire/tables.py
"""

from aggregate import (
    CATEGORIES, FIRST, HEADERS, MASTER, SOURCES, build_rows, open_sheet,
)
from voting import col_letter

AGG_HEADERS = [
    "Avg importance", "Avg distinguishes", "Avg answerable", "Mean score",
    "Votes cast", "F: our view", "F: users", "F: allies", "F: how",
    "Needs rewording", "Shouldn't be graded",
    "Exclude votes", "Status", "Comments",
]

NUMERIC = {
    "Avg importance", "Avg distinguishes", "Avg answerable", "Mean score",
    "Votes cast", "F: our view", "F: users", "F: allies", "F: how",
    "Needs rewording", "Shouldn't be graded", "Exclude votes",
}


def one_of(values):
    return {"condition": {"type": "ONE_OF_LIST",
                          "values": [{"userEnteredValue": v} for v in values]}}


def column_properties():
    """Column types for the Questions table, in sheet order.

    Shared with append.py so the Category and Source dropdowns stay in step with
    CATEGORIES and SOURCES no matter which script last touched the table.
    """
    col_props = []
    for i, name in enumerate(HEADERS + AGG_HEADERS):
        if name == "Category":
            col_props.append({"columnIndex": i, "columnName": name,
                              "columnType": "DROPDOWN",
                              "dataValidationRule": one_of(CATEGORIES)})
        elif name == "Source":
            col_props.append({"columnIndex": i, "columnName": name,
                              "columnType": "DROPDOWN",
                              "dataValidationRule": one_of(SOURCES)})
        else:
            col_props.append({"columnIndex": i, "columnName": name,
                              "columnType": "DOUBLE" if name in NUMERIC else "TEXT"})
    return col_props


def main():
    sh = open_sheet()
    ws = sh.worksheet(MASTER)

    rows = build_rows(sh)
    last = FIRST + len(rows) - 1

    # Tables refuse to coexist with a basic filter, and addTable errors over an
    # existing table - strip both before rebuilding.
    meta = sh.fetch_sheet_metadata()
    props = next(s for s in meta["sheets"] if s["properties"]["sheetId"] == ws.id)
    teardown = [{"deleteTable": {"tableId": t["tableId"]}} for t in props.get("tables", [])]
    if props.get("basicFilter"):
        teardown.append({"clearBasicFilter": {"sheetId": ws.id}})
    if teardown:
        sh.batch_update({"requests": teardown})

    n_cols = len(HEADERS) + len(AGG_HEADERS)
    ws.clear()
    if ws.col_count < n_cols:
        ws.resize(rows=max(ws.row_count, last + 50), cols=n_cols)
    ws.update([HEADERS + AGG_HEADERS], "A1", value_input_option="RAW")
    ws.update(rows, f"A{FIRST}", value_input_option="RAW")

    col_props = column_properties()

    sh.batch_update({"requests": [{"addTable": {"table": {
        "name": "Questions",
        "range": {"sheetId": ws.id, "startRowIndex": 0, "endRowIndex": last,
                  "startColumnIndex": 0, "endColumnIndex": n_cols},
        "columnProperties": col_props,
    }}}]})
    ws.freeze(rows=1)

    print(f"Questions table: A1:{col_letter(n_cols)}{last} ({len(rows)} questions)")
    print("run summary.py to refresh the Summary tab")


if __name__ == "__main__":
    main()
