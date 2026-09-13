---
name: grade-questionnaire
description: Grade candidate questionnaire answers on a "Grade - <Subject>" tab of the coalition submissions sheet. Use when asked to grade questions by label (CLI-03, HFL-11, GOV-02), to grade a topic, or to re-run grading after new candidate submissions arrive.
---

# Grading the candidate questionnaire

The answer-to-letter mapping is **code, not prose**: read
`scripts/questionnaire/rubrics.py`. Do not re-derive a grade by reasoning about
an answer when `RUBRICS` already has an entry for that question. Apply it with
`scripts/questionnaire/apply_rubric.py`, which skips rows a person already
filled in and is safe to re-run.

Your job is the three things the script cannot do: decide whether a decline is
excused, write the rationales, and notice when the sheet has drifted.

## The loop

The sheet id comes from `~/livable-crd-grading/sheet-id`, so no environment
variable is needed for the read-only steps.

```bash
# 1. What needs grading
python3 scripts/questionnaire/apply_rubric.py <Subject> \
  --rationales ~/livable-crd-grading/<subject>-rationales.json \
  --excused ~/livable-crd-grading/<subject>-excused.json

# 2. Stub the missing rationales, write them, merge back into the file
python3 scripts/questionnaire/apply_rubric.py <Subject> \
  --rationales ~/livable-crd-grading/<subject>-rationales.json \
  --stub-rationales /tmp/new.json

# 3. Apply. Interactive OAuth, so the user runs this one with a ! prefix.
QUESTIONNAIRE_SUBMISSIONS_SHEET_ID=... \
python3 scripts/questionnaire/apply_rubric.py <Subject> \
  --rationales ... --excused ... --apply
```

Step 3 backs up every tab to `~/livable-crd-backups/` first, and refuses to run
while any row lacks a rationale.

## Declines: the judgement the script defers to you

"Decline to answer" is not one position. Grade it `F` **only** where nothing
explains it. Leave the Grade cell **blank** (add the Key to the excused file)
where either holds:

- the candidate explained the decline in that topic's `-GEN` comment box, which
  lives on the raw tab and not on the grading tab, so you have to go and read it
- they answered the rest of that topic solidly, so the position is obvious

Candidates reach for "Decline" when the answer menu does not fit, and grading
that the same as opposition penalises them for the questionnaire's limits.

## Writing rationales

Two sentences. Restate what the answer commits to, then say why the grade lands
where it does. No dashes of any kind, no acronyms (write "all ages and
abilities", never "AAA"), and never mention another candidate.

**Vary the wording on every single row**, including the twenty-plus whose answer
is just "Yes". A pasted line across rows is the failure mode here.

## Before you report success

- **There is no `A+`, `B+` or `D`.** The scale is exactly `A, B, C, C-, F`
  (`VALID_GRADES`, mirrored in four places). Anything else is refused at sync.
- **Never type `N/A` to mean "not graded".** `categoryFormula` in
  `appsscript/Code.gs` filters on `H<>""`, so `N/A` enters the denominator and
  then fails the `MATCH` inside it, scoring 0, which is `F`. Only a blank cell
  drops a row out of the rollup. `N/A` means "this question does not apply to
  this candidate", nothing else.
- **Check the topic has weights.** The letter rollup divides by
  `SUMPRODUCT(filter * weightCol)`. If the `Question Registry` weights for that
  subject are blank the category grade renders empty however well you grade it,
  and Climate is in exactly that state. Say so rather than reporting the topic
  as finished. Housing is the exception; it is scored in points.
- `ANSWER NOT IN RUBRIC` in the output means a Tally option got reworded. Add
  the entry to `rubrics.py`; do not grade that row by hand and move on.

## Adding a question

New closed question: add it to `RUBRICS` in `rubrics.py` with a `notes` string
saying why the letters fall where they do. Free-text questions get no entry and
are graded by a person.

Precedents worth keeping consistent, all recorded in `rubrics.py`: a conditional
yes is `B`; a named, testable condition is `B` but "case by case" is `C`; a plain
`No` is `C-` on a governance or conduct question and `F` on one about
infrastructure, land use or funding; "Unsure" is ungraded.

## Never

Do not add, rename, reorder or remove columns or tabs on the submissions sheet.
Column positions are hardcoded as indexes in at least three files, and the sheet
is live-wired to Tally and the Apps Script. Reads are fine and expected.
