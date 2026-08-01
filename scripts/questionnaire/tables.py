#!/usr/bin/env python3
"""Rebuild the 'All Refined Questions' tab as two native Google Sheets tables.

  Questions       A1:V<last>   header row 1, data from row 2.
                               A-J question data, K-V vote aggregates (values are
                               written by voting.py once voter tabs exist).
  CategoryCounts  X1:Y15       live COUNTIF per official category.

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

AGG_HEADERS = [
    "Avg importance", "Avg distinguishes", "Avg answerable", "Mean score",
    "Votes cast", "F: our view", "F: users", "F: allies", "F: how",
    "Exclude votes", "Status", "Comments",
]

COUNTS_COL = 24  # X

NUMERIC = {
    "Avg importance", "Avg distinguishes", "Avg answerable", "Mean score",
    "Votes cast", "F: our view", "F: users", "F: allies", "F: how", "Exclude votes",
}


def one_of(values):
    return {"condition": {"type": "ONE_OF_LIST",
                          "values": [{"userEnteredValue": v} for v in values]}}


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

    ws.clear()
    # X:Y holds the counts table, so the grid needs to reach at least column Y.
    if ws.col_count < COUNTS_COL + 1:
        ws.resize(rows=max(ws.row_count, last + 50), cols=COUNTS_COL + 4)
    ws.update([HEADERS + AGG_HEADERS], "A1", value_input_option="RAW")
    ws.update(rows, f"A{FIRST}", value_input_option="RAW")

    counts = [["Category", "Questions"]]
    counts += [[c, f'=COUNTIF($B${FIRST}:$B,"{c}")'] for c in CATEGORIES]
    counts += [["Uncategorised", f'=COUNTIF($B${FIRST}:$B{last},"")'],
               ["TOTAL", f'=COUNTA($A${FIRST}:$A)']]
    ws.update(counts, "X1", value_input_option="USER_ENTERED")

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

    requests = [
        {"addTable": {"table": {
            "name": "Questions",
            "range": {"sheetId": ws.id, "startRowIndex": 0, "endRowIndex": last,
                      "startColumnIndex": 0,
                      "endColumnIndex": len(HEADERS) + len(AGG_HEADERS)},
            "columnProperties": col_props,
        }}},
        {"addTable": {"table": {
            "name": "CategoryCounts",
            "range": {"sheetId": ws.id, "startRowIndex": 0, "endRowIndex": len(counts),
                      "startColumnIndex": COUNTS_COL - 1, "endColumnIndex": COUNTS_COL + 1},
            # No columnProperties on purpose: columnIndex is validated table-relative
            # but the resulting columnName is written back at the *sheet* offset, so
            # naming a table anchored at column X clobbers A1/B1. Letting Sheets infer
            # the names from X1:Y1 avoids that.
        }}},
    ]
    sh.batch_update({"requests": requests})
    ws.freeze(rows=1)

    print(f"Questions table: A1:V{last} ({len(rows)} questions)")
    print(f"CategoryCounts table: X1:Y{len(counts)}")


if __name__ == "__main__":
    main()
