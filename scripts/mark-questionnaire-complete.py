#!/usr/bin/env python3
"""Tick "Completed Questionnaire" in the candidate-tracking sheet.

Two sheets, one direction. Reads who submitted the questionnaire from Tally's
submission spreadsheet (`QUESTIONNAIRE_SUBMISSIONS_SHEET_ID`), matches them
against the coalition candidate-tracking sheet (`CANDIDATES_CSV_URL`), and
ticks the tracking sheet's "Completed Questionnaire" checkbox for every match
that is not ticked already. Meant to run daily in CI; see
.github/workflows/mark-questionnaire-complete.yml.

WHAT IT NEVER DOES
  - Unticks. A ticked box is left alone even if no submission matches it: the
    coalition ticks boxes by hand too (a candidate who answered by email, a
    submission filed under a different name), and a sync that fought those
    edits would be worse than no sync. The box only ever goes one way.
  - Touches any other cell, column, or tab, in either spreadsheet. The
    submission sheet is read-only here, as it is everywhere else in scripts/.
  - Reads candidate email addresses. Four identity columns come back from the
    submission sheet's raw tab (submission id, first name, last name,
    municipality) via a gviz column select, the same way
    scripts/sync-questionnaire.py does it.

MATCHING
  On normalized full name, disambiguated by municipality only where it has to
  be: one tracking row with that name gets ticked outright, several (the same
  name running in two municipalities) need the submission's municipality to
  pick one, and anything still unresolved is reported and skipped rather than
  guessed at. A submission matching nobody is reported too — usually a
  candidate the tracking sheet has not caught up with yet.

  Row status is not consulted. "Running?" decides who the website publishes,
  not who filled in the form; an unconfirmed candidate who answered has still
  answered, and that is what the column records.

CREDENTIALS
  Reading needs nothing: both sheets come over HTTP as CSV. Writing needs a
  Google service account with edit access to the tracking sheet — share the
  sheet with the service account's email, and put the account's JSON key in
  $GOOGLE_SERVICE_ACCOUNT_JSON (CI: the repo secret of the same name). It is
  the only credential in scripts/ that can write to a spreadsheet, so it is
  scoped to spreadsheets alone and used by this script alone.

  Which spreadsheet and which tab are taken from CANDIDATES_CSV_URL, so there
  is no second copy of the sheet id to keep in step. The export URL is
  read-only on its own; it names the target, the service account authorizes it.

Usage:
  python3 scripts/mark-questionnaire-complete.py --dry-run   # report, write nothing
  python3 scripts/mark-questionnaire-complete.py             # tick the boxes
"""

import argparse
import csv
import importlib.util
import io
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

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
# was one, and re-ticking a row that is already marked would be a pointless
# write with a real chance of clobbering the note somebody left in it.
TICKED_VALUES = {"true", "yes", "y", "x", "✓", "✔", "1", "done", "complete", "completed"}

# Written into an empty checkbox. Sent with USER_ENTERED, so Sheets parses it
# into the boolean a checkbox holds rather than storing the four letters beside
# an untouched tickbox.
TICK = "TRUE"

# Least privilege for the write: this account can touch spreadsheets shared with
# it and nothing else in the Drive it was created in.
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


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

def parse_export_url(url):
    """(spreadsheet id, worksheet gid or None) from a CSV export URL.

    The gid may legitimately be absent — an export URL without one means the
    first tab — but the id may not, and a URL this function cannot read is a
    misconfigured secret rather than something to work around.
    """
    parsed = urllib.parse.urlparse(url)
    parts = [p for p in parsed.path.split("/") if p]
    try:
        sheet_id = parts[parts.index("d") + 1]
    except (ValueError, IndexError):
        sys.exit("FATAL: CANDIDATES_CSV_URL has no /d/<sheet id>/ in it; expected a "
                 "Google Sheets export URL.")

    query = urllib.parse.parse_qs(parsed.query)
    gid = (query.get("gid") or [None])[0]
    if gid is None and parsed.fragment:
        gid = (urllib.parse.parse_qs(parsed.fragment).get("gid") or [None])[0]
    if gid is not None:
        try:
            gid = int(gid)
        except ValueError:
            sys.exit(f"FATAL: CANDIDATES_CSV_URL has a non-numeric gid: {gid!r}")
    return sheet_id, gid


def read_tracking_rows(text):
    """(header list, [(sheet row number, {column: value})]) from the export CSV.

    Row numbers are the spreadsheet's own, 1-based and counting the header, so
    that what comes out of here can address a cell without a second pass over
    the sheet.
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
    """{normalized name: [(row number, municipality slug or None, ticked?)]}.

    A list per name, not a row: two people with the same name in different
    municipalities is the case this script has to notice rather than average
    over.
    """
    index = {}
    for row_number, record in records:
        name = norm(record.get(NAME_COLUMN, ""))
        if not name:
            continue
        slug = muni_lookup.get(norm(record.get(MUNICIPALITY_COLUMN, "")))
        ticked = norm(record.get(CHECKBOX_COLUMN, "")) in TICKED_VALUES
        index.setdefault(name, []).append((row_number, slug, ticked))
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

def resolve(submissions, candidates, warnings):
    """Sheet row numbers to tick, in sheet order.

    Also reports, once per candidate, every submission that could not be placed
    in the tracking sheet. Those are the interesting ones: a candidate the sheet
    has not heard of, or a name spelled differently in the two systems.
    """
    to_tick = {}
    unmatched = []
    already = 0

    for key, slug, display in submissions:
        rows = candidates.get(key)
        if not rows:
            unmatched.append((display, "no row with that name in the tracking sheet"))
            continue

        if len(rows) > 1:
            narrowed = [r for r in rows if slug is not None and r[1] == slug]
            if len(narrowed) != 1:
                unmatched.append((display, f"{len(rows)} rows share that name and the "
                                           "submission's municipality does not pick one"))
                continue
            rows = narrowed

        row_number, _, ticked = rows[0]
        if ticked:
            already += 1
        else:
            to_tick[row_number] = display

    for display, reason in sorted(set(unmatched)):
        warnings.append(f"{display}: {reason}")
    return to_tick, already


# --- The write ---------------------------------------------------------------

def open_worksheet(sheet_id, gid):
    """The tracking sheet's tab, opened with the service account.

    gspread and google-auth are imported here rather than at the top of the
    file so that --dry-run, which needs neither, runs on a stdlib-only box the
    way the rest of scripts/ does.
    """
    try:
        import gspread
        from google.oauth2.service_account import Credentials
    except ImportError:
        sys.exit("FATAL: writing needs gspread and google-auth "
                 "(pip install -r scripts/questionnaire/requirements.txt), or pass --dry-run.")

    blob = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
    if not blob:
        sys.exit("FATAL: set GOOGLE_SERVICE_ACCOUNT_JSON to the service account's JSON key "
                 "(or pass --dry-run).")
    try:
        info = json.loads(blob)
    except json.JSONDecodeError as e:
        sys.exit(f"FATAL: GOOGLE_SERVICE_ACCOUNT_JSON is not valid JSON: {e}")

    client = gspread.authorize(Credentials.from_service_account_info(info, scopes=SCOPES))
    spreadsheet = client.open_by_key(sheet_id)
    if gid is None:
        return spreadsheet.get_worksheet(0)
    try:
        return spreadsheet.get_worksheet_by_id(gid)
    except Exception:
        sys.exit(f"FATAL: the tracking spreadsheet has no tab with gid {gid} "
                 "(the one CANDIDATES_CSV_URL points at).")


def tick(worksheet, column_index, row_numbers):
    """Tick one cell per row, in a single batched request."""
    letter = a1(column_index)
    worksheet.batch_update(
        [{"range": f"{letter}{n}", "values": [[TICK]]} for n in sorted(row_numbers)],
        value_input_option="USER_ENTERED",
    )


# --- Main --------------------------------------------------------------------

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--csv-url", default=os.environ.get("CANDIDATES_CSV_URL"),
                    help="Tracking sheet CSV export URL (default: $CANDIDATES_CSV_URL)")
    ap.add_argument("--sheet-id", default=os.environ.get("QUESTIONNAIRE_SUBMISSIONS_SHEET_ID"),
                    help="Submission spreadsheet id (default: $QUESTIONNAIRE_SUBMISSIONS_SHEET_ID)")
    ap.add_argument("--dry-run", action="store_true",
                    help="Report what would be ticked; write nothing, and need no credentials.")
    args = ap.parse_args(argv)

    if not args.csv_url:
        sys.exit("FATAL: set CANDIDATES_CSV_URL (or pass --csv-url).")
    if not args.sheet_id:
        sys.exit("FATAL: set QUESTIONNAIRE_SUBMISSIONS_SHEET_ID (or pass --sheet-id).")

    sheet_id, gid = parse_export_url(args.csv_url)
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
    if not submissions:
        print("No submissions in the sheet; nothing to tick.")
        return 0

    candidates = index_candidates(records, muni_lookup)
    to_tick, already = resolve(submissions, candidates, warnings)

    for message in warnings:
        print(f"warning: {message}", file=sys.stderr)

    print(f"{len(submissions)} submission(s), {already} already ticked, "
          f"{len(to_tick)} to tick.")
    for row_number in sorted(to_tick):
        print(f"  row {row_number}: {to_tick[row_number]}")

    if not to_tick:
        return 0
    if args.dry_run:
        print("Dry run: the tracking sheet was not modified.")
        return 0

    worksheet = open_worksheet(sheet_id, gid)
    tick(worksheet, checkbox_index, to_tick)
    print(f"Ticked {len(to_tick)} checkbox(es) in {CHECKBOX_COLUMN!r}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
