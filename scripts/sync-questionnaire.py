#!/usr/bin/env python3
"""Regenerate _data/questions.yml and _data/scores.yml from the grading sheet.

Source is Tally's submission spreadsheet ("Submissions - 2026 Municipal
Elections", `QUESTIONNAIRE_SUBMISSIONS_SHEET_ID`), the same sheet
scripts/questionnaire/grading_tabs.py bootstraps and appsscript/Code.gs keeps
current. Four tabs matter here:

  Question Registry     One row per question the coalition grades. Published in
                        full: it is most of the list of what candidates were
                        asked, and the source for every graded question.
  Category Grades       One row per candidate, one column per graded subject.
                        The "<Subject> - Deploy to website" checkbox that used to
                        follow each of them is gone from the sheet; PUBLISH_GRADES
                        below replaces it, releasing every subject at once rather
                        than one partner org's work at a time.
  Grade - <Subject>     One row per candidate per question, carrying the answer,
                        the grade, the weight and the grader's rationale. These
                        are the sub-grades shown under a published subject.
  2026 Municipal ...    Tally's raw dump, and the only home of the questions
                        nobody grades: GEN-01, GEN-02, and the per-topic
                        "anything to add" boxes. They never reached the registry,
                        which lists what gets graded, so both their wording and
                        the answers to them are read from the form's own columns.

PUBLISH_GRADES decides what is publishable, and it is off. Nothing graded and no
free-text answer is written to _data/scores.yml at all, so neither a grade in
progress nor an unreviewed answer can reach the site. Every candidate with a row
is still written out with an empty `subjects`, which is the site's "returned it,
still being graded". Flipping the switch on the coalition's release date
publishes every subject at once; flipping it back removes them on the next run.

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
import json
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
#
# REC maps to governance, not to a topic of its own. The two reconciliation
# questions were folded into Governance and their codes were deliberately left
# alone, so REC-GEN's "anything to add" box has to follow them: it never reaches
# the registry, so this map is the only thing that decides where it is published.
# The graded pair get their subject from the registry's Category column instead,
# which has to say Governance for the same reason.
PREFIX_SUBJECT = {
    "GEN": "general",
    "HFL": "housing",
    "TRN": "transit",
    "WLK": "walking",
    "ROL": "rolling-cycling",
    "CLI": "climate",
    "ART": "arts",
    "GOV": "governance",
    "REC": "governance",
    "HLT": "healthcare-access",
}

# The publication switch, in place of the per-subject "<Subject> - Deploy to
# website" checkboxes the Category Grades tab used to carry. While this is False
# no candidate result is published; it is flipped to True in one commit on the
# release date. PUBLISH_GRADES=1 in the environment, or --publish, overrides it
# for a single run without committing anything.
PUBLISH_GRADES = False

# Those checkbox columns are gone from the sheet, but grading_tabs.py and
# appsscript/Code.gs still know the suffix and would write them again if a tab
# were bootstrapped from scratch. A column whose header ends in it is ignored
# rather than read as a subject, so the sync is the same either way.
DEPLOY_SUFFIX = " - Deploy to website"

# Registry columns, 0-based. Mirrors REGISTRY_HEADERS in grading_tabs.py.
R_LABEL, R_CATEGORY, R_QUESTION, R_TYPE, R_GRADED, R_WEIGHT, R_RAW, R_NOTES, R_OWNER = range(9)

# Grading-tab columns, 0-based. Mirrors GRADE_HEADERS in grading_tabs.py.
G_KEY, G_CANDIDATE, G_MUNICIPALITY, G_LABEL, G_QUESTION, G_ANSWER, G_OWNER, \
    G_GRADE, G_WEIGHT, G_RATIONALE = range(10)

# Subjects whose graders score each question rather than grading it, and how.
# Two partner orgs do, and not the same way. Both tabs are the same thirteen
# columns as every other one; what differs is what the two cells a grader uses
# hold, and how Category Grades turns them into a letter.
#
# housing - Homes for Living score each question out of a stated number of
# points, ask different questions in different municipalities, and hand back one
# cumulative grade. G_GRADE holds the score and G_WEIGHT what it is out of, and
# the letter is the share of the available points banded at 85/70/60/50. A
# housing score can be negative, and housing is the only subject where one can:
# their rubric has options that cost a candidate points rather than earning
# none, so an answer can be worth less than no answer. The arts scale has no
# such option and starts at 0.
#
# arts - Victori'us score each question 0-3 against their own rubric and weight
# the questions against each other. G_GRADE holds the score and G_WEIGHT is the
# ordinary percentage every letter-graded tab carries, and the letter is the
# weighted average of the scores banded at 86/70/60. No C-: their bands have
# none, so the arts rubric can never produce one.
#
# Mirrors POINTS_CATEGORIES and SCALE_CATEGORIES in grading_tabs.py and
# appsscript/Code.gs, keyed to subject ids rather than to the registry's
# category names.
POINTS = "points"
SCALE = "scale"
POINTS_SUBJECTS = {"housing"}
SCALE_SUBJECTS = {"arts": 3}

# The incumbent record. One row on Grade - Housing that no candidate answered:
# Homes for Living score a sitting councillor's record on housing over the term
# just ending, and the Apps Script creates the row only for candidates this
# repository's own _data/candidates.yml lists as sitting incumbents.
#
# It is scored in points like every other housing row and it is NOT summed in
# with them. RECORD_SHARE of the topic is the record and the rest is the
# questionnaire, whatever each is scored out of, so the two are worked out
# against their own maxima and blended - see subject_score(). Summing it in
# would give it the share its points happen to be of the total, a different
# number on every candidate and none of them 30%.
#
# A candidate with no scored record row is published on the questionnaire alone,
# at 100%: every challenger, and every incumbent nobody has scored yet.
#
# It is also not published as a question. /questionnaire/ is what candidates
# were asked, and this was asked of nobody, so it is kept out of
# _data/questions.yml and carried in its own `record` block on the subject.
#
# Mirrors RECORD_LABEL / RECORD_SHARE in scripts/questionnaire/grading_tabs.py
# and appsscript/Code.gs; the three change together.
RECORD_LABEL = "HFL-INC"
RECORD_SHARE = 0.3

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
    "healthcare access": "healthcare-access",
    "general": "general",
    # What _data/subjects.yml called the General topic until the GEN-* questions
    # were on their way into the registry. Kept as an alias so a registry row
    # already typed the long way still resolves instead of failing the sync.
    "all categories / general": "general",
    # Reconciliation is deliberately absent: the topic was folded into
    # Governance and dropped from _data/subjects.yml. A "Reconciliation" column
    # left behind on Category Grades is a half-finished migration, and the
    # unmapped-category error is the point - a subject with no questions and no
    # topic to publish under should stop the run, not sync as an empty column.
}

# Registry `Type` values, expanded for a reader who has never seen the sheet.
# An unrecognized type publishes no label rather than the raw token.
#
# `single` and `text` used to publish no label either, on the argument that "one
# answer" is what a reader already assumes and printing it under 39 of the 55 is
# noise. That was right for a reader skimming the page and wrong for the reader
# it turned out to have: candidates asked for this page so they could work the
# questionnaire through with their team before opening the form, and a team
# drafting answers offline needs to know a box wants a sentence and not an essay
# before it starts writing one. Every question states its shape now.
TYPE_LABELS = {
    "single": "One answer",
    "text": "Written answer",
    "multi": "Select all that apply",
    "pair": "Answer plus a written follow-up",
    "variant": "Asked separately for each municipality",
    "variant,multi": "Asked separately for each municipality; select all that apply",
    "multi,pair": "Select all that apply, plus a written follow-up",
    "allocation": "Split $10 million across twelve areas",
}

# Most multi-select questions state their own selection rule, because that is how
# the form asks them. Repeating it underneath is a caption restating the sentence
# above it, so the clause is dropped where the question has already said it.
# Matched loosely: the form is not consistent about whether it says "select",
# "check", or just "all that apply".
#
# The capped ones matter more than the redundancy does. ART-05 asks candidates to
# "Select up to five" and HFL-12 "Select up to two", and a label underneath them
# reading "select all that apply" is not a repetition but a contradiction - one
# that got easy to miss while the label sat alone and impossible to miss now that
# it sits under the sixteen options it is describing.
SELECTION_RULE_CUES = (
    "select all", "check all", "all that apply",
) + ("select up to", "choose up to", "select at most")

# The subset of those that state a cap. A question saying "Select up to five"
# has already published its own `option_limit` in words, so printing the number
# under its list is the same sentence twice. "Select all that apply" has not:
# TRN-01 says it and the form still stops a candidate at four of the six, which
# is the sort of thing worth finding out before the form is open, not after.
SELECTION_CAP_CUES = ("select up to", "choose up to", "select at most", "maximum of")

# What each label says once its selection clause is dropped. A multi-select whose
# question states its own rule is still worth labelling for everything else the
# label carries: HFL-12 is asked once per municipality, and that is not something
# the question text says anywhere.
WITHOUT_SELECTION_CLAUSE = {
    "multi": "",
    "variant,multi": "Asked separately for each municipality",
    "multi,pair": "Answer plus a written follow-up",
}

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
#   options   What the question offers to pick from, in form order. Present only
#             on multi-select questions: the raw tab names every option of one
#             in a column header, picked or not, while a single-choice question
#             exports as one column holding whichever answer came back. So the
#             absence of `options` on a single-choice question means the option
#             set is not recoverable from the spreadsheet, not that the question
#             has none.
#   graded    Whether the question carries a grade. An ungraded question is
#             published unscored: it was asked, and the answer informs the
#             coalition, but no letter is assigned to it.
#   weight    This question's share of its subject's grade, as written in the
#             registry ("20%"). Omitted where the registry leaves it blank,
#             which is most of them: weighting is set per subject by the
#             partner organization that owns it, and several have not.
#
#             Always absent on a housing question, and that is not a gap. Homes
#             for Living score housing in points rather than weights, and how
#             many points a question is worth out of how many the candidate had
#             available is a fact about that candidate's municipality, not about
#             the question. It is published per candidate, in _data/scores.yml.
#             Present on an arts question, which is scored and weighted both:
#             Victori'us score each answer 0-3 and weight the questions against
#             each other exactly as a letter-graded subject does.
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
# PUBLICATION IS ALL OR NOTHING, AND IS CURRENTLY OFF. The per-subject "<Subject>
# - Deploy to website" checkboxes are gone from the Category Grades tab, and
# PUBLISH_GRADES in scripts/sync-questionnaire.py replaces them: while it is
# False no grade and no free-text answer is written here at all, so grading in
# progress never reaches the site. It is flipped on the coalition's release date,
# and flipping it back removes every published subject on the next run.
#
# EVERY CANDIDATE WITH A ROW ON THAT TAB IS LISTED HERE, with `subjects` an empty
# list for all of them while publication is off. Having a row means
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
#                    promise a letter is coming for either. A returned candidate
#                    still shows an hourglass on them until their answers are
#                    deployed, which is the truthful "not published yet"; what
#                    this list decides is what replaces it — a letter for a
#                    graded topic, a speech bubble for these two.
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
#     score       Present only on a subject whose graders score each question
#                 rather than grading it, and `percent` - the figure `grade` is
#                 banded from - is the only field both kinds carry.
#
#                 Housing, scored by Homes for Living, also carries `points` out
#                 of `max`. The maximum is the candidate's own: the
#                 municipality-specific questions are not asked everywhere, so a
#                 Sooke candidate is scored out of 54 where a Victoria one is
#                 scored out of 66. `points`, and with it `percent`, can be
#                 negative, because their rubric has answers that cost points;
#                 `max` cannot. `grade` still bottoms out at F, so a negative
#                 percentage sits under an F rather than under a blank.
#
#                 Arts, scored by Victori'us, carries `percent` alone. Each
#                 question is scored 0-3 and weighted, so the percentage is the
#                 weighted average of the scores; the raw scores do add up, but
#                 that total is unweighted and is not what the grade is from.
#
#                 A subject appears here only when every question its candidate
#                 was asked carries a score; half-scored is not published,
#                 because a missing question drops out of the denominator as
#                 well as the total and reads as a better result than it is.
#
#                 `record` and `overall` appear on a sitting incumbent whose
#                 housing record Homes for Living have scored, and on nobody
#                 else. `record` is that score - `points` out of `max`, its own
#                 `percent`, the `share` of the topic it carries, and the
#                 grader's `rationale` - and `overall` is the blend `grade` was
#                 banded from: the record's share of it, and the questionnaire's
#                 `percent` for the rest. The two fractions are published
#                 separately because they do not add up into one; a record worth
#                 30% on its own is not 10 more points on a 60-point total.
#                 Without them, `percent` is the whole of the grade.
#     questions   One entry per graded question, in form order:
#       label     Joins to _data/questions.yml.
#       grade     Letter, or null where the question has not been graded yet.
#                 Absent on a scored subject, which carries the two fields below
#                 instead.
#       points    What the question earned, on a scored subject. Negative on a
#                 housing question whose answer cost the candidate points.
#       max_points What it was worth: the question's own maximum on housing, and
#                 the top of the scale - the same 3 on every arts question - on
#                 arts.
#       weight    Share of the subject grade. Omitted where the sheet is blank,
#                 and always absent on housing, where the points are the
#                 weighting. Present on arts, which weights its questions and
#                 scores them both.
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


# --- Answer choices ---------------------------------------------------------
# What a question offers to pick from, which the Question Registry does not
# record and the site had no way to publish. Two sources, and they are not
# interchangeable:
#
#   The Tally form   Every question, in the order and wording a candidate reads
#                    them, plus the selection cap and character limits. Needs an
#                    API key, so it is the source that can be missing.
#   The raw tab      Multi-selects only, because Tally exports one column per
#                    checkbox option and names each in the header. Free, always
#                    available, and the independent check on the other one.
#
# The form wins where both know a question: it is what candidates actually see,
# and the raw tab's column order was frozen whenever those columns were created.
# A disagreement about *which* options exist is still worth saying out loud.

def split_options(texts):
    """(non-option columns, [option texts]) for one question's columns.

    Mirrors split_options() in scripts/questionnaire/grading_tabs.py, inlined
    rather than imported because that module pulls in gspread at import time and
    this script deliberately has no dependencies. Change both together.

    Tally exports a checkbox question as one column holding the question, plus
    one column per option repeating the question with " (the option)" appended.
    So the shortest text is the question and anything extending it is an option.
    A column that extends nothing is a written follow-up part (GOV-01, CLI-01,
    ART-01), returned with the question.
    """
    base = min(texts, key=len)
    options, plain = [], []
    for text in texts:
        if text != base and text.startswith(base) and text.rstrip().endswith(")"):
            options.append(text[len(base):].strip().strip("()").strip())
        else:
            plain.append(text)
    return plain, options


def header_options(header):
    """{label: [option, ...]} for every multi-select question on the form.

    The one place the full option set of a question is recoverable without
    asking Tally: the raw tab names every option in a column header whether or
    not a candidate ever picked it. Single-choice questions export as one column
    holding the chosen value, so they are absent here and their options have to
    come from the form itself.

    Municipality variants are collapsed to the label the registry lists, the
    same fold ungraded_questions() does. HFL-12 asks the same six options of
    five municipalities; publishing them once is the whole point of collapsing.
    A variant whose options differ from its siblings' is reported rather than
    silently resolved, because there is no honest way to print one list for it.
    """
    grouped = {}
    for cell in header:
        m = LABEL_RE.match((cell or "").strip())
        if not m:
            continue
        grouped.setdefault(m.group(1), []).append(" ".join(cell.split()))

    collapsed = {}
    for full_label, texts in grouped.items():
        _, options = split_options(texts)
        if not options:
            continue
        variant = VARIANT_RE.match(full_label)
        label = variant.group(1) if variant else full_label
        collapsed.setdefault(label, {})[full_label] = options

    out, conflicts = {}, []
    for label, per_variant in collapsed.items():
        distinct = {tuple(options) for options in per_variant.values()}
        if len(distinct) > 1:
            conflicts.append(label)
            continue
        out[label] = list(next(iter(distinct)))
    return out, conflicts


# --- Ungraded questions, which live only on the raw tab ---------------------
# The Question Registry lists what gets graded, so the free-text questions never
# reached it: GEN-01, the per-topic "anything to add" boxes, and GEN-02. They
# were still asked, and the answers are still worth publishing, so they are read
# from the form's own columns instead. HLT-01 is the exception in the other
# direction: it does have a registry row, hand-marked Graded=No, and is
# published from there like any other registry question.

TALLY_FORM_URL = "https://api.tally.so/forms/{id}"

# Blocks that hold one selectable option, and the ones that take an answer but
# offer nothing to list.
TALLY_OPTION_BLOCKS = {"MULTIPLE_CHOICE_OPTION", "CHECKBOX"}
TALLY_WRITTEN_BLOCKS = {"TEXTAREA", "INPUT_TEXT"}
TALLY_ANSWER_BLOCKS = TALLY_OPTION_BLOCKS | TALLY_WRITTEN_BLOCKS | {
    "INPUT_NUMBER", "LINEAR_SCALE",
}


def fetch_form(form_id, api_key, timeout=60):
    """The Tally form definition, or None if it cannot be read.

    Returns None rather than raising on a credential or lookup failure, so a
    missing key degrades to publishing multi-select options from the raw tab
    instead of stopping a run that also publishes grades.
    """
    request = urllib.request.Request(
        TALLY_FORM_URL.format(id=form_id),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
            # Cloudflare fronts api.tally.so and refuses the stdlib default
            # ("Python-urllib/3.x") with error 1010, browser_signature_banned.
            "User-Agent": "livablecrd-website-sync/1.0 (+https://livablecrd.ca)",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.load(response)
    except urllib.error.HTTPError as e:
        if e.code in (401, 403, 404):
            return None
        raise


def block_text(payload):
    """The visible text of a Tally rich-text block.

    `safeHTMLSchema` is a list of runs, each `[text]` or `[text, [[attr, value],
    ...]]` where the attributes carry styling and links. Only the text matters
    here; a link's href is part of the question a candidate reads on the form,
    not part of the question this site publishes.
    """
    runs = (payload or {}).get("safeHTMLSchema") or []
    return " ".join("".join(
        run[0] for run in runs if run and isinstance(run[0], str)
    ).split())


def form_options(blocks):
    """({label: {options, limit}}, [conflicting label, ...]) from a Tally form.

    Blocks are a flat list in form order. A question opens with a TITLE block in
    the QUESTION group and owns every answer block after it until the next one,
    so the label parsed off that title names the options that follow.

    Municipality variants are collapsed the same way header_options() collapses
    them, and on the same test: the same options, not the same ordering. HFL-11
    asks ten municipalities about their own housing target and Colwood's copy
    lists two of the four answers the other way round, which is a fact about how
    the form was typed rather than a different question being asked.
    """
    by_label, current = {}, None
    for block in blocks:
        payload = block.get("payload") or {}
        if block.get("type") == "TITLE" and block.get("groupType") == "QUESTION":
            m = LABEL_RE.match(block_text(payload))
            current = m.group(1) if m else None
            if current:
                by_label.setdefault(current, [])
            continue
        if current and block.get("type") in TALLY_ANSWER_BLOCKS:
            by_label[current].append((block["type"], payload))

    collapsed = {}
    for full_label, blocks_for_label in by_label.items():
        if not blocks_for_label:
            continue
        variant = VARIANT_RE.match(full_label)
        label = variant.group(1) if variant else full_label
        picked = [p for kind, p in blocks_for_label if kind in TALLY_OPTION_BLOCKS]
        written = [p for kind, p in blocks_for_label if kind in TALLY_WRITTEN_BLOCKS]
        limits = [p["maxCharacters"] for p in written if p.get("hasMaxCharacters")]
        collapsed.setdefault(label, {})[full_label] = {
            # "Other, I have another idea!" is a choice a candidate can pick and
            # a column on the raw tab, so it is listed like any other.
            "options": [" ".join((p.get("text") or "").split()) for p in picked],
            "limit": picked[0].get("maxChoices") if picked and picked[0].get("hasMaxChoices") else None,
            # A question that takes writing and offers nothing to pick. The
            # registry cannot see this: it infers a question's shape by counting
            # the columns Tally exports for it, and a text box and a
            # single-choice question are one column each. Eleven questions the
            # registry calls `single` are 2000-character essay boxes.
            "written_only": bool(written) and not picked,
            "max_characters": max(limits) if limits else None,
        }

    out, conflicts = {}, []
    for label, per_variant in collapsed.items():
        distinct = {frozenset(v["options"]) for v in per_variant.values()}
        if len(distinct) > 1:
            conflicts.append(label)
            continue
        # The first variant in form order. Where variants disagree about
        # ordering they still offer the same options, so any of them is true of
        # the question; taking the first keeps the choice deterministic and
        # keeps it to an order some candidate actually reads.
        out[label] = next(iter(per_variant.values()))
    return out, conflicts


def reconcile_options(from_form, from_header, warnings):
    """{label: record} to publish, the form's reading first.

    The raw tab knows only multi-selects, so it covers a third of the questions
    and agreeing with it is the only independent evidence the form was read
    correctly. Where the two disagree about which options exist, the form is
    published and the disagreement is reported: the form is what a candidate is
    looking at, and a sync that refused to run over it would take the grades
    down with it.

    Ordering disagreements are not reported. Two questions list their last two
    options the other way round on the tab, because a column's position was
    fixed when that column was created and the form has been edited since. The
    form's order is the order a candidate reads, so it wins quietly.
    """
    merged = {label: {"options": options, "limit": None,
                      "written_only": False, "max_characters": None}
              for label, options in from_header.items()}

    for label, record in from_form.items():
        checked = from_header.get(label)
        if checked and not record["options"]:
            # The form says this question offers nothing to pick and the tab
            # named columns for it. Trusting the form here would silently drop a
            # list the tab can prove exists, so keep it and say so.
            warnings.append(
                f"{label}: the {RAW_TAB} names option columns for this question "
                f"and the Tally form reports none. Keeping the tab's list."
            )
            merged[label].update({k: v for k, v in record.items() if k != "options"})
            continue
        if checked is not None and set(checked) != set(record["options"]):
            only_form = [o for o in record["options"] if o not in checked]
            only_sheet = [o for o in checked if o not in record["options"]]
            warnings.append(
                f"{label}: the Tally form and the {RAW_TAB} columns list different "
                f"options. Publishing the form's. Only on the form: {only_form or 'none'}. "
                f"Only on the tab: {only_sheet or 'none'}."
            )
        merged[label] = record
    return merged


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

def unstated_limit(limit, question):
    """The selection cap, unless the question has already spelled it out."""
    if not limit or any(cue in question.lower() for cue in SELECTION_CAP_CUES):
        return None
    return limit


def form_corrected_kind(kind, choice):
    """The registry's answer shape, corrected against the form where it is wrong.

    The registry infers a question's shape by counting the columns Tally exports
    for it (see describe() in scripts/questionnaire/grading_tabs.py), and a text
    box and a single-choice question are one column each. Eleven questions are
    2000-character essay boxes filed as `single`, which published as "One
    answer" over a box wanting several paragraphs - the opposite of what a
    candidate drafting with their team needs to know.

    Only this one correction is made. The registry's other types carry knowledge
    the form's flat block list does not: `variant` knows ten municipality copies
    are one question, and `pair` knows a follow-up asked under its own title
    belongs to the question above it.
    """
    if kind == "single" and choice.get("written_only"):
        return "text"
    return kind


def with_character_limit(type_label, kind, choice):
    """"Written answer" plus the cap, where the form sets one.

    The difference between a 500-character answer and a 2000-character one is
    the difference between a sentence and an argument, and it is the kind of
    thing a team splitting up drafting work needs before it starts writing.
    """
    limit = choice.get("max_characters")
    if not (type_label and limit and kind == "text"):
        return type_label
    return f"{type_label}, up to {limit:,} characters"


def build_questions(registry, extra, choices, subject_order, warnings, errors):
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
        if label == RECORD_LABEL:
            # Scored, but never asked. /questionnaire/ is the question set the
            # coalition put to candidates, and listing a row nobody answered
            # there would make the page say something untrue about itself. It is
            # published under its subject's own `record` block instead.
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

        choice = choices.get(label, {})
        kind = form_corrected_kind(kind, choice)
        type_label = TYPE_LABELS.get(kind, "")
        if kind in WITHOUT_SELECTION_CLAUSE and \
                any(cue in question.lower() for cue in SELECTION_RULE_CUES):
            type_label = WITHOUT_SELECTION_CLAUSE[kind]
        type_label = with_character_limit(type_label, kind, choice)

        by_subject.setdefault(subject, []).append({
            "label": label,
            "subject": subject,
            "question": question,
            "type": kind,
            "type_label": type_label,
            "graded": norm(cell(R_GRADED)) in {"yes", "true", "y"},
            "weight": cell(R_WEIGHT),
            "owner": owner,
            "options": choice.get("options") or [],
            "option_limit": unstated_limit(choice.get("limit"), question),
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
            "options": choices.get(q["label"], {}).get("options") or [],
            "option_limit": choices.get(q["label"], {}).get("limit"),
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
        # What the question offers to pick from, so a candidate can work through
        # the questionnaire with their team before opening the form.
        if q.get("options"):
            parts.append("    options:")
            parts.extend(f"      - {scalar(option)}" for option in q["options"])
            # How many of them may be picked, where the form caps it. ART-05
            # allows five of sixteen, which changes what the list means.
            if q.get("option_limit"):
                parts.append(f"    option_limit: {q['option_limit']}")
        # GEN-02's line items, so /questionnaire/ can show what the allocation is
        # split across without a candidate having answered it.
        if q.get("areas"):
            parts.append("    areas:")
            parts.extend(f"      - {scalar(area)}" for area in q["areas"])
    return "\n".join(parts) + "\n"


# --- Scores ------------------------------------------------------------------

def subject_columns(header):
    """[(subject display name, column)] for every subject the tab grades.

    The header is the list, as it has always been: which subjects are graded,
    and in what order, is the sheet's business and not this script's. What has
    changed is that a subject is one column rather than a (grade, checkbox) pair,
    so everything after the three identity columns is a grade column - except a
    leftover checkbox, which is skipped by its suffix the way Code.gs recognises
    it, so a tab that still has some syncs identically to one that does not.
    """
    columns = []
    for i, cell in enumerate(header[C_MUNICIPALITY + 1:], start=C_MUNICIPALITY + 1):
        name = tidy(cell)
        if name and not name.endswith(DEPLOY_SUFFIX):
            columns.append((name, i))
    return columns


# How Code.gs writes a multi-select answer: the written parts on their own
# lines, then every ticked option on one "Selected: " line joined by "; ". Both
# the webhook and the timer build it this way, so it is the shape every answer
# cell arrives in and the only thing that has to be agreed on to take it apart.
SELECTED_PREFIX = "Selected: "
SELECTED_JOIN = "; "


def _alnum(text):
    """Letters and digits only, lowercased, for comparing two renderings of the
    same content without caring how either one punctuated it."""
    return re.sub(r"[^a-z0-9]", "", (text or "").lower())


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

    text = "\n".join(prose).strip()

    # Drop a prose line that is only the ticked options run together again.
    #
    # A multi-select reaches the Answer cell twice over. The webhook writes one
    # "Selected: " line from the payload; the timer sync then rewrites the cell
    # from the spreadsheet, which is authoritative, and the sheet stores the same
    # options a second time in the question's own column, comma-joined. Left
    # alone, the site prints the run-on line and the tidy list one above the
    # other, which is worse than the run-on line was on its own.
    #
    # Compared on letters and digits only, so it holds whatever separator either
    # side happens to use. A prose part that says anything the options do not -
    # a written follow-up alongside the ticks - will not match and is kept.
    if selected and _alnum(text) == _alnum("".join(selected)):
        text = ""

    return text, selected


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


def graded_tab_subjects(category):
    """Subject display names with a `Grade - <Subject>` tab worth opening.

    The subjects the tab has a grade column for, and no others: General and
    Healthcare access carry no graded question, so their answers come off the raw
    tab rather than out of a per-question grading sheet, and opening a tab for
    them would be an API call against a shared quota for nothing.

    Sorted, so the warnings a run emits come out in the same order every time and
    two runs over the same sheet produce comparable logs.
    """
    return sorted({name for name, _ in subject_columns(category[0])})


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
                 muni_lookup, candidates, question_labels, publish,
                 warnings, errors):
    header = category[0]
    columns = subject_columns(header)
    if not columns:
        errors.append(f"{CATEGORY_TAB}: no subject columns after Key/Candidate/"
                      f"Municipality, so nothing on the tab names a subject.")
        return []

    graded = {}
    for name, col in columns:
        sid = SUBJECT_FOR_CATEGORY.get(norm(name))
        if not sid:
            errors.append(f"{CATEGORY_TAB}: column {name!r} maps to no subject id.")
        elif sid not in subject_order:
            errors.append(f"{CATEGORY_TAB}: subject {sid!r} is not in _data/subjects.yml.")
        else:
            graded[sid] = (name, col)

    # What a publishing run walks, in _data/subjects.yml order: every subject
    # with a grade column, and the ones without one too. Nobody grades General or
    # Healthcare access, so neither has a column to be graded in, but what
    # candidates wrote under them is published like any other topic's answers.
    targets = [(sid,) + graded.get(sid, (sid, None)) for sid in subject_order]

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
        for subject_id, subject_name, grade_col in (targets if publish else []):
            where = f"{CATEGORY_TAB} row {i} ({name}, {subject_name})"
            grade = None
            if grade_col is not None:
                grade = grade_or_none(row[grade_col] if grade_col < len(row) else "",
                                      where, warnings)
            questions, record = subject_questions(
                grade_rows.get((key, subject_name), []), name, subject_name,
                subject_id, question_labels, warnings)

            # A scored subject publishes a cumulative total, and refuses to
            # publish at all until every question a candidate was asked carries
            # a score. The deploy checkbox says the partner org is finished;
            # this says whether the numbers behind it agree.
            score = None
            if rubric_for(subject_id):
                score = subject_score(questions, record, name, subject_name,
                                      subject_id, warnings)
                if score is None:
                    continue
                # Questions this candidate's municipality was never asked. The
                # Apps Script fans every label out to every candidate, so a
                # Sooke candidate has an HFL-11 row with no answer in it; left
                # in, it would publish as a pending em-dash and read as a
                # question still being graded rather than one never put to them.
                questions = [q for q in questions if q["points"] is not None]

            # This subject's ungraded answers: the per-topic "anything to add"
            # box, and for General and Healthcare access every answer there is.
            unscored = unscored_answers(
                answers.get(key, {}), subject_id, ungraded, name, warnings)

            # A subject this candidate was neither graded on nor wrote anything
            # under is not an empty section, it is no section. Every candidate is
            # walked against every subject now that no checkbox says which ones
            # they have something to show for.
            if grade is None and not questions and not unscored:
                continue

            published.append({
                "id": subject_id,
                "grade": grade,
                "score": score,
                "questions": questions,
                "unscored": unscored,
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
                f"{name} ({muni_slug}), and only one can be shown. Delete the "
                f"superseded row, or clear its grades."
            )
        elif published:
            records[where] = record
            seen[identity] = (where, i)

    records.sort(key=lambda r: (r["municipality"], norm(r["name"])))
    return records


def rubric_for(subject_id):
    """How this subject is scored, or None where it is graded in letters."""
    if subject_id in POINTS_SUBJECTS:
        return POINTS
    if subject_id in SCALE_SUBJECTS:
        return SCALE
    return None


def subject_questions(rows, candidate, subject_name, subject_id, question_labels, warnings):
    """(the questions this candidate was graded on, their incumbent record).

    The record is the one row on a grading tab that is not a question - see
    RECORD_LABEL - so it is lifted out here rather than published alongside
    them. A challenger has no such row and gets None, which is what makes their
    questionnaire the whole of their grade.
    """
    rubric = rubric_for(subject_id)
    out = []
    record = None
    for row in rows:
        cell = lambda idx: tidy(row[idx]) if idx < len(row) else ""
        label = cell(G_LABEL)
        if not label:
            continue
        if label == RECORD_LABEL:
            where = f"{GRADE_TAB_PREFIX}{subject_name} ({candidate}, {label})"
            record = {
                "label": label,
                "points": number_or_none(cell(G_GRADE), where, "score", warnings),
                "max_points": number_or_none(cell(G_WEIGHT), where, "max points",
                                             warnings),
                "rationale": clean_text(row[G_RATIONALE] if G_RATIONALE < len(row) else ""),
            }
            continue
        if label not in question_labels:
            warnings.append(
                f"{GRADE_TAB_PREFIX}{subject_name}: {candidate}'s row for {label} has "
                f"no {REGISTRY_TAB} entry, so the site has no question text for it"
            )
            continue
        where = f"{GRADE_TAB_PREFIX}{subject_name} ({candidate}, {label})"
        prose, selected = split_selections(clean_text(row[G_ANSWER] if G_ANSWER < len(row) else ""))
        question = {
            "label": label,
            "grade": None if rubric else grade_or_none(
                row[G_GRADE] if G_GRADE < len(row) else "", where, warnings),
            # Column I is a maximum on a points subject and has no business
            # being published as a share of anything. On every other kind,
            # scored or not, it is the share it has always been.
            "weight": "" if rubric == POINTS else cell(G_WEIGHT),
            "rationale": clean_text(row[G_RATIONALE] if G_RATIONALE < len(row) else ""),
            "answer": prose,
            "selected": selected,
        }
        if rubric:
            question["points"] = number_or_none(cell(G_GRADE), where, "score", warnings)
        if rubric == POINTS:
            question["max_points"] = number_or_none(cell(G_WEIGHT), where,
                                                    "max points", warnings)
        elif rubric == SCALE:
            # The same number on every row of the subject: what a question is
            # worth against the others is the weight in column I, not the top of
            # the scale, which is a property of the rubric and not of the
            # question. Published per question all the same, because "2" beside
            # an answer says nothing without it.
            question["max_points"] = SCALE_SUBJECTS[subject_id]
        out.append(question)
    return out, record


def number_or_none(value, where, what, warnings):
    """A score cell as a number, or None for the blank that means "not scored".

    Blank is the ordinary state of a score cell and carries real meaning, so it
    is not a warning: a question a candidate's municipality never asked is
    fanned out to their tab like every other and simply never scored. Anything
    that is neither blank nor a number is the warning.
    """
    if not value:
        return None
    try:
        number = float(value.replace(",", ""))
    except ValueError:
        warnings.append(f"{where}: {what} {value!r} is not a number, treated as unscored")
        return None
    return int(number) if number == int(number) else number


def subject_score(questions, record, candidate, subject_name, subject_id, warnings):
    """The cumulative figure behind one candidate's letter on a scored subject.

    A question with no score drops out of the total and out of what the total is
    measured against, which is what lets one rule cover every municipality:
    HFL-11 is only asked in ten of them and HFL-12 in five, the Apps Script fans
    all of them out to every candidate regardless, and the ones nobody was asked
    are simply never scored. A Sooke candidate is graded out of the 54 they were
    asked rather than the 66 somebody in Victoria was.

    That same rule is why an unscored question a candidate *did* answer must stop
    publication: it would quietly leave that question out of the denominator as
    well as the total, and the candidate would read better than they are. The two
    states are different and the warnings say which is which.

    Both checks are the rubrics' in common; what each returns is not. A points
    subject publishes the points, the maximum and the share of it. A scale
    subject has no meaningful running total to publish - a raw 19 out of 24 is
    the unweighted figure, and the weighting is the whole rubric - so it
    publishes the weighted percentage and nothing else.

    A points total, and the percentage with it, can come out negative: Homes for
    Living score some answers below zero. Neither is floored here, because the
    two figures are the arithmetic of what the graders typed and a reader is
    owed it. The letter is a separate question and is floored, at F, in the
    Category Grades formula - see points_rollup_formula() in
    scripts/questionnaire/grading_tabs.py.

    An incumbent's scored record is published beside the questionnaire rather
    than folded into it, with `overall` stating the blend the letter came from.
    Three figures rather than one because the blend is not arithmetic a reader
    can do from a single fraction: 38 of 60 and 7 of 10 are not 45 of 70 once
    the second is worth RECORD_SHARE on its own. A record scored with no maximum
    beside it stops the subject publishing, exactly as a question in that state
    does - there the total would be flattered, here the letter on the sheet and
    the figures on the page would be computed from different rules.
    """
    scored = [q for q in questions if q["points"] is not None]
    answered_unscored = [q for q in questions
                         if q["points"] is None and (q["answer"] or q["selected"])]

    if not scored:
        warnings.append(
            f"{GRADE_TAB_PREFIX}{subject_name}: {candidate} has no score on any "
            f"question, so the subject is not published."
        )
        return None
    if answered_unscored:
        missing = ", ".join(q["label"] for q in answered_unscored)
        warnings.append(
            f"{GRADE_TAB_PREFIX}{subject_name}: {candidate} answered {missing} but "
            f"it carries no score, so the subject is not published. An unscored "
            f"answer drops out of the maximum as well as the total, which would "
            f"publish a better result than they earned."
        )
        return None

    if rubric_for(subject_id) == SCALE:
        return scale_score(scored, candidate, subject_name,
                           SCALE_SUBJECTS[subject_id], warnings)

    missing_max = [q["label"] for q in scored if q["max_points"] is None]
    if missing_max:
        warnings.append(
            f"{GRADE_TAB_PREFIX}{subject_name}: {candidate} is scored on "
            f"{', '.join(missing_max)}, which has no Max points on its "
            f"{REGISTRY_TAB} row, so the subject is not published."
        )
        return None

    points = sum(q["points"] for q in scored)
    maximum = sum(q["max_points"] for q in scored)
    share = 100 * points / maximum if maximum else 0
    score = {"points": points, "max": maximum, "percent": round(share)}

    if record is None or record["points"] is None:
        return score
    if not record["max_points"]:
        warnings.append(
            f"{GRADE_TAB_PREFIX}{subject_name}: {candidate} is scored "
            f"{record['points']} on {RECORD_LABEL}, which has no Max points on "
            f"its {REGISTRY_TAB} row, so the subject is not published. The "
            f"record would count for nothing, and the sheet's own letter says "
            f"so too."
        )
        return None

    record_share = 100 * record["points"] / record["max_points"]
    score["record"] = {
        "points": record["points"],
        "max": record["max_points"],
        "percent": round(record_share),
        "share": round(100 * RECORD_SHARE),
        "rationale": record["rationale"],
    }
    # Rounded once, from the unrounded shares, so the published figure is the
    # one the sheet banded into the letter above it rather than a blend of two
    # numbers that have each already lost their decimals.
    score["overall"] = round((1 - RECORD_SHARE) * share + RECORD_SHARE * record_share)
    return score


def scale_score(scored, candidate, subject_name, ceiling, warnings):
    """The weighted percentage behind a scale-scored subject's letter.

    Each question's score is its share of the scale, and each question's share
    of the subject is its weight, so the subject is the one divided by the
    other: the scores weighted, over the weights that carried a score. Dividing
    by the weights present rather than by 100% is the same courtesy the rest of
    this pays a partly-scored candidate, and it is also what keeps the figure
    right when a question is left unasked.

    Refused rather than approximated in two cases, because both would publish a
    number that is not the one the graders arrived at: a scored question with no
    weight beside it (its score would count for nothing), and a score above the
    top of the scale (the sheet's validation should have stopped it, and if it
    did not, the rubric is not what this thinks it is).
    """
    unweighted = [q["label"] for q in scored if share_or_none(q["weight"]) is None]
    if unweighted:
        warnings.append(
            f"{GRADE_TAB_PREFIX}{subject_name}: {candidate} is scored on "
            f"{', '.join(unweighted)}, which carries no weight, so the subject is "
            f"not published. A scored question with no weight counts towards "
            f"nothing, and the grade would be of the other questions only."
        )
        return None

    over = [f"{q['label']} ({q['points']})" for q in scored if q["points"] > ceiling]
    if over:
        warnings.append(
            f"{GRADE_TAB_PREFIX}{subject_name}: {candidate} scores "
            f"{', '.join(over)} above the {ceiling} the rubric tops out at, so "
            f"the subject is not published."
        )
        return None

    weights = [share_or_none(q["weight"]) for q in scored]
    earned = sum(q["points"] * w for q, w in zip(scored, weights))
    available = ceiling * sum(weights)
    return {"percent": round(100 * earned / available) if available else 0}


def share_or_none(value):
    """A weight cell as a fraction of one, or None if it is not a weight.

    The sheet renders column I as a percentage and gviz hands it back the way it
    is rendered, so "16.67%" is what arrives for a sixth of a subject. Parsed
    rather than rounded to an integer percentage the way it is published: eight
    weights rounded to whole percents total 101%, and a weighted average taken
    against that is not the one the graders' own workbook computes.
    """
    text = (value or "").strip().replace(",", "")
    if not text:
        return None
    percent = text.endswith("%")
    try:
        number = float(text[:-1] if percent else text)
    except ValueError:
        return None
    return number / 100 if percent else number


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
            if subject.get("score"):
                score = subject["score"]
                parts.append("        score:")
                # Only a points subject has a running total to state. A scale
                # subject's figure is the weighted percentage and nothing else:
                # its raw scores add up to something, but that something is
                # unweighted and would contradict the percentage beside it.
                if score.get("max") is not None:
                    parts.append(f"          points: {score['points']}")
                    parts.append(f"          max: {score['max']}")
                parts.append(f"          percent: {score['percent']}")
                # An incumbent scored on their record: what the questionnaire
                # above is worth stops being the whole grade, so both halves and
                # the blend are stated rather than one fraction a reader cannot
                # reconcile with the letter.
                if score.get("record"):
                    incumbency = score["record"]
                    parts.append(f"          overall: {score['overall']}")
                    parts.append("          record:")
                    parts.append(f"            points: {incumbency['points']}")
                    parts.append(f"            max: {incumbency['max']}")
                    parts.append(f"            percent: {incumbency['percent']}")
                    parts.append(f"            share: {incumbency['share']}")
                    if incumbency["rationale"]:
                        parts.append(f"            rationale: "
                                     f"{text_value(incumbency['rationale'], 14)}")

            if subject["questions"]:
                parts.append("        questions:")
                for q in subject["questions"]:
                    parts.append(f"          - label: {scalar(q['label'])}")
                    if q.get("max_points") is not None:
                        parts.append(f"            points: {q['points']}")
                        parts.append(f"            max_points: {q['max_points']}")
                    else:
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


def env_flag(name, default):
    """A boolean environment variable, or `default` where it is unset or empty.

    So a run can publish, or not, without editing and committing the switch:
    what CI does every morning is what this file says, and a local check of what
    release day would produce is one variable.
    """
    value = (os.environ.get(name) or "").strip().lower()
    if not value:
        return default
    return value in {"1", "true", "yes", "on"}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--sheet-id", default=os.environ.get("QUESTIONNAIRE_SUBMISSIONS_SHEET_ID", ""),
                        help="Submission spreadsheet id (default: $QUESTIONNAIRE_SUBMISSIONS_SHEET_ID)")
    parser.add_argument("--form-id", default=os.environ.get("TALLY_FORM_ID", ""),
                        help="Tally form id (default: $TALLY_FORM_ID)")
    parser.add_argument("--api-key", default=os.environ.get("TALLY_API_KEY", ""),
                        help="Tally API key (default: $TALLY_API_KEY)")
    parser.add_argument("--publish", action=argparse.BooleanOptionalAction,
                        default=env_flag("PUBLISH_GRADES", PUBLISH_GRADES),
                        help="Write candidate results to _data/scores.yml "
                             "(default: PUBLISH_GRADES in this script, overridden "
                             "by $PUBLISH_GRADES)")
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
        ungraded, options = [], {}
    else:
        ungraded = ungraded_questions(
            raw_header[0], graded_labels, subject_order, warnings, errors)
        options, conflicts = header_options(raw_header[0])
        for label in sorted(conflicts):
            warnings.append(
                f"{RAW_TAB} ({label}): municipality variants offer different "
                f"options, so no single list is true of the question. Published "
                f"without options."
            )

    # What the raw tab alone can say: the multi-selects' options, and nothing
    # about a selection cap or a character limit, neither of which reaches a
    # column header. The form fills the rest in below.
    choices = {label: {"options": found, "limit": None,
                       "written_only": False, "max_characters": None}
               for label, found in options.items()}

    # The form covers the questions the raw tab cannot: a single-choice question
    # exports as one column holding whichever answer came back, so its options
    # exist nowhere but here.
    if not (args.form_id and args.api_key):
        warnings.append(
            "no Tally credentials (TALLY_FORM_ID / TALLY_API_KEY), so only "
            "multi-select questions are published with their answer choices"
        )
    else:
        form = fetch_form(args.form_id, args.api_key)
        if form is None:
            warnings.append(
                f"Tally form {args.form_id} could not be read: check the id and "
                f"that the key is still valid. Answer choices fall back to the "
                f"multi-selects the {RAW_TAB} columns name."
            )
        else:
            from_form, form_conflicts = form_options(form.get("blocks") or [])
            for label in sorted(form_conflicts):
                warnings.append(
                    f"Tally form ({label}): municipality variants offer different "
                    f"options, so no single list is true of the question. Published "
                    f"without options."
                )
            choices = reconcile_options(from_form, options, warnings)

    questions = build_questions(registry, ungraded, choices, subject_order,
                                warnings, errors)
    question_labels = {q["label"] for q in questions}

    # Which subjects carry a grade at all, read off the questions rather than off
    # the Category Grades columns. The two are the same list today, and asking
    # the questions keeps "being graded" off General and Healthcare access -
    # which nobody grades - whatever columns the sheet happens to grow.
    graded_subjects = [sid for sid in subject_order
                       if any(q["graded"] and q["subject"] == sid for q in questions)]

    category = tab_values(args.sheet_id, CATEGORY_TAB,
                          expect=TAB_FIRST_HEADER[CATEGORY_TAB])
    if category is None:
        warnings.append(f"{CATEGORY_TAB}: tab missing, no candidate results published")
        records = []
    else:
        # Not read at all while publication is off: no grade and no answer can
        # reach _data/scores.yml, and each tab is an API call against a quota
        # this job shares with everything else touching the spreadsheet.
        grade_rows, answers = {}, {}
        if args.publish:
            grade_rows = load_grade_rows(
                args.sheet_id, graded_tab_subjects(category), warnings)
            answers = raw_answers(args.sheet_id, ungraded, warnings) if ungraded else {}
        records = build_scores(
            category, grade_rows, answers, ungraded, subject_order, muni_lookup,
            candidates, question_labels, args.publish, warnings, errors)

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
    if not args.publish:
        print("publication is off (PUBLISH_GRADES is False): every candidate is "
              "listed as returned, and no result is published")

    write_if_changed(QUESTIONS_OUT, render_questions(questions, subject_order),
                     args.dry_run, "_data/questions.yml")
    write_if_changed(SCORES_OUT, render_scores(graded_subjects, records),
                     args.dry_run, "_data/scores.yml")
    return 0


if __name__ == "__main__":
    sys.exit(main())
