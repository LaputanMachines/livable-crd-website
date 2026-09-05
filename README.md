# Livable CRD website

Jekyll site for [livablecrd.ca](https://livablecrd.ca), a coalition candidate scorecard for Capital Regional District municipal elections.

## Local development

Requires Ruby 3.x and Bundler.

```bash
bundle install          # installs to vendor/bundle (isolated from system gems)
bundle exec jekyll serve
```

Open [http://127.0.0.1:4000/](http://127.0.0.1:4000/).

To mirror production URL settings:

```bash
JEKYLL_ENV=production bundle exec jekyll serve
```

## Production build

```bash
bundle exec jekyll build
```

Output is written to `_site/`.

## Deploy (GitHub Pages)

Pushes to `main` run [.github/workflows/jekyll.yml](.github/workflows/jekyll.yml), which builds and deploys via the shared [deploy.yml](.github/workflows/deploy.yml) reusable workflow (also used by the daily candidate sync below).

1. Repo **Settings → Pages → Build and deployment → Source**: GitHub Actions
2. **Settings → Pages → Custom domain**: `livablecrd.ca`
3. Enable **Enforce HTTPS** after DNS and the certificate are ready

### DNS at your registrar

| Host | Type | Value |
|------|------|--------|
| `@` (apex) | `A` | `185.199.108.153`, `185.199.109.153`, `185.199.110.153`, `185.199.111.153` |
| `www` (optional) | `CNAME` | `laputanmachines.github.io` |

The repo root [`CNAME`](CNAME) file must contain `livablecrd.ca` (already committed).

## Candidate data sync

[`_data/candidates.yml`](_data/candidates.yml) is **auto-generated: do not edit it by hand.** A scheduled GitHub Action, [.github/workflows/sync-candidates.yml](.github/workflows/sync-candidates.yml), runs daily (and on demand via *Actions → Sync candidates from Google Sheet → Run workflow*). It:

1. Fetches the coalition candidate-tracking sheet as CSV ([`scripts/sync-candidates.py`](scripts/sync-candidates.py));
2. Keeps only confirmed-running candidates and the published fields (name, municipality, office, standing, slate, per-topic grades), subjective columns are never read;
3. Commits the regenerated file to `main` and redeploys, only when something changed.

The job **fails without writing** if the sheet can't be fetched, isn't valid CSV, has zero confirmed candidates, or contains an unknown municipality, an invalid grade, or a standing with no entry in [`_data/standings.yml`](_data/standings.yml), so bad data can't reach the live site.

Slate is the deliberate exception to that strictness: an unrecognized slate **warns and publishes as written** instead of failing. New electoral organizations get announced mid-campaign, and a fatal error there would stall every grade update until someone edited this repo. See [Slates](#slates).

### One-time setup

1. **Secret**: add repo secret `CANDIDATES_CSV_URL` (**Settings → Secrets and variables → Actions → New repository secret**), set to the sheet's CSV export URL:
   `https://docs.google.com/spreadsheets/d/<SHEET_ID>/export?format=csv&gid=<GID>`
   The sheet must be shared as "Anyone with the link can view."
2. **Workflow permissions**: **Settings → Actions → General → Workflow permissions → Read and write permissions** (lets the action commit `candidates.yml` to `main`).

### Editing the data

Edit the **source spreadsheet**, not the YAML. To support a new municipality, add its `slug`/`name` to [`_data/municipalities.yml`](_data/municipalities.yml) first; grades live in the topic columns and must be one of `A`, `B`, `C`, `C-`, `F`. The sheet's `Incumbent?` column is role-specific (`Incumbent Councillor`, `Ex-Incumbent Mayor`, `Challenger, …`); to support new wording there, add an entry to [`_data/standings.yml`](_data/standings.yml) and map it in `normalize_standing()`. Preview locally:

```bash
CANDIDATES_CSV_URL="…" python3 scripts/sync-candidates.py --dry-run
```

### Slates

The sheet's optional `Slate` column names the electoral organization a candidate runs with. Listing a slate is a factual public-record field, not an endorsement. It surfaces in three places:

- The scorecard **meta line** under each name: `Councillor · Incumbent · Sooke First`.
- The **search box**, which matches slate as well as name, so typing `sooke first` narrows to that slate. There is deliberately no slate filter group: the filter bar already carries four controls, and since most candidates run unaffiliated, pills would cost every reader vertical space to filter a minority of rows. Note search matches name and slate only, not municipality, which has its own filter.
- An opt-in **row tint**, one colour per slate, toggled by a *Highlight Slate Candidates* checkbox in each municipality's heading; see below.
- Each **candidate page**, on its own labelled line (`Running with Sooke First`) with a dot in that slate's colour, which also prints on the leaflet. Kept off that page's uppercase meta line on purpose: beside the standing, a bare slate name read as another attribute of the same kind.

#### Colour coding

Slates get one colour each, defined as `.slate-c1` … `.slate-c8` in [`_sass/_slates.scss`](_sass/_slates.scss) and assigned to slates by `slate_classes` in [`_plugins/candidate_pages.rb`](_plugins/candidate_pages.rb). That map is published as `site.data.slate_classes`, so the table, the legends and the candidate pages all colour from one source and cannot disagree.

- **Assigned alphabetically by slate name**, not by order of appearance in the sheet. Spreadsheet row order changes whenever someone sorts it, and a colour that silently jumped between slates on a nightly sync would be worse than no colour.
- **Off by default, and scoped per municipality.** The checkbox sits in the municipality heading band, because a slate contests one council; a table-wide legend would list entries irrelevant to every group but one. Only municipalities that actually have slates get a control.
- **Colour is never the only carrier** (WCAG 1.4.1): the row already names its slate in text and each legend labels its swatch. That is also what keeps things readable past eight slates, where colours start repeating.
- The tint class goes on the **row**, not the municipality's `<tbody>`, so a row keeps its colour when `favourites.js` moves it into the pinned group.
- Palette hues deliberately avoid the letter-grade colours, so a tinted row never reads as a grade. Worst-case measured contrast: body text 12.6:1, meta text 5.8:1, swatches 4.4:1.

Unlike municipality and standing, [`_data/slates.yml`](_data/slates.yml) is **not an allowlist**: the sheet's own text is the label, and a slate missing from that file is published as written with a warning. Add an entry only to tidy up the sheet's wording:

```yaml
- id: together-victoria     # slugified sheet text
  label: Together Victoria  # what the scorecard shows instead
```

Behaviour worth knowing:

- **Every spelling that slugifies alike publishes one label**, so `Together Victoria` and `together victoria` produce a single filter pill. A `slates.yml` label wins; otherwise the first spelling in the sheet does.
- **A blank cell publishes no slate** and shows nothing. `Independent` is treated as a real, publishable answer: if you want candidates labelled that way, write it in the sheet rather than leaving the cell empty.
- **No `Slate` column at all** is fine: the job warns once and no slate is published.

### Grades come from a separate sheet

As of August 2026 the tracking sheet no longer has the per-topic grade columns (`Housing`, `Transit`, …). Grades live in the grading sheet instead, and reach the site through [Questionnaire and grade sync](#questionnaire-and-grade-sync) below. `sync-candidates.py` handles their absence without failing: it publishes every topic as pending (`—`) and leaves the grades to the other job. `SCORE_MAP` in [`scripts/sync-candidates.py`](scripts/sync-candidates.py) still lists the pairs, so a grade column reappearing in the tracking sheet is picked up automatically; anything the grading sheet publishes wins over it.

## Questionnaire and grade sync

[`_data/questions.yml`](_data/questions.yml) and [`_data/scores.yml`](_data/scores.yml) are **auto-generated: do not edit them by hand.** A scheduled GitHub Action, [.github/workflows/sync-questionnaire.yml](.github/workflows/sync-questionnaire.yml), runs daily (and on demand via *Actions → Sync questionnaire and grades from Google Sheet → Run workflow*). [`scripts/sync-questionnaire.py`](scripts/sync-questionnaire.py) reads three tabs of the candidate **grading** sheet — a different spreadsheet from the candidate tracking sheet above — and writes:

| File | From | Rendered by |
|---|---|---|
| `_data/questions.yml` | `Question Registry` | [`/questionnaire/`](questionnaire/index.md), the full published question set |
| `_data/scores.yml` | `Category Grades` + `Grade - <Subject>` | each candidate's own scorecard page |

### What gets published, and what decides it

**The spreadsheet decides, not this repo.** Each subject on the `Category Grades` tab is followed by a `<Subject> - Deploy to website` checkbox. A subject is written to `scores.yml` only when that box is ticked, and unticking it removes the subject from the site on the next run. Grading in progress cannot reach a public page by accident.

A published subject brings with it the top-level letter (`B` for Transit) **and** every graded question behind it: the question, the candidate's answer, the grade, the weight, and the grader's rationale where one was written. Weight and rationale are simply omitted where the sheet leaves them blank.

### The three states a topic can be in

Having a row on `Category Grades` at all means the candidate returned the questionnaire, and the site says so even when nothing has been published for them. Every candidate with a row is written to `scores.yml`, with an empty `subjects` list if no box is ticked. That gives the scorecard three states rather than two, on the matrix and on each candidate's page alike:

| Shown | Means |
|---|---|
| `A`–`F` | Published. The candidate's page also carries every graded question behind it. |
| hourglass | The candidate returned the questionnaire and this topic has not been published yet. The default for every topic a returned candidate is waiting on, graded or not. Says nothing about how it is going. |
| speech bubble | The candidate answered, nobody grades this topic, and their answers are published: there is something to read and no letter is coming. |
| `—` | No completed questionnaire has come back. |

The arrow is scoped to the topics that carry a graded question at all — `graded_subjects` at the top of `scores.yml`, derived from the registry rather than from which columns the sheet happens to have. Only `general` and `healthcare-access` fall outside it, so only they can show the bubble. A written comment on a *graded* topic (`TRN-GEN` and friends) shows inside that topic on the candidate's page, not in a matrix cell with no room for it.

### The questions nobody grades

Three kinds, and none of them reaches the Question Registry, which lists what gets graded:

- **`GEN-01`** — one policy, bylaw or asset the candidate would change.
- **`GEN-02`** — a $10 million budget split across twelve areas, rendered as a small allocation table. Alone among the questions it arrives with no `GEN-02:` prefix on any column, because Tally exports an allocation grid as one bare column per line item. `sync-questionnaire.py` matches it on the twelve exact headers in `GEN02_AREAS` and **fails the run** if they are not all present and contiguous; prefixing those columns in the form would retire that block.
- **`<TOPIC>-GEN`** — the "anything you'd like to add" box at the end of each topic. Eight of them; Housing has none.

`HLT-01` is the exception in the other direction: it *is* in the registry, hand-marked `Graded=No`, so its wording comes from there and only its answer is read off the raw tab.

All of them are gated exactly like grades. General and Healthcare access have their own `- Deploy to website` checkbox on `Category Grades` with no grade column beside it; a `<TOPIC>-GEN` comment rides its topic's existing checkbox, so nothing a candidate wrote about transit appears before the transit section is signed off.

Before this, a candidate who filled the questionnaire in and a candidate who ignored it were drawn identically, which was the one thing the scorecard could not afford to get wrong about somebody who did the work.

Deliberately **not** published: candidate email addresses and the rest of Tally's raw tab (never read), the grader's name and grading timestamp, and any `Owner` in the registry that is an email address rather than an organization — those are dropped with a warning, so put the organization's name in that column.

A grade of `N/A` is published as its own badge, meaning "graded, and this question does not apply to this candidate" (`ROL-05` asks about a previous term in office). It is distinct from a blank, which means not graded yet and renders as `—`.

### Answer choices

Candidates asked to work the questionnaire through with their team before opening the form, which means the published page has to say what each question offers to pick from, not just what it asks. `_data/questions.yml` carries an `options` list for that, plus `option_limit` where the form caps how many may be picked, and `/questionnaire/` prints both under the question. All 44 choice questions have their options; the other 22 are free-text boxes and GEN-02's allocation, which offer nothing to list.

They come from **two sources, and the difference matters if either ever disagrees**:

| Source | Covers | Needs |
|---|---|---|
| The Tally form (`TALLY_FORM_ID`, `TALLY_API_KEY`) | Every question, in the wording and order a candidate reads, plus selection caps and character limits | An API key |
| The `2026 Municipal Elections` tab | Multi-selects only — Tally exports one column per checkbox option and names each in the header | Nothing extra |

The form wins where both know a question, because it is what a candidate is looking at and a column's position was fixed whenever that column was created. `reconcile_options()` reports a disagreement about *which* options exist as a warning rather than an error: the form is the better authority, and a sync that refused to run over a mismatch would take the grades down with it. Ordering disagreements are resolved silently in the form's favour — two questions currently list their last two options the other way round on the tab.

Cross-checking against the tab is the only independent evidence the form is being read correctly, and it is worth keeping for that alone. As of writing, all 11 multi-selects agree on the option set exactly.

**Without the Tally secrets the sync still runs**, warns, and publishes only the multi-selects' options. It does not fail: answer choices are not worth blocking a grade release over.

`HFL-11` and `HFL-12` are asked once per municipality, and their variants are collapsed to one list on the test of offering the same options, not of listing them in the same order — Colwood's copy of `HFL-11` happens to list two of its four answers the other way round. If two variants ever offer genuinely different options, the question is published without them and the run warns, because no single list would be true of it.

### What the form knows that the registry cannot

The registry infers a question's answer shape by counting the columns Tally exports for it (`describe()` in [`scripts/questionnaire/grading_tabs.py`](scripts/questionnaire/grading_tabs.py)), and a text box and a single-choice question are one column each. Eleven questions are essay boxes filed as `single`, which the site published as "One answer" over a box wanting several paragraphs. `form_corrected_kind()` corrects exactly those, using the form's block type, and nothing else: the registry's other types carry knowledge the form's flat block list does not, since `variant` knows ten municipality copies are one question and `pair` knows a follow-up asked under its own title belongs to the question above it.

Every question also states its answer shape (`type_label`: "One answer", "Written answer, up to 2,000 characters", "Select all that apply"), except the ten multi-selects whose own wording already says it — see `SELECTION_RULE_CUES`. That exception exists because `ART-05` says "Select up to five" and `HFL-12` "Select up to two", and a label underneath them reading "select all that apply" would contradict the question rather than repeat it. `option_limit` is suppressed on those same questions and kept everywhere else: `TRN-01` reads "select all that apply" and the form still stops a candidate at four of its six.

### How it joins to the candidate list

`scores.yml` is a separate file from `candidates.yml` because the two come from different spreadsheets on different schedules, and anything written into `candidates.yml` would be overwritten by the nightly candidate sync. [`_plugins/questionnaire_scores.rb`](_plugins/questionnaire_scores.rb) joins them at build time, matching on name and municipality. A result for somebody not listed as a confirmed candidate is dropped by the script (with a warning) — there is no page to show it on.

### One-time setup

Add the repository secret `QUESTIONNAIRE_SUBMISSIONS_SHEET_ID`, set to the spreadsheet id from its URL. Same arrangement as `CANDIDATES_CSV_URL` above and treated the same way: the id is a capability, so it stays in a secret and out of source.

### Running it locally

Stdlib-only, no dependencies to install:

```bash
QUESTIONNAIRE_SUBMISSIONS_SHEET_ID="…" python3 scripts/sync-questionnaire.py --dry-run
```

The run **fails without writing either file** if a registry category maps to no subject in [`_data/subjects.yml`](_data/subjects.yml), if the `Category Grades` tab has no `<Subject> - Deploy to website` columns, or if GEN-02's twelve line-item columns are not all present and adjacent. Anything recoverable — an unmatched candidate, an unknown grade, an email-shaped owner — warns and is skipped.

Each tab is checked against its expected first header before being parsed. Asking for a tab that does not exist does not fail: the spreadsheet answers with its *first* sheet instead, so a renamed tab would otherwise feed 236 columns of the wrong data into a parser expecting nine. A mismatch is treated as a missing tab.

## Questionnaires to check off

The tracking sheet has a `Completed Questionnaire` column that somebody keeps by hand, and the only way to know who is missing from it is to read two spreadsheets side by side. A scheduled GitHub Action, [.github/workflows/questionnaire-checkoff-report.yml](.github/workflows/questionnaire-checkoff-report.yml), does that reading daily (and on demand via *Actions → Questionnaires to check off in the candidate sheet → Run workflow*). [`scripts/questionnaire-checkoff-report.py`](scripts/questionnaire-checkoff-report.py) matches the questionnaire submissions against the tracking sheet and writes the run's **summary page** with everyone whose box is still empty — cell reference, name, municipality — so the ticking is a scroll and a click rather than a comparison.

It ticks nothing itself, and holds no credential that could. Writing to the sheet would need a Google service account with edit access to a document the coalition edits by hand all day; the list is the useful half of that job and needs no credential at all, since both sheets are read over plain HTTP as CSV like everything else in `scripts/`. Nothing is committed and no deploy follows: the published site takes nothing from this column, and reads its "did they answer?" state from `scores.yml` instead (see [the three states a topic can be in](#the-three-states-a-topic-can-be-in)).

The job runs at 14:17 UTC, after both sync jobs' slots, so a candidate confirmed the same morning is already a row in the tracking sheet by the time this looks for one.

### What the summary says

- **Who to tick**, one row per candidate, as `Cell | Candidate | Municipality`. The cell is the sheet's own reference — `P42` — so the column letter follows the sheet if the column moves.
- **Submissions with no row to tick**: a candidate the tracking sheet has not heard of, or a name spelled differently in the two systems. These are the ones worth acting on; they usually mean a missing row rather than a missing tick.
- A box already ticked drops out silently. The coalition ticks boxes by hand too — a candidate who answered by email, a submission filed under a different name — and the report has nothing to say about those.

**The summary page is public**, because this repository is. It names candidates and municipalities, including candidates the tracking sheet has not confirmed yet, and never the spreadsheet ids or export URLs — those are capabilities over the whole sheets, contact details included, and stay in secrets. If the names should not be public, the report has to move off a public run.

Matching is on normalized full name, disambiguated by municipality only where it has to be: one tracking row with that name is reported outright, and two people sharing a name need the submission's municipality to pick between them. Anything still unresolved is listed as unresolved rather than guessed at.

Row status is not consulted. `Running?` decides who the website publishes, not who filled the form in; an unconfirmed candidate who answered has still answered.

It reads four identity columns from the submission sheet's raw tab (submission id, first name, last name, municipality) via a column select, never the email addresses beside them.

### One-time setup

None. The two secrets it reads, `CANDIDATES_CSV_URL` and `QUESTIONNAIRE_SUBMISSIONS_SHEET_ID`, are the ones the sync jobs already use.

### Running it locally

```bash
CANDIDATES_CSV_URL="…" QUESTIONNAIRE_SUBMISSIONS_SHEET_ID="…" \
  python3 scripts/questionnaire-checkoff-report.py
```

Stdlib-only, and read-only whatever happens. The list goes to stdout; `--summary FILE` also appends the Markdown report to a file, which is how CI gets it into `$GITHUB_STEP_SUMMARY`. A tracking sheet with no `Completed Questionnaire` column fails the run and lists the columns it did find.


## Questionnaire committee tooling

[`scripts/questionnaire/`](scripts/questionnaire/) builds the working sheet the committee uses to choose which questions make the questionnaire: it collects every submitted question into one categorised master list and generates a per-member voting tab so scoring can happen asynchronously. See [`scripts/questionnaire/README.md`](scripts/questionnaire/README.md).

These scripts only touch that working Google Sheet, never the site or `_data/`. They need `gspread` and interactive Google auth, so unlike the rest of `scripts/` they are run locally, not in CI. The spreadsheet key comes from `QUESTIONNAIRE_SHEET_ID`; it is kept out of source because the sheet holds submitter email addresses.

## Adding content later

- **Municipalities**: [`_data/municipalities.yml`](_data/municipalities.yml)
- **Candidates**: auto-generated from the sheet, see [Candidate data sync](#candidate-data-sync)
- **Questions**: auto-generated from the grading sheet, see [Questionnaire and grade sync](#questionnaire-and-grade-sync)
- **Grades**: auto-generated from the grading sheet, same section
- **Grading scale**: [`_data/grades.yml`](_data/grades.yml), [`_data/subjects.yml`](_data/subjects.yml)
- **Partners**: [`_data/partners.yml`](_data/partners.yml)

Contact email is set in [`_config.yml`](_config.yml) (`email` key).

### Municipality pages

Each municipality with at least one confirmed candidate gets an index at
`/scorecard/<slug>/`, generated by
[`_plugins/candidate_pages.rb`](_plugins/candidate_pages.rb) and laid out by
[`_layouts/municipality.html`](_layouts/municipality.html). Most of what is on
it is derived from `_data/candidates.yml` and needs no maintenance, but four
hand-written fields per entry in
[`_data/municipalities.yml`](_data/municipalities.yml) feed it:

| Field | What it is |
| --- | --- |
| `mayor_seats` | How many mayors this municipality elects (1 everywhere in the region). |
| `council_seats` | How many councillors. **Varies**: 8 in Saanich and Victoria, 6 in most others, 4 in Metchosin. |
| `elections_url` | That municipality's own election page, linked for voting places and the official candidate list. |
| `summary` | A paragraph about this municipality, rendered above the candidate list. |

All four are optional and the template draws nothing for a missing one, which
is the behaviour to rely on rather than guessing at a value. **Do not fill in a
seat count from memory.** Every one currently in the file was read off that
municipality's own 2026 nomination notice or council page in September 2026;
a council can change its size by bylaw, so re-check all of them at the start of
each election cycle.

Keep each `summary` about the municipality and what its council decides, not
about the race. Candidate data re-syncs daily and this file does not, so
anything written here about who is running or which seats are open goes stale
silently. The point of them is that the indexes stop reading as one page with
the name swapped, so no two should share a sentence.

Election day itself is set once in [`_config.yml`](_config.yml) as
`election_day` (an ISO date string), beside `election_year`. It is deliberately
not in `_data/deadlines.yml`, which is the coalition's own project schedule.
Both the municipality indexes and the FAQ's "When is the election?" panel read
it, so the date is written in one place. Blank it and every mention of the date
disappears cleanly rather than going stale.

## License

Content © Livable CRD coalition. Adjust as needed for your governance model.
