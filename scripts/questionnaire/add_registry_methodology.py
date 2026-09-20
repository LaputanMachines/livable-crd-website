#!/usr/bin/env python3
"""Fill the registry's `Methodology` column from the rubrics that grade each question.

`add_methodology.py` created the column. This writes into it, for the questions
whose answer-to-letter mapping lives in `rubrics.py` rather than in whoever was
grading that day. The text is the mapping plus the reason the letters fall where
they do, which is what the committee asked the column to hold, and it is
transcribed from `RUBRICS[label]["notes"]` rather than restated from memory, so
the sheet and the code cannot drift apart without someone noticing.

A question with no entry in `RUBRICS` is graded by a person off free text, and
this has nothing to say about it. Those rows are listed and left alone.

Only a blank `Methodology` cell is written. A cell somebody already typed is
theirs, and is reported as skipped rather than overwritten.

Nothing else on the tab is touched: no column is added, moved or renamed, and no
other cell is written. The column positions the grading tabs look up by number
are unaffected.

Dry-run by default, and it asserts the header layout before it writes anything.

  python3 scripts/questionnaire/add_registry_methodology.py            # preview
  python3 scripts/questionnaire/add_registry_methodology.py --apply    # do it
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
REGISTRY_TAB = "Question Registry"
BACKUP_DIR = os.path.expanduser("~/livable-crd-backups")
SHEET_ID_FILE = os.path.expanduser("~/livable-crd-grading/sheet-id")

# The layout this writes into. Checked against the live header before anything
# is sent, so a registry that has drifted stops the run rather than having a
# paragraph written into whatever now sits in column G.
HEADERS = ["Label", "Category", "Question", "Type", "Graded", "Weight",
           "Methodology", "Raw columns", "Notes", "Owner"]
LABEL_COLUMN = 0
METHODOLOGY_COLUMN = 6

# The shared non-answer policy, appended to every cell. It is per question in
# the sheet because each cell has to stand on its own for whoever reads that
# row, and it is one string here because there is only one policy.
NON_ANSWER = (
    "Decline to answer is F where nothing explains it, and the Grade is left "
    "blank where the candidate explained the decline in the topic's comment "
    "box or answered the rest of the topic solidly. Unsure is left blank. A "
    "blank Grade drops the row out of the category rollup entirely; N/A is "
    "reserved for a question that does not apply to a candidate and never "
    "means ungraded."
)

METHODOLOGY = {
    "CLI-01": (
        "Two commitments in one question, so the menu answer alone cannot reach "
        "the top. The menu sets a base and a Yes on the follow-up about "
        "advocating at the Victoria Regional Transit Commission raises it one "
        "step. Yes, both advertising and sponsorship = B, and A with the "
        "follow-up. Yes, advertising only or Yes, sponsorship only = C, and B "
        "with the follow-up. No = F, because ending the advertising is "
        "something the municipality controls outright. A follow-up written as "
        "free text rather than ticked is a judgement about the candidate and "
        "is graded by hand."
    ),
    "CLI-02": (
        "The overriding priority, other decisions should be tested against it "
        "= A. One of the top three priorities, with a dedicated budget = B. "
        "One priority among many, addressed where affordable = C-. Not a "
        "municipal priority = F. The ladder skips C on purpose: a dedicated "
        "budget is the line between a priority and a sentiment, so addressing "
        "climate only where affordable drops two steps rather than one. "
        "Handing the file to another order of government is F."
    ),
    "CLI-03": (
        "Yes = A, No = C-. The No is C- rather than F because of the split the "
        "grading settled on: a plain No is C- where the question is about "
        "governance or conduct and F where it is about infrastructure, land "
        "use or funding. This one asks a candidate to give up a channel of "
        "access to themselves, which is conduct."
    ),
    "CLI-04": (
        "Yes = A. Yes, if municipal costs are capped = B, because a "
        "conditional yes is B wherever one appears and a cap on municipal "
        "exposure lands there. No = F, because the question is about spending "
        "to recover costs, which is the funding side of the split CLI-03 sits "
        "on the other side of."
    ),
    "CLI-05": (
        "Yes = A, No = F. A land use question, so a No is F rather than C-."
    ),
    "CLI-06": (
        "Up to five measures may be ticked. Four or more ticks including at "
        "least two of the three the municipality has to pay for (subsidized "
        "home assessments, grants or financing for retrofits, designated "
        "centres with guaranteed opening hours) = A. Three or more ticks = B. "
        "Two = C. One = C-. None of the above = F. The funding floor is there "
        "because a straight count of ticks would let a candidate reach the top "
        "on the two cheapest options, a vegetation bylaw and an information "
        "campaign, while committing no money to anyone actually living in an "
        "overheating home."
    ),
    "CLI-07": (
        "Yes = A, No = F. A regulatory phase-out, graded on the same footing "
        "as CLI-05."
    ),
    "CLI-08": (
        "Oppose all new data centres = A. Support only with waste-heat "
        "recovery and no net increase in potable water use = B. Support only "
        "under conditions set case by case = C. Support without special "
        "conditions = F. The two conditional options are separated by whether "
        "the condition binds. Waste-heat recovery and no net potable water "
        "increase is a testable commitment, so it takes the conditional-yes B. "
        "Conditions set case by case name nothing and commit to nothing, so it "
        "takes the C that a depends-case-by-case answer gets everywhere else."
    ),
    "CLI-12": (
        "Yes = A, No = F. Graded by RUSH from 2026-09-01; the mapping is "
        "recorded so the remaining rows match the ones already typed."
    ),
    "ROL-02": (
        "Yes = A. Yes, except where physically impossible = B. No = F. Except "
        "where physically impossible is a condition that can be checked "
        "against a street, so it takes the conditional-yes B, and that is "
        "where the 19 rows graded before this rubric existed put it. A No is F "
        "because the question sets a construction standard, which is "
        "infrastructure."
    ),
    "ROL-03": (
        "Yes = A. Depends, case-by-case = C. No = F. Depends case by case "
        "names no test and commits to nothing, which is the C it gets on "
        "CLI-08 and TRN-02; 13 of the 14 rows graded before this rubric "
        "existed agree. A No is F because the question is about keeping built "
        "infrastructure in place. An answer of N/A is a claim that the "
        "question does not apply to that municipality, which is a judgement "
        "about a candidate and is passed in by hand, like an excused decline."
    ),
    "TRN-01": (
        "A count of ticks, because no option here is cheaper than the others "
        "in the way CLI-06's are. Four or more = A. Three = B. Two = C. One = "
        "C-. None = F. The rows graded before this rubric was written are not "
        "perfectly consistent with it at three and two ticks; they were left "
        "as typed and the majority letter was taken."
    ),
    "TRN-02": (
        "Yes, across the whole corridor = A. Yes, only during peak hours = B. "
        "Kind of, only when a specific project requires it = C. No = F. Peak "
        "hours only is a real, testable limit on a yes, so it takes the "
        "conditional-yes B. Only when a specific project requires it names no "
        "project and commits to nothing in advance, which is the case-by-case "
        "answer CLI-08 puts at C. A No is F because the question is about "
        "street space, which is infrastructure. Eight of the earlier rows put "
        "the case-by-case option at B and nineteen put it at C; the nineteen "
        "were followed."
    ),
    "TRN-03": (
        "Yes = A. Yes, but not at the cost of a general-purpose travel lane = "
        "C-. No = F. The question asks specifically about giving up a traffic "
        "lane, so a yes that rules the lane out withholds the one thing being "
        "asked for and cannot take the conditional-yes B. C- rather than F "
        "because the rest of the toolkit is still on the table."
    ),
    "TRN-04": (
        "Yes = A, No = C-. A No is C- rather than F because this asks who "
        "should decide, not what should be built or funded, which puts it on "
        "the governance side of the CLI-03 split. Three earlier rows typed F "
        "and two typed C-; the governance rule was followed over the count."
    ),
    "TRN-05": (
        "Yes = A. Yes, if no mature trees are lost during construction = B. No "
        "= F. Losing no mature trees is a named and checkable condition, so it "
        "takes the conditional-yes B. A No is F because the question is about "
        "building a connection, which is infrastructure."
    ),
}


def default_sheet_id():
    if os.environ.get("QUESTIONNAIRE_SUBMISSIONS_SHEET_ID"):
        return os.environ["QUESTIONNAIRE_SUBMISSIONS_SHEET_ID"]
    if os.path.exists(SHEET_ID_FILE):
        return open(SHEET_ID_FILE).read().strip()
    return None


def fetch_registry(sheet_id, timeout=120):
    params = {"tqx": "out:csv", "sheet": REGISTRY_TAB, "headers": "1"}
    url = GVIZ.format(id=sheet_id) + "?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=timeout) as response:
        body = response.read().decode("utf-8")
    rows = list(csv.reader(io.StringIO(body)))
    if not rows or rows[0][:1] != ["Label"]:
        raise SystemExit(f"{REGISTRY_TAB!r} did not come back with a Label header")
    return rows


def check_layout(header):
    got = [c.strip() for c in header[:len(HEADERS)]]
    if got != HEADERS:
        raise SystemExit(
            f"{REGISTRY_TAB!r} header is not the layout this writes into.\n"
            f"  expected: {HEADERS}\n  got:      {got}"
        )


def proposals(rows):
    """(to write, already filled, no rubric), each a list of (row number, label)."""
    write, filled, no_rubric = [], [], []
    for i, row in enumerate(rows[1:], start=2):
        row = row + [""] * (len(HEADERS) - len(row))
        label = row[LABEL_COLUMN].strip()
        if not label:
            continue
        if row[METHODOLOGY_COLUMN].strip():
            filled.append((i, label))
        elif label not in METHODOLOGY:
            no_rubric.append((i, label))
        else:
            write.append((i, label))
    return write, filled, no_rubric


def backup(sh, stamp):
    os.makedirs(BACKUP_DIR, exist_ok=True)
    path = os.path.join(BACKUP_DIR, f"submissions-tabs-{stamp}.json")
    dump = {ws.title: ws.get_all_values() for ws in sh.worksheets()}
    with open(path, "w") as fh:
        json.dump(dump, fh, indent=1)
    return path


def worksheet_by_title(sh, title):
    want = title.strip().lower()
    for ws in sh.worksheets():
        if ws.title.strip().lower() == want:
            return ws
    raise SystemExit(f"no tab {title!r} on the spreadsheet")


def text_for(label):
    return f"{METHODOLOGY[label]} {NON_ANSWER}"


def apply(sheet_id, write):
    import gspread  # imported late: only the write path needs it installed

    sh = gspread.oauth().open_by_key(sheet_id)
    stamp = datetime.datetime.now().strftime("%Y%m%dT%H%M%S")
    print(f"backup: {backup(sh, stamp)}")

    ws = worksheet_by_title(sh, REGISTRY_TAB)
    live = ws.col_values(LABEL_COLUMN + 1)
    column = chr(ord("A") + METHODOLOGY_COLUMN)

    updates = []
    for row, label in write:
        if row > len(live) or live[row - 1].strip() != label:
            raise SystemExit(
                f"row {row} holds {live[row - 1].strip()!r}, not {label!r}. "
                f"The tab moved between the read and the write; nothing written."
            )
        updates.append({"range": f"{column}{row}", "values": [[text_for(label)]]})

    ws.batch_update(updates, value_input_option="RAW")
    print(f"wrote {len(updates)} Methodology cell(s) to {REGISTRY_TAB}")


def main():
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--sheet-id", default=default_sheet_id())
    p.add_argument("--apply", action="store_true", help="write to the sheet")
    args = p.parse_args()

    if not args.sheet_id:
        sys.exit(f"no sheet id: set QUESTIONNAIRE_SUBMISSIONS_SHEET_ID, pass "
                 f"--sheet-id, or write it to {SHEET_ID_FILE}")

    unknown = sorted(set(METHODOLOGY) - set(rubrics.RUBRICS))
    if unknown:
        sys.exit(f"methodology written for questions with no rubric: {unknown}")
    uncovered = sorted(set(rubrics.RUBRICS) - set(METHODOLOGY))
    if uncovered:
        sys.exit(f"rubric with no methodology text: {uncovered}")

    rows = fetch_registry(args.sheet_id)
    check_layout(rows[0])
    write, filled, no_rubric = proposals(rows)

    for row, label in write:
        print(f"  {label} (row {row}): {text_for(label)[:96]}...")
    if filled:
        print(f"  {len(filled)} cell(s) already written, left alone: "
              f"{', '.join(label for _, label in filled)}")
    if no_rubric:
        print(f"  {len(no_rubric)} question(s) graded by hand off free text, "
              f"nothing to say: {', '.join(label for _, label in no_rubric)}")
    print(f"{len(write)} cell(s) to write")

    if args.apply:
        apply(args.sheet_id, write)
    else:
        print("dry run; pass --apply to write")


if __name__ == "__main__":
    main()
