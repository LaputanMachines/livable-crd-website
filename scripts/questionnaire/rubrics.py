#!/usr/bin/env python3
"""Answer-to-grade rubrics for the questions the coalition grades by hand.

A grading tab's Grade column is typed by a person, and for most questions that
is a judgement call on free text. For the closed questions - the ones offering a
fixed menu of answers - it is not: every candidate who picked the same option
should get the same letter, and the only reason that has not been enforced is
that the mapping lived in whoever was grading that day.

This module is that mapping, written down. It holds one rubric per closed
question, the shared policy on answers that are not positions, and the helper
that turns a raw answer cell into a letter.

Nothing here writes to the sheet. Callers read a grading tab, ask `grade_for`
what each answer is worth, and do what they like with the result.

Usage:
    from rubrics import grade_for, RUBRICS

    letter, note = grade_for("CLI-05", "Yes")     # ("A", None)
    letter, note = grade_for("CLI-03", "No")      # ("C-", None)
"""

# Letters a rubric may return. Mirrors VALID_GRADES in grading_tabs.py,
# sync-candidates.py and sync-questionnaire.py; anything else is refused at sync
# rather than published as an unstyled badge. There is no A+, B+ or D: a rubric
# wanting finer resolution than this has to be re-expressed, not extended.
VALID_GRADES = ("A", "B", "C", "C-", "F")

# Grades that mean "this row does not count", as opposed to a letter.
#
# UNGRADED is the empty string, and it has to be: the letter rollup in
# appsscript/Code.gs filters rows on `H<>""`, so a blank Grade drops out of both
# the numerator and the weight it is divided by. A row holding the literal text
# "N/A" passes that filter and then fails the MATCH inside it, scoring 0, which
# is the same as F. N/A is therefore reserved for a question that genuinely does
# not apply to a candidate and is never a way to say "not graded".
UNGRADED = ""
NOT_APPLICABLE = "N/A"

# --- The non-answer policy ---------------------------------------------------
#
# "Decline to answer" is an offered option on every closed question, and it is
# not one position. Reading the submissions, candidates reached for it in two
# different situations:
#
#   The menu did not fit.   They hold a position the options could not express,
#                           and said so in the topic's written comment box, or
#                           answered the neighbouring questions in a way that
#                           makes the position obvious.
#   No position offered.    Nothing explains the decline, and the surrounding
#                           answers do not supply one either.
#
# Grading both the same way penalises the first group for the questionnaire's
# own limits. So a decline is UNGRADED where the candidate explained themselves
# or answered solidly elsewhere in the topic, and FAILED otherwise, on the
# reasoning that an unexplained decline may be concealed opposition.
#
# This is a judgement about a candidate, not about an answer string, so it
# cannot live in the per-question tables below. `grade_for` takes `excused` and
# the caller decides.
DECLINE_ANSWERS = {"decline to answer", "declined", "decline"}
DECLINE_EXCUSED = UNGRADED
DECLINE_UNEXCUSED = "F"

# "Unsure" is an absence of a position rather than a refusal to state one, and
# the coalition grades it as no answer at all rather than as a weak yes.
#
# Set 2026-09-13 on CLI-04, reversing the earlier GOV-02 precedent that graded
# an Unsure as C. The GOV-02 row was left as it was; if that ever gets revisited
# this constant is the single place the two have to agree.
UNSURE_ANSWERS = {"unsure"}
UNSURE_GRADE = UNGRADED


def normalise(answer):
    """An answer cell reduced to what a rubric table is keyed on.

    Tally writes the option text verbatim, and the same option reaches the sheet
    with and without its trailing period depending on how the form was edited
    between submissions ("Decline to answer" and "Decline to answer."). Case and
    surrounding whitespace vary the same way.
    """
    return " ".join(str(answer or "").split()).strip().rstrip(".").lower()


def selected_options(answer):
    """The options a candidate ticked on a multi-select question.

    A multi-select answer cell holds the ticked options twice: once as Tally's
    own comma-joined list, and again after a "Selected:" line that the Apps
    Script appends semicolon-separated. The second is parsed, because an option
    containing a comma ("Small homes (< 500 sq. ft.)") splits wrongly out of the
    first. A cell with no "Selected:" line is one option, unsplit.

    Some cells carry only the "Selected:" list and no comma-joined line above
    it, so the marker starts the cell instead of a line within it. Splitting on
    the newline form alone leaves that marker glued to the first option, which
    then matches nothing in a rubric that names its options.
    """
    text = str(answer or "")
    if "\nSelected:" in text:
        tail = text.split("\nSelected:", 1)[1]
    elif text.lstrip().startswith("Selected:"):
        tail = text.lstrip()[len("Selected:"):]
    else:
        tail = text
    return [part.strip().rstrip(".") for part in tail.split(";") if part.strip()]


# --- Per-question rubrics ----------------------------------------------------
#
# One entry per closed question, keyed on the registry label. `answers` maps a
# normalised option to its letter. `multi` names the callable that grades a
# multi-select instead of a lookup. `notes` is why the letters fall where they
# do, for the next person to grade this question or a question like it.

CLI_06_FUNDED = {
    "subsidized home assessments for heat, air quality and wildfire risk",
    "grants or financing for cooling, filtration and building retrofits",
    "designated cooling and clean-air centres with guaranteed opening hours",
}


def cli_06(answer):
    """CLI-06, heat and wildfire protection for people in existing homes.

    Counting ticks alone would let a candidate reach the top of the scale on the
    two cheapest options, a vegetation bylaw and an information campaign, while
    committing no money to anyone actually living in an overheating home. So the
    top band needs breadth AND at least two of the three measures the
    municipality has to pay for.
    """
    picked = {normalise(option) for option in selected_options(answer)}
    if picked == {"none of the above"}:
        return "F"
    count = len(picked)
    funded = len(picked & CLI_06_FUNDED)
    if count >= 4 and funded >= 2:
        return "A"
    if count >= 3:
        return "B"
    if count == 2:
        return "C"
    return "C-"


def trn_01(answer):
    """TRN-01, which fare measures a candidate would push for at the VRTC.

    Every option on this menu is a fare cut for a group that cannot easily pay,
    so unlike CLI-06 there is no cheap option to guard the top band against and
    breadth is the whole signal. The ladder is a straight count of ticks, set to
    match how the 78 rows graded before this rubric existed were actually
    letters: four ticks was A on every one of them, three was usually B, two
    usually C and one usually C-.
    """
    picked = {normalise(option) for option in selected_options(answer)}
    picked.discard("none of the above")
    count = len(picked)
    if count >= 4:
        return "A"
    if count == 3:
        return "B"
    if count == 2:
        return "C"
    if count == 1:
        return "C-"
    return "F"


RUBRICS = {
    "CLI-03": {
        "question": "Will you pledge to never take meetings from fossil fuel "
                    "company lobbyists?",
        "answers": {
            "yes": "A",
            "no": "C-",
        },
        "notes": (
            "A No is C- rather than F because of the split the earlier grading "
            "settled on: a plain No is C- where the question is about "
            "governance or conduct and F where it is about infrastructure or "
            "funding. This one asks a candidate to give up a channel of access "
            "to themselves, which is conduct."
        ),
    },
    "CLI-04": {
        "question": "Would you vote to have your municipality join other BC "
                    "local governments in legal action to recover climate "
                    "costs from major fossil fuel producers?",
        "answers": {
            "yes": "A",
            "yes, if municipal costs are capped": "B",
            "no": "F",
        },
        "notes": (
            "A conditional yes is B wherever one appears, so a cap on municipal "
            "exposure lands there. The No is F rather than C- because the "
            "question is about spending to recover costs, which is the funding "
            "side of the split CLI-03 sits on the other side of."
        ),
    },
    "CLI-05": {
        "question": "Will you support a zoning bylaw amendment prohibiting new "
                    "or expanded commercial gas stations?",
        "answers": {
            "yes": "A",
            "no": "F",
        },
        "notes": "A land use question, so a No is F rather than C-.",
    },
    "CLI-06": {
        "question": "Extreme heat, wildfire smoke and wildfire risk all affect "
                    "people living in existing homes. What would you have your "
                    "municipality do to protect them?",
        "multi": cli_06,
        "notes": (
            "Breadth with a floor on the measures that cost the municipality "
            "money. See cli_06 for why a straight count was rejected."
        ),
    },
    "CLI-07": {
        "question": "Are you supportive of phasing out fossil fuel powered "
                    "tools such as leaf blowers?",
        "answers": {
            "yes": "A",
            "no": "F",
        },
        "notes": "A regulatory phase-out, graded on the same footing as CLI-05.",
    },
    "CLI-08": {
        "question": "Under what conditions, if any, would you support a new "
                    "data centre in your municipality?",
        "answers": {
            "oppose all new data centres": "A",
            "support only with waste-heat recovery and no net increase in "
            "potable water use": "B",
            "support only under conditions set case by case": "C",
            "support without special conditions": "F",
        },
        "notes": (
            "The two conditional options are separated by whether the condition "
            "binds. Waste-heat recovery and no net potable water increase is a "
            "testable commitment, so it takes the conditional-yes B. Conditions "
            "set case by case name nothing and commit to nothing, so it takes "
            "the C that a depends-case-by-case answer gets everywhere else."
        ),
    },
    "CLI-12": {
        "question": "Do you support blue-green infrastructure upgrades as a "
                    "requirement of developments for climate readiness?",
        "answers": {
            "yes": "A",
            "no": "F",
        },
        "notes": "Graded by RUSH from 2026-09-01; the mapping is recorded here "
                 "so the remaining rows match the ones already typed.",
    },
    "ROL-02": {
        "question": "Will you commit (or continue to commit) to physical "
                    "protection (not paint alone) as the standard for all new "
                    "and upgraded cycling infrastructure on busy streets in "
                    "your municipality?",
        "answers": {
            "yes": "A",
            "yes, except where physically impossible": "B",
            "no": "F",
        },
        "notes": (
            "Except where physically impossible is a condition that can be "
            "checked against a street, so it takes the conditional-yes B, and "
            "that is where the 19 rows graded before this rubric existed put "
            "it. A No is F because the question sets a construction standard, "
            "which is infrastructure."
        ),
    },
    "ROL-03": {
        "question": "Will you oppose efforts (current and future) to remove, "
                    "narrow or downgrade existing protected bike lanes and "
                    "other all-ages-and-abilities cycling infrastructure in "
                    "your municipality during your term?",
        "answers": {
            "yes": "A",
            "depends, case-by-case": "C",
            "no": "F",
        },
        "notes": (
            "Depends case by case names no test and commits to nothing, which "
            "is the C it gets on CLI-08 and TRN-02; 13 of the 14 rows graded "
            "before this rubric existed agree. A No is F because the question "
            "is about keeping built infrastructure in place. An answer of N/A "
            "is not listed: it is a claim that the question does not apply to "
            "that municipality, which is a judgement about a candidate and is "
            "passed in by hand, like an excused decline."
        ),
    },
    "TRN-01": {
        "question": "Which fare measures would you actively advocate for at "
                    "the VRTC? Select all that apply.",
        "multi": trn_01,
        "notes": (
            "A count of ticks, because no option here is cheaper than the "
            "others in the way CLI-06's are. See trn_01 for where the "
            "boundaries came from. The rows graded before this rubric was "
            "written are not perfectly consistent with it at three and two "
            "ticks; they were left as typed and the majority letter was taken."
        ),
    },
    "TRN-02": {
        "question": "Do you support removing general on-street parking from "
                    "frequent transit corridors and main arterial streets, and "
                    "reallocating that space to bus lanes, loading zones, and "
                    "walking and cycling infrastructure?",
        "answers": {
            "yes, across the whole corridor": "A",
            "yes, only during peak hours": "B",
            "kind of, only when a specific project requires it": "C",
            "no": "F",
        },
        "notes": (
            "Peak hours only is a real, testable limit on a yes, so it takes "
            "the conditional-yes B. Only when a specific project requires it "
            "names no project and commits to nothing in advance, which is the "
            "case-by-case answer CLI-08 puts at C. A No is F because the "
            "question is about street space, which is infrastructure. Eight "
            "of the earlier rows put the case-by-case option at B and "
            "nineteen put it at C; the nineteen were followed."
        ),
    },
    "TRN-03": {
        "question": "Do you support rapid deployment of transit priority "
                    "measures on frequent transit corridors, even where this "
                    "requires removing on-street parking or a general-purpose "
                    "traffic lane?",
        "answers": {
            "yes": "A",
            "yes, but not at the cost of a general-purpose travel lane": "C-",
            "no": "F",
        },
        "notes": (
            "The question asks specifically about giving up a traffic lane, so "
            "a yes that rules the lane out withholds the one thing being "
            "asked for and cannot take the conditional-yes B. C- rather than "
            "F because the rest of the toolkit is still on the table. A No is "
            "F on the infrastructure side of the split."
        ),
    },
    "TRN-04": {
        "question": "Do you support the creation of a regional transportation "
                    "authority?",
        "answers": {
            "yes": "A",
            "no": "C-",
        },
        "notes": (
            "A No is C- rather than F because this asks who should decide, not "
            "what should be built or funded, which puts it on the governance "
            "side of the CLI-03 split. Three earlier rows typed F and two "
            "typed C-; the governance rule was followed over the count."
        ),
    },
    "TRN-05": {
        "question": "Do you support building new bus-only and bike-only "
                    "connections through parks, golf courses or public land "
                    "when doing so would substantially shorten transit and "
                    "cycling trips?",
        "answers": {
            "yes": "A",
            "yes, if no mature trees are lost during construction": "B",
            "no": "F",
        },
        "notes": (
            "Losing no mature trees is a named and checkable condition, so it "
            "takes the conditional-yes B. A No is F because the question is "
            "about building a connection, which is infrastructure."
        ),
    },
}


def grade_for(label, answer, excused=False):
    """(grade, note) for one answer, or (None, reason) if no rubric applies.

    `grade` is a letter, or UNGRADED for a row that should be left blank and
    drop out of the category rollup. `excused` is the caller's judgement on a
    decline: see the non-answer policy above.

    A question with no rubric, or an answer the rubric does not list, returns
    None rather than guessing. Both mean a person has to look at the row.
    """
    rubric = RUBRICS.get(label)
    if rubric is None:
        return None, f"no rubric for {label}"

    text = normalise(answer)
    if not text:
        return None, "empty answer"
    if text in DECLINE_ANSWERS:
        return (DECLINE_EXCUSED if excused else DECLINE_UNEXCUSED), (
            "decline, explained or answered elsewhere" if excused
            else "decline, unexplained"
        )
    if text in UNSURE_ANSWERS:
        return UNSURE_GRADE, "unsure, graded as no answer"

    if "multi" in rubric:
        return rubric["multi"](answer), None

    grade = rubric["answers"].get(text)
    if grade is None:
        return None, f"{label}: answer not in rubric: {text!r}"
    return grade, None
