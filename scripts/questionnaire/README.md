# Questionnaire committee tooling

Scripts that build and maintain the candidate-questionnaire working sheet: they
collect every submitted question into one master list, categorise it, and generate
per-member voting tabs so the committee can score questions asynchronously.

These write to a working Google Sheet. They do **not** touch the Jekyll site or any
published data: `_data/candidates.yml` and the scorecard pages are unaffected.

Unlike the rest of `scripts/`, these need third-party packages (`gspread`) and
interactive Google auth, so they are not run in CI.

## Sheet layout

| Tab | Role |
|---|---|
| `Form Responses 1` | Public intake form. Source, read-only. |
| `HFL Questions` | Homes for Living submissions. Source, read-only. |
| `Victori'Us Questions` | Arts & culture submissions. Source, read-only. |
| `RUSH Questions` | RUSH Initiative climate submissions. Source, read-only. |
| `All Refined Questions` | **Master.** Every question, categorised, plus vote aggregates. Generated. |
| `Vote - <Name>` | One per committee member. Generated. |
| `Summary` | All counts and roll-ups. Generated. |
| `Reworded Questions` | Post-voting. Every question that changed, and why. Generated. |
| `Finalized Questions` | Post-voting. **The shipping set.** Export as CSV for Tally. Generated. |
| `Excluded Questions` | Post-voting. Every question with no shipping row, and why not. Generated. |

`All Refined Questions` holds one native table, **`Questions`** (`A1:X`): `A–J`
question data, `K–X` vote aggregates.

`Summary` holds six, side by side, all live formulas:

| Table | Range | Shows |
|---|---|---|
| `CategoryCounts` | `A:D` | Questions per category, with strong / excluded splits |
| `Totals` | `F:G` | Question count, committee size, completion percentage |
| `VoterProgress` | `I:P` | Per-member progress, exclude ticks, comments, mark ticks |
| `StatusMix` | `R:T` | Distribution across `STRONG` / `MAYBE` / `WEAK` / `EXCLUDE` / unvoted |
| `FlagTotals` | `V:Y` | Questions carrying each criterion flag, and total ticks |
| `Dispositions` | `AA:AD` | Questions marked *needs rewording* / *shouldn't be graded* |

### Official categories

`General` · `Transit` · `Housing` · `Climate` · `Arts` · `Rolling & cycling` ·
`Walking` · `Healthcare access` · `Reconciliation` · `Governance`

Plus `Housekeeping`, **internal only**, used for logistics questions (fundraising,
viability, photos). Not published on the scorecard.

The `Category` column is a dropdown restricted to this list, so the taxonomy can't
drift through typos. Edit the list in `aggregate.py` and re-run `tables.py` to change it.

## Setup

One-time, on your own machine.

```bash
python3 -m venv ~/.venvs/sheets
~/.venvs/sheets/bin/pip install -r scripts/questionnaire/requirements.txt
```

Google credentials, needed once:

1. In the Google Cloud console, enable the **Google Sheets API** and **Google Drive API**.
2. **Credentials → Create credentials → OAuth client ID → Desktop app**.
3. Save the downloaded JSON to `~/.config/gspread/credentials.json` (`chmod 600`).
4. If the OAuth consent screen is in *Testing*, add your own address under
   **Audience → Test users**, or the first run fails with `Error 403: access_denied`.

The first script run opens a browser once and caches a refresh token to
`~/.config/gspread/authorized_user.json`. Later runs are non-interactive.

**Never commit either file.** They live outside the repo for that reason. The
refresh token is the more sensitive of the two: it grants ongoing access to your
Google account's sheets.

## Configuration

The spreadsheet key comes from the environment, never from source; the sheet
contains submitter email addresses and this repo is public. Same convention as
`CANDIDATES_CSV_URL` in [`scripts/sync-candidates.py`](../sync-candidates.py).

```bash
export QUESTIONNAIRE_SHEET_ID=<the key from the sheet URL>
```

The key is the segment between `/d/` and `/edit` in the sheet URL.

## Scripts

### `aggregate.py`: preview, read-only

```bash
python3 scripts/questionnaire/aggregate.py
```

Prints the question count per category and lists flagged near-duplicates. Writes
nothing. Run this first to sanity-check categorisation after editing the source tabs.

It's also the shared data layer imported by the other two, and it holds the two
things you're most likely to want to edit:

- `FR_OVERRIDES` / `VU_OVERRIDES`: questions whose submitted topic was wrong. Each
  carries a reason string that gets written into the sheet's `Notes` column, so every
  recategorisation is auditable.
- `DUPES`: near-duplicate clusters, also surfaced in `Notes`.

### `tables.py`: rebuild the master

```bash
python3 scripts/questionnaire/tables.py
```

Clears `All Refined Questions` and rebuilds it from the source tabs as native tables.
Question IDs (`FR-01`, `HFL-01`, `VU-01`, `RUSH-01`) are positional, stable as long as
the source tabs keep their row order.

**Once voting has started, use `append.py` instead.** This wipes votes.

### `append.py`: add new questions mid-vote

```bash
python3 scripts/questionnaire/append.py --dry-run   # preview
python3 scripts/questionnaire/append.py
```

The non-destructive path for a source tab that has grown. It writes only the rows
that aren't in the master yet, at the bottom, then extends the `Questions` table, the
`Status` colour rules and every `Vote - <Name>` tab to match. Existing rows are never
rewritten, so hand edits to categories and question text survive, and no votes are lost.

New questions land below the existing ones because `build_rows()` reads the source tabs
in a fixed, append-only order: a new tab goes on the *end* of `SOURCES`, never in the
middle, or its rows would interleave and shift every voter tab out of alignment.

It aborts if the master's IDs are no longer a prefix of what the source tabs produce.
That means rows were reordered, renumbered or deleted at source, where appending would
pair votes with the wrong questions; rebuild with `tables.py` + `voting.py` instead.

Handles growth only. Removing or replacing a question needs `resubmit.py` (below) or a
full rebuild. Run `summary.py` afterwards to repoint the roll-ups at the longer range.

### `resubmit.py`: swap a source tab's questions after voting closes

```bash
python3 scripts/questionnaire/resubmit.py --dry-run   # preview
python3 scripts/questionnaire/resubmit.py
```

Written for one event and kept as the record of it: on 2026-08-09 Victori'Us resubmitted
their whole arts set through the public intake form, replacing the eleven questions the
committee had already voted on with twelve new ones. Neither of the other two paths fits
that. `append.py` only appends, and aborts anyway because the twelve arrived at the *top*
of `Form Responses 1` and renumbered every `FR-*` ID; `tables.py` + `voting.py` express it
but cost every vote on the sheet, and voting was finished.

So it does the swap surgically: the submissions move into `Victori'Us Questions` and out of
`Form Responses 1`, the master's VU block is rewritten in place and grown by one row, and
each voter tab gets the same one inserted row with its twelve arts rows cleared. `FR-*`,
`HFL-*` and `RUSH-*` never move relative to their votes, so only the arts votes are lost,
which they had to be: they were cast on questions that no longer exist.

Every tab it overwrites is dumped to `~/livable-crd-backups/questionnaire-<stamp>.json`
first. **The old arts votes are in that file and nowhere else.**

It asserts its way in rather than searching: the master must still hold `VU-01`..`VU-11` at
rows 84-94, each submission must still be findable by timestamp, and after the source edits
`build_rows()` must still reproduce every non-arts ID. Any of those failing stops the run.

The reason the swap was this cheap is that the new set mapped 1:1 onto the old one in
submission order, so `VU-01`..`VU-11` kept their subject matter and only `VU-12` was new.
That is what let `finalize.py`'s `origins` lists survive. A resubmission that reorders or
drops questions would not have that property and would need `FINAL` rewritten too.

### `voting.py`: build voter tabs

```bash
python3 scripts/questionnaire/voting.py "Alice" "Bob" "Carla"
```

Creates or rebuilds a `Vote - <Name>` tab per member and writes the aggregate
formulas into master columns `K–V`.

**Always pass the full committee list.** Named tabs that already exist are cleared
and rebuilt, so re-running with one name wipes that person's votes and leaves the
aggregates referencing only them.

### `finalize.py`: build the questionnaire, after voting

```bash
python3 scripts/questionnaire/finalize.py --dry-run
python3 scripts/questionnaire/finalize.py --csv ~/finalized-questions.csv
```

Run once grading is finished. It applies the committee's dispositions (the `Needs
rewording` and `Shouldn't be graded` ticks, the EXCLUDE votes and, mostly, the free-text
comments) and rebuilds three tabs:

- **`Reworded Questions`**: one row per question that changed, with its original text
  beside the new one, who asked for the change, and the argument for it. Dropped
  questions are listed here too, with their reason. This is the audit trail: nothing
  changes without a comment behind it.
- **`Finalized Questions`**: the shipping set, one row per question a candidate will see.
  Flat enough to export straight to CSV and import into Tally.
- **`Excluded Questions`**: the other side of the same ledger, one row per master question
  that has no shipping row of its own, with the scores it got, the voter comments verbatim,
  and why it is not in the questionnaire. See below.

The editorial decisions live in `FINAL` in the script, in question order, so a
disagreement about one question is a one-line diff rather than a re-run of the vote.
Submitter, source tab and municipality scope are read from the master at run time and
never restated in the script; that's what keeps submitter emails out of this repo.
`--csv` writes the same rows to a path of your choosing; send it somewhere outside the
repo for the same reason.

`Finalized Questions` carries one hand-maintained column, **`Added To Tally Questionnaire`**:
a checkbox ticked as each question goes into the Tally form. It is the only thing on
either tab that isn't generated, so `finalize.py` reads the existing ticks back before it
clears the tab and re-applies them by `Ref`. A question whose `Ref` changed, or that has
stopped shipping, comes back unticked. The column is sheet-only: `--csv` omits it, since
an empty tracking column is noise in a Tally import.

All three tabs are rebuilt wholesale on every run, and nothing else reads them, so this
is safe to re-run at any time. It never touches the master or any voter tab.

#### `Excluded Questions`

A question can be missing from the shipping set two ways, and only one of them is a
rejection:

- **Dropped**: not asked at all. The nine in `DROPPED`, each with the argument for cutting it.
- **Merged**: absorbed into somebody else's row. `Shipped instead` gives the `Ref` to read it
  under, and `Kept from` gives the master ID that ended up carrying it, which is the answer
  to "which one beat mine".

That distinction is the point of the tab. 28 of 97 questions have no row of their own, but
only 9 were actually rejected; the other 19 are in the questionnaire under another ID, and
one of them, `FR-53`, scored `STRONG`. Reading `Finalized Questions` alone, all 28 look the
same.

Reasons come from `DROPPED` for the dropped ones and from `MERGED_WHY` for the merges, which
argues each merge from the *excluded* question's side; the destination row's `why` argues it
from the surviving question's. A merge with no `MERGED_WHY` entry falls back to that
destination `why` and is listed on stdout, so it degrades to a vaguer answer rather than a
blank one. The last column carries every voter comment verbatim, so the tab cites the
committee rather than paraphrasing it.

The run now aborts if a master question appears in neither the shipping set nor `DROPPED`.
It could previously vanish from all three tabs without a word.

Re-running does **not** fold in new votes. `FINAL` is hand-authored, so grading that
lands after it was written changes nothing until someone edits it; compare the master's
`Status` column against the shipping set to see where the two have diverged.

It aborts if an origin ID in `FINAL` is missing from the master. Every one of the master's
questions must appear either in a `FINAL` row's `origins` or in `DROPPED`; the tabs are not
a filtered view of the master, so a question left out of both would vanish silently.

#### Questions with no master row

A `FINAL` row may have `origins=[]`. That is for a question that arrived too late to go
through intake, voting and the master at all: `CLI-12`, added 2026-08-13, and `WLK-05` and
`WLK-06`, added 2026-08-16. Such a row has to carry its own `question`, `options`, `qtype`
and `source`, because there is no master row to read them from, and the run aborts if
`question` or `qtype` is missing rather than shipping a blank cell to candidates. It appears
in no `Excluded Questions` bookkeeping, since it displaced nothing.

`CLI-12` is ungraded, like the other questions no committee member scored. The two walking
questions are graded anyway, by a decision made off the sheet, so `graded` is the one field
where the two cases differ.

The alternative is to put the question through `append.py` so it lands in the master properly,
which is the better path if the committee wants to score it — but it is not currently open to
a `Form Responses 1` submission. `FR-*` IDs are positional, so a new row anywhere in that tab
renumbers the block and `append.py`'s prefix check refuses the run; only a tab appended to the
end of `SOURCES` lands cleanly. Until there is one, `origins=[]` is the only route a late
question has.

#### Homes for Living ships verbatim

Homes for Living objected on 2026-08-13 to their questions having been reworded. All 25 now
ship exactly as submitted, under their own submission codes (`HFL-01`..`HFL-25`) and in
submission order, as one contiguous block of `FINAL`. Every one is `change="Unchanged"`, which
is what keeps the whole block off `Reworded Questions`, and none carries a `question` or
`options` key, so the text comes from the master, which holds HFL's own words.

Three consequences, all of them deliberate:

- The eight `HSG-*` rows that were rewrites or merges of HFL text are gone; the HFL row each
  was built on ships in its place. Those refs are also the refs that lose their
  `Added To Tally Questionnaire` tick, so the Tally form needs the same swap by hand.
- The non-HFL questions those rows had absorbed (`FR-13`, `FR-14`, `FR-15`, `FR-16`, `FR-36`)
  are absorbed into the HFL row that replaced them, so nothing is asked twice and nothing
  leaves the ledger. `MERGED_WHY` still carries the committee's argument for each merge; what
  changed is which question carries it, and each entry now says so.
- The committee's edits are reversed, not hidden. What each row lost - HFL-09's copy-paste
  error, HFL-18's `1/2/3` options, HFL-02's uncapped nine-option list, the Bill 44 and Bill 47
  framings - is stated in that row's `Notes` cell rather than fixed in its text.

The HFL tab has no question-type column, so `qtype` is the one call this file still makes on
an HFL row. Where the answer list does not settle select-one against select-all, the note says
the type was inferred and asks for confirmation, because getting it wrong changes the question.

`MUNICIPALITIES` is the questionnaire's scope: 13 jurisdictions. The CRD's three electoral
areas (Juan de Fuca, Salt Spring Island, Southern Gulf Islands) are excluded, because
they elect an electoral area director rather than a council and neither municipality-specific
question applies. `_data/municipalities.yml` still publishes all 16 on the site; who gets a
questionnaire is a separate decision, so this script does not touch it.

Only one municipality-specific block is still templated: the infrastructure funding gap, and
only for the eight municipalities in `INFRA_FIGURES`, which are the ones HFL never wrote an
infrastructure question for. The five in `HFL_INFRA` (Victoria, Saanich, Oak Bay, Esquimalt,
Colwood) ask it in HFL's wording, with HFL's figure, so a municipality whose figure is still
blank ships the generic version and is printed with `<- FIGURE NEEDED` on every run and
flagged in the `Notes` column of `Finalized Questions`. Every housing-target question is
HFL's own row; the three in `NO_TARGET` (Sooke, Highlands, Metchosin) received no provincial
target order, so they get one municipality-specific question rather than two.

The wording of the target and infrastructure questions can therefore drift between
municipalities again - HFL-18's numbered options against its siblings' lettered ones is the
existing case - and that is now HFL's call rather than a bug to fix here.

### `summary.py`: rebuild the Summary tab

```bash
python3 scripts/questionnaire/summary.py
```

Rebuilds all five roll-up tables. Committee members are discovered from the
`Vote - <Name>` tab names, so it needs no arguments and picks up changes on its own.

Everything on the tab is a live formula, so it only needs re-running when the
committee or the question set changes, not to refresh numbers. This is the only
write script that's safe to run mid-voting: it touches nothing but its own tab.

### `grading_tabs.py` + `appsscript/`: grading the submissions

**A different spreadsheet.** Everything above works on the committee's working sheet
(`QUESTIONNAIRE_SHEET_ID`). These work on Tally's submission sheet, "Submissions - 2026
Municipal Elections" (`QUESTIONNAIRE_SUBMISSIONS_SHEET_ID`): one row per candidate, one
column per form field, 236 columns wide.

Nobody grades in that tab. A multi-select question sprawls across up to 17 columns, and
Tally rewrites the tab on every submission, so grading happens on separate tabs, one per
scorecard subject, in long form: **one row per candidate per question**.

```bash
python3 scripts/questionnaire/grading_tabs.py --dry-run    # preview
python3 scripts/questionnaire/grading_tabs.py              # create the tabs
python3 scripts/questionnaire/grading_tabs.py --refresh    # re-read the form's wording
```

| Tab | Who writes it |
|---|---|
| `Raw Submissions` | Tally. Untouched. |
| `Question Registry` | Generated once, then hand-maintained. |
| `Grade - <Subject>` | `A-F` and `L` by the Apps Script, `G-I` by graders. Nine of them. |
| `Category Grades` | `A-C` by the Apps Script, the rest by graders. One row per candidate, one column per graded subject. |
| `Category Stats` | Generated, all of it. The same grid, showing each grade's underlying percentage. |
| `Sync Log` | The Apps Script. |

#### `Question Registry`

One row per graded question - 55 at present - and the single source of truth for what
gets graded and what it is worth:

`Label | Category | Question | Type | Graded | Weight | Methodology | Raw columns | Notes | Owner`

Weight lives here, once per question, rather than repeated on every candidate's row. The
block at `J1:L` totals the weights per category; each category should reach 100%.

`Category` is why this tab exists rather than a regex over the header row. Prefixes don't
map onto subjects on their own: Governance owns the `GOV-*` block and the two `REC-*`
reconciliation questions, whose codes were left alone when the topic was folded in.
`PREFIX_CATEGORY` and `CATEGORY_OVERRIDE` in the script seed the column; it is
authoritative afterwards, and `move_question.py` is what changes it safely.

Housing rows carry **no weight**, and that is not an omission - see "Housing is scored in
points" below. `Check setup` skips the 100% test for them. Arts rows are the other way
round: they are scored rather than graded too, but they carry ordinary weights that still
have to total 100%, and `Check setup` still says so.

`Owner` is who submitted the question, so a grader who needs to check intent knows whom
to ask. Populated from the `Finalized Questions` tab of the committee sheet, matching on
question text rather than `Ref`: the Tally form renumbered several questions, so the two
sheets' refs disagree (the committee sheet's `HFL-09` is the parking-minimums question;
the form's is non-market housing). Questions that reached the form without going through
that tab are blank and filled in by hand.

`Methodology` is optional and hand-maintained: a grader's own description of how a
question is scored, sitting beside the `Weight` that says what it is worth. Nothing
generated writes it, and `--refresh` leaves it alone with `Category`, `Graded`,
`Weight` and `Owner`.

**It is published.** `sync-questionnaire.py` carries it into `_data/questions.yml` as
`methodology`, and `/questionnaire/` renders it under the question it belongs to,
headed "How this is graded" — or "Why we ask this" on the one ungraded question that
has text there. Write it for a reader who does not work here: it is the coalition's
grading rule in the partner's own voice, on a public page, beside the question a
candidate answered. A blank cell publishes nothing at all, which is the case on
eighteen of them.

A bare web address in the cell becomes a link on that page (`autolink` in
`_plugins/autolink.rb`), shown as its domain and opening in a new tab. Paste the
address on its own — no Markdown, no HTML, neither of which is interpreted — and put
it where the sentence would take a citation. Everything else in the cell is escaped
and published as typed.

Anything added to this tab goes in column **N or beyond**: `A:J` is the schema both
scripts read by position, and `K:M` holds the tally block.

**Inserting a column into `A:J` is not a one-cell edit.** Every grading row's `Owner`
and every housing row's `Max points` is a `VLOOKUP` into the registry *by column
number*, and Sheets widens such a lookup's range on insert without ever renumbering
it - so the lookup goes on pointing at whatever now sits in that position, silently.
`Methodology` moved `Owner` from `I` to `J` and `Max points` from `M` to `N`, which
meant rewriting 3,421 `Owner` lookups across eight tabs and 775 `Max points` lookups on
`Grade - Housing`. `add_methodology.py` is that migration, kept as the record of it.
The next such insert is the same job: change `REGISTRY_HEADERS` and
`REGISTRY_OWNER_COLUMN` here and in `Code.gs`, the `R_*` indexes in
`sync-questionnaire.py`, and rewrite both lookup families on every grading row.

`--refresh` rewrites `Question`, `Type`, `Raw columns` and `Notes` from the current form,
for when wording or columns changed. It never touches `Category`, `Graded`, `Weight`,
`Methodology` or `Owner`.

#### Grading tabs

`Key | Candidate | Municipality | Label | Question | Answer | Owner | Grade | Weight | Rationale | Grader | Graded at | Answer hash`

`A-G` and the hidden hash in `M` are generated and carry an edit warning. Graders fill
`Grade` (a dropdown of the five grades the site can render), `Rationale`, and nothing else;
`Grader` / `Graded at` stamp themselves.

Two subjects take a number in `H` instead of a letter, because the partner orgs who own
them score rather than grade - see "Housing is scored in points" and "Arts is scored 0-3"
below. Every tab is the same thirteen columns either way.

`Owner` and `Weight` are `VLOOKUP`s into the registry rather than copies, so correcting
either there corrects every grading row at once, including rows already graded.

`Key` is `<Submission ID>|<Label>`, and it is what makes the sync safe: rows are matched by
key, never by position.

#### "Other" on a multi-select

Tally gives an `Other` option no column of its own. Its checkbox column says only that
it was ticked; what the candidate actually typed is joined into the *question's* own
column, comma-separated, among the labels of every other option they ticked and in no
fixed position. Nothing marks it apart from a label.

So `buildAnswer` subtracts the ticked labels from that column and what is left is what
they wrote, which the `Selected:` line carries as `Other: <their words>` rather than a
bare `Other, please specify.`. Three questions have such an option - `HFL-04`, `ART-05`
and `ART-08` - and 23 answers across them were affected.

Subtraction removes each label's **first** occurrence only, so a candidate who quotes an
option inside their own text (`Mandated requirements should be carefully designed.`, with
*Mandated requirements.* also ticked) keeps their sentence: Tally joins the standalone
label in first. A tick with nothing typed falls back to the option's own label rather
than reading `Other:` and then stopping.

The question's own column is still reproduced verbatim on the answer's first line, as it
is for every multi-select, so the two lines say the same thing twice. That is the older
behaviour and is left alone: changing it would change the answer hash on every
multi-select row on every tab and flag them all as drift.

#### Housing is scored in points

Two subjects are scored rather than graded, on the rubrics their partner orgs already use.
This is the first; "Arts is scored 0-3" below is the other, and they have almost nothing in
common beyond `H` holding a number.

Homes for Living grade housing on their own rubric: every question is worth a set number
of points, the municipality-specific ones are only asked where they apply, and a candidate
gets **one cumulative grade** from their share of the points available to them rather than
a letter on each answer.

It is also the one tab carrying a row nobody was asked: `HFL-INC`, Homes for Living's
score for a sitting councillor's record over the term just ending, worth 30% of the
housing grade on its own - and the whole of it for a sitting incumbent who never returned
the questionnaire. See "The incumbent record, and the 70/30 split" below; everything in
this section describes the questionnaire's 70%.

`Grade - Housing` is the same thirteen columns as every other grading tab. Two of them
mean something else on it, and their headers say so:

| Column | Letter-graded tab | `Grade - Housing` |
|---|---|---|
| `H` | `Grade` - a letter from the dropdown | `Score` - a whole number, validated -8 to 8 |
| `I` | `Weight` - `VLOOKUP` of the registry's `Weight` | `Max points` - `VLOOKUP` of the registry's `Max points` |

Everything else is unchanged: same width, same indices, same `Rationale`, same
`Grader` / `Graded at` stamps, same hidden hash.

`Category Grades` bands the ratio instead of averaging letters:

```
SUM(scores) / SUM(maximums, where the score is not blank)
   >= 85% A   >= 70% B   >= 60% C   >= 50% C-   below that F
```

**The `where the score is not blank` is what makes one formula work everywhere.** `HFL-11`
is asked in ten municipalities and `HFL-12` in five, but the Apps Script fans every
question out to every candidate, so a Sooke candidate has an `HFL-11` row with nothing in
it. Leave it unscored and it drops out of the total *and* out of the maximum, so they are
graded out of the 54 they were asked rather than the 66 somebody in Victoria was.

The same rule is why a question a candidate **did** answer must never be left blank: it
would quietly shrink the denominator and flatter them. `sync-questionnaire.py` refuses to
publish the topic when that happens and says which question it was. A zero is a score and
counts; blank means "not scored".

#### Housing, and only housing, scores below zero

Homes for Living's rubric has options that *cost* a candidate points rather than earning
none - `HFL-12`'s five options score 5, 1, -2, 0 and 1 - so a housing answer can be worth
less than no answer at all, and a housing score can be negative. No other tab's can: a
letter tab has no numbers in `H`, and Victori'us score 0-3 with nothing below.

Three places carry that, and they are the three to change together:

- **The column's validation**, `SCORE_FLOOR` in `grading_tabs.py`. It mirrors
  `SCORE_CEILING`, so `H` on `Grade - Housing` takes -8 to 8, and a scale tab's floor stays
  0. One floor for the whole column rather than each question's own, for the same reason
  there is one ceiling: validation runs down a column and cannot know which question a row
  holds, so it is a typo guard, not the rubric. What any one answer may cost is Homes for
  Living's call as they score the row.
- **The `Category Grades` band**, `MAX(points/maximum, 0)` in both `points_rollup_formula()`
  and `pointsCategoryFormula()`. A negative total lands below the bottom threshold, `MATCH`
  returns `#N/A`, and the `IFERROR` around it would leave the cell **blank** - which on that
  tab means "not graded yet". The candidate who had most clearly earned an `F` would be the
  one showing no grade at all. The floor pins them to `F` instead.
- **What the site publishes**, `subject_score()` in `sync-questionnaire.py`. Neither the
  points nor the percentage is floored: they are the arithmetic of what the graders typed,
  and a candidate page reads `-3 of 66 points (-5%)` under an `F`. Only the letter stops.

A negative score is a score, so it counts in both the total and the maximum, exactly as a
zero does. Blank still means "not scored" and still drops out of both.

#### The incumbent record, and the 70/30 split

Homes for Living also score what a sitting councillor actually did about housing
this term, not only what they say they will do next one. That score lives on
`Grade - Housing` as one more row per incumbent, labelled **`HFL-INC`**, scored in
column `H` out of the `Max points` in `I` like every other housing row.

It is the only row on any grading tab that is not a question. Nobody was asked it,
so it has no `Raw columns` on the registry, and column `F` carries a fixed line
saying as much rather than a blank that would read as an unanswered question.
`readRegistry` in `Code.gs` lets that one label through without a column span;
every other row without one is still skipped, which is what stops a half-filled
registry row fanning empty answers out to everybody.

**It is not summed in with the questions.** The record carries 30% of the housing
grade on its own and the questionnaire carries the other 70%, whatever each is
scored out of, so the two shares are worked out against their own maxima and
blended:

```
0.7 x (questionnaire points / questionnaire maximum)
  + 0.3 x (record points / record maximum)
```

Adding the record's points to the total instead would give it whatever share its
points happened to be of the sum - a different number for every candidate, and
30% for none of them. The formula is `points_rollup_formula()` in
`grading_tabs.py` and `pointsCategoryFormula()` in `Code.gs`, which render the
same string; both still floor the ratio at 0 for the same reason they always did.

A candidate with no scored record is graded on the questionnaire alone, at 100%.
That is every challenger, every incumbent nobody has scored yet, and - by the
same branch - an incumbent whose record was scored with no `Max points` beside
it, which `Grading > Check setup` reports and `sync-questionnaire.py` refuses to
publish.

#### The incumbents who never replied

The record is a fact about a term in office, not about a questionnaire, so it is
scored for **every** sitting incumbent and not only for the ones who answered.
The sweep therefore creates an `HFL-INC` row for each of them - 42 of the 66 on
the roster today have no submission at all - and for those candidates the blend
collapses the other way: there is no questionnaire for the 70% to be a share of,
so the record is 100% of the housing grade. The same `MAX(IF(...))` carries both
collapses, one per maximum being zero.

Those candidates have no submission id, so their rows are keyed off the roster
instead: `INC-` then their name and municipality, which is stable run to run and
cannot be mistaken for one of Tally's seven-character ids. The key is the only
thing about them that is different; the row is the same thirteen columns, scored
in the same column H, out of the same `Max points`.

They get a `Category Grades` and a `Category Stats` row too, because a score with
nothing to roll up to is not a grade. On that row **every subject but Housing
reads `N/A`** - not blank, which on that tab means "not graded yet" and would be
a promise nobody is going to keep. It is a formula rather than typed text, so the
row stays blank all the way across until Homes for Living score the record, and
a partner org who does grade one of these candidates from the public record types
their letter straight over it.

The municipality is written the way the Tally form spells it ("Oak Bay", not
`oak-bay`), taken from the submissions already on the sheet and title-cased where
no one has submitted from that municipality yet. That is not cosmetic: the
housing rollup finds a candidate's record row by name **and** municipality, so a
record filed one way beside answers filed the other counts towards nothing.

One case needs a human. A roster row is only ever created for somebody with no
submission, but the sweep is append-only, so an incumbent who returns the
questionnaire *after* being given one ends up with two rows and two identities on
this sheet. `Grading > Check setup` names them, `sync-questionnaire.py` warns and
publishes the submission, and the fix is to copy the record score onto the
submission's own `HFL-INC` row and delete the `INC-` rows from `Grade - Housing`
and `Category Grades`.

#### Who counts as an incumbent

Nothing in this spreadsheet says, and nothing should be added to it that does.
The coalition tracks it in the candidate tracking sheet, whose id is a capability
over contact details, and the website republishes the same fact as `standing` in
[`_data/candidates.yml`](../../_data/candidates.yml) - a public file in a public
repository, regenerated from that sheet daily by CI.

So `Code.gs` reads it from there, over `raw.githubusercontent.com`, cached for six
hours. No credential, no second spreadsheet, and it follows the tracking sheet on
its own. A standing starting `incumbent` is sitting; `ex-incumbent-councillor` is
a former one and gets no record row, because the record is of a term they are not
serving.

Two failure modes, and both are quiet rather than wrong:

- **The roster cannot be read.** `incumbentIndex()` returns null, the sweep creates
  no `HFL-INC` row for anybody that run, and `Sync Log` says so. Appending them to
  everyone on a bad read would be far worse: the rows are append-only, so a wrong
  one has to be deleted by hand.
- **A submission matches no confirmed candidate.** Candidates type their own name
  into Tally, so a spelling the tracking sheet does not carry cannot be looked up
  at all. They get no record row, `Sync Log` names them, and `Grading > Check setup`
  lists them as a problem. All 63 submissions match today.

#### Switching the incumbent record on, in order

```bash
# 1. The HFL-INC registry row, the -10..10 validation on column H, and the
#    blended rollup on every Category Grades row that already exists.
python3 scripts/questionnaire/grading_tabs.py --dry-run
python3 scripts/questionnaire/grading_tabs.py
```

2. Paste `appsscript/Code.gs` into the sheet's Apps Script editor and save, then
   **Deploy > Manage deployments > (pencil) > Version: New version**. Until this
   is done no `HFL-INC` row is created for anybody: step 1 writes the registry row
   and the formula, and the Apps Script is what fans the row out.
3. Homes for Living type the record's **`Max points`** into column `N` of its
   registry row, and `Homes for Living` into its `Owner`. The script writes
   neither: a maximum is the rubric, and an owner is a claim about who graded it.
   Until the maximum is there, no incumbent's record counts towards their grade.
4. `Grading > Sync now`, which appends one `HFL-INC` row per sitting incumbent -
   24 who submitted and 42 who did not, and a `Category Grades` and `Category
   Stats` row for each of that second group.
5. `Grading > Check setup`. It now also reports the roster, the record's missing
   maximum, and any submission it could not find on the roster.

Column `H`'s validation is one range for the whole column, because validation runs
down a column and cannot know which question a row holds. It is a typo guard, not
the rubric. `points_ceiling()` sizes it from the maxima actually on the registry,
so a `Max points` the partner org raises widens the column on the next run of
`grading_tabs.py` - which is the run that has to happen before a grader can type
the top of a scale they have just widened. `SCORE_CEILING` is the floor of that
calculation rather than the answer, so a maximum deleted from the registry never
narrows the column under a grader part-way through typing.

`HFL-INC` went from 8 to 29 the day after it shipped, and `-29` to `29` is what
the column takes today.

#### `Max points` on the registry

Column **N** of `Question Registry`, past the `K:M` weight tally, on the same "anything
after `A:J` goes in N or beyond" rule as everything else added to that tab. One number per
question, and the single thing that decides what a question is worth for every candidate.

`grading_tabs.py` seeds it from Homes for Living's workbook - 8, 8, 6, 5, 3, 6, 3, 2, 6, 7
for `HFL-01`-`HFL-10`, then 6 and 6 - and never overwrites a value that is already there.
Their Questions and Cross Check tabs both say `HFL-12` is worth 5, but every scoring tab
that produced a real percentage divides by 6, and those are the totals they have published.

`Grading > Check setup` flags a scored question with no maximum, because a blank one lets
the question's score count towards the total while adding nothing to what that total is
out of.

#### Arts is scored 0-3

Victori'us grade arts on their own rubric too, and not the same way. Every question is
scored **0 to 3** against their criteria and carries the ordinary `Weight` every
letter-graded question does, and the topic grade is the weighted average of those scores
read as a percentage.

`Grade - Arts` changes in exactly one place. `H` stops being a letter and becomes a score:

| Column | Letter-graded tab | `Grade - Arts` |
|---|---|---|
| `H` | `Grade` - a letter from the dropdown | `Score / 3` - a whole number, validated 0-3 |
| `I` | `Weight` - `VLOOKUP` of the registry's `Weight` | unchanged |

`I` being unchanged is the point: arts weights its questions like everything else, they
still have to total 100%, and `Grading > Check setup` still checks that they do. Nothing on
the registry moves, and `Max points` stays empty on every `ART-*` row.

It is rendered to **two decimal places**, unlike a letter tab's whole percent. The arts
weights are sixths and fifteenths, and eight of them rounded to whole percents read
7 + 17 + 13 + 10 + 17 + 10 + 10 + 17 = 101% of a topic. `/questionnaire/` already publishes
them to two places from the registry, and the candidate pages take theirs from this column,
so the two would disagree on the same number.

`Category Grades` bands the weighted average:

```
SUM(score x weight) / (3 x SUM(weight, where the score is a number))
   >= 90% A   >= 80% B   >= 60% C   below that F
```

**Not the same bands as housing.** Victori'us have no `C-` at all and start `A` and `B`
higher, at 90% and 80%. Both band tables are each org's own, copied from their own workbook.

**The arts table moved on 2026-09-22**, at Victori'us' request: `A` from 86% to 90% and `B`
from 70% to 80%, with `C` and `F` left where they were. Changing it is two edits and a
rerun - `SCALE_BANDS` in `grading_tabs.py` and in `appsscript/Code.gs`, then
`grading_tabs.py` to rewrite the arts cells on `Category Grades` that already exist, then
paste `Code.gs` in so new rows are written with the new table. `refresh_scored_rollup()`
rewrites a cell only while it still holds a formula, so a letter a grader typed over the
rollup is left alone and reported. No score changes, and an arts letter already published
can still fall a band, so resync the site afterwards.

Two details of the formula are deliberate, and both are worth leaving alone:

- The score is read through `MATCH` into `{0;1;2;3}` rather than multiplied. `SUMPRODUCT`
  evaluates the whole column, and a column of mostly-empty cells cannot be multiplied - one
  `""` anywhere in it and the arithmetic is `#VALUE!` before the filter gets a say. The
  letter rollup reads a letter through `MATCH` for the same reason.
- `ISNUMBER`, not `<>""`, decides whether a row counts. Three rows on the tab still held a
  letter from the pass that graded the first candidate before this rubric arrived; they are
  left where they are rather than deleted, and `ISNUMBER` keeps them out of the weight they
  would be divided by as well as out of the total. A stale letter therefore scores nothing
  and drags nothing down. `grading_tabs.py` prints each one it finds.

`sync-questionnaire.py` publishes the weighted percentage and **not** a running total: the
raw scores do add up, but that total is unweighted and would contradict the percentage
beside it. Each question publishes its own `2 / 3` and its weight, and a candidate's page
reads `87% weighted score across 8 questions`.

#### Switching arts over, in order

```bash
# 1. The H header, the 0-3 validation, and Category Grades' arts rollup.
#    Nothing else on the tab moves, and no registry cell changes at all.
python3 scripts/questionnaire/grading_tabs.py --dry-run
python3 scripts/questionnaire/grading_tabs.py
```

2. Paste `appsscript/Code.gs` into the sheet's Apps Script editor and save, then
   **Deploy > Manage deployments > (pencil) > Version: New version**. Saving is enough for
   the daily trigger and the menu, which always run the latest code; the web app Tally
   posts to runs the deployed version and needs the new one.

   Needed for every `Category Grades` row appended from here on: the old formula reads a
   0-3 score as a letter, matches nothing, and bands the resulting zero to `F`. The rows
   already there are fixed by step 1.
3. `Grading > Check setup` in the sheet. Arts is checked exactly as it was - its weights
   still have to total 100%.
4. Tell Victori'us where to type: column `H` of `Grade - Arts`, one row per candidate per
   question, a whole number 0-3. The three cells that still hold a letter are named in
   step 1's output and want retyping as scores.

#### `Category Stats`: the percentage behind each letter

A band is a wide thing to be inside. Two candidates both reading `A` on housing
can be 85% and 99%, and `Category Grades` cannot show the difference, because a
letter is all it holds. Somebody choosing between two `A` candidates wants that
difference, so it has a tab of its own.

The same grid as `Category Grades` - `Key | Candidate | Municipality`, then one
column per graded subject - with each cell holding the figure that subject's
letter was banded from, to two decimal places. No deploy checkboxes: nothing on
this tab is published and nothing on it gates anything.

**The columns are not all the same measure**, and the tab is not worth reading as
if they were:

| Subject | What its percentage is |
|---|---|
| Housing | Points earned over points available, with the incumbent record blended in at its 30% |
| Arts | The weighted average of the 0-3 scores, as a share of a straight 3 |
| Everything else | Where the weighted average sits on the A-F scale: `A` 100%, `B` 75%, `C` 50%, `C-` 25%, `F` 0% |

The first two are shares of something a candidate could have earned. The third is
a position on a scale, and its usefulness is narrower but real: it is the
unrounded number the letter was rounded from, so two candidates who both round to
`B` rarely share it.

Every figure is the rollup's own expression with the banding taken off, which is
enforced rather than promised: `points_ratio()`, `scale_ratio()` and
`letter_ratio()` are the fragments both the letter and the percentage are built
from, in `grading_tabs.py` and in `Code.gs` alike, and the four renderings are
diffed against each other rather than kept in step by hand.

Two consequences worth knowing:

- **A typed-over letter is not reflected here.** `Category Grades` is meant to be
  overridden - a partner org typing their own top-level call over the rollup is
  the intended use - and this tab goes on showing what the question-level grading
  computes. That is the point of it, but it means the two can disagree, and where
  they do, the letter is the coalition's and this is the arithmetic.
- **A blank cell means nothing has been graded**, not 0%. An ungraded subject
  divides by zero and the `IFERROR` blanks it, exactly as the letter blanks.

`grading_tabs.py` creates the tab and backfills every candidate already on
`Category Grades`; `ensureStatsRows` in `Code.gs` appends each new submission's
row alongside its `Category Grades` one. Re-running the script levels the two
tabs again and rewrites any formula that has fallen behind, and leaves anything
somebody typed where it is, reporting it.

#### `move_question.py`: changing a question's subject

Changing the `Category` cell alone strands grading work: `syncAll` keys rows per tab, so
the question appends a fresh batch of blank rows to its new `Grade - <Subject>` tab and
abandons the answers, grades, rationales and hashes on the old one.

```bash
python3 scripts/questionnaire/move_question.py HFL-12 --to Housing            # preview
python3 scripts/questionnaire/move_question.py HFL-12 --to Housing --apply    # do it
```

It carries `Grade`, `Rationale`, `Grader`, `Graded at` and the answer hash across,
re-derives the `Owner` and `Weight` lookups for the rows they land on, deletes the rows it
copied, and rebalances the weights of whatever is left in the old category. Every tab is
dumped to `~/livable-crd-backups/` before the first write.

The routing itself needs no script change: `readRegistry` in `Code.gs` takes a question's
category from the registry's `Category` cell and nothing else, so the moment that cell says
`Housing` the Apps Script stops sending the question to `Grade - Governance`.

#### Switching housing over, in order

```bash
# 1. HFL-12 joins Housing. Preview, then --apply.
python3 scripts/questionnaire/move_question.py HFL-12 --to Housing
python3 scripts/questionnaire/move_question.py HFL-12 --to Housing --apply

# 2. Max points on the registry, the H/I headers and validation, column I on every
#    row that predates the rubric, and Category Grades' housing rollup.
python3 scripts/questionnaire/grading_tabs.py --dry-run
python3 scripts/questionnaire/grading_tabs.py
```

3. Paste `appsscript/Code.gs` into the sheet's Apps Script editor and save. Needed for
   everything appended *after* this point - a new submission's housing rows, and any
   candidate who gets a `Category Grades` row from here on.
4. `Grading > Check setup` in the sheet. It now checks that every scored question has a
   `Max points` instead of that the category's weights total 100%.
5. Tell Homes for Living where to type: column `H` of `Grade - Housing`, one row per
   candidate per question, the number out of the `Max points` beside it. Sorting the tab
   by `Candidate` puts each person's twelve rows together.

Step 2 is what fixes the rows that already exist. The Apps Script writes column `I` only
on rows it appends - deliberately, so a sync never overwrites a grader - so it will never
revisit the 264 housing rows that were already there, or re-touch the `Category Grades`
cells it wrote with the old letter-average formula. A `Category Grades` cell holding a
letter somebody typed is left alone and reported rather than overwritten.

#### The Apps Script

`appsscript/Code.gs` runs inside the spreadsheet and fans submissions out into those tabs.
Three ways in:

- **`doPost`** - Tally's webhook, ~1 second after a candidate submits. It builds the rows
  from the webhook's own JSON and never reads `Raw Submissions`, because Tally posts the
  webhook and writes that tab on independent paths: waiting for the row to appear used to
  cost up to 20 seconds of every submission.
- **`timerSync`** - every 5 minutes. Reconciles what the webhook wrote against the sheet,
  and appends anything the webhook missed entirely. Exits in under a second when there is
  nothing to do, which keeps it inside the 90 min/day trigger runtime a consumer Google
  account gets.
- **`Grading > Sync now`** - a menu item, for a human who doesn't want to wait.

#### Why two answer builders, and how they stay agreed

The webhook reads Tally's JSON; the timer reads the spreadsheet. They phrase a few answers
differently - a multi-select in the sheet repeats the choice in its own column *and* in each
ticked option column, while the payload states it once - so left alone they would disagree
forever and the drift check would fire on every row.

The sheet is therefore authoritative, and the hash column says which rows have been checked
against it:

- The webhook writes its rows with an **empty hash**, meaning *not yet reconciled*.
- The next sweep recomputes those rows from the sheet, corrects the `Answer` cell silently,
  and stamps the hash.
- Only a row that already **has** a hash can be flagged for drift.

So a grader sees the row within a second of submission, and within five minutes it says
exactly what the spreadsheet says.

A time-driven trigger is unavoidable as the backstop: Tally writes through the Sheets API,
and API writes never fire `onEdit` or `onChange`.

All three call `syncAll()`, which is **append-only**. It adds rows for (submission,
question) pairs that have none and never rewrites, reorders or deletes an existing row.
That is what keeps a typed grade welded to its question as submissions and questions
arrive. Adding a question mid-grading is the same non-event: a new registry row, and the
next run appends that question for every candidate already in the sheet.

The one exception is answer drift. If Tally rewrites an answer under a grade already given,
the sync refreshes the `Answer` cell, highlights it, logs it, and leaves `Grade`,
`Weight` and `Rationale` alone for a human to re-check. The hidden hash in `M` is how it
notices, and an empty one means the row is a webhook row still awaiting its first check.

#### Reading an answer

Driven by `Raw columns` in the registry, which covers three shapes:

- **Multi-select**: one column per option, each header being the question's own text with
  `" (the option)"` appended. Option columns are found by that prefix, not by a trailing
  parenthesis - option text contains its own brackets ("Small homes (< 500 sq. ft.)").
- **Question plus follow-up** (`GOV-01`, `CLI-01`, `ART-01`, `ROL-01`): both parts are kept
  in one cell, because they earn one grade between them.
- **Municipality variants** (`HFL-11` across ten municipalities, `HFL-12` across five): the
  candidate answered exactly one, so the sync takes whichever is filled and prefixes the
  answer with the variant it came from.

#### Deploying it

The running copy lives in the spreadsheet (**Extensions > Apps Script**), so this directory
is the reviewable copy, not the live one. Paste both files in, or push with `clasp`.

Then, in order:

1. **Grading > Set up** in the spreadsheet menu. It asks for a webhook token
   (`openssl rand -hex 24`) and installs the two triggers.
2. **Deploy > New deployment > Web app**, execute as yourself, access "Anyone".
3. In Tally: **Integrations > Webhooks**, URL `<web app URL>?token=<the token>`.
4. Send one test submission and check `Sync Log`.

The token in the URL is the whole of the authentication. Apps Script web apps cannot read
request headers, so Tally's `tally-signature` header is unverifiable from inside the script.
Treat the deployment URL like `CANDIDATES_CSV_URL`: it is a capability, and it stays out of
this repo.

#### Publishing a graded subject to the website

Grading in this sheet is invisible to the public until somebody says otherwise. The gate is
no longer in this sheet: the per-subject **`<Subject> - Deploy to website`** checkboxes have
been removed from `Category Grades`, and a single switch in the website repo —
`PUBLISH_GRADES` at the top of `scripts/sync-questionnaire.py` — releases everything at once
on the coalition's chosen date.

| `PUBLISH_GRADES` | What the site shows for every candidate and subject |
|---|---|
| `False` (today) | An hourglass, meaning "returned the questionnaire, this topic is not published yet". No grade, no answers, no rationale. |
| `True` | The top-level letter on the scorecard, plus every graded question behind it on the candidate's own page: question, the candidate's answer, the grade, the weight, and the rationale. Also that topic's ungraded `<TOPIC>-GEN` comment, if the candidate wrote one. |

**General** and **Healthcare access** have no column on this tab at all. Nobody grades
either, so there is nothing to roll up, but their answers (`GEN-01`, `GEN-02`, `HLT-01` and
both comment boxes) are published verbatim by the same switch, and carry a speech-bubble
mark rather than a letter, meaning "answered, not graded, readable". A candidate who wrote
nothing under a topic and was graded on nothing there simply has no section for it.

Turning the switch back off takes every subject off the site on the next sync. Nothing in
this sheet overrides it, and nothing here needs editing to publish or unpublish — what a
release would produce can be checked first with
`PUBLISH_GRADES=1 python3 scripts/sync-questionnaire.py --dry-run`.

Note what the unpublished state still says. **Having a row on this tab is itself published**, as
the fact that the candidate returned the questionnaire — the site draws that differently
from a candidate who never replied, who gets a plain `—`. It says nothing about how the
grading is going, only that it is under way. A candidate whose row should not say even that
needs the row gone.

A candidate with two rows (a resubmission) is fine while at most one of them publishes
anything; the publishing row wins. Two rows both publishing fails the sync with an error
naming both, rather than silently picking one — so a superseded row should be deleted
before the switch is flipped.

What reads this tab is [`scripts/sync-questionnaire.py`](../sync-questionnaire.py) in the
website repo, running daily in CI. It writes two files there — `_data/questions.yml` from
`Question Registry`, and `_data/scores.yml` from `Category Grades` and the `Grade - <Subject>`
tabs — and commits them only when they changed. Full setup is in that repo's README, under
"Questionnaire and grade sync".

Three things about this sheet matter to what gets published:

- **`Question Registry` is the published list of graded questions.** Every row reaches
  `/questionnaire/` on the website, whether `Graded` says Yes or No. Wording fixed there
  is wording fixed on the site the next morning. The questions it does not list -
  `GEN-01`, `GEN-02` and the per-topic `*-GEN` comment boxes - are published too, read
  straight off the raw tab's own column headers, so they need no registry row and adding
  one would duplicate them.
- **`Owner` is printed on the site**, as the organization that wrote and grades the
  question. Rows whose `Owner` is a personal email address are dropped with a warning
  rather than published; several `ROL-*` rows are in that state. Put the organization's
  name there.
- **`Grade` accepts `N/A`** as well as the five letters, and it is published as its own
  badge meaning "does not apply to this candidate" — for `ROL-05`, which asks what
  somebody did in a previous term, a first-time candidate is `N/A`, not a blank. A blank
  publishes as "not graded yet". Letter-graded tabs only: on `Grade - Housing` and
  `Grade - Arts` the cell takes a number, and a question that does not apply is left blank,
  which drops it out of that candidate's total and out of what the total is measured
  against.

`Grader` and `Graded at` are never published. Grades go out as the coalition's.

## How committee members vote

Send each person the sheet link and their tab name. In their tab:

1. Three dropdowns per question, `1–5`:
   - **Importance**: how much the topic matters to us. 1 marginal, 5 central.
   - **Distinguishes**: how well it separates candidates. 1 everyone answers the
     same, 5 sharply separating.
   - **Answerable**: can a candidate answer confidently with modest research?
     1 needs deep specialist knowledge, 5 squarely in public discourse.
2. Four checkbox flags, ticked **only if the question trips that criterion**:
   - `F: our view`: doesn't reflect the view of the folks involved in this effort
   - `F: users`: doesn't reflect the view of the folks we hope use the scorecard
   - `F: allies`: risks pitting us against communities or constituencies we care about
   - `F: how`: prescribes *how* rather than asking *what* we want
3. **EXCLUDE**: argue the question should be dropped entirely.
4. **Comment**: rewrites, merges, objections.
5. Two disposition checkboxes, what should *happen* to the question, as opposed to how
   well it scores:
   - `Needs rewording`: worth asking, but not as currently written. Say how in `Comment`.
   - `Shouldn't be graded`: worth asking, but answers shouldn't be scored on the
     scorecard.

Blank scores don't count toward averages, so partial progress is safe. Every header
carries the full criterion wording as a hover note. Columns `A–C` warn on edit; they
are formulas pulled from the master.

Because each tab is a table, members can filter to one category and vote a theme at
a time rather than facing the whole list at once.

### Why three scores, four flags and two dispositions

The committee's criteria split into two kinds. Importance, distinguishing power and
answerability are matters of degree, so they're scored. The other four are pass/fail
conditions: averaging a 1–5 on "reflects our view" produces noise, while a flag count
shows dissent directly (one person flagged versus five).

It's also a completion argument: seven scores across ~96 questions is ~670 cells per
member, which nobody finishes.

The two dispositions are a third kind again. A flag says the question is *faulty*;
a disposition says what to *do* with it, and a question can score well on every
criterion and still need rewording, or be worth asking without being gradeable. They
started as two columns one member added to their own tab, which is a good sign they
were answering a question the rubric didn't ask.

## Reading the results

Master columns `K–V`:

| Col | Meaning |
|---|---|
| `K–M` | Average per criterion |
| `N` | Mean score, the headline number |
| `O` | Votes cast on this row |
| `P–S` | Flag tallies, one column per flag |
| `T` | Exclude votes |
| `U` | `STRONG` / `MAYBE` / `WEAK` / `EXCLUDE`, colour-coded |
| `V` | All comments, prefixed by voter name |

Sort by `Mean score` descending for the shortlist. Filter `Status = EXCLUDE` to find
the fights. A row with both a high mean and a high flag count is the one to discuss: 
that's disagreement the average is hiding.

Always read `Status` alongside `Votes cast`. `STRONG` on two votes is two people.

For the aggregate picture (who still owes votes, how the categories are splitting,
which flags are firing), read the `Summary` tab instead.

### Status thresholds

Set in `aggregate_formulas()` in `voting.py`:

- `EXCLUDE`: exclude ticks are at least half of votes cast
- `STRONG`: mean ≥ 4 · `MAYBE`: mean ≥ 3 · `WEAK`: below 3

The exclude rule is relative to *votes cast*, not committee size, so it's jumpy early:
one exclude among the first two voters flips the row. It settles as people finish.
Add a minimum-vote guard if that's noisy in practice.

## Gotchas

**Row alignment.** Voter tabs pull from the master by row number. Inserting or
deleting master rows shifts every voter tab out of alignment. Do dedupe and pruning
*before* voting starts. Afterwards, `append.py` can still add questions safely, because
appending only ever writes below the last row, but anything that reorders or removes
rows needs `tables.py` + `voting.py`, and loses votes.

**Rebuilds wipe votes.** `tables.py` and `voting.py` are destructive by design. Once
voting is under way, treat them as off-limits unless you've exported the voter tabs
first. `append.py` and `summary.py` are the two that are safe to run mid-vote.

**Late submissions land at the top of `Form Responses 1`.** Rows have been inserted above
the existing ones rather than appended at least once, and because `FR-*` IDs are positional
that silently renumbers all of them. `append.py`'s prefix check catches it, but only if you
run something; the sheet itself looks fine. Check where new intake rows actually sit before
assuming a submission is additive.

**Voter tabs must keep the standard column order.** The master's aggregates and the
Summary read voter tabs *positionally*: `D:F` scores, `G:J` flags, `K` exclude, `L`
comment. A member who inserts their own column shifts everything to its right, and the
formulas then read the wrong column without erroring; a checkbox gets reported as that
person's comments. Keep custom columns to the *right* of `Comment`.

`append.py` and `summary.py` call `check_voter_columns()` and refuse to run when a tab
drifts, so this fails loudly rather than quietly corrupting column `V`.

**`addTable` column naming.** In the Sheets API, `columnIndex` inside
`columnProperties` is validated *table-relative*, but the resulting `columnName` is
written back at the *sheet* offset. Passing `columnProperties` for a table anchored
away from column A silently overwrites the headers in columns A, B, … That's why
`CategoryCounts` is created without them and infers its names from `X1:Y1`.

**Editing questions.** Edit the master directly; text and category propagate to
every voter tab automatically. Recategorise with the column `B` dropdown and the
`Summary` counts update immediately. Only structural changes need a rebuild.
