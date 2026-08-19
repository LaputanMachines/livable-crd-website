#!/usr/bin/env python3
"""Regenerate _data/questions.yml and _data/scores.yml from the grading sheet.

Source is Tally's submission spreadsheet ("Submissions - 2026 Municipal
Elections", `QUESTIONNAIRE_SUBMISSIONS_SHEET_ID`), the same sheet
scripts/questionnaire/grading_tabs.py bootstraps and appsscript/Code.gs keeps
current. Three tabs matter here:

  Question Registry     One row per question the coalition asked. Published in
                        full as the questionnaire page: it is the list of what
                        candidates were asked, graded or not.
  Category Grades       One row per candidate, one column per subject, each
                        followed by a "<Subject> - Deploy to website" checkbox.
                        The checkbox is the publication gate: a subject is only
                        published for a candidate once it is ticked.
  Grade - <Subject>     One row per candidate per question, carrying the answer,
                        the grade, the weight and the grader's rationale. These
                        are the sub-grades shown under a published subject.

Nothing here decides what is publishable. The checkbox does. An unticked subject
is not written to _data/scores.yml at all, so a grade in progress cannot reach
the site by accident, and unticking one removes it on the next run.

WHAT IS DELIBERATELY NOT PUBLISHED
  - Candidate email addresses and every other identity column from the raw Tally
    tab. This script never opens that tab.
  - The grader's name and the grading timestamp. Who graded a response is
    internal; the coalition publishes grades as the coalition's.
  - An `Owner` that looks like an email address. Question ownership is published
    as an organization ("Better Transit YYJ"), and some registry rows name an
    individual's address instead. Those are dropped, with a warning, rather than
    printed on a public page.

Auth, in order of preference:
  GOOGLE_SERVICE_ACCOUNT_JSON  the JSON key itself (CI: a repo secret). The
                               spreadsheet must be shared with the service
                               account's address, read access is enough.
  gspread.oauth()              the interactive local flow the rest of
                               scripts/questionnaire/ uses.

Usage:
  python3 scripts/sync-questionnaire.py --dry-run     # print, write nothing
  python3 scripts/sync-questionnaire.py               # rewrite both data files
"""

import argparse
import importlib.util
import json
import os
import re
import sys

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

def open_sheet(sheet_id):
    import gspread

    raw = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
    if raw:
        client = gspread.service_account_from_dict(json.loads(raw))
    else:
        client = gspread.oauth()
    return client.open_by_key(sheet_id)


def tab_values(sh, title):
    import gspread

    try:
        return sh.worksheet(title).get_all_values()
    except gspread.WorksheetNotFound:
        return None


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

def build_questions(registry, subject_order, warnings, errors):
    """One published entry per registry row, in subjects.yml order."""
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
    return "\n".join(parts) + "\n"


# --- Scores ------------------------------------------------------------------

def deployed_columns(header):
    """[(subject display name, grade column, deploy column)] from Category Grades.

    A grade column is one immediately followed by its own deploy checkbox; that
    pairing is what Code.gs writes and what tells a grade column from anything
    else somebody adds to the right of the tab.
    """
    pairs = []
    for i, cell in enumerate(header):
        name = tidy(cell)
        if not name or name.endswith(DEPLOY_SUFFIX) or i < 3:
            continue
        gate = i + 1
        if gate < len(header) and tidy(header[gate]) == name + DEPLOY_SUFFIX:
            pairs.append((name, i, gate))
    return pairs


def is_ticked(value):
    return norm(value) in {"true", "yes", "checked", "1"}


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
    columns = deployed_columns(category[0])
    names = set()
    for row in category[1:]:
        for name, _, gate in columns:
            if gate < len(row) and is_ticked(row[gate]):
                names.add(name)
    # Sorted, so the warnings a run emits come out in the same order every time
    # and two runs over the same sheet produce comparable logs.
    return sorted(names)


def load_grade_rows(sh, subject_names, warnings):
    """{(submission key, subject display name): [row, ...]} in sheet order."""
    rows = {}
    for name in subject_names:
        values = tab_values(sh, GRADE_TAB_PREFIX + name)
        if values is None:
            warnings.append(f"{GRADE_TAB_PREFIX}{name}: tab missing, no sub-grades published")
            continue
        for row in values[1:]:
            key = tidy(row[G_KEY]) if G_KEY < len(row) else ""
            if not key:
                continue
            rows.setdefault((key.split("|", 1)[0], name), []).append(row)
    return rows


def build_scores(category, grade_rows, subject_order, muni_lookup, candidates,
                 question_labels, warnings, errors):
    header = category[0]
    columns = deployed_columns(header)
    if not columns:
        errors.append(f"{CATEGORY_TAB}: no '<Subject>{DEPLOY_SUFFIX}' column pairs found.")
        return [], []

    subject_ids = {}
    for name, _, _ in columns:
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
        for subject_name, grade_col, gate_col in columns:
            if subject_name not in subject_ids:
                continue
            if not is_ticked(row[gate_col] if gate_col < len(row) else ""):
                continue
            where = f"{CATEGORY_TAB} row {i} ({name}, {subject_name})"
            published.append({
                "id": subject_ids[subject_name],
                "grade": grade_or_none(row[grade_col] if grade_col < len(row) else "",
                                       where, warnings),
                "questions": subject_questions(
                    grade_rows.get((key, subject_name), []), name, subject_name,
                    question_labels, warnings),
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
    # The subjects this sheet grades at all, which is not the same as the site's
    # topic list: `general` and `healthcare-access` have no column here because
    # neither carries a graded question. The site needs the distinction to say
    # "still being graded" about the right topics and stay quiet about the ones
    # nobody is grading.
    graded = sorted(dict.fromkeys(subject_ids.values()), key=subject_order.index)
    return graded, records


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
        out.append({
            "label": label,
            "grade": grade_or_none(row[G_GRADE] if G_GRADE < len(row) else "", where, warnings),
            "weight": cell(G_WEIGHT),
            "rationale": clean_text(row[G_RATIONALE] if G_RATIONALE < len(row) else ""),
            "answer": clean_text(row[G_ANSWER] if G_ANSWER < len(row) else ""),
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
            if not subject["questions"]:
                parts.append("        questions: []")
                continue
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

    sh = open_sheet(args.sheet_id)

    registry = tab_values(sh, REGISTRY_TAB)
    if registry is None:
        print(f"error: no '{REGISTRY_TAB}' tab in that spreadsheet", file=sys.stderr)
        return 1
    questions = build_questions(registry, subject_order, warnings, errors)
    question_labels = {q["label"] for q in questions}

    category = tab_values(sh, CATEGORY_TAB)
    if category is None:
        warnings.append(f"{CATEGORY_TAB}: tab missing, no candidate results published")
        graded_subjects, records = [], []
    else:
        graded_subjects, records = build_scores(
            category, load_grade_rows(sh, ticked_subjects(category), warnings),
            subject_order, muni_lookup, candidates, question_labels, warnings, errors)

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
