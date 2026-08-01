# Questionnaire committee tooling

Scripts that build and maintain the candidate-questionnaire working sheet: they
collect every submitted question into one master list, categorise it, and generate
per-member voting tabs so the committee can score questions asynchronously.

These write to a working Google Sheet. They do **not** touch the Jekyll site or any
published data — `_data/candidates.yml` and the scorecard pages are unaffected.

Unlike the rest of `scripts/`, these need third-party packages (`gspread`) and
interactive Google auth, so they are not run in CI.

## Sheet layout

| Tab | Role |
|---|---|
| `Form Responses 1` | Public intake form. Source, read-only. |
| `HFL Questions` | Homes for Living submissions. Source, read-only. |
| `Victori'Us Questions` | Arts & culture submissions. Source, read-only. |
| `All Refined Questions` | **Master.** Every question, categorised, plus vote aggregates. Generated. |
| `Vote - <Name>` | One per committee member. Generated. |

`All Refined Questions` holds two native tables:

- **`Questions`** (`A1:V`) — `A–J` question data, `K–V` vote aggregates.
- **`CategoryCounts`** (`X1:Y`) — live `COUNTIF` per official category.

### Official categories

`General` · `Transit` · `Housing` · `Climate` · `Arts` · `Rolling & cycling` ·
`Walking` · `Healthcare access` · `Reconciliation` · `Governance`

Plus `Housekeeping` — **internal only**, used for logistics questions (fundraising,
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
refresh token is the more sensitive of the two — it grants ongoing access to your
Google account's sheets.

## Configuration

The spreadsheet key comes from the environment, never from source — the sheet
contains submitter email addresses and this repo is public. Same convention as
`CANDIDATES_CSV_URL` in [`scripts/sync-candidates.py`](../sync-candidates.py).

```bash
export QUESTIONNAIRE_SHEET_ID=<the key from the sheet URL>
```

The key is the segment between `/d/` and `/edit` in the sheet URL.

## Scripts

### `aggregate.py` — preview, read-only

```bash
python3 scripts/questionnaire/aggregate.py
```

Prints the question count per category and lists flagged near-duplicates. Writes
nothing. Run this first to sanity-check categorisation after editing the source tabs.

It's also the shared data layer imported by the other two, and it holds the two
things you're most likely to want to edit:

- `FR_OVERRIDES` / `VU_OVERRIDES` — questions whose submitted topic was wrong. Each
  carries a reason string that gets written into the sheet's `Notes` column, so every
  recategorisation is auditable.
- `DUPES` — near-duplicate clusters, also surfaced in `Notes`.

### `tables.py` — rebuild the master

```bash
python3 scripts/questionnaire/tables.py
```

Clears `All Refined Questions` and rebuilds it from the source tabs as native tables.
Question IDs (`FR-01`, `HFL-01`, `VU-01`) are positional — stable as long as the
source tabs keep their row order.

### `voting.py` — build voter tabs

```bash
python3 scripts/questionnaire/voting.py "Alice" "Bob" "Carla"
```

Creates or rebuilds a `Vote - <Name>` tab per member and writes the aggregate
formulas into master columns `K–V`.

**Always pass the full committee list.** Named tabs that already exist are cleared
and rebuilt, so re-running with one name wipes that person's votes and leaves the
aggregates referencing only them.

## How committee members vote

Send each person the sheet link and their tab name. In their tab:

1. Three dropdowns per question, `1–5`:
   - **Importance** — how much the topic matters to us. 1 marginal, 5 central.
   - **Distinguishes** — how well it separates candidates. 1 everyone answers the
     same, 5 sharply separating.
   - **Answerable** — can a candidate answer confidently with modest research?
     1 needs deep expertise, 5 squarely in public discourse.
2. Four checkbox flags, ticked **only if the question trips that criterion**:
   - `F: our view` — doesn't reflect the view of the folks involved in this effort
   - `F: users` — doesn't reflect the view of the folks we hope use the scorecard
   - `F: allies` — risks pitting us against communities or constituencies we care about
   - `F: how` — prescribes *how* rather than asking *what* we want
3. **EXCLUDE** — argue the question should be dropped entirely.
4. **Comment** — rewrites, merges, objections.

Blank scores don't count toward averages, so partial progress is safe. Every header
carries the full criterion wording as a hover note. Columns `A–C` warn on edit; they
are formulas pulled from the master.

Because each tab is a table, members can filter to one category and vote a theme at
a time rather than facing the whole list at once.

### Why three scores and four flags

The committee's criteria split into two kinds. Importance, distinguishing power and
answerability are matters of degree, so they're scored. The other four are pass/fail
conditions — averaging a 1–5 on "reflects our view" produces noise, while a flag count
shows dissent directly (one person flagged versus five).

It's also a completion argument: seven scores across ~93 questions is ~650 cells per
member, which nobody finishes.

## Reading the results

Master columns `K–V`:

| Col | Meaning |
|---|---|
| `K–M` | Average per criterion |
| `N` | Mean score — the headline number |
| `O` | Votes cast on this row |
| `P–S` | Flag tallies, one column per flag |
| `T` | Exclude votes |
| `U` | `STRONG` / `MAYBE` / `WEAK` / `EXCLUDE`, colour-coded |
| `V` | All comments, prefixed by voter name |

Sort by `Mean score` descending for the shortlist. Filter `Status = EXCLUDE` to find
the fights. A row with both a high mean and a high flag count is the one to discuss —
that's disagreement the average is hiding.

Always read `Status` alongside `Votes cast`. `STRONG` on two votes is two people.

### Status thresholds

Set in `aggregate_formulas()` in `voting.py`:

- `EXCLUDE` — exclude ticks are at least half of votes cast
- `STRONG` — mean ≥ 4 · `MAYBE` — mean ≥ 3 · `WEAK` — below 3

The exclude rule is relative to *votes cast*, not committee size, so it's jumpy early:
one exclude among the first two voters flips the row. It settles as people finish.
Add a minimum-vote guard if that's noisy in practice.

## Gotchas

**Row alignment.** Voter tabs pull from the master by row number. Inserting or
deleting master rows shifts every voter tab out of alignment. Do dedupe and pruning
*before* voting starts; if you must change the row set afterwards, re-run both
`tables.py` and `voting.py` — and accept that votes are lost.

**Rebuilds wipe votes.** Both write scripts are destructive by design. Once voting is
under way, treat them as off-limits unless you've exported the voter tabs first.

**`addTable` column naming.** In the Sheets API, `columnIndex` inside
`columnProperties` is validated *table-relative*, but the resulting `columnName` is
written back at the *sheet* offset. Passing `columnProperties` for a table anchored
away from column A silently overwrites the headers in columns A, B, … That's why
`CategoryCounts` is created without them and infers its names from `X1:Y1`.

**Editing questions.** Edit the master directly — text and category propagate to
every voter tab automatically. Recategorise with the column `B` dropdown and
`CategoryCounts` updates immediately. Only structural changes need a rebuild.
