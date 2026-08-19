#!/usr/bin/env python3
"""Regenerate _data/questions.yml and _data/scores.yml from the grading sheet.

Source is Tally's submission spreadsheet ("Submissions - 2026 Municipal
Elections", `QUESTIONNAIRE_SUBMISSIONS_SHEET_ID`), the same sheet
scripts/questionnaire/grading_tabs.py bootstraps and appsscript/Code.gs keeps
current. Four tabs matter here:

  Question Registry     One row per question the coalition grades. Published in
                        full: it is most of the list of what candidates were
                        asked, and the source for every graded question.
  Category Grades       One row per candidate, one column per graded subject,
                        each followed by a "<Subject> - Deploy to website"
                        checkbox. General and Healthcare access have a checkbox
                        and no grade column: nobody grades them, but their
                        answers are published and still need releasing.
  Grade - <Subject>     One row per candidate per question, carrying the answer,
                        the grade, the weight and the grader's rationale. These
                        are the sub-grades shown under a published subject.
  2026 Municipal ...    Tally's raw dump, and the only home of the questions
                        nobody grades: GEN-01, GEN-02, and the per-topic
                        "anything to add" boxes. They never reached the registry,
                        which lists what gets graded, so both their wording and
                        the answers to them are read from the form's own columns.

Nothing here decides what is publishable. The checkbox does. An unticked subject
is not written to _data/scores.yml at all, so neither a grade in progress nor an
unreviewed free-text answer can reach the site by accident, and unticking one
removes it on the next run.

WHAT IS DELIBERATELY NOT PUBLISHED
  - Candidate email addresses and the rest of the raw tab's contact columns. The
    tab is 236 columns wide and this script fetches four identity columns and
    the ungraded question columns by name; it never pulls the sheet wholesale.
  - The grader's name and the grading timestamp. Who graded a response is
    internal; the coalition publishes grades as the coalition's.
  - An `Owner` that looks like an email address. Question ownership is published
    as an organization ("Better Transit YYJ"), and some registry rows name an
    individual's address instead. Those are dropped, with a warning, rather than
    printed on a public page.

Reads the spreadsheet a tab at a time over HTTP, no client library and no
credentials, the same shape as scripts/sync-candidates.py. The sheet id is the
only input; it is a capability and stays out of source, in $QUESTIONNAIRE_
SUBMISSIONS_SHEET_ID locally and a repo secret in CI.

Usage:
  python3 scripts/sync-questionnaire.py --dry-run     # print, write nothing
  python3 scripts/sync-questionnaire.py               # rewrite both data files
"""

import argparse
import csv
import importlib.util
import io
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "_data")
MUNI_YML = os.path.join(DATA, "municipalities.yml")
SUBJECTS_YML = os.path.join(DATA, "subjects.yml")
CANDIDATES_YML = os.path.join(DATA, "candidates.yml")
QUESTIONS_OUT = os.path.join(DATA, "questions.yml")
SCORES_OUT = os.path.join(DATA, "scores.yml")

REGISTRY_TAB = "Question Registry"
CATEGORY_TAB = "Category Grades"
GRADE_TAB_PREFIX = "Grade - "
RAW_TAB = "2026 Municipal Elections"

# Raw-tab columns, 0-based. Mirrors COL_* in grading_tabs.py, which numbers them
# from 1. These four and the ungraded question columns are the only ones this
# script ever fetches: the tab is 236 columns wide and the rest of it is the
# candidate's contact details and their graded answers, neither of which belongs
# in a generated data file.
RAW_SUBMISSION_ID = 0
RAW_FIRST_NAME = 3
RAW_LAST_NAME = 4
RAW_MUNICIPALITY = 7

# Header prefix of a question column: "GEN-01: ...", "TRN-GEN: ...". Same
# pattern as grading_tabs.py's LABEL_RE; change both together.
LABEL_RE = re.compile(r"^([A-Z]{2,4}-(?:\d{2}|GEN)(?:-[A-Za-z]+)?):\s*(.*)$", re.S)

# One question asked once per municipality ("HFL-11-Victoria"), of which a
# candidate answers exactly one. The registry lists the collapsed form, so a
# variant has to be folded back to it before asking whether the registry knows
# the question - otherwise all fifteen variants look like questions the registry
# never listed, which is to say ungraded, which they are not. Mirrors
# grading_tabs.py's VARIANT_RE. The "-GEN" suffix is deliberately not matched:
# GEN is not two digits, so a comment box never collapses into anything.
VARIANT_RE = re.compile(r"^([A-Z]{2,4}-\d{2})-[A-Za-z]+$")

# Label prefix -> subject id. grading_tabs.py has the same map keyed to the
# registry's category names; this one is keyed to _data/subjects.yml ids,
# because ungraded questions never reach the registry and so have no category
# cell to read. General is here and absent there for exactly that reason.
PREFIX_SUBJECT = {
    "GEN": "general",
    "HFL": "housing",
    "TRN": "transit",
    "WLK": "walking",
    "ROL": "rolling-cycling",
    "CLI": "climate",
    "ART": "arts",
    "GOV": "governance",
    "REC": "reconciliation",
    "HLT": "healthcare-access",
}

# Mirrors CATEGORY_DEPLOY_SUFFIX in scripts/questionnaire/grading_tabs.py and
# appsscript/Code.gs. Change all three together.
DEPLOY_SUFFIX = " - Deploy to website"

# Registry columns, 0-based. Mirrors REGISTRY_HEADERS in grading_tabs.py.
R_LABEL, R_CATEGORY, R_QUESTION, R_TYPE, R_GRADED, R_WEIGHT, R_RAW, R_NOTES, R_OWNER = range(9)

# Grading-tab columns, 0-based. Mirrors GRADE_HEADERS in grading_tabs.py.
G_KEY, G_CANDIDATE, G_MUNICIPALITY, G_LABEL, G_QUESTION, G_ANSWER, G_OWNER, \
    G_GRADE, G_WEIGHT, G_RATIONALE = range(10)

# Category Grades identity columns, 0-based.
C_KEY, C_CANDIDATE, C_MUNICIPALITY = range(3)

# Letter grades with a .grade-* class in _sass/_components.scss. Mirrors
# VALID_GRADES in scripts/sync-candidates.py and grading_tabs.py. Anything else
# is refused rather than shipped as an unstyled badge.
VALID_GRADES = {"A", "B", "C", "C-", "F"}

# Not every question applies to every candidate: ROL-05 asks what someone did in
# a previous term, so a first-time candidate has nothing to be graded on.
# Graders write that in the grade cell, and it is published as its own badge
# rather than as a blank. A blank means "not graded yet", which is a different
# statement and the wrong one to make about a question that will never be graded.
NOT_APPLICABLE = {"N/A", "NA", "N.A.", "N/A."}
NOT_APPLICABLE_LABEL = "N/A"

# The registry's `Category` column holds the subject's display name; the site
# keys everything off the ids in _data/subjects.yml. Only the pairs that differ
# need spelling out, but all of them are listed so an unmapped category is a
# loud failure rather than a silently dropped question.
SUBJECT_FOR_CATEGORY = {
    "housing": "housing",
    "transit": "transit",
    "walking": "walking",
    "rolling & cycling": "rolling-cycling",
    "climate": "climate",
    "arts": "arts",
    "governance": "governance",
    "reconciliation": "reconciliation",
    "healthcare access": "healthcare-access",
    "general": "general",
    # What _data/subjects.yml called the General topic until the GEN-* questions
    # were on their way into the registry. Kept as an alias so a registry row
    # already typed the long way still resolves instead of failing the sync.
    "all categories / general": "general",
}

# Registry `Type` values, expanded for a reader who has never seen the sheet.
# An unrecognized type publishes no label rather than the raw token, and neither
# does `single`: "one answer" is what a reader already assumes a question wants,
# so printing it under 39 of the 55 is noise standing where information should.
TYPE_LABELS = {
    "multi": "Select all that apply",
    "pair": "Answer plus a written follow-up",
    "variant": "Asked separately for each municipality",
    "variant,multi": "Asked separately for each municipality; select all that apply",
    "multi,pair": "Select all that apply, plus a written follow-up",
    # The two shapes only ungraded questions come in. "text" gets no label for
    # the same reason "single" gets none: an open box is what a reader assumes.
    "allocation": "Split $10 million across twelve areas",
}

# Most multi-select questions say "Select all that apply" in their own wording,
# because that is how the form asks them. Repeating it underneath is a caption
# restating the sentence above it, so the label is dropped where the question has
# already said it. Matched loosely: the form is not consistent about whether it
# says "select", "check", or just "all that apply".
SELECT_ALL_CUES = ("select all", "check all", "all that apply")

# An `Owner` naming a person's inbox rather than an organization. See the module
# docstring: these are dropped, not published.
EMAILISH = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# GEN-02, the budget trade-off. Alone among the questions it reaches the raw tab
# with no "GEN-02:" prefix on any of its columns: Tally exports an allocation
# grid as one bare column per line item, so there is nothing for LABEL_RE to
# match and nothing that named the question. Both have to be supplied here.
#
# Matched on the exact twelve headers below, which must appear once each and
# next to each other. That is the header-guessing the Question Registry exists
# to avoid, so it fails the run rather than warning: a silently missed line item
# would publish an allocation that does not add up, and a silently matched wrong
# column would publish a number that is not an allocation at all. Prefixing
# these columns with "GEN-02:" in the form would retire this whole block.
GEN02_LABEL = "GEN-02"
GEN02_QUESTION = (
    "Your municipality has received $10 million in new annual funding and must "
    "spend all of it. How would you allocate it across the following areas? "
    "Your answers must total $10 million."
)
GEN02_AREAS = [
    "Housing",
    "Transit",
    "Walking Infrastructure",
    "Rolling & Cycling Infrastructure",
    "Roadway Infrastructure",
    "Policing",
    "Fire & Emergency Services",
    "Parks & Recreation",
    "Arts & Culture",
    "Climate Action & Environment",
    "Unhoused Resident Services",
    "Community-Based Clinics",
]

QUESTIONS_HEADER = """\
# Every question on the coalition candidate questionnaire.
#
# AUTO-GENERATED: do not edit by hand.
# Regenerated from the "Question Registry" tab of the candidate submission sheet
# by scripts/sync-questionnaire.py (CI: .github/workflows/sync-questionnaire.yml).
# Edit the spreadsheet, not this file; manual changes are overwritten.
#
# This is the published questionnaire: /questionnaire/ renders it in full, and
# each candidate's scorecard page renders the same list with that candidate's
# grades attached. Questions appear here whether or not they are graded, because
# the point of the page is to show what candidates were asked.
#
# Fields:
#   label     Question id as printed on the form ("TRN-01"). Stable, and the key
#             the per-candidate grades in _data/scores.yml join on.
#   subject   Topic id from _data/subjects.yml.
#   question  The question as candidates read it on the form.
#   type      Answer shape: single, multi, pair, variant, or a comma-joined
#             combination. `type_label` is the same thing spelled out for a
#             reader; absent when the combination has no wording yet.
#   graded    Whether the question carries a grade. An ungraded question is
#             published unscored: it was asked, and the answer informs the
#             coalition, but no letter is assigned to it.
#   weight    This question's share of its subject's grade, as written in the
#             registry ("20%"). Omitted where the registry leaves it blank,
#             which is most of them: weighting is set per subject by the
#             partner organization that owns it, and several have not.
#   owner     The coalition organization that submitted the question and grades
#             the answers to it. Omitted where the registry names an individual
#             rather than an organization.
#
# Order matches _data/subjects.yml, then the registry's own order within a
# subject, which is the order candidates met the questions on the form."""

SCORES_HEADER = """\
# Published questionnaire results, per candidate and per subject.
#
# AUTO-GENERATED: do not edit by hand.
# Regenerated from the "Category Grades" and "Grade - <Subject>" tabs of the
# candidate submission sheet by scripts/sync-questionnaire.py
# (CI: .github/workflows/sync-questionnaire.yml).
# Edit the spreadsheet, not this file; manual changes are overwritten.
#
# PUBLICATION IS GATED BY THE SHEET, NOT BY THIS FILE. A subject appears under a
# candidate only when its "<Subject> - Deploy to website" checkbox is ticked on
# the Category Grades tab. Grading in progress never reaches the site, and
# unticking a box removes that subject from the site on the next run. Nothing
# else in the repo decides what is publishable.
#
# EVERY CANDIDATE WITH A ROW ON THAT TAB IS LISTED HERE, including one with
# nothing ticked at all, whose `subjects` is an empty list. Having a row means
# the candidate returned the questionnaire, and the site says so: "returned it,
# still being graded" and "never replied" are different facts about a candidate
# and the scorecard draws them differently. What it does not say is anything
# about how a topic is going before it is published.
#
# _plugins/questionnaire_scores.rb joins these entries onto _data/candidates.yml
# by name and municipality at build time, which is why this file is separate:
# candidates.yml is regenerated from a different spreadsheet on its own
# schedule, and anything written into it by this script would be overwritten.
#
# Top-level:
#   graded_subjects  Topic ids the Category Grades tab has a column for, in
#                    _data/subjects.yml order. Narrower than the site's topic
#                    list: `general` and `healthcare-access` carry no graded
#                    question, so nobody is grading them and the site must not
#                    claim a returned candidate's are "still being graded".
#
# Fields, per candidate:
#   name          As written on the Category Grades tab. Matched against
#                 _data/candidates.yml case- and whitespace-insensitively; a
#                 candidate with no match there is dropped, because there is no
#                 scorecard page to show the result on.
#   municipality  Slug from _data/municipalities.yml.
#   scores        {subject id: letter}. The top-level grade per published
#                 subject, which is what the scorecard matrix renders. A subject
#                 deployed with no top-level letter typed yet is absent here but
#                 still present under `subjects` with its per-question grades.
#                 Absent entirely when nothing is published.
#   subjects      One entry per published subject, in _data/subjects.yml order,
#                 or an empty list when none is published yet:
#     id          Topic id.
#     grade       Top-level letter, or null if not yet assigned.
#     questions   One entry per graded question, in form order:
#       label     Joins to _data/questions.yml.
#       grade     Letter, or null where the question has not been graded yet.
#       weight    Share of the subject grade. Omitted where the sheet is blank.
#       rationale The grader's written reasoning. Omitted where blank.
#       answer    What the candidate submitted, as the sheet records it. Blank
#                 lines are collapsed and trailing spaces trimmed so the value
#                 survives a YAML round trip; nothing else is changed.
#
# Grader identity and grading timestamps are intentionally not published."""


# --- Helpers borrowed from sync-candidates.py --------------------------------
# Imported rather than copied so the two scripts cannot drift on how a name is
# normalized for matching or how a YAML scalar is quoted. The filename has a
# hyphen in it, so it is not importable by name.

def _load_sync_candidates():
    path = os.path.join(ROOT, "scripts", "sync-candidates.py")
    spec = importlib.util.spec_from_file_location("sync_candidates", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_SC = _load_sync_candidates()
norm = _SC.norm
tidy = _SC.tidy
scalar = _SC.scalar
load_municipalities = _SC.load_municipalities


# --- YAML emitters -----------------------------------------------------------

def clean_text(value):
    """Normalize a sheet cell into text a YAML block scalar round-trips.

    Tabs become spaces and trailing whitespace goes, because either would be
    silently rewritten by a YAML parser and the file would stop being stable
    across runs. Runs of blank lines collapse to one. Line breaks the candidate
    actually typed are kept.
    """
    text = (value or "").replace("\r\n", "\n").replace("\r", "\n").replace("\t", " ")
    lines = [line.rstrip() for line in text.split("\n")]
    out = []
    for line in lines:
        if not line and (not out or not out[-1]):
            continue
        out.append(line.lstrip() if not out else line)
    while out and not out[-1]:
        out.pop()
    return "\n".join(out)


def wrap(text, width):
    """Greedy word wrap. Never emits an empty line or one starting with a space,
    which is what keeps a folded block scalar equivalent to the single line."""
    lines, current = [], ""
    for word in text.split():
        candidate = f"{current} {word}" if current else word
        if current and len(candidate) > width:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines


def text_value(value, indent, width=78):
    """A YAML scalar for free text, choosing the most readable safe form.

    Multi-line text uses a literal block, so the candidate's own line breaks
    survive. Long single-line text uses a folded block wrapped on word
    boundaries, which reads as a paragraph and rejoins to exactly the original.
    Anything short falls through to the ordinary quoting rules.
    """
    text = clean_text(value)
    pad = " " * indent
    if "\n" in text:
        return "|-\n" + "\n".join((pad + line) if line else "" for line in text.split("\n"))
    if len(text) + indent > width:
        return ">-\n" + "\n".join(pad + line for line in wrap(text, width - indent))
    return scalar(text)


def emit(lines, indent, key, value):
    """Append `key: value` for a plain scalar, skipping None."""
    if value is None:
        return
    lines.append(f"{' ' * indent}{key}: {scalar(value)}")


# --- Sheet readers -----------------------------------------------------------
# One tab at a time over HTTP, no client library and no credentials, the same
# shape as scripts/sync-candidates.py. The sheet id is the only input.

GVIZ = "https://docs.google.com/spreadsheets/d/{id}/gviz/tq"

# First header cell of each tab, used to check that the response is the tab that
# was asked for. See fetch_tab() on why that check is not optional.
TAB_FIRST_HEADER = {
    REGISTRY_TAB: "Label",
    CATEGORY_TAB: "Key",
    RAW_TAB: "Submission ID",
}


def a1(col_index):
    """0-based column index to its A1 letters. Mirrors grading_tabs.py's a1()."""
    letters = ""
    n = col_index + 1
    while n:
        n, rem = divmod(n - 1, 26)
        letters = chr(65 + rem) + letters
    return letters


def fetch_tab(sheet_id, title, expect=None, select=None, header_only=False, timeout=60):
    """One tab as a list of rows, or None if it is not there.

    `select` is a gviz column list ("A, D, E") limiting what comes back, so a
    236-column tab can be read four columns wide. `header_only` limits it the
    other way, to the header row and no data, for when all that is wanted is
    what the columns are called.

    `expect` is the tab's first header cell, and checking it is the whole
    difference between this being safe and not. Asking gviz for a tab that does
    not exist does not fail: it answers 200 with the spreadsheet's *first* sheet
    instead, which here is the raw dump of every candidate's contact details and
    answers. A renamed tab would therefore feed 236 columns of the wrong data
    into a parser expecting nine, rather than reporting anything wrong. Any
    response whose first header cell is not the one asked for is treated as a
    missing tab.
    """
    params = {"tqx": "out:csv", "sheet": title}
    query = ("select " + select) if select else ""
    if header_only:
        # Returns the header row and no data rows at all. The point on the raw
        # tab, where "no data rows" means no email addresses.
        query = (query + " limit 0").strip()
    if query:
        params["tq"] = query
    url = GVIZ.format(id=sheet_id) + "?" + urllib.parse.urlencode(params)

    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        if e.code in (401, 403, 404):
            return None
        raise

    rows = list(csv.reader(io.StringIO(body)))
    if not rows:
        return None
    if expect and tidy(rows[0][0] if rows[0] else "") != expect:
        return None
    return rows


def tab_values(sheet_id, title, expect=None):
    return fetch_tab(sheet_id, title, expect=expect)


# --- Ungraded questions, which live only on the raw tab ---------------------
# The Question Registry lists what gets graded, so the free-text questions never
# reached it: GEN-01, the per-topic "anything to add" boxes, and GEN-02. They
# were still asked, and the answers are still worth publishing, so they are read
# from the form's own columns instead. HLT-01 is the exception in the other
# direction: it does have a registry row, hand-marked Graded=No, and is
# published from there like any other registry question.

def ungraded_questions(header, graded_labels, subject_order, warnings, errors):
    """Ungraded questions on the raw tab, in form order.

    Returns [{label, subject, question, columns, kind, areas}] where `columns`
    are 0-based indices into a raw row and `kind` is "text" or "allocation".

    Keyed on the *graded* labels, not on every label the registry lists. HLT-01
    is the reason: it has a registry row, hand-marked Graded=No, so the Apps
    Script never fanned it out to a grading tab and its answer exists nowhere but
    here. Skipping every registry label would publish the question and silently
    drop the answer to it. build_questions() still takes HLT-01's wording from
    the registry, which is the hand-editable copy; only the answer comes from
    these columns.
    """
    found = []
    for i, cell in enumerate(header):
        m = LABEL_RE.match((cell or "").strip())
        if not m:
            continue
        variant = VARIANT_RE.match(m.group(1))
        label = variant.group(1) if variant else m.group(1)
        # A graded question's answer comes off its Grade tab, where it sits
        # beside the grade it earned. Everything else is read here.
        if label in graded_labels:
            continue

        subject = PREFIX_SUBJECT.get(label.split("-")[0])
        if not subject:
            errors.append(
                f"{RAW_TAB} column {i + 1} ({label}): prefix maps to no subject. "
                f"Add it to PREFIX_SUBJECT."
            )
            continue
        if subject not in subject_order:
            errors.append(
                f"{RAW_TAB} column {i + 1} ({label}): subject {subject!r} is not in "
                f"_data/subjects.yml."
            )
            continue

        # A question already seen is a multi-select's option column: same label,
        # further right. Ungraded questions are all free text, so this should not
        # happen, and if the form ever grows one the extra columns are ignored
        # rather than published as separate questions.
        if any(q["label"] == label for q in found):
            continue

        found.append({
            "label": label,
            "subject": subject,
            "question": clean_text(m.group(2)),
            "columns": [i],
            "kind": "text",
            "areas": [],
        })

    allocation = allocation_question(header, errors)
    if allocation:
        found.append(allocation)
        found.sort(key=lambda q: q["columns"][0])
    return found


def allocation_question(header, errors):
    """GEN-02's block, located by its twelve bare line-item headers."""
    tidied = [tidy(h) for h in header]
    columns = []
    for area in GEN02_AREAS:
        hits = [i for i, h in enumerate(tidied) if h == area]
        if len(hits) != 1:
            errors.append(
                f"{RAW_TAB}: expected exactly one column headed {area!r} for "
                f"{GEN02_LABEL}, found {len(hits)}. Fix GEN02_AREAS, or prefix the "
                f"allocation columns with '{GEN02_LABEL}:' so they need no guessing."
            )
            return None
        columns.append(hits[0])

    if columns != list(range(columns[0], columns[0] + len(columns))):
        errors.append(
            f"{RAW_TAB}: the {GEN02_LABEL} line-item columns are not contiguous "
            f"(found {columns}). Something else now sits between them, so matching "
            f"them by header name is no longer safe."
        )
        return None

    return {
        "label": GEN02_LABEL,
        "subject": PREFIX_SUBJECT[GEN02_LABEL.split("-")[0]],
        "question": GEN02_QUESTION,
        "columns": columns,
        "kind": "allocation",
        "areas": list(GEN02_AREAS),
    }


def raw_answers(sheet_id, questions, warnings):
    """{submission id: {label: answer}} for the ungraded questions.

    Asks for the identity columns and the question columns and nothing else, via
    a gviz column select. The raw tab is 236 columns wide and holds every
    candidate's email address; pulling the whole thing and picking through it in
    memory would make the module docstring's claim that this script never reads
    those columns untrue in the only way that matters.
    """
    wanted = [RAW_SUBMISSION_ID, RAW_FIRST_NAME, RAW_LAST_NAME, RAW_MUNICIPALITY]
    for q in questions:
        wanted.extend(q["columns"])
    wanted = sorted(set(wanted))

    rows = fetch_tab(sheet_id, RAW_TAB, expect=TAB_FIRST_HEADER[RAW_TAB],
                     select=", ".join(a1(c) for c in wanted))
    if rows is None:
        warnings.append(f"{RAW_TAB}: tab missing, no ungraded answers published")
        return {}

    # gviz returns the selected columns in the order they were asked for, so the
    # sheet's own indices have to be mapped onto positions in the response.
    at = {c: i for i, c in enumerate(wanted)}
    columns = {c: [(row[at[c]] if at[c] < len(row) else "") for row in rows[1:]]
               for c in wanted}
    depth = len(rows) - 1

    answers = {}
    for r in range(depth):
        key = tidy(columns[RAW_SUBMISSION_ID][r])
        if not key:
            continue
        row = {}
        for q in questions:
            if q["kind"] == "allocation":
                amounts = [(area, tidy(columns[c][r]))
                           for area, c in zip(q["areas"], q["columns"])]
                if any(amount for _, amount in amounts):
                    row[q["label"]] = amounts
            else:
                value = clean_text(columns[q["columns"][0]][r])
                if value:
                    row[q["label"]] = value
        if row:
            answers[key] = row
    return answers


def load_subject_order(path):
    """Subject ids in the order _data/subjects.yml lists them."""
    ids = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            stripped = line.strip()
            if stripped.startswith("- id:"):
                ids.append(stripped.split(":", 1)[1].strip().strip("\"'"))
    return ids


def load_candidate_index(path):
    """{(normalized name, municipality slug): name as candidates.yml spells it}.

    Read from the generated file rather than the tracking sheet: the site can
    only show a result on a page that exists, and that file is what decides
    which pages exist.
    """
    index = {}
    name = None
    with open(path, encoding="utf-8") as f:
        for line in f:
            stripped = line.strip()
            if stripped.startswith("- name:"):
                name = stripped.split(":", 1)[1].strip().strip("\"'")
            elif stripped.startswith("municipality:") and name is not None:
                slug = stripped.split(":", 1)[1].strip().strip("\"'")
                index[(norm(name), slug)] = name
                name = None
    return index


# --- Questions ---------------------------------------------------------------

def build_questions(registry, extra, subject_order, warnings, errors):
    """Every published question, in subjects.yml order.

    Registry rows first within a subject, then the ungraded ones the registry
    never listed, which is the order a candidate met them on the form: the
    per-topic "anything to add" box always sits at the end of its topic's block,
    and General's two questions precede its box.
    """
    rows = registry[1:] if registry else []
    by_subject = {}
    for i, row in enumerate(rows, start=2):
        cell = lambda idx: tidy(row[idx]) if idx < len(row) else ""
        label = cell(R_LABEL)
        if not label:
            continue

        category = cell(R_CATEGORY)
        subject = SUBJECT_FOR_CATEGORY.get(norm(category))
        if not subject:
            errors.append(
                f"{REGISTRY_TAB} row {i} ({label}): category {category!r} maps to no "
                f"subject. Add it to SUBJECT_FOR_CATEGORY, or fix the sheet."
            )
            continue
        if subject not in subject_order:
            errors.append(
                f"{REGISTRY_TAB} row {i} ({label}): subject {subject!r} is not in "
                f"_data/subjects.yml."
            )
            continue

        question = clean_text(row[R_QUESTION] if R_QUESTION < len(row) else "")
        if not question:
            warnings.append(f"{REGISTRY_TAB} row {i} ({label}): no question text, skipped")
            continue

        kind = cell(R_TYPE)
        owner = cell(R_OWNER)
        if owner and EMAILISH.match(owner):
            warnings.append(
                f"{REGISTRY_TAB} row {i} ({label}): owner {owner!r} is an email "
                f"address, not published. Put the organization's name there."
            )
            owner = ""

        type_label = TYPE_LABELS.get(kind, "")
        if type_label.startswith("Select all") and \
                any(cue in question.lower() for cue in SELECT_ALL_CUES):
            type_label = ""

        by_subject.setdefault(subject, []).append({
            "label": label,
            "subject": subject,
            "question": question,
            "type": kind,
            "type_label": type_label,
            "graded": norm(cell(R_GRADED)) in {"yes", "true", "y"},
            "weight": cell(R_WEIGHT),
            "owner": owner,
        })

    # The ungraded ones carry no weight and no owner: nobody grades them, so
    # there is no share of a grade to state and no organization to name as the
    # grader. `type` says what shape the answer takes, which is the one thing
    # about them a reader still benefits from knowing.
    listed = {q["label"] for qs in by_subject.values() for q in qs}
    for q in extra:
        # HLT-01 arrives from both sources: the registry names and describes it,
        # the raw tab holds the answer. The registry copy wins, because it is
        # the one a human can correct.
        if q["label"] in listed:
            continue
        by_subject.setdefault(q["subject"], []).append({
            "label": q["label"],
            "subject": q["subject"],
            "question": q["question"],
            "type": q["kind"],
            "type_label": TYPE_LABELS.get(q["kind"], ""),
            "graded": False,
            "weight": "",
            "owner": "",
            "areas": q["areas"],
        })

    return [q for sid in subject_order for q in by_subject.get(sid, [])]


def render_questions(items, subject_order):
    graded = sum(1 for q in items if q["graded"])
    parts = [
        QUESTIONS_HEADER,
        "",
        f"count: {len(items)}",
        f"graded_count: {graded}",
        # A page needs to know whether it has anything to show before it decides
        # what to say; counting `items` in Liquid on every page is the same test
        # spelled less clearly.
        f"status: {'published' if items else 'drafting'}",
        "items:",
    ]
    if not items:
        parts[-1] = "items: []"
        return "\n".join(parts) + "\n"

    current = None
    for q in items:
        if q["subject"] != current:
            current = q["subject"]
            parts.append(f"  # --- {current} ---")
        parts.append(f"  - label: {scalar(q['label'])}")
        parts.append(f"    subject: {q['subject']}")
        parts.append(f"    question: {text_value(q['question'], 6)}")
        parts.append(f"    type: {scalar(q['type'])}" if q["type"] else "    type: null")
        if q["type_label"]:
            parts.append(f"    type_label: {scalar(q['type_label'])}")
        parts.append(f"    graded: {'true' if q['graded'] else 'false'}")
        if q["weight"]:
            parts.append(f"    weight: {scalar(q['weight'])}")
        if q["owner"]:
            parts.append(f"    owner: {scalar(q['owner'])}")
        # GEN-02's line items, so /questionnaire/ can show what the allocation is
        # split across without a candidate having answered it.
        if q.get("areas"):
            parts.append("    areas:")
            parts.extend(f"      - {scalar(area)}" for area in q["areas"])
    return "\n".join(parts) + "\n"


# --- Scores ------------------------------------------------------------------

def deploy_gates(header):
    """[(subject display name, grade column or None, deploy column)].

    Keyed off the deploy columns rather than off (grade, deploy) pairs, because
    the two ungraded subjects have a gate and no grade column beside it: nobody
    grades General or Healthcare access, so there is nothing to roll up, but
    their answers are published verbatim and still need releasing. Code.gs tells
    the two kinds of header apart by the same suffix.
    """
    index = {}
    for i, cell in enumerate(header):
        name = tidy(cell)
        if name and name not in index:
            index[name] = i

    gates = []
    for i, cell in enumerate(header):
        name = tidy(cell)
        if not name.endswith(DEPLOY_SUFFIX):
            continue
        subject = name[: -len(DEPLOY_SUFFIX)]
        if subject:
            gates.append((subject, index.get(subject), i))
    return gates


def is_ticked(value):
    return norm(value) in {"true", "yes", "checked", "1"}


# How Code.gs writes a multi-select answer: the written parts on their own
# lines, then every ticked option on one "Selected: " line joined by "; ". Both
# the webhook and the timer build it this way, so it is the shape every answer
# cell arrives in and the only thing that has to be agreed on to take it apart.
SELECTED_PREFIX = "Selected: "
SELECTED_JOIN = "; "


def split_selections(answer):
    """(prose, [ticked options]) for one answer cell.

    Run together on one line, a dozen ticked options are a paragraph of
    semicolons that nobody reads to the end; as a list they are scannable. The
    split happens here rather than in the template because it is parsing, and a
    template that parses is a template that fails silently.

    Split on the exact separator Code.gs joins with, not on a bare semicolon: an
    option is a full sentence and several end in one. An option containing "; "
    internally would still split wrongly, but none does, and the alternative -
    matching against the registry's own option lists - is a great deal of
    machinery for a case that has not happened.
    """
    prose, selected = [], []
    for line in (answer or "").split("\n"):
        if line.startswith(SELECTED_PREFIX):
            selected.extend(
                part.strip() for part in line[len(SELECTED_PREFIX):].split(SELECTED_JOIN)
                if part.strip()
            )
        else:
            prose.append(line)
    return "\n".join(prose).strip(), selected


def grade_or_none(value, where, warnings):
    letter = tidy(value).upper().replace("−", "-")
    if not letter:
        return None
    if letter in NOT_APPLICABLE:
        return NOT_APPLICABLE_LABEL
    if letter not in VALID_GRADES:
        warnings.append(
            f"{where}: grade {letter!r} has no style on the site, not published "
            f"(expected one of {', '.join(sorted(VALID_GRADES))} or "
            f"{NOT_APPLICABLE_LABEL})"
        )
        return None
    return letter


def ticked_subjects(category):
    """Subject display names at least one candidate has released for publication.

    Used to decide which `Grade - <Subject>` tabs to read at all. Reading the
    ones nobody has published is a wasted API call per tab against a quota this
    job shares with everything else touching the spreadsheet, and early in a
    cycle that is every tab.
    """
    gates = deploy_gates(category[0])
    names = set()
    for row in category[1:]:
        for name, grade_col, gate in gates:
            # An ungraded subject has no Grade tab worth opening: its answers
            # come off the raw tab, not out of a per-question grading sheet.
            if grade_col is None:
                continue
            if gate < len(row) and is_ticked(row[gate]):
                names.add(name)
    # Sorted, so the warnings a run emits come out in the same order every time
    # and two runs over the same sheet produce comparable logs.
    return sorted(names)


def load_grade_rows(sheet_id, subject_names, warnings):
    """{(submission key, subject display name): [row, ...]} in sheet order."""
    rows = {}
    for name in subject_names:
        values = tab_values(sheet_id, GRADE_TAB_PREFIX + name, expect="Key")
        if values is None:
            warnings.append(f"{GRADE_TAB_PREFIX}{name}: tab missing, no sub-grades published")
            continue
        for row in values[1:]:
            key = tidy(row[G_KEY]) if G_KEY < len(row) else ""
            if not key:
                continue
            rows.setdefault((key.split("|", 1)[0], name), []).append(row)
    return rows


def allocation_lines(pairs, where, warnings):
    """[(area, amount, display, share)] for one candidate's GEN-02 answer.

    The share and the thousands-separated figure are computed here rather than
    in the template because Liquid has neither integer division that rounds the
    way a percentage should nor a delimiter filter, and a bar chart whose widths
    are worked out in a template is a bar chart nobody can test.
    """
    amounts = []
    for area, raw in pairs:
        cleaned = raw.replace("$", "").replace(",", "").strip()
        if not cleaned:
            continue
        try:
            amounts.append((area, int(float(cleaned))))
        except ValueError:
            warnings.append(
                f"{where}: {area!r} is {raw!r}, which is not a number, so the "
                f"allocation is not published"
            )
            return []

    total = sum(amount for _, amount in amounts)
    return [
        (area, amount, f"${amount:,}", round(amount * 100 / total) if total else 0)
        for area, amount in amounts
    ]


def unscored_answers(answers, subject_id, ungraded, candidate, warnings):
    """This candidate's ungraded answers for one subject, in form order."""
    out = []
    for q in ungraded:
        if q["subject"] != subject_id or q["label"] not in answers:
            continue
        value = answers[q["label"]]
        if q["kind"] == "allocation":
            lines = allocation_lines(value, f"{RAW_TAB} ({candidate}, {q['label']})", warnings)
            if lines:
                out.append({"label": q["label"], "answer": "", "allocation": lines})
        else:
            prose, selected = split_selections(value)
            out.append({"label": q["label"], "answer": prose,
                        "selected": selected, "allocation": []})
    return out


def build_scores(category, grade_rows, answers, ungraded, subject_order,
                 muni_lookup, candidates, question_labels, warnings, errors):
    header = category[0]
    gates = deploy_gates(header)
    if not gates:
        errors.append(f"{CATEGORY_TAB}: no '<Subject>{DEPLOY_SUFFIX}' columns found.")
        return [], []

    subject_ids = {}
    for name, _, _ in gates:
        sid = SUBJECT_FOR_CATEGORY.get(norm(name))
        if not sid:
            errors.append(f"{CATEGORY_TAB}: column {name!r} maps to no subject id.")
        elif sid not in subject_order:
            errors.append(f"{CATEGORY_TAB}: subject {sid!r} is not in _data/subjects.yml.")
        else:
            subject_ids[name] = sid

    records = []
    seen = {}
    for i, row in enumerate(category[1:], start=2):
        cell = lambda idx: tidy(row[idx]) if idx < len(row) else ""
        key, name, muni_name = cell(C_KEY), cell(C_CANDIDATE), cell(C_MUNICIPALITY)
        if not name:
            continue

        muni_slug = muni_lookup.get(norm(muni_name))
        if not muni_slug:
            warnings.append(
                f"{CATEGORY_TAB} row {i} ({name}): municipality {muni_name!r} matches "
                f"nothing in _data/municipalities.yml, candidate skipped"
            )
            continue
        if (norm(name), muni_slug) not in candidates:
            warnings.append(
                f"{CATEGORY_TAB} row {i}: {name} ({muni_slug}) is not a confirmed "
                f"candidate in _data/candidates.yml, so has no page to publish on"
            )
            continue

        published = []
        for subject_name, grade_col, gate_col in gates:
            if subject_name not in subject_ids:
                continue
            if not is_ticked(row[gate_col] if gate_col < len(row) else ""):
                continue
            subject_id = subject_ids[subject_name]
            where = f"{CATEGORY_TAB} row {i} ({name}, {subject_name})"
            grade = None
            if grade_col is not None:
                grade = grade_or_none(row[grade_col] if grade_col < len(row) else "",
                                      where, warnings)
            published.append({
                "id": subject_id,
                "grade": grade,
                "questions": subject_questions(
                    grade_rows.get((key, subject_name), []), name, subject_name,
                    question_labels, warnings),
                # The ungraded answers for this subject, released by the same
                # checkbox as its grades. A per-topic "anything to add" box only
                # goes public once its topic does, so nothing a candidate wrote
                # about transit appears before the transit section is signed off.
                "unscored": unscored_answers(
                    answers.get(key, {}), subject_id, ungraded, name, warnings),
            })

        # Deliberately kept even with nothing published. Having a row on this tab
        # means the candidate returned the questionnaire, and that on its own is
        # something the site should say: "returned it, still being graded" and
        # "never replied" are very different facts about a candidate, and until
        # now the site drew both as the same dash.
        published.sort(key=lambda s: subject_order.index(s["id"]))
        record = {
            "name": candidates[(norm(name), muni_slug)],
            "municipality": muni_slug,
            "subjects": published,
        }

        # One scorecard page per candidate, so a second row for the same person
        # has nowhere of its own to go. This happens when someone submits the
        # questionnaire twice: Code.gs keys grading rows by submission id and
        # gives the second submission its own Category Grades row, which is
        # right for grading and ambiguous for publishing.
        #
        # Resolvable in every case but one. Neither row publishing anything is
        # the ordinary case and says the same thing twice; one row publishing
        # and the other not is unambiguous, and the publishing row wins. Two
        # rows both publishing is a real conflict, and it is refused rather than
        # guessed at: whichever row lost would be silently unpublished while the
        # sheet went on showing it as published.
        identity = (norm(name), muni_slug)
        if identity not in seen:
            seen[identity] = (len(records), i)
            records.append(record)
            continue

        where, previous_row = seen[identity]
        if records[where]["subjects"] and published:
            errors.append(
                f"{CATEGORY_TAB} rows {previous_row} and {i}: both publish subjects for "
                f"{name} ({muni_slug}), and only one can be shown. Clear the deploy "
                f"checkboxes on the superseded row, or delete it."
            )
        elif published:
            records[where] = record
            seen[identity] = (where, i)

    records.sort(key=lambda r: (r["municipality"], norm(r["name"])))
    return records


def subject_questions(rows, candidate, subject_name, question_labels, warnings):
    out = []
    for row in rows:
        cell = lambda idx: tidy(row[idx]) if idx < len(row) else ""
        label = cell(G_LABEL)
        if not label:
            continue
        if label not in question_labels:
            warnings.append(
                f"{GRADE_TAB_PREFIX}{subject_name}: {candidate}'s row for {label} has "
                f"no {REGISTRY_TAB} entry, so the site has no question text for it"
            )
            continue
        where = f"{GRADE_TAB_PREFIX}{subject_name} ({candidate}, {label})"
        prose, selected = split_selections(clean_text(row[G_ANSWER] if G_ANSWER < len(row) else ""))
        out.append({
            "label": label,
            "grade": grade_or_none(row[G_GRADE] if G_GRADE < len(row) else "", where, warnings),
            "weight": cell(G_WEIGHT),
            "rationale": clean_text(row[G_RATIONALE] if G_RATIONALE < len(row) else ""),
            "answer": prose,
            "selected": selected,
        })
    return out


def render_scores(graded_subjects, records):
    # Deliberately carries no generation date. This file is rewritten daily and
    # committed only when it differs; a timestamp would differ every day and
    # turn every run into a commit and a rebuild that changed nothing.
    parts = [SCORES_HEADER, ""]
    if graded_subjects:
        parts.append("graded_subjects:")
        parts.extend(f"  - {sid}" for sid in graded_subjects)
    else:
        parts.append("graded_subjects: []")
    parts.append("")

    if not records:
        parts.append("candidates: []")
        return "\n".join(parts) + "\n"

    parts.append("candidates:")
    for record in records:
        parts.append(f"  - name: {scalar(record['name'])}")
        parts.append(f"    municipality: {record['municipality']}")

        # The flat map first, because it is what the scorecard matrix reads and
        # what `c.scores[subject.id]` has always meant. `subjects` below carries
        # the same letters again, in the shape the detail sections iterate.
        graded = [s for s in record["subjects"] if s["grade"]]
        if graded:
            parts.append("    scores:")
            for subject in graded:
                parts.append(f"      {subject['id']}: {subject['grade']}")

        if not record["subjects"]:
            # Returned the questionnaire, nothing released yet. The entry exists
            # to say the first half of that, and an empty list says the second.
            parts.append("    subjects: []")
            continue

        parts.append("    subjects:")
        for subject in record["subjects"]:
            parts.append(f"      - id: {subject['id']}")
            parts.append(f"        grade: {subject['grade'] or 'null'}")

            if subject["questions"]:
                parts.append("        questions:")
                for q in subject["questions"]:
                    parts.append(f"          - label: {scalar(q['label'])}")
                    parts.append(f"            grade: {q['grade'] or 'null'}")
                    if q["weight"]:
                        parts.append(f"            weight: {scalar(q['weight'])}")
                    if q["rationale"]:
                        parts.append(f"            rationale: {text_value(q['rationale'], 14)}")
                    if q["answer"]:
                        parts.append(f"            answer: {text_value(q['answer'], 14)}")
                    if q["selected"]:
                        parts.append("            selected:")
                        for option in q["selected"]:
                            parts.append(f"              - {text_value(option, 16)}")
            else:
                parts.append("        questions: []")

            # Answers to the questions nobody grades. Kept in their own list
            # rather than mixed into `questions` with a null grade: a reader
            # meeting a run of blank grade chips reads them as ungraded-yet, and
            # these will never carry one. The site labels the block as such.
            if not subject["unscored"]:
                continue
            parts.append("        unscored:")
            for q in subject["unscored"]:
                parts.append(f"          - label: {scalar(q['label'])}")
                if q["allocation"]:
                    parts.append("            allocation:")
                    for area, amount, display, share in q["allocation"]:
                        parts.append(f"              - area: {scalar(area)}")
                        parts.append(f"                amount: {amount}")
                        parts.append(f"                display: {scalar(display)}")
                        parts.append(f"                share: {share}")
                else:
                    if q["answer"]:
                        parts.append(f"            answer: {text_value(q['answer'], 14)}")
                    if q["selected"]:
                        parts.append("            selected:")
                        for option in q["selected"]:
                            parts.append(f"              - {text_value(option, 16)}")
    return "\n".join(parts) + "\n"


# --- Main --------------------------------------------------------------------

def write_if_changed(path, content, dry_run, label):
    existing = None
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            existing = f.read()
    if existing == content:
        print(f"{label}: unchanged")
        return False
    if dry_run:
        print(f"{label}: would rewrite ({len(content.splitlines())} lines)")
        return True
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"{label}: written ({len(content.splitlines())} lines)")
    return True


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--sheet-id", default=os.environ.get("QUESTIONNAIRE_SUBMISSIONS_SHEET_ID", ""),
                        help="Submission spreadsheet id (default: $QUESTIONNAIRE_SUBMISSIONS_SHEET_ID)")
    parser.add_argument("--dry-run", action="store_true", help="Report what would change, write nothing")
    args = parser.parse_args(argv)

    if not args.sheet_id:
        print("error: set QUESTIONNAIRE_SUBMISSIONS_SHEET_ID or pass --sheet-id", file=sys.stderr)
        return 2

    warnings, errors = [], []
    subject_order = load_subject_order(SUBJECTS_YML)
    _, muni_lookup = load_municipalities(MUNI_YML)
    candidates = load_candidate_index(CANDIDATES_YML)

    registry = tab_values(args.sheet_id, REGISTRY_TAB,
                          expect=TAB_FIRST_HEADER[REGISTRY_TAB])
    if registry is None:
        print(f"error: no '{REGISTRY_TAB}' tab in that spreadsheet", file=sys.stderr)
        return 1
    graded_labels = {tidy(r[R_LABEL]) for r in registry[1:]
                     if r and tidy(r[R_LABEL]) and norm(r[R_GRADED] if R_GRADED < len(r) else "")
                     in {"yes", "true", "y"}}

    # The header carries the wording of every ungraded question, and locating
    # them needs every column's name, so this one read is necessarily the full
    # width. raw_answers() below then asks for only the columns it needs.
    raw_header = fetch_tab(args.sheet_id, RAW_TAB, expect=TAB_FIRST_HEADER[RAW_TAB],
                           header_only=True)
    if raw_header is None:
        warnings.append(f"{RAW_TAB}: tab missing, no ungraded questions published")
        ungraded = []
    else:
        ungraded = ungraded_questions(
            raw_header[0], graded_labels, subject_order, warnings, errors)

    questions = build_questions(registry, ungraded, subject_order, warnings, errors)
    question_labels = {q["label"] for q in questions}

    # Which subjects carry a grade at all, read off the questions rather than off
    # the Category Grades columns. Those columns now include gates for General
    # and Healthcare access, which have a publication gate and no grade; asking
    # the questions instead keeps "being graded" off the two topics nobody
    # grades, whatever columns the sheet happens to have grown.
    graded_subjects = [sid for sid in subject_order
                       if any(q["graded"] and q["subject"] == sid for q in questions)]

    category = tab_values(args.sheet_id, CATEGORY_TAB,
                          expect=TAB_FIRST_HEADER[CATEGORY_TAB])
    if category is None:
        warnings.append(f"{CATEGORY_TAB}: tab missing, no candidate results published")
        records = []
    else:
        answers = raw_answers(args.sheet_id, ungraded, warnings) if ungraded else {}
        records = build_scores(
            category, load_grade_rows(args.sheet_id, ticked_subjects(category), warnings),
            answers, ungraded, subject_order, muni_lookup, candidates,
            question_labels, warnings, errors)

    for warning in warnings:
        print(f"warning: {warning}", file=sys.stderr)
    if errors:
        for error in errors:
            print(f"error: {error}", file=sys.stderr)
        print(f"\n{len(errors)} error(s); neither data file was written.", file=sys.stderr)
        return 1

    published = sum(len(r["subjects"]) for r in records)
    awaiting = sum(1 for r in records if not r["subjects"])
    print(f"{len(questions)} question(s) across {len(set(q['subject'] for q in questions))} subject(s); "
          f"{len(records)} candidate(s) returned the questionnaire; "
          f"{published} published subject grade(s), {awaiting} candidate(s) with none yet")

    write_if_changed(QUESTIONS_OUT, render_questions(questions, subject_order),
                     args.dry_run, "_data/questions.yml")
    write_if_changed(SCORES_OUT, render_scores(graded_subjects, records),
                     args.dry_run, "_data/scores.yml")
    return 0


if __name__ == "__main__":
    sys.exit(main())
