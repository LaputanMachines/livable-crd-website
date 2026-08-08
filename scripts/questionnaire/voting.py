#!/usr/bin/env python3
"""Create one voting tab per committee member and wire aggregates into the master.

Each voter tab is a native table: header row 1, data from row 2 - the same row
offsets as the master, so every aggregate formula is a straight per-row reference.
Columns A-C are pulled from the master by formula, so question edits propagate.

Destructive: named tabs that already exist are cleared and rebuilt, which wipes
votes cast in them. Always pass the FULL committee list, not just the new member.

Usage:
  QUESTIONNAIRE_SHEET_ID=... python3 scripts/questionnaire/voting.py "Alice" "Bob"
"""

import re
import sys

from aggregate import FIRST, MASTER, open_sheet

AGG_START_COL = 11  # K
STATUS_COL = AGG_START_COL + 12  # W

SCORES = [
    ("Importance",
     "How important is this topic to us? 1 = marginal, 5 = central."),
    ("Distinguishes",
     "How well does this separate candidates? 1 = everyone answers the same, "
     "5 = sharply separating."),
    ("Answerable",
     "Can a candidate answer confidently with modest research? 1 = needs deep "
     "specialist knowledge, 5 = squarely in public discourse."),
]

FLAGS = [
    ("F: our view",
     "Tick if this does NOT reflect the view of the folks involved in this effort."),
    ("F: users",
     "Tick if this does NOT reflect the view of the folks we hope use our scorecard."),
    ("F: allies",
     "Tick if this risks pitting us against communities or constituencies we care about."),
    ("F: how",
     "Tick if this prescribes HOW rather than asking WHAT we want."),
]

# Dispositions: what should happen to the question, as opposed to how it scores or
# which criterion it trips. Kept separate from FLAGS because they are not pass/fail
# judgements about the question's fitness - a question can be excellent and still need
# rewording. Appended after Comment rather than grouped with the flags so that adding
# them to a sheet mid-vote moves nobody's existing columns.
MARKS = [
    ("Needs rewording",
     "Tick if the question should be reworded before it goes out. Say how in Comment."),
    ("Shouldn't be graded",
     "Tick if the question is worth asking but answers to it should not be scored on "
     "the scorecard."),
]

RUBRIC = ("Score 1-5 (leave blank to skip). Tick a flag only if the question TRIPS that "
          "criterion. Tick EXCLUDE to argue it should be dropped entirely. Columns A-C are "
          "pulled from the master - do not edit.")

HEADERS = ["ID", "Category", "Question"] + [s[0] for s in SCORES] + \
          [f[0] for f in FLAGS] + ["EXCLUDE", "Comment"] + [m[0] for m in MARKS]

STATUS_COLOURS = [
    ("EXCLUDE", 0.96, 0.80, 0.80),
    ("STRONG", 0.80, 0.94, 0.80),
    ("MAYBE", 1.00, 0.95, 0.75),
    ("WEAK", 0.90, 0.90, 0.90),
]


def tab_name(voter):
    return f"Vote - {voter}"


def table_name(voter):
    return "Vote_" + re.sub(r"\W+", "_", voter)


def col_letter(idx):
    out = ""
    while idx:
        idx, rem = divmod(idx - 1, 26)
        out = chr(65 + rem) + out
    return out


def check_voter_columns(sh, voters):
    """Abort if any voter tab's leading columns aren't the standard layout.

    Every aggregate on the master and the Summary reads voter tabs *by position* -
    D:F scores, G:J flags, K exclude, L comment, M:N marks. A member who inserts a
    column of their own shifts everything to its right, and the formulas then read the
    wrong column without erroring: a checkbox gets reported as somebody's comments.
    Nothing in Sheets prevents that, so it is checked before any script trusts those
    offsets.

    Extra columns are fine to the *right* of the last standard one, which is where a
    member's own working columns should go.
    """
    if not voters:
        return
    end = col_letter(len(HEADERS))
    resp = sh.values_batch_get([f"'{tab_name(v)}'!A1:{end}1" for v in voters])
    bad = []
    for voter, vr in zip(voters, resp["valueRanges"]):
        got = (vr.get("values") or [[]])[0][:len(HEADERS)]
        if got != HEADERS:
            bad.append((voter, got))
    if not bad:
        return
    detail = "\n".join(
        f"  {tab_name(v)!r}\n    expected {HEADERS}\n    found    {got}" for v, got in bad)
    sys.exit(
        "FATAL: these voter tabs have non-standard columns, so the master's aggregates "
        f"would silently read the wrong ones:\n{detail}\n"
        f"Move any custom columns to the right of {HEADERS[-1]!r}, then re-run."
    )


def voter_column_properties():
    """Column types for a voter tab, in sheet order. Shared with the header notes."""
    col_props = [
        {"columnIndex": 0, "columnName": "ID", "columnType": "TEXT"},
        {"columnIndex": 1, "columnName": "Category", "columnType": "TEXT"},
        {"columnIndex": 2, "columnName": "Question", "columnType": "TEXT"},
    ]
    for i, (label, _) in enumerate(SCORES):
        col_props.append({
            "columnIndex": 3 + i, "columnName": label, "columnType": "DROPDOWN",
            "dataValidationRule": {"condition": {
                "type": "ONE_OF_LIST",
                "values": [{"userEnteredValue": str(n)} for n in range(1, 6)]}},
        })
    for i, (label, _) in enumerate(FLAGS):
        col_props.append({"columnIndex": 6 + i, "columnName": label, "columnType": "BOOLEAN"})
    col_props.append({"columnIndex": 10, "columnName": "EXCLUDE", "columnType": "BOOLEAN"})
    col_props.append({"columnIndex": 11, "columnName": "Comment", "columnType": "TEXT"})
    for i, (label, _) in enumerate(MARKS):
        col_props.append({"columnIndex": 12 + i, "columnName": label, "columnType": "BOOLEAN"})
    return col_props


def header_notes():
    """(column index, hover text) for every header cell that carries its full wording."""
    return [(0, RUBRIC)] + [(3 + i, tip) for i, (_, tip) in enumerate(SCORES)] \
        + [(6 + i, tip) for i, (_, tip) in enumerate(FLAGS)] \
        + [(12 + i, tip) for i, (_, tip) in enumerate(MARKS)]


def build_voter_tab(sh, voter, last, existing, tables_by_sheet):
    title = tab_name(voter)
    if title in existing:
        ws = existing[title]
        for t in tables_by_sheet.get(ws.id, []):
            sh.batch_update({"requests": [{"deleteTable": {"tableId": t["tableId"]}}]})
        ws.clear()
        ws.resize(rows=max(ws.row_count, last + 20), cols=len(HEADERS))
        print(f"  rebuilt {title!r}")
    else:
        ws = sh.add_worksheet(title=title, rows=last + 20, cols=len(HEADERS))
        print(f"  created {title!r}")

    ws.update([HEADERS], "A1", value_input_option="RAW")
    pulled = [[f"='{MASTER}'!A{r}", f"='{MASTER}'!B{r}", f"='{MASTER}'!D{r}"]
              for r in range(FIRST, last + 1)]
    ws.update(pulled, f"A{FIRST}", value_input_option="USER_ENTERED")

    reqs = [{"addTable": {"table": {
        "name": table_name(voter),
        "range": {"sheetId": ws.id, "startRowIndex": 0, "endRowIndex": last,
                  "startColumnIndex": 0, "endColumnIndex": len(HEADERS)},
        "columnProperties": voter_column_properties(),
    }}}]

    # Full criterion wording as hover notes on the header cells.
    for idx, tip in header_notes():
        reqs.append({"updateCells": {
            "range": {"sheetId": ws.id, "startRowIndex": 0, "endRowIndex": 1,
                      "startColumnIndex": idx, "endColumnIndex": idx + 1},
            "fields": "note", "rows": [{"values": [{"note": tip}]}],
        }})
    reqs.append({"addProtectedRange": {"protectedRange": {
        "range": {"sheetId": ws.id, "startColumnIndex": 0, "endColumnIndex": 3},
        "description": "Pulled from master - do not edit", "warningOnly": True,
    }}})

    sh.batch_update({"requests": reqs})
    ws.freeze(rows=1, cols=3)


def aggregate_formulas(voters, row):
    """The K:X formula block for one master row.

    Voter tabs carry the two MARKS columns at M:N, after Comment, but the master
    groups every tick-tally together at P:U - the tallies are formulas, so they can be
    laid out for reading rather than to match the source columns.
    """
    def ref(col):
        return [f"'{tab_name(v)}'!{col}{row}" for v in voters]

    def tally(col):
        return f'={"+".join("N(" + r + ")" for r in ref(col))}'

    avg = [f'=IFERROR(AVERAGE({",".join(ref(c))}),"")' for c in ("D", "E", "F")]
    allscores = ref("D") + ref("E") + ref("F")
    mean = f'=IFERROR(ROUND(AVERAGE({",".join(allscores)}),2),"")'
    votes = f'=COUNT({",".join(ref("D"))})'
    flags = [tally(c) for c in ("G", "H", "I", "J")]
    marks = [tally(c) for c in ("M", "N")]
    excl = tally("K")
    # EXCLUDE wins when half or more of the votes cast so far tick it.
    status = (f'=IF(O{row}=0,"-",IF(V{row}*2>=O{row},"EXCLUDE",'
              f'IF(N{row}>=4,"STRONG",IF(N{row}>=3,"MAYBE","WEAK"))))')
    comments = '=TEXTJOIN(" | ",TRUE,' + ",".join(
        f'IF(\'{tab_name(v)}\'!L{row}="","","{v}: "&\'{tab_name(v)}\'!L{row})'
        for v in voters) + ')'
    return avg + [mean, votes] + flags + marks + [excl, status, comments]


def main():
    voters = sys.argv[1:]
    if not voters:
        sys.exit('FATAL: pass the full committee list, e.g. voting.py "Alice" "Bob"')

    sh = open_sheet()
    master = sh.worksheet(MASTER)

    ids = [v for v in master.col_values(1)[FIRST - 1:] if v.strip()]
    last = FIRST + len(ids) - 1
    print(f"master data rows {FIRST}-{last} ({len(ids)} questions)")

    existing = {ws.title: ws for ws in sh.worksheets()}
    meta = sh.fetch_sheet_metadata()
    tables_by_sheet = {s["properties"]["sheetId"]: s.get("tables", []) for s in meta["sheets"]}

    for voter in voters:
        build_voter_tab(sh, voter, last, existing, tables_by_sheet)

    body = [aggregate_formulas(voters, row) for row in range(FIRST, last + 1)]
    master.update(body, f"{col_letter(AGG_START_COL)}{FIRST}",
                  value_input_option="USER_ENTERED")

    sh.batch_update({"requests": [{"addConditionalFormatRule": {"index": 0, "rule": {
        "ranges": [{"sheetId": master.id, "startRowIndex": FIRST - 1, "endRowIndex": last,
                    "startColumnIndex": STATUS_COL - 1, "endColumnIndex": STATUS_COL}],
        "booleanRule": {"condition": {"type": "TEXT_EQ", "values": [{"userEnteredValue": lbl}]},
                        "format": {"backgroundColor": {"red": r, "green": g, "blue": b}}},
    }}} for lbl, r, g, b in STATUS_COLOURS]})

    print(f"wired {len(voters)} voter tabs into {MASTER} cols K-X")


if __name__ == "__main__":
    main()
