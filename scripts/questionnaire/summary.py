#!/usr/bin/env python3
"""Build the 'Summary' tab: every count and roll-up in one place.

Six native tables, side by side, all live formulas over the master and the voter
tabs - nothing here is a stored value, so it never goes stale:

  A:D   CategoryCounts  questions per official category, with strong/excluded splits
  F:G   Totals          question count, committee size, completion percentage
  I:P   VoterProgress   per-member progress, exclude ticks, comments, mark ticks
  R:T   StatusMix       distribution across STRONG / MAYBE / WEAK / EXCLUDE / unvoted
  V:Y   FlagTotals      questions carrying each criterion flag, and total ticks
  AA:AD Dispositions    questions marked 'needs rewording' / "shouldn't be graded"

Voter tabs are discovered by name ('Vote - <Name>'), so this picks up committee
changes without arguments. Safe to re-run at any time: it only rewrites this tab.

Usage:
  QUESTIONNAIRE_SHEET_ID=... python3 scripts/questionnaire/summary.py
"""

from aggregate import CATEGORIES, FIRST, MASTER, open_sheet
from voting import check_voter_columns

TAB = "Summary"

# Master columns the roll-ups read. Keep in step with AGG_HEADERS in tables.py.
CAT, MEAN, VOTES = "B", "N", "O"
FLAG_COLS = ["P", "Q", "R", "S"]
MARK_COLS = ["T", "U"]
EXCLUDE, STATUS = "V", "W"

# Voter-tab columns. Comment sits at L and the marks follow it, so that adding the
# marks to a sheet already being voted on moved nobody's existing data.
V_SCORE, V_EXCLUDE, V_COMMENT = "D", "K", "L"
V_MARK_COLS = ["M", "N"]

FLAG_LABELS = [
    ("F: our view", "Does not reflect the view of the folks involved in this effort"),
    ("F: users", "Does not reflect the view of the folks we hope use the scorecard"),
    ("F: allies", "Risks pitting us against communities or constituencies we care about"),
    ("F: how", "Prescribes HOW rather than asking WHAT we want"),
]

MARK_LABELS = [
    ("Needs rewording", "Should be reworded before it goes out"),
    ("Shouldn't be graded", "Worth asking, but answers should not be scored"),
]

STATUSES = [
    ("STRONG", "Mean score 4 or above"),
    ("MAYBE", "Mean score 3 to 4"),
    ("WEAK", "Mean score below 3"),
    ("EXCLUDE", "Half or more of votes cast ticked EXCLUDE"),
    ("-", "No votes cast yet"),
]


def m(col, last, first=FIRST):
    """An absolute range over one master column."""
    return f"'{MASTER}'!${col}${first}:${col}${last}"


def category_counts(last):
    rows = [["Category", "Questions", "Strong", "Excluded"]]
    for c in CATEGORIES:
        rows.append([
            c,
            f'=COUNTIF({m(CAT, last)},$A{len(rows) + 1})',
            f'=COUNTIFS({m(CAT, last)},$A{len(rows) + 1},{m(STATUS, last)},"STRONG")',
            f'=COUNTIFS({m(CAT, last)},$A{len(rows) + 1},{m(STATUS, last)},"EXCLUDE")',
        ])
    rows.append([
        "TOTAL",
        f'=SUM(B2:B{len(rows)})',
        f'=SUM(C2:C{len(rows)})',
        f'=SUM(D2:D{len(rows)})',
    ])
    return rows


def totals(last, voters):
    n = len(voters)
    q = f'=COUNTA({m("A", last)})'
    return [
        ["Metric", "Value"],
        ["Questions", q],
        ["Committee members", str(n)],
        ["Scores possible", f"=G2*G3"],
        ["Scores cast", f'=SUM({m(VOTES, last)})'],
        ["Completion", "=IF(G4=0,0,G5/G4)"],
        ["Questions with no votes", f'=COUNTIF({m(VOTES, last)},0)'],
        ["Questions fully voted", f'=COUNTIF({m(VOTES, last)},G3)'],
        ["Questions flagged at least once", f'=SUMPRODUCT(--(({m(FLAG_COLS[0], last)}+'
                                           f'{m(FLAG_COLS[1], last)}+{m(FLAG_COLS[2], last)}+'
                                           f'{m(FLAG_COLS[3], last)})>0))'],
        ["Mean of all mean scores", f'=IFERROR(ROUND(AVERAGE({m(MEAN, last)}),2),"-")'],
    ]


def voter_progress(last, voters):
    rows = [["Voter", "Scored", "Remaining", "Complete", "Excludes", "Comments"]
            + [lbl for lbl, _ in MARK_LABELS]]
    for v in voters:
        t = f"'Vote - {v}'"
        r = len(rows) + 1
        rows.append([
            v,
            f'=COUNT({t}!${V_SCORE}${FIRST}:${V_SCORE}${last})',
            f"=$G$2-J{r}",
            f"=IF($G$2=0,0,J{r}/$G$2)",
            f'=COUNTIF({t}!${V_EXCLUDE}${FIRST}:${V_EXCLUDE}${last},TRUE)',
            f'=COUNTIF({t}!${V_COMMENT}${FIRST}:${V_COMMENT}${last},"<>")',
        ] + [f'=COUNTIF({t}!${c}${FIRST}:${c}${last},TRUE)' for c in V_MARK_COLS])
    return rows


def status_mix(last):
    rows = [["Status", "Questions", "What it means"]]
    for label, meaning in STATUSES:
        rows.append([label, f'=COUNTIF({m(STATUS, last)},"{label}")', meaning])
    return rows


def tick_totals(header, labels, cols, last):
    """Per-question and total tick counts for one block of checkbox columns."""
    rows = [[header, "Questions marked", "Total ticks", "Meaning"]]
    for (label, meaning), col in zip(labels, cols):
        rows.append([
            label,
            f'=COUNTIF({m(col, last)},">0")',
            f'=SUM({m(col, last)})',
            meaning,
        ])
    return rows


def flag_totals(last):
    return tick_totals("Flag", FLAG_LABELS, FLAG_COLS, last)


def dispositions(last):
    return tick_totals("Disposition", MARK_LABELS, MARK_COLS, last)


def table(name, sheet_id, rows, start_col, col_types):
    """addTable request for a block anchored at start_col (1-indexed)."""
    return {"addTable": {"table": {
        "name": name,
        "range": {"sheetId": sheet_id, "startRowIndex": 0, "endRowIndex": len(rows),
                  "startColumnIndex": start_col - 1,
                  "endColumnIndex": start_col - 1 + len(rows[0])},
        # columnProperties deliberately omitted for blocks not anchored at column A:
        # the API validates columnIndex table-relative but writes columnName back at
        # the sheet offset, which would clobber the headers in columns A, B, ...
        **({"columnProperties": col_types} if start_col == 1 and col_types else {}),
    }}}


def main():
    sh = open_sheet()
    master = sh.worksheet(MASTER)

    ids = [v for v in master.col_values(1)[FIRST - 1:] if v.strip()]
    last = FIRST + len(ids) - 1

    voters = sorted(ws.title[len("Vote - "):] for ws in sh.worksheets()
                    if ws.title.startswith("Vote - "))
    if not voters:
        print("warning: no 'Vote - <Name>' tabs found; VoterProgress will be empty")
    print(f"{len(ids)} questions, {len(voters)} voters: {', '.join(voters) or '(none)'}")
    check_voter_columns(sh, voters)

    meta = sh.fetch_sheet_metadata()

    existing = {ws.title: ws for ws in sh.worksheets()}
    if TAB in existing:
        ws = existing[TAB]
        sprops = next(s for s in meta["sheets"] if s["properties"]["sheetId"] == ws.id)
        drop = [{"deleteTable": {"tableId": t["tableId"]}} for t in sprops.get("tables", [])]
        if drop:
            sh.batch_update({"requests": drop})
        ws.clear()
        print(f"rebuilt {TAB!r}")
    else:
        ws = sh.add_worksheet(title=TAB, rows=60, cols=26)
        print(f"created {TAB!r}")

    blocks = [
        ("CategoryCounts", 1, category_counts(last)),
        ("Totals", 6, totals(last, voters)),
        ("VoterProgress", 9, voter_progress(last, voters)),
        ("StatusMix", 18, status_mix(last)),
        ("FlagTotals", 22, flag_totals(last)),
        ("Dispositions", 27, dispositions(last)),
    ]
    widest = max(col + len(rows[0]) for _, col, rows in blocks)
    if ws.col_count < widest:
        ws.resize(rows=ws.row_count, cols=widest + 2)

    def letter(idx):
        out = ""
        while idx:
            idx, rem = divmod(idx - 1, 26)
            out = chr(65 + rem) + out
        return out

    for _, col, rows in blocks:
        ws.update(rows, f"{letter(col)}1", value_input_option="USER_ENTERED")

    cat_types = [
        {"columnIndex": 0, "columnName": "Category", "columnType": "TEXT"},
        {"columnIndex": 1, "columnName": "Questions", "columnType": "DOUBLE"},
        {"columnIndex": 2, "columnName": "Strong", "columnType": "DOUBLE"},
        {"columnIndex": 3, "columnName": "Excluded", "columnType": "DOUBLE"},
    ]
    sh.batch_update({"requests": [
        table(name, ws.id, rows, col, cat_types if col == 1 else None)
        for name, col, rows in blocks
    ]})

    # Percentages read as percentages, not 0.42.
    sh.batch_update({"requests": [
        {"repeatCell": {
            "range": {"sheetId": ws.id, "startRowIndex": 5, "endRowIndex": 6,
                      "startColumnIndex": 6, "endColumnIndex": 7},
            "cell": {"userEnteredFormat": {"numberFormat": {"type": "PERCENT",
                                                            "pattern": "0.0%"}}},
            "fields": "userEnteredFormat.numberFormat"}},
        {"repeatCell": {
            "range": {"sheetId": ws.id, "startRowIndex": 1,
                      "endRowIndex": 1 + len(voters),
                      "startColumnIndex": 11, "endColumnIndex": 12},
            "cell": {"userEnteredFormat": {"numberFormat": {"type": "PERCENT",
                                                            "pattern": "0.0%"}}},
            "fields": "userEnteredFormat.numberFormat"}},
    ]})
    ws.freeze(rows=1)

    for name, col, rows in blocks:
        print(f"  {name:16} {letter(col)}1:{letter(col + len(rows[0]) - 1)}{len(rows)}")


if __name__ == "__main__":
    main()
