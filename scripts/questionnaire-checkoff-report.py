#!/usr/bin/env python3
"""Report who to tick off in the candidate-tracking sheet's questionnaire column.

Two sheets, no writes. Reads who submitted the questionnaire from Tally's
submission spreadsheet (`QUESTIONNAIRE_SUBMISSIONS_SHEET_ID`), matches them
against the coalition candidate-tracking sheet (`CANDIDATES_CSV_URL`), and
names every candidate whose "Completed Questionnaire" checkbox is still empty
so a human can tick it. Meant to run daily in CI, where the list is written to
the run's job summary; see .github/workflows/questionnaire-checkoff-report.yml.

WHY IT DOES NOT TICK THE BOXES ITSELF
  Ticking would need a Google service account with edit access to the tracking
  sheet — the only write credential the repo would hold, against a working
  document the coalition edits by hand all day. The list is the useful half of
  that job, and it needs no credential at all: both sheets are read over plain
  HTTP as CSV, the same way the rest of scripts/ reads them.

WHAT IT NEVER DOES
  - Writes to either spreadsheet, or to the repository. Nothing here holds a
    credential that could.
  - Reads candidate email addresses. Four identity columns come back from the
    submission sheet's raw tab (submission id, first name, last name,
    municipality) via a gviz column select, the same way
    scripts/sync-questionnaire.py does it.
  - Names the spreadsheets in its output. The report goes to a job summary on a
    public repository, and a sheet id is a capability over the whole sheet. It
    prints a cell reference (column letter and row number) and nothing that
    says which document to open it in.

  A ticked box is only ever read, never cleared: a box the coalition ticked by
  hand (a candidate who answered by email, a submission filed under a different
  name) drops out of the report and is not questioned.

MATCHING
  On normalized full name, disambiguated by municipality only where it has to
  be: one tracking row with that name is reported outright, several (the same
  name running in two municipalities) need the submission's municipality to
  pick one, and anything still unresolved is reported as unresolved rather than
  guessed at. A submission matching nobody is reported too — usually a
  candidate the tracking sheet has not caught up with yet.

  Row status is not consulted. "Running?" decides who the website publishes,
  not who filled in the form; an unconfirmed candidate who answered has still
  answered, and that is what the column records.

Usage:
  python3 scripts/questionnaire-checkoff-report.py             # print the list
  python3 scripts/questionnaire-checkoff-report.py --summary out.md
"""

import argparse
import csv
import importlib.util
import io
import os
import sys
import urllib.error

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MUNI_YML = os.path.join(ROOT, "_data", "municipalities.yml")

# The tracking sheet's own column headers. NAME_COLUMN and MUNICIPALITY_COLUMN
# are what sync-candidates.py already requires of that sheet; CHECKBOX_COLUMN is
# this script's one addition, and a sheet without it is a fatal error rather
# than a warning — the whole job is that column.
NAME_COLUMN = "Candidate Name"
MUNICIPALITY_COLUMN = "Municipality"
CHECKBOX_COLUMN = "Completed Questionnaire"

# Cell values that count as already ticked. A Sheets checkbox exports as
# TRUE/FALSE, but the column may have been a hand-typed "yes" column before it
# was one, and a row somebody wrote "done" into is a row already dealt with.
TICKED_VALUES = {"true", "yes", "y", "x", "✓", "✔", "1", "done", "complete", "completed"}


# --- Helpers borrowed from the sync scripts ----------------------------------
# Imported rather than copied, for the reason sync-questionnaire.py gives for
# doing the same: the three scripts must not drift on how a name is normalized
# or how the submission sheet is read. Both filenames have hyphens in them, so
# neither is importable by name.

def _load(filename, module_name):
    path = os.path.join(ROOT, "scripts", filename)
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_SC = _load("sync-candidates.py", "sync_candidates")
_SQ = _load("sync-questionnaire.py", "sync_questionnaire")

norm = _SC.norm
tidy = _SC.tidy
fetch_csv = _SC.fetch_csv
load_municipalities = _SC.load_municipalities

a1 = _SQ.a1
fetch_tab = _SQ.fetch_tab
RAW_TAB = _SQ.RAW_TAB
RAW_SUBMISSION_ID = _SQ.RAW_SUBMISSION_ID
RAW_FIRST_NAME = _SQ.RAW_FIRST_NAME
RAW_LAST_NAME = _SQ.RAW_LAST_NAME
RAW_MUNICIPALITY = _SQ.RAW_MUNICIPALITY
TAB_FIRST_HEADER = _SQ.TAB_FIRST_HEADER


# --- The tracking sheet ------------------------------------------------------

def read_tracking_rows(text):
    """(header list, [(sheet row number, {column: value})]) from the export CSV.

    Row numbers are the spreadsheet's own, 1-based and counting the header, so
    that what comes out of here can name a cell the reader will scroll to.
    """
    rows = list(csv.reader(io.StringIO(text)))
    if not rows:
        sys.exit("FATAL: the tracking sheet exported no rows at all.")

    header = [tidy(c) for c in rows[0]]
    records = []
    for offset, row in enumerate(rows[1:]):
        record = {header[i]: row[i] for i in range(min(len(header), len(row)))}
        records.append((offset + 2, record))
    return header, records


def find_column(header, wanted):
    """0-based index of a column, matched on normalized header text."""
    target = norm(wanted)
    for i, name in enumerate(header):
        if norm(name) == target:
            return i
    return None


def index_candidates(records, muni_lookup):
    """{normalized name: [row dict]}, each row dict describing one tracking row.

    A list per name, not a row: two people with the same name in different
    municipalities is the case this script has to notice rather than average
    over.
    """
    index = {}
    for row_number, record in records:
        name = tidy(record.get(NAME_COLUMN, ""))
        if not name:
            continue
        municipality = tidy(record.get(MUNICIPALITY_COLUMN, ""))
        index.setdefault(norm(name), []).append({
            "row": row_number,
            "name": name,
            "municipality": municipality,
            "slug": muni_lookup.get(norm(municipality)),
            "ticked": norm(record.get(CHECKBOX_COLUMN, "")) in TICKED_VALUES,
        })
    return index


# --- The submission sheet ----------------------------------------------------

def read_submissions(sheet_id, muni_lookup, warnings):
    """[(normalized name, municipality slug or None, name as submitted)].

    One entry per submission, not per candidate: a candidate who submitted
    twice appears twice, and both entries resolve to the same tracking row.
    """
    wanted = [RAW_SUBMISSION_ID, RAW_FIRST_NAME, RAW_LAST_NAME, RAW_MUNICIPALITY]
    rows = fetch_tab(sheet_id, RAW_TAB, expect=TAB_FIRST_HEADER[RAW_TAB],
                     select=", ".join(a1(c) for c in wanted))
    if rows is None:
        sys.exit(f"FATAL: could not read the {RAW_TAB!r} tab of the submission sheet "
                 "(check QUESTIONNAIRE_SUBMISSIONS_SHEET_ID and the tab's name).")

    # gviz returns the selected columns in the order they were asked for.
    at = {c: i for i, c in enumerate(wanted)}
    cell = lambda row, c: tidy(row[at[c]]) if at[c] < len(row) else ""

    submissions = []
    for row in rows[1:]:
        if not cell(row, RAW_SUBMISSION_ID):
            continue
        name = tidy(f"{cell(row, RAW_FIRST_NAME)} {cell(row, RAW_LAST_NAME)}")
        if not name:
            warnings.append(f"submission {cell(row, RAW_SUBMISSION_ID)}: no name, skipped")
            continue
        municipality = cell(row, RAW_MUNICIPALITY)
        slug = muni_lookup.get(norm(municipality))
        if municipality and slug is None:
            warnings.append(f"{name}: submission municipality {municipality!r} is not in "
                            "municipalities.yml; matching on name alone")
        submissions.append((norm(name), slug, name))
    return submissions


# --- Matching ----------------------------------------------------------------

def resolve(submissions, candidates):
    """({sheet row number: row dict} to tick, already ticked count, [unresolved]).

    The unresolved list is the other half of the report: a candidate the sheet
    has not heard of, or a name spelled differently in the two systems. Each is
    listed once per candidate, not once per submission.
    """
    to_check = {}
    unresolved = []
    already = 0

    for key, slug, display in submissions:
        rows = candidates.get(key)
        if not rows:
            unresolved.append((display, "no row with that name in the tracking sheet"))
            continue

        if len(rows) > 1:
            narrowed = [r for r in rows if slug is not None and r["slug"] == slug]
            if len(narrowed) != 1:
                unresolved.append((display, f"{len(rows)} rows share that name and the "
                                            "submission's municipality does not pick one"))
                continue
            rows = narrowed

        if rows[0]["ticked"]:
            already += 1
        else:
            to_check[rows[0]["row"]] = rows[0]

    return to_check, already, sorted(set(unresolved))


# --- Reporting ---------------------------------------------------------------

def cell_ref(column_index, row_number):
    """The cell to tick, as the sheet itself labels it: "P42"."""
    return f"{a1(column_index)}{row_number}"


def render_summary(to_check, already, submissions, unresolved, warnings, column_index):
    """The job summary, as Markdown. Names no spreadsheet: see the module docstring."""
    out = ["## Questionnaires to check off", ""]

    if to_check:
        out.append(f"**{len(to_check)} to tick** in the tracking sheet's "
                   f"`{CHECKBOX_COLUMN}` column — nothing is ticked for you.")
        out.append("")
        out.append("| Cell | Candidate | Municipality |")
        out.append("| --- | --- | --- |")
        for row_number in sorted(to_check):
            row = to_check[row_number]
            out.append(f"| `{cell_ref(column_index, row_number)}` | {row['name']} | "
                       f"{row['municipality'] or '—'} |")
    else:
        out.append(f"**Nothing to tick.** Every submission that matches a tracking row "
                   f"already has its `{CHECKBOX_COLUMN}` box ticked.")
    out.append("")

    if unresolved:
        out.append(f"### {len(unresolved)} submission(s) with no row to tick")
        out.append("")
        out.append("| Candidate | Why |")
        out.append("| --- | --- |")
        for display, reason in unresolved:
            out.append(f"| {display} | {reason} |")
        out.append("")

    if warnings:
        out.append("### Warnings")
        out.append("")
        out.extend(f"- {w}" for w in warnings)
        out.append("")

    out.append(f"<sub>{len(submissions)} submission(s) read · {already} already ticked · "
               f"read-only: this job writes to no spreadsheet.</sub>")
    out.append("")
    return "\n".join(out)


# --- Main --------------------------------------------------------------------

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--csv-url", default=os.environ.get("CANDIDATES_CSV_URL"),
                    help="Tracking sheet CSV export URL (default: $CANDIDATES_CSV_URL)")
    ap.add_argument("--sheet-id", default=os.environ.get("QUESTIONNAIRE_SUBMISSIONS_SHEET_ID"),
                    help="Submission spreadsheet id (default: $QUESTIONNAIRE_SUBMISSIONS_SHEET_ID)")
    ap.add_argument("--summary", default=os.environ.get("GITHUB_STEP_SUMMARY"),
                    help="Append the report as Markdown to this file "
                         "(default: $GITHUB_STEP_SUMMARY, i.e. the CI run's summary page)")
    args = ap.parse_args(argv)

    if not args.csv_url:
        sys.exit("FATAL: set CANDIDATES_CSV_URL (or pass --csv-url).")
    if not args.sheet_id:
        sys.exit("FATAL: set QUESTIONNAIRE_SUBMISSIONS_SHEET_ID (or pass --sheet-id).")

    _, muni_lookup = load_municipalities(MUNI_YML)

    try:
        text = fetch_csv(args.csv_url)
    except (urllib.error.URLError, urllib.error.HTTPError, OSError) as e:
        sys.exit(f"FATAL: could not fetch the tracking sheet: {e}")
    if text.lstrip()[:1] == "<":
        sys.exit("FATAL: the tracking sheet responded with HTML, not CSV "
                 "(check its sharing settings / export URL).")

    header, records = read_tracking_rows(text)
    for column in (NAME_COLUMN, MUNICIPALITY_COLUMN, CHECKBOX_COLUMN):
        if find_column(header, column) is None:
            sys.exit(f"FATAL: the tracking sheet has no {column!r} column. "
                     f"Columns found: {', '.join(header)}")
    checkbox_index = find_column(header, CHECKBOX_COLUMN)

    warnings = []
    submissions = read_submissions(args.sheet_id, muni_lookup, warnings)
    candidates = index_candidates(records, muni_lookup)
    to_check, already, unresolved = resolve(submissions, candidates)

    for message in warnings:
        print(f"warning: {message}", file=sys.stderr)

    print(f"{len(submissions)} submission(s), {already} already ticked, "
          f"{len(to_check)} to tick by hand.")
    for row_number in sorted(to_check):
        row = to_check[row_number]
        print(f"  {cell_ref(checkbox_index, row_number)}  {row['name']}"
              f"{' — ' + row['municipality'] if row['municipality'] else ''}")
    for display, reason in unresolved:
        print(f"  (no row) {display}: {reason}")

    if args.summary:
        report = render_summary(to_check, already, submissions, unresolved,
                                warnings, checkbox_index)
        try:
            with open(args.summary, "a", encoding="utf-8") as fh:
                fh.write(report)
        except OSError as e:
            print(f"warning: could not write the summary to {args.summary}: {e}",
                  file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
