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
| `Category Grades` | `A-C` by the Apps Script, the rest by graders. One row per candidate; its deploy checkboxes are what publish a subject to the website. |
| `Sync Log` | The Apps Script. |

#### `Question Registry`

One row per graded question - 55 at present - and the single source of truth for what
gets graded and what it is worth:

`Label | Category | Question | Type | Graded | Weight | Raw columns | Notes | Owner`

Weight lives here, once per question, rather than repeated on every candidate's row. The
block at `J1:L` totals the weights per category; each category should reach 100%.

`Category` is why this tab exists rather than a regex over the header row. Prefixes don't
map onto subjects: `HFL-12` is the infrastructure funding gap, which `finalize.py` grades
as Governance even though Homes for Living submitted it, and Governance also owns the
separate `GOV-*` block. `CATEGORY_OVERRIDE` in the script seeds that; the column is
authoritative afterwards.

`Owner` is who submitted the question, so a grader who needs to check intent knows whom
to ask. Populated from the `Finalized Questions` tab of the committee sheet, matching on
question text rather than `Ref`: the Tally form renumbered several questions, so the two
sheets' refs disagree (the committee sheet's `HFL-09` is the parking-minimums question;
the form's is non-market housing). Questions that reached the form without going through
that tab are blank and filled in by hand.

Anything added to this tab goes in column **M or beyond**: `A:I` is the schema both
scripts read by position, and `J:L` holds the tally block.

`--refresh` rewrites `Question`, `Type`, `Raw columns` and `Notes` from the current form,
for when wording or columns changed. It never touches `Category`, `Graded`, `Weight` or
`Owner`.

#### Grading tabs

`Key | Candidate | Municipality | Label | Question | Answer | Owner | Grade | Weight | Rationale | Grader | Graded at | Answer hash`

`A-G` and the hidden hash in `M` are generated and carry an edit warning. Graders fill
`Grade` (a dropdown of the five grades the site can render), `Rationale`, and nothing else;
`Grader` / `Graded at` stamp themselves.

`Owner` and `Weight` are `VLOOKUP`s into the registry rather than copies, so correcting
either there corrects every grading row at once, including rows already graded.

`Key` is `<Submission ID>|<Label>`, and it is what makes the sync safe: rows are matched by
key, never by position.

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

Grading in this sheet is invisible to the public until somebody says otherwise. The
`Category Grades` tab pairs every subject column with a **`<Subject> - Deploy to
website`** checkbox, and that checkbox is the entire publication gate:

| Checkbox | What the site shows for that candidate and subject |
|---|---|
| unticked | A circular arrow, meaning "returned the questionnaire, this topic is still being graded". No grade, no answers, no rationale. |
| ticked | The top-level letter on the scorecard, plus every graded question behind it on the candidate's own page: question, the candidate's answer, the grade, the weight, and the rationale. |

Unticking it takes the subject back off the site on the next sync. Nothing in the website
repo overrides this, and nothing else needs editing to publish or unpublish.

Note what the unticked state now says. **Having a row on this tab is itself published**, as
the fact that the candidate returned the questionnaire — the site draws that differently
from a candidate who never replied, who gets a plain `—`. It says nothing about how the
grading is going, only that it is under way. A candidate whose row should not say even that
needs the row gone, not its boxes cleared.

A candidate with two rows (a resubmission) is fine while at most one of them publishes
anything; the publishing row wins. Two rows both publishing fails the sync with an error
naming both, rather than silently picking one.

What reads the box is [`scripts/sync-questionnaire.py`](../sync-questionnaire.py) in the
website repo, running daily in CI. It writes two files there — `_data/questions.yml` from
`Question Registry`, and `_data/scores.yml` from `Category Grades` and the `Grade - <Subject>`
tabs — and commits them only when they changed. Full setup is in that repo's README, under
"Questionnaire and grade sync".

Three things about this sheet matter to what gets published:

- **`Question Registry` is the published question list.** Every row reaches
  `/questionnaire/` on the website, whether `Graded` says Yes or No. Wording fixed there
  is wording fixed on the site the next morning. Questions the registry does not list are
  not published at all, which currently includes `GEN-01`, `GEN-02` and the per-topic
  `*-GEN` comment boxes: `grading_tabs.py` skips them as ungraded, so they never got a
  registry row. Add rows for them if they should appear.
- **`Owner` is printed on the site**, as the organization that wrote and grades the
  question. Rows whose `Owner` is a personal email address are dropped with a warning
  rather than published; several `ROL-*` rows are in that state. Put the organization's
  name there.
- **`Grade` accepts `N/A`** as well as the five letters, and it is published as its own
  badge meaning "does not apply to this candidate" — for `ROL-05`, which asks what
  somebody did in a previous term, a first-time candidate is `N/A`, not a blank. A blank
  publishes as "not graded yet".

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
