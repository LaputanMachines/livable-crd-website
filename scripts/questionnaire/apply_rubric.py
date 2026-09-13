#!/usr/bin/env python3
"""Fill a grading tab's Grade column from the rubrics in `rubrics.py`.

The closed questions on the questionnaire have one right letter per answer
option, and typing them by hand thirty one times is how two candidates who
picked the same option end up with different grades. This reads a
`Grade - <Subject>` tab, asks `rubrics.grade_for` what each answer is worth, and
either reports what it would write or writes it.

Rationales are not generated. They are hand-written per candidate and passed in
with --rationales as a JSON object keyed on the row Key in column A, which is
also how --apply finds the row to write.

Declines need a judgement the rubric cannot make - whether the candidate
explained themselves or answered solidly elsewhere in the topic - so pass the
excused ones with --excused, as a JSON list of "Key" strings. Anything not
listed is graded as an unexplained decline.

Read-only unless --apply is passed, and every tab is dumped to
~/livable-crd-backups/ before the first write.

Re-running as new submissions arrive
------------------------------------
Safe and expected. A row that already holds a grade is skipped, so a re-run only
ever touches the blank rows the Apps Script appended for the new candidate, and
the letters come back for free.

The rationales do not. They are hand-written per row, and a new candidate has
new Keys that no rationale file knows about, so the loop is:

  1. Dry run. It prints a tally per question and how many rows have no
     rationale yet.

         apply_rubric.py Climate --rationales rationales.json

  2. Stub out what is missing, fill in the blanks, merge it back.

         apply_rubric.py Climate --rationales rationales.json \
             --stub-rationales new.json

  3. Check for declines among the new rows. A decline is graded F unless its
     Key is listed in the --excused file, so read the topic comment box and the
     candidate's other answers in that topic before deciding, then add the Key.

  4. Apply. It refuses to run while any row still lacks a rationale, which is
     the mistake this loop exists to prevent; --allow-blank-rationale overrides.

         apply_rubric.py Climate --rationales rationales.json \
             --excused excused.json --apply

Keep the rationale and excused files somewhere durable. They are the record of
what was written, and step 1 of the next re-run needs them to tell an old row
from a new one.

Usage:
  QUESTIONNAIRE_SUBMISSIONS_SHEET_ID=... python3 scripts/questionnaire/apply_rubric.py Climate
  ... apply_rubric.py Climate --labels CLI-03,CLI-04 --rationales r.json --tsv out.tsv
  ... apply_rubric.py Climate --rationales r.json --excused e.json --apply
"""

import argparse
import csv
import datetime
import io
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rubrics  # noqa: E402

GVIZ = "https://docs.google.com/spreadsheets/d/{id}/gviz/tq"
GRADE_PREFIX = "Grade - "

# Grading tab columns, 0-based, as grading_tabs.GRADE_HEADERS lays them out.
G_KEY, G_CANDIDATE, G_MUNICIPALITY, G_LABEL = 0, 1, 2, 3
G_ANSWER, G_OWNER, G_GRADE = 5, 6, 7
G_RATIONALE, G_GRADER, G_GRADED_AT = 9, 10, 11

# 1-based, for the write side.
COL_GRADE, COL_RATIONALE, COL_GRADER, COL_GRADED_AT = 8, 10, 11, 12

BACKUP_DIR = os.path.expanduser("~/livable-crd-backups")

# Where the sheet id is read from when QUESTIONNAIRE_SUBMISSIONS_SHEET_ID is not
# set. The id stays out of the repo - it is a capability over a sheet holding
# every candidate's contact details - but retyping it on the read-only steps is
# how those steps get skipped, so a local file is the fallback.
SHEET_ID_FILE = os.path.expanduser("~/livable-crd-grading/sheet-id")


def default_sheet_id():
    if os.environ.get("QUESTIONNAIRE_SUBMISSIONS_SHEET_ID"):
        return os.environ["QUESTIONNAIRE_SUBMISSIONS_SHEET_ID"]
    if os.path.exists(SHEET_ID_FILE):
        return open(SHEET_ID_FILE).read().strip()
    return None


def fetch_tab(sheet_id, title, timeout=120):
    """One tab as a list of rows, header first, or None if it is not there.

    `headers=1` is not optional. Without it gviz guesses how many leading rows
    are headers, and on a tab whose Grade column is mostly empty it guesses
    wrong, folding every data row into one header row. The first header cell is
    checked afterwards because gviz answers a request for a missing tab with the
    spreadsheet's first sheet, which here is the raw dump of candidate contact
    details.
    """
    params = {"tqx": "out:csv", "sheet": title, "headers": "1"}
    url = GVIZ.format(id=sheet_id) + "?" + urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        if e.code in (401, 403, 404):
            return None
        raise
    rows = list(csv.reader(io.StringIO(body)))
    if not rows or not rows[0] or rows[0][0].strip() != "Key":
        return None
    return rows


def proposals(rows, labels, excused, rationales, grader, graded_at):
    """What would be written, one record per row the rubric has an answer for.

    A row already holding a grade is skipped rather than overwritten: someone
    typed it, and this script is not the authority on a cell a person filled in.

    A row holding a rationale and no grade is skipped too, and that case is the
    whole reason re-running is safe. An excused decline and an unsure are both
    finished rows whose Grade is *deliberately* blank, with the rationale saying
    why. Judging "done" on the Grade cell alone would re-propose all of them on
    every run and restamp their Graded at with the day of the re-run, quietly
    moving dates that record when a call was actually made.

    `no_rubric` is kept apart from `unmatched`. A question nobody wrote a rubric
    for is expected and uninteresting; an answer a rubric was written for and
    does not recognise means a form option changed, and somebody needs to look.
    """
    out, skipped, unmatched, no_rubric = [], [], [], set()
    for row in rows[1:]:
        row = row + [""] * (G_GRADED_AT + 1 - len(row))
        label = row[G_LABEL].strip()
        if labels and label not in labels:
            continue
        if label not in rubrics.RUBRICS:
            no_rubric.add(label)
            continue
        key = row[G_KEY].strip()
        if row[G_GRADE].strip() or row[G_RATIONALE].strip():
            skipped.append((key, label, row[G_GRADE].strip()))
            continue
        grade, note = rubrics.grade_for(
            label, row[G_ANSWER], excused=key in excused
        )
        if grade is None:
            unmatched.append((key, label, note))
            continue
        out.append({
            "key": key,
            "candidate": row[G_CANDIDATE],
            "municipality": row[G_MUNICIPALITY],
            "label": label,
            "answer": " ".join(row[G_ANSWER].split())[:60],
            "grade": grade,
            "rationale": rationales.get(key, ""),
            "grader": grader or row[G_OWNER].strip(),
            "graded_at": graded_at,
            "note": note or "",
        })
    return out, skipped, unmatched, sorted(no_rubric)


def write_stub(path, records):
    """A rationale file for the rows that have none yet, ready to fill in.

    The point of the whole re-run loop: the grades come back automatically when
    a new candidate lands, and the rationales cannot. This writes the keys that
    still need one, each with the candidate, the question and the answer beside
    it as a comment key, so the file can be filled in without going back to the
    sheet to see what was actually said.

    Merge it into the real rationale file when done; only the "<key>" entries
    are read back, the "#" ones are ignored.
    """
    stub = {}
    for r in records:
        if r["rationale"]:
            continue
        stub[f"# {r['key']}"] = (
            f"{r['candidate']} ({r['municipality']}) | {r['label']} | "
            f"grade {r['grade'] or '(blank)'} | answered: {r['answer']}"
        )
        stub[r["key"]] = ""
    with open(path, "w") as fh:
        json.dump(stub, fh, indent=1)
    return len(stub) // 2


def write_tsv(path, records):
    with open(path, "w", newline="") as fh:
        writer = csv.writer(fh, delimiter="\t")
        writer.writerow(["Key", "Grade", "Rationale", "Grader", "Graded at"])
        for r in records:
            writer.writerow([r["key"], r["grade"], r["rationale"],
                             r["grader"], r["graded_at"]])


def backup(sh, stamp):
    """Every tab to one JSON file, before the first write. Same shape as
    reorder_grade_rows.py's, so the two land side by side in one directory."""
    os.makedirs(BACKUP_DIR, exist_ok=True)
    path = os.path.join(BACKUP_DIR, f"submissions-tabs-{stamp}.json")
    dump = {ws.title: ws.get_all_values() for ws in sh.worksheets()}
    with open(path, "w") as fh:
        json.dump(dump, fh, indent=1)
    return path


def apply(sheet_id, category, records):
    """Write Grade, Rationale, Grader and Graded at, matched on the Key in A.

    Keyed rather than positional because nothing on a grading tab reads it
    positionally, and a row that moved between the read and the write would
    otherwise take another candidate's grade.

    `Graded at` gets an explicit date format. The column is left unformatted by
    grading_tabs.py and only becomes a date because onGradeEdit formats the one
    cell it touches, and onGradeEdit does not fire on an API write, so a date
    written here would otherwise land as a bare serial number.
    """
    import gspread  # imported late: only the write path needs it installed

    sh = gspread.oauth().open_by_key(sheet_id)
    stamp = datetime.datetime.now().strftime("%Y%m%dT%H%M%S")
    print(f"backup: {backup(sh, stamp)}")

    ws = sh.worksheet(GRADE_PREFIX + category)
    keys = {k.strip(): i + 1 for i, k in enumerate(ws.col_values(1))}

    updates, date_rows, missing = [], [], []
    for r in records:
        row = keys.get(r["key"])
        if not row:
            missing.append(r["key"])
            continue
        # Grade is written unconditionally, empty included: a blank Grade is the
        # meaningful value for an excused decline or an unsure, and the row was
        # only proposed because the cell was empty to begin with.
        updates.append({"range": gspread.utils.rowcol_to_a1(row, COL_GRADE),
                        "values": [[r["grade"]]]})
        # The other three are written only when there is something to write.
        # A row can carry a rationale a grader typed before deciding on a
        # letter, and an empty value here would erase it on a re-run.
        for column, value in ((COL_RATIONALE, r["rationale"]),
                              (COL_GRADER, r["grader"]),
                              (COL_GRADED_AT, r["graded_at"])):
            if value:
                updates.append({"range": gspread.utils.rowcol_to_a1(row, column),
                                "values": [[value]]})
        date_rows.append(row)

    if missing:
        sys.exit(f"keys not on the tab, nothing written: {missing}")

    ws.batch_update(updates, value_input_option="USER_ENTERED")
    sh.batch_update({"requests": [{
        "repeatCell": {
            "range": {"sheetId": ws.id, "startRowIndex": row - 1,
                      "endRowIndex": row, "startColumnIndex": COL_GRADED_AT - 1,
                      "endColumnIndex": COL_GRADED_AT},
            "cell": {"userEnteredFormat": {"numberFormat": {"type": "DATE",
                                                            "pattern": "M/d/yyyy"}}},
            "fields": "userEnteredFormat.numberFormat",
        }} for row in date_rows]})
    print(f"wrote {len(date_rows)} rows to {GRADE_PREFIX}{category}")


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("category", help="scorecard subject, e.g. Climate")
    p.add_argument("--sheet-id", default=default_sheet_id())
    p.add_argument("--labels", help="comma-separated question labels; default every label with a rubric")
    p.add_argument("--rationales", help="JSON object of key to rationale")
    p.add_argument("--excused", help="JSON list of keys whose decline is excused")
    p.add_argument("--grader", help="override; default is the row's Owner")
    p.add_argument("--date", help="Graded at, YYYY-MM-DD; default today")
    p.add_argument("--tsv", help="write the proposal as a paste-ready TSV")
    p.add_argument("--stub-rationales", metavar="PATH",
                   help="write a fill-in-the-blanks rationale file for the rows "
                        "that still have none, then exit without applying")
    p.add_argument("--allow-blank-rationale", action="store_true",
                   help="let --apply write rows with an empty Rationale")
    p.add_argument("--apply", action="store_true", help="write to the sheet")
    args = p.parse_args()

    if not args.sheet_id:
        sys.exit(f"no sheet id: set QUESTIONNAIRE_SUBMISSIONS_SHEET_ID, pass "
                 f"--sheet-id, or write it to {SHEET_ID_FILE}")

    labels = set(args.labels.split(",")) if args.labels else set()
    rationales = {}
    if args.rationales:
        rationales = {k: v for k, v in json.load(open(args.rationales)).items()
                      if not k.startswith("#")}
    excused = set(json.load(open(args.excused))) if args.excused else set()
    day = (datetime.date.fromisoformat(args.date) if args.date
           else datetime.date.today())
    graded_at = f"{day.month}/{day.day}/{day.year}"

    rows = fetch_tab(args.sheet_id, GRADE_PREFIX + args.category)
    if rows is None:
        sys.exit(f"no tab {GRADE_PREFIX}{args.category!r}, or it is not shared")

    records, skipped, unmatched, no_rubric = proposals(
        rows, labels, excused, rationales, args.grader, graded_at)

    if no_rubric:
        print(f"  no rubric, not touched: {', '.join(no_rubric)}")
    for key, label, note in unmatched:
        print(f"  ANSWER NOT IN RUBRIC: {label} {key}: {note}")
    if skipped:
        print(f"  {len(skipped)} row(s) already done, left alone")

    by_label = {}
    for r in records:
        by_label.setdefault(r["label"], []).append(r)
    for label in sorted(by_label):
        tally = {}
        for r in by_label[label]:
            tally[r["grade"] or "(blank)"] = tally.get(r["grade"] or "(blank)", 0) + 1
        print(f"  {label}: " + ", ".join(f"{g} x{n}" for g, n in sorted(tally.items())))
    blank_rationale = [r["key"] for r in records if not r["rationale"]]
    print(f"{len(records)} row(s) to write, {len(blank_rationale)} with no rationale")

    if args.tsv:
        write_tsv(args.tsv, records)
        print(f"tsv: {args.tsv}")
    if args.stub_rationales:
        count = write_stub(args.stub_rationales, records)
        print(f"stub: {args.stub_rationales} ({count} to fill in)")
        return
    if args.apply:
        if blank_rationale and not args.allow_blank_rationale:
            sys.exit(
                f"{len(blank_rationale)} row(s) have no rationale and nothing "
                f"was written. Write them with --stub-rationales, or pass "
                f"--allow-blank-rationale to grade without them."
            )
        apply(args.sheet_id, args.category, records)


if __name__ == "__main__":
    main()
