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
| ↻ | A clockwise circular arrow. The candidate returned the questionnaire and this topic has not been published yet. Says nothing about how it is going. |
| speech bubble | The candidate answered and nobody grades this topic, so there is something to read and no letter is coming. |
| `—` | No completed questionnaire has come back, **or** nothing is published. |

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

### How it joins to the candidate list

`scores.yml` is a separate file from `candidates.yml` because the two come from different spreadsheets on different schedules, and anything written into `candidates.yml` would be overwritten by the nightly candidate sync. [`_plugins/questionnaire_scores.rb`](_plugins/questionnaire_scores.rb) joins them at build time, matching on name and municipality. A result for somebody not listed as a confirmed candidate is dropped by the script (with a warning) — there is no page to show it on.

### One-time setup

The grading sheet is not public and must not become public, so this job authenticates rather than fetching a CSV. Create a Google Cloud service account, download its JSON key, share the grading spreadsheet with the service account's email address (Viewer is enough), and add two repository secrets:

- `GOOGLE_SERVICE_ACCOUNT_JSON` — the key file's entire contents
- `QUESTIONNAIRE_SUBMISSIONS_SHEET_ID` — the spreadsheet id from its URL

The credential can read candidate emails and every submitted answer, because they live on other tabs of the same spreadsheet. The script never opens those tabs, but the credential's access is not that narrow. To withdraw it, revoke the key.

### Running it locally

Falls back to the same interactive Google auth the rest of [`scripts/questionnaire/`](scripts/questionnaire/) uses when `GOOGLE_SERVICE_ACCOUNT_JSON` is unset:

```bash
pip install -r scripts/questionnaire/requirements.txt
QUESTIONNAIRE_SUBMISSIONS_SHEET_ID="…" python3 scripts/sync-questionnaire.py --dry-run
```

The run **fails without writing either file** if a registry category maps to no subject in [`_data/subjects.yml`](_data/subjects.yml), or if the `Category Grades` tab has no `<Subject> - Deploy to website` column pairs. Anything recoverable — an unmatched candidate, an unknown grade, an email-shaped owner — warns and is skipped.

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

## License

Content © Livable CRD coalition. Adjust as needed for your governance model.
