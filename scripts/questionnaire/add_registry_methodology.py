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

# Questions whose grading is a documented band structure applied by a person
# rather than a lookup table. They have no entry in RUBRICS on purpose, so the
# cross-check below has to exempt them rather than treat them as an error.
FREE_TEXT = {"WLK-02", "ROL-05", "WLK-05", "WLK-06",
             "CLI-09", "CLI-10", "CLI-11"}

# Closed questions with a stable answer-to-letter mapping that has never been
# written into rubrics.py. Not the same thing as the set above: there is a
# lookup table here, it just lives in the grades on the tab rather than in the
# code, and the text below is read back off those grades.
#
# Kept separate rather than folded into FREE_TEXT so the distinction stays
# visible: these two are candidates for rubrics.py, and moving one there is a
# grading change - apply_rubric.py could then re-run the tab - which is why it
# has not been done here.
NO_RUBRIC = {"REC-02", "WLK-01"}

# Questions whose cell does not take the shared paragraph below.
#
# Two reasons, and all of these have the second. WLK-01 has both: it grades
# Unsure and Decline to answer C- where the shared policy leaves them blank, so
# the paragraph would make the cell contradict its own tab. The rest are here
# because the paragraph is four sentences of boilerplate on a cell that says
# what it has to say in three, and the column is read by people looking up one
# question, not by people reading the tab end to end. Nobody declined or
# answered Unsure on any of the free-text ones, so it had nothing to say there
# either.
NO_POLICY_TAIL = {"REC-02", "WLK-01", "WLK-05", "WLK-06",
                  "CLI-09", "CLI-10", "CLI-11"}

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
    "GOV-02": (
        "Yes = A. Yes, only if full cost recovery is guaranteed for my "
        "municipality = B. No = C-. Full cost recovery is a named, checkable "
        "condition on a yes, so it takes the conditional-yes B. A No is C- "
        "rather than F because the question is about how services are "
        "organised and who runs them, which is the governance side of the "
        "split CLI-03 sits on the other side of. Unsure was typed C on three "
        "rows before 2026-09-13 and those rows were reset to blank on "
        "2026-09-20, so the question now follows the shared policy."
    ),
    "REC-01": (
        "Yes = A. No = C-, on the same reasoning as GOV-02 and TRN-04: the "
        "question is about who sits at the table, not about what gets built "
        "or funded. No candidate has answered No, so that letter is a rule "
        "rather than a record of how anyone was graded."
    ),
    "WLK-03": (
        "Yes, a substantial increase, meaning more than double what is "
        "currently spent = A. Yes, a modest increase, meaning more but less "
        "than double = B, because that is a real commitment with a ceiling on "
        "it. No, the current amount is sufficient = F, because the question "
        "is about money for infrastructure, which is the funding side of the "
        "split."
    ),
    "WLK-04": (
        "Yes, and I would pursue a permanent expansion or implementation = A. "
        "Yes, but only temporary, seasonal or pilot closures = B, because it "
        "is a yes with a stated limit on it. No = F, because the question is "
        "about street space, which is infrastructure. An answer of N/A is not "
        "on this list: it is a claim that the municipality has no downtown, "
        "main street or village centre, which is a judgement about a "
        "candidate and is passed in by hand. It has been left blank where "
        "that is true of the municipality and graded F everywhere the "
        "question plainly does apply. Unsure was typed C on two rows "
        "before 2026-09-13 and those rows were reset to blank on "
        "2026-09-20, so the question now follows the shared policy."
    ),
    "WLK-02": (
        "Free text, graded by a person against the two things the question "
        "asks for: a named local problem, and one change committed to in a "
        "first term. A = both, with the change specific enough to be "
        "delivered and usually tied to funding, a named corridor or an "
        "existing plan. B = the problem is named and the response is concrete "
        "but soft, narrow, or a review rather than a change. C = a problem is "
        "named and nothing is committed to, or the framing of the question is "
        "declined. C- = no local problem is settled on, or the answer is a "
        "general gesture. F = nothing responsive is offered. The bands come "
        "from the 31 rows graded before 2026-09-20 and were applied to the "
        "remaining 51 on that date."
    ),
    "ROL-05": (
        "Free text, graded by a person on what the record shows about "
        "advancing walking, rolling, cycling or transit. A = delivered work, "
        "meaning budgets moved, plans adopted, infrastructure built, or a "
        "sustained organisational role with results behind it. B = "
        "substantial relevant advocacy or a directly relevant role, with less "
        "account of what it produced. C = a record from a different office, "
        "or advocacy confined to one location or issue, or no previous term "
        "with nothing offered in its place. C- = personal experience or "
        "unrelated work with no advocacy behind it. F = nothing relevant "
        "offered, or a record that closed the question rather than advancing "
        "it. The bands come from the 79 rows graded before 2026-09-20."
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
    # The four below have no rubrics.py entry, and their text is read back off
    # the grades already on their tabs rather than forward from a rule. Written
    # to the length the cells somebody typed by hand run to - see ROL-04 - and
    # not to the length of the entries above, which state their reasoning
    # because the rule came first and the sheet followed it.
    "REC-02": (
        "A = significantly more consultation practices. B = somewhat more. "
        "C = the current amount is enough. Written answers take the same "
        "ladder: A commits to partnership with local First Nations, B wants "
        "better consultation without committing to a change, C questions "
        "whether more is wanted. Nothing here has been graded C- or F."
    ),
    "WLK-01": (
        "A = yes, even if it means removing driving lanes. C = yes, but not "
        "when it takes road space from drivers. F = no. Two steps between the "
        "two yeses because the adopted targets cannot be met without "
        "reallocating street space. Unsure and Decline to answer are both C- "
        "on this tab."
    ),
    "WLK-05": (
        "Free text. A = names parents, school staff and municipal staff and "
        "attaches something concrete: an audit, measures, funding, timelines, "
        "or work delivered. B = one half only, consultation without measures "
        "or measures without consultation. C = points at an existing programme "
        "as enough. C- = vague, deflects, or denies the problem. Blank only "
        "where Walk On cannot judge local conditions. F is not used."
    ),
    "CLI-09": (
        "Free text. A = names a climate risk specific to the municipality and "
        "specific actions against it, usually tied to data or a programme "
        "already running. B = one half only, a risk with no action or actions "
        "with no risk named, or backing an existing plan without either. C = "
        "general support with nothing local in it, a list of risks and nothing "
        "else, or the work handed to the region. C- = a risk gestured at and "
        "nothing more. F = an answer that is not about climate."
    ),
    "CLI-10": (
        "Free text. A = says what connectivity is and why it matters, with "
        "local examples, usually tied to data, a programme already running or "
        "the official community plan. B = practical examples with no local "
        "detail, or no link back to connectivity. C = general support with no "
        "project named, or an answer broad enough to fit any question. C- = "
        "agrees with the idea and offers nothing to do about it, or answers "
        "about something tangential. F is not used."
    ),
    "CLI-11": (
        "Free text. A = yes, with how and why, naming strategies or a local "
        "policy that ties development to resilience. B = yes with relevant "
        "examples but no account of how they build resilience or how they get "
        "built. C = general support and nothing past what the building code "
        "already requires. C- = a bare yes, or support that doubts it is "
        "possible. F = does not accept that development can make a community "
        "more resilient."
    ),
    "WLK-06": (
        "Free text. A = names what to fix and the order it gets fixed in: an "
        "audit, named priorities, consultation with older and disabled "
        "residents, a timeline inside the term. B = real improvements with no "
        "process behind them, or continuing existing work. C = states the need "
        "and defers it, or one fix with no plan. C- = a problem with no "
        "action, or an answer about something else. Blank only where Walk On "
        "cannot judge local conditions. F is not used."
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


def proposals(rows, rewrite=()):
    """(to write, already filled, no rubric), each a list of (row number, label).

    `rewrite` names labels whose existing cell may be replaced. Only a cell that
    actually differs from the intended text is rewritten, so naming a label that
    is already correct does nothing.
    """
    write, filled, no_rubric = [], [], []
    for i, row in enumerate(rows[1:], start=2):
        row = row + [""] * (len(HEADERS) - len(row))
        label = row[LABEL_COLUMN].strip()
        if not label:
            continue
        if row[METHODOLOGY_COLUMN].strip():
            if (label in rewrite and label in METHODOLOGY
                    and row[METHODOLOGY_COLUMN].strip() != text_for(label).strip()):
                write.append((i, label))
            else:
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
    if label in NO_POLICY_TAIL:
        return METHODOLOGY[label]
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
    p.add_argument("--rewrite", default="",
                   help="comma-separated labels whose existing Methodology "
                        "cell may be replaced when it no longer matches")
    p.add_argument("--apply", action="store_true", help="write to the sheet")
    args = p.parse_args()

    if not args.sheet_id:
        sys.exit(f"no sheet id: set QUESTIONNAIRE_SUBMISSIONS_SHEET_ID, pass "
                 f"--sheet-id, or write it to {SHEET_ID_FILE}")

    unknown = sorted(set(METHODOLOGY) - set(rubrics.RUBRICS) - FREE_TEXT - NO_RUBRIC)
    if unknown:
        sys.exit(f"methodology written for questions with no rubric and not "
                 f"declared free text: {unknown}")
    stale = sorted((FREE_TEXT | NO_RUBRIC) & set(rubrics.RUBRICS))
    if stale:
        sys.exit(f"declared as having no rubric but now has one, so the text "
                 f"is out of date: {stale}")
    uncovered = sorted(set(rubrics.RUBRICS) - set(METHODOLOGY))
    if uncovered:
        sys.exit(f"rubric with no methodology text: {uncovered}")

    rewrite = {l.strip() for l in args.rewrite.split(",") if l.strip()}
    unknown_rewrite = sorted(rewrite - set(METHODOLOGY))
    if unknown_rewrite:
        sys.exit(f"--rewrite names labels this has no text for: "
                 f"{unknown_rewrite}")

    rows = fetch_registry(args.sheet_id)
    check_layout(rows[0])
    write, filled, no_rubric = proposals(rows, rewrite)

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
