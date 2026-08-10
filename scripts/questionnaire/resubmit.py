#!/usr/bin/env python3
"""Swap the Victori'Us arts block for the 2026-08-09 resubmission, mid-vote.

Victori'Us sent a revised arts set through the public intake form on 2026-08-09,
replacing the eleven questions the committee had already voted on. The twelve new
questions arrived as rows at the *top* of 'Form Responses 1', which renumbers every
FR-* ID and makes append.py abort, and they are a replacement rather than growth,
which append.py cannot express at all.

tables.py + voting.py would express it, at the price of every vote on the sheet.
Voting is finished, so that price is not payable: the master's Status column and the
comments behind finalize.py's FINAL are the record of a completed process. This does
the swap surgically instead:

  - the twelve submissions are written into "Victori'Us Questions", the arts source
    of record, and deleted from 'Form Responses 1', restoring FR-01..FR-57;
  - the master's VU block is rewritten in place and grown by one row, so FR-*, HFL-*
    and RUSH-* rows never move relative to their votes;
  - every voter tab gets the same single inserted row, and its twelve arts rows are
    cleared, because those votes were cast on questions that no longer exist.

The new set maps 1:1 onto the old one in submission order, so VU-01..VU-11 keep their
meaning and only VU-12 is new. That is what lets finalize.py's existing origins lists
survive; without it this would have needed a rewrite of the whole arts block there.

Everything the run overwrites is dumped to a JSON file outside the repo first. The
old arts votes are in it, and they are the only copy.

One-off. Kept in the tree as the record of what was done to the sheet on 2026-08-09,
and as a worked example if another source tab is ever revised after voting closes.

Usage:
  QUESTIONNAIRE_SHEET_ID=... python3 scripts/questionnaire/resubmit.py --dry-run
  QUESTIONNAIRE_SHEET_ID=... python3 scripts/questionnaire/resubmit.py
"""

import json
import os
import sys
from datetime import datetime

from aggregate import FIRST, HEADERS, MASTER, build_rows, open_sheet
from tables import AGG_HEADERS, column_properties
from voting import (
    AGG_START_COL, STATUS_COL, STATUS_COLOURS, aggregate_formulas, check_voter_columns,
    col_letter, tab_name,
)
from voting import HEADERS as VOTE_HEADERS

INTAKE = "Form Responses 1"
ARTS = "Victori'Us Questions"

# The arts block as it stands before this run: master rows 84-94, IDs VU-01..VU-11.
# Asserted rather than searched for, so a sheet that has moved on since this was
# written stops the run instead of rewriting the wrong twelve rows.
EXPECT_FIRST_VU = 84
EXPECT_OLD_VU = [f"VU-{n:02d}" for n in range(1, 12)]

RESUBMITTED = "Resubmitted 2026-08-09; replaces the 2026-08-01 Victori'Us set."

# One entry per submission, oldest first, which is the order the old tab was in and
# therefore the order that keeps VU-01..VU-11 pointing at the same subject matter.
#
#   ts        locates the row in the intake tab; the row index is not stable
#   drop      title line stripped off the front of the question, having been lifted
#             into the Category column - verified present, never searched for
#   split     where the option list starts; everything from here goes to Answers
#   answers   overrides the split for the two open responses, whose "(N characters)"
#             tail is a length limit rather than a set of options
NEW_ARTS = [
    dict(
        ts="8/9/2026 17:35:21", category="Budget priorities",
        drop='Applies to "All" \'What topic best applies to your question?"\n\n'
             "Budget Allocation Scenario:\n\n",
        split="Housing\nTransit\n",
        notes="Allocation question - responses must total $10M. "
              "No per-question rubric supplied.",
    ),
    dict(
        ts="8/9/2026 17:36:43", category="Economic development",
        drop="Arts & Culture as Economic Infrastructure: \n",
        split="☐ Yes\n",
        notes="Conditional follow-up, 500 character limit. "
              "No per-question rubric supplied.",
    ),
    dict(
        ts="8/9/2026 17:40:39", category="Commitment",
        drop="First-Year Arts & Culture Commitment:\n\n",
        split="(1000 characters)", answers="Open response (1000 characters)",
        notes="1000 character limit. Submitted scope: Victoria, the only one of the "
              "twelve not submitted as All municipalities. "
              "Prior 0-3 rubric not restated in this revision.",
    ),
    dict(
        ts="8/9/2026 17:46:13", category="Cultural space",
        drop="Cultural Space Strategy & Implementation:\n\n",
        split="Select all that you would support:\n",
        notes="Organisation field on this one submission reads \"No, I'm providing a "
              "helpful suggestion\"; same submitter and same set as the other eleven. "
              "Prior 0-3 rubric not restated in this revision.",
    ),
    dict(
        ts="8/9/2026 17:50:06", category="Permitting & regulation",
        drop="Municipal Systems Reform:\n\n",
        split="Select all that apply:\n",
        notes="Prior 0-3 rubric not restated in this revision.",
    ),
    dict(
        ts="8/9/2026 17:59:52", category="Funding",
        drop="Investing in Cultural Infrastructure:\n",
        split="☐ Increase funding for existing municipal cultural infrastructure",
        notes="Prior 0-3 rubric not restated in this revision.",
    ),
    dict(
        ts="8/9/2026 18:00:24", category="Ownership & financing",
        drop="Cultural Ownership & Financing Models:\n\n",
        split="☐ Yes\n",
        notes="Two-part question: single-select position, then multi-select tools "
              "conditional on 'Yes'. Prior 0-3 rubric not restated in this revision.",
    ),
    dict(
        ts="8/9/2026 18:01:11", category="Budget priorities",
        drop="Municipal Budget Priorities:\n\n",
        split="☐ Yes — arts and culture",
        notes="No per-question rubric supplied.",
    ),
    dict(
        ts="8/9/2026 18:03:15", category="Housing & cultural space",
        drop="Housing and Cultural Space Trade-offs:\n\n",
        split="☐ Preserve existing cultural spaces where feasible",
        notes="No per-question rubric supplied. Select-one vs select-all not "
              "specified in source.",
    ),
    dict(
        ts="8/9/2026 18:04:08", category="Tax tools", drop="",
        split="☐ Requiring or incentivizing cultural space",
        notes="Expanded from the 2026-08-01 version's Yes / No / Unsure into a "
              "seven-option select-all.",
    ),
    dict(
        ts="8/9/2026 18:05:26", category="Accountability",
        drop="Four-Year Accountability Commitments\n\n",
        split="Please identify measurable outcomes wherever possible.",
        answers="Open response (2000 characters)\n\n"
                "Please identify measurable outcomes wherever possible. "
                "Consider including:\n\n"
                "- policy changes\n- funding commitments\n- infrastructure projects\n"
                "- regulatory reforms\n- partnerships",
        notes="2000 character limit. The 2026-08-01 version referenced the global "
              "rubric at the bottom of this tab; not restated in this revision.",
    ),
    dict(
        # The submitter's "informational, not scored" preamble is a scoring
        # instruction to us, not text for a candidate, so it moves to Scoring.
        ts="8/9/2026 18:09:30", category="Investment priorities",
        drop="Types of Art & Cultural Activity:\n\n"
             "*Informational question — not scored.\n\n"
             "This question is intended to provide additional insight into candidates' "
             "perspectives on arts and cultural investment. Responses will be published "
             "with the scorecard results but will not affect a candidate's overall "
             "grade.\n\n",
        split="For example, should priorities be based on",
        answers="Open response (1000 characters)\n\n"
                "For example, should priorities be based on community demand, gaps in "
                "cultural infrastructure, economic impact, equity and access, "
                "preservation of cultural heritage, or other criteria?",
        scoring="Informational - not scored. The submitter asks that responses be "
                "published alongside the scorecard results without affecting a "
                "candidate's grade.",
        notes="New in the 2026-08-09 submission; no counterpart in the 2026-08-01 "
              "version.",
    ),
]

ARTS_HEADERS = ["Number", "Category", "Question", "Answers", "Scoring", "Notes"]


def backup(sh, voters):
    """Dump every tab this run overwrites, outside the repo. The votes are the point."""
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out = os.path.expanduser(f"~/livable-crd-backups/questionnaire-{stamp}.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    titles = [INTAKE, ARTS, MASTER] + [tab_name(v) for v in voters]
    with open(out, "w") as f:
        json.dump({t: sh.worksheet(t).get_all_values() for t in titles}, f, indent=1)
    os.chmod(out, 0o600)
    return out


def arts_rows(intake):
    """The twelve submissions, as rows for the Victori'Us tab.

    Question and Answers are sliced out of the submitted text rather than retyped, so
    the tab carries the submitter's words exactly. Every marker is asserted present:
    a silent miss here would put an option list in the question column and nobody
    would notice until it reached a candidate.
    """
    by_ts = {r[0].strip(): r for r in intake[1:] if r and r[0].strip()}
    rows = []
    for n, spec in enumerate(NEW_ARTS, 1):
        src = by_ts.get(spec["ts"])
        if src is None:
            sys.exit(f"FATAL: no {INTAKE} row timestamped {spec['ts']!r}. "
                     "The intake tab has changed since this script was written.")
        text = src[7].replace("\r\n", "\n").strip()
        if spec["drop"]:
            if not text.startswith(spec["drop"].strip()):
                sys.exit(f"FATAL: {spec['ts']} does not start with {spec['drop']!r}.")
            text = text[len(spec["drop"].strip()):].strip()
        if spec["split"] not in text:
            sys.exit(f"FATAL: {spec['ts']} has no {spec['split']!r} to split on.")
        at = text.index(spec["split"])
        question = text[:at].strip()
        rows.append([
            str(n), spec["category"], question,
            spec.get("answers", text[at:].strip()), spec.get("scoring", ""),
            f"{spec['notes']} {RESUBMITTED}".strip(),
        ])
    return rows


def write_arts_tab(sh, rows, tail):
    """Replace the tab's question block, keeping the preamble and rubric below it."""
    ws = sh.worksheet(ARTS)
    ws.batch_clear([f"A2:F{1 + len(rows) + 1 + len(tail) + 4}"])
    ws.update([ARTS_HEADERS], "A1", value_input_option="RAW")
    ws.update(rows, "A2", value_input_option="RAW")
    ws.update(tail, f"A{2 + len(rows) + 1}", value_input_option="RAW")


def table_by_sheet(meta):
    return {s["properties"]["sheetId"]: s.get("tables", []) for s in meta["sheets"]}


def retable(tables, sheet_id, new_last, col_props=None):
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
    """Repoint the Status colour rules at the longer range, one rule per status."""
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


def insert_row(sheet_id, at):
    """One row at 1-based `at`, inheriting the row above so table types come with it."""
    return {"insertDimension": {
        "range": {"sheetId": sheet_id, "dimension": "ROWS",
                  "startIndex": at - 1, "endIndex": at},
        "inheritFromBefore": True,
    }}


def main():
    dry_run = "--dry-run" in sys.argv[1:]

    sh = open_sheet()
    master = sh.worksheet(MASTER)
    voters = sorted(ws.title[len("Vote - "):] for ws in sh.worksheets()
                    if ws.title.startswith("Vote - "))
    check_voter_columns(sh, voters)

    have = [v for v in master.col_values(1)[FIRST - 1:] if v.strip()]
    old_last = FIRST + len(have) - 1
    old_vu = have[EXPECT_FIRST_VU - FIRST:EXPECT_FIRST_VU - FIRST + len(EXPECT_OLD_VU)]
    if old_vu != EXPECT_OLD_VU:
        sys.exit(f"FATAL: expected {EXPECT_OLD_VU[0]}..{EXPECT_OLD_VU[-1]} at master rows "
                 f"{EXPECT_FIRST_VU}-{EXPECT_FIRST_VU + len(EXPECT_OLD_VU) - 1}, found "
                 f"{old_vu}. The sheet has moved on; re-read this script before running it.")

    intake = sh.worksheet(INTAKE).get_all_values()
    new_arts = arts_rows(intake)
    drop_rows = sorted(
        (i for i, r in enumerate(intake, 1)
         if r and r[0].strip() in {s["ts"] for s in NEW_ARTS}), reverse=True)
    if len(drop_rows) != len(NEW_ARTS):
        sys.exit(f"FATAL: found {len(drop_rows)} intake rows to remove, expected "
                 f"{len(NEW_ARTS)}.")

    old_arts = sh.worksheet(ARTS).get_all_values()
    tail = [r[:len(ARTS_HEADERS)] for r in old_arts
            if any(c.strip() for c in r) and not r[0].strip().isdigit()][1:]

    new_last = old_last + (len(NEW_ARTS) - len(EXPECT_OLD_VU))
    vu_end = EXPECT_FIRST_VU + len(NEW_ARTS) - 1

    print(f"master holds {len(have)} questions (rows {FIRST}-{old_last})")
    print(f"arts block rows {EXPECT_FIRST_VU}-{EXPECT_FIRST_VU + len(EXPECT_OLD_VU) - 1} "
          f"({len(EXPECT_OLD_VU)} questions) -> {EXPECT_FIRST_VU}-{vu_end} "
          f"({len(NEW_ARTS)}), master ends at row {new_last}")
    print(f"removing intake rows {', '.join(str(r) for r in reversed(drop_rows))} "
          f"(restores FR-01..FR-57)")
    print(f"clearing arts votes for {len(voters)} members: {', '.join(voters)}")
    for r in new_arts:
        print(f"  VU-{int(r[0]):02d} {r[1]:26} {r[2][:64]}")
    print(f"carrying {len(tail)} non-question rows down the arts tab: "
          f"{', '.join(t[0] for t in tail)}")

    if dry_run:
        print("\n--dry-run: nothing written")
        return

    saved = backup(sh, voters)
    print(f"\nbacked up {INTAKE}, {ARTS}, {MASTER} and every voter tab to {saved}")

    write_arts_tab(sh, new_arts, tail)
    print(f"wrote {len(new_arts)} questions to {ARTS!r}")

    intake_ws = sh.worksheet(INTAKE)
    sh.batch_update({"requests": [
        {"deleteDimension": {"range": {"sheetId": intake_ws.id, "dimension": "ROWS",
                                       "startIndex": r - 1, "endIndex": r}}}
        for r in drop_rows]})
    print(f"deleted {len(drop_rows)} rows from {INTAKE!r}")

    # Regenerated rather than hand-written, so the master cannot drift from the data
    # layer every other script reads the sheet through.
    desired = build_rows(sh)
    want = [r[0] for r in desired]
    outside = [(a, b) for a, b in zip(have[:EXPECT_FIRST_VU - FIRST], want) if a != b]
    tail_have = have[EXPECT_FIRST_VU - FIRST + len(EXPECT_OLD_VU):]
    tail_want = want[EXPECT_FIRST_VU - FIRST + len(NEW_ARTS):]
    if outside or tail_have != tail_want or len(want) != new_last - FIRST + 1:
        sys.exit(f"FATAL: source tabs no longer reproduce the master's non-arts IDs "
                 f"({len(want)} questions, expected {new_last - FIRST + 1}). "
                 f"The sheet is now half-migrated - restore from {saved}.")

    meta = sh.fetch_sheet_metadata()
    tables = table_by_sheet(meta)
    voter_ws = {v: sh.worksheet(tab_name(v)) for v in voters}

    reqs = [insert_row(master.id, vu_end)]
    reqs += [insert_row(voter_ws[v].id, vu_end) for v in voters]
    reqs += retable(tables, master.id, new_last, column_properties())
    for v in voters:
        reqs += retable(tables, voter_ws[v].id, new_last)
    reqs += restatus_formats(meta, master.id, new_last)
    sh.batch_update({"requests": reqs})
    print(f"inserted row {vu_end} into {MASTER!r} and every voter tab, "
          f"extended their tables to row {new_last}")

    n_cols = len(HEADERS) + len(AGG_HEADERS)
    if master.row_count < new_last:
        master.resize(rows=new_last + 50, cols=max(master.col_count, n_cols))
    master.update(desired[EXPECT_FIRST_VU - FIRST:EXPECT_FIRST_VU - FIRST + len(NEW_ARTS)],
                  f"A{EXPECT_FIRST_VU}", value_input_option="RAW")
    print(f"rewrote {MASTER!r} A{EXPECT_FIRST_VU}:J{vu_end} as VU-01..VU-{len(NEW_ARTS)}")

    # Every aggregate rewritten, not just the arts rows. Sheets rewrites cross-sheet
    # references itself when a row is inserted, and it gets this right, but the whole
    # block is cheap and leaves nothing depending on that.
    master.update([aggregate_formulas(voters, row) for row in range(FIRST, new_last + 1)],
                  f"{col_letter(AGG_START_COL)}{FIRST}", value_input_option="USER_ENTERED")
    print(f"rewrote K{FIRST}:{col_letter(n_cols)}{new_last} aggregates for all "
          f"{new_last - FIRST + 1} rows")

    pulled = [[f"='{MASTER}'!A{r}", f"='{MASTER}'!B{r}", f"='{MASTER}'!D{r}"]
              for r in range(FIRST, new_last + 1)]
    blank = [[""] * (len(VOTE_HEADERS) - 3) for _ in range(len(NEW_ARTS))]
    for v in voters:
        ws = voter_ws[v]
        if ws.row_count < new_last:
            ws.resize(rows=new_last + 20, cols=max(ws.col_count, len(VOTE_HEADERS)))
        ws.update(pulled, f"A{FIRST}", value_input_option="USER_ENTERED")
        ws.update(blank, f"D{EXPECT_FIRST_VU}", value_input_option="RAW")
        print(f"  {tab_name(v)!r}: repulled A:C, cleared votes on rows "
              f"{EXPECT_FIRST_VU}-{vu_end}")

    print("\nnext: edit FINAL in finalize.py for the new arts text, then run")
    print("  python3 scripts/questionnaire/finalize.py --dry-run")
    print("  python3 scripts/questionnaire/summary.py")


if __name__ == "__main__":
    main()
