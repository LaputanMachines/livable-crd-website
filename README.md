# Livable CRD website

Jekyll site for [livablecrd.ca](https://livablecrd.ca) — a coalition candidate scorecard for Capital Regional District municipal elections.

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

[`_data/candidates.yml`](_data/candidates.yml) is **auto-generated — do not edit it by hand.** A scheduled GitHub Action, [.github/workflows/sync-candidates.yml](.github/workflows/sync-candidates.yml), runs daily (and on demand via *Actions → Sync candidates from Google Sheet → Run workflow*). It:

1. Fetches the coalition candidate-tracking sheet as CSV ([`scripts/sync-candidates.py`](scripts/sync-candidates.py));
2. Keeps only confirmed-running candidates and the published fields (name, municipality, office, standing, slate, per-topic grades) — subjective columns are never read;
3. Commits the regenerated file to `main` and redeploys — only when something changed.

The job **fails without writing** if the sheet can't be fetched, isn't valid CSV, has zero confirmed candidates, or contains an unknown municipality, an invalid grade, or a standing with no entry in [`_data/standings.yml`](_data/standings.yml) — so bad data can't reach the live site.

Slate is the deliberate exception to that strictness: an unrecognized slate **warns and publishes as written** instead of failing. New electoral organizations get announced mid-campaign, and a fatal error there would stall every grade update until someone edited this repo. See [Slates](#slates).

### One-time setup

1. **Secret** — add repo secret `CANDIDATES_CSV_URL` (**Settings → Secrets and variables → Actions → New repository secret**), set to the sheet's CSV export URL:
   `https://docs.google.com/spreadsheets/d/<SHEET_ID>/export?format=csv&gid=<GID>`
   The sheet must be shared as "Anyone with the link can view."
2. **Workflow permissions** — **Settings → Actions → General → Workflow permissions → Read and write permissions** (lets the action commit `candidates.yml` to `main`).

### Editing the data

Edit the **source spreadsheet**, not the YAML. To support a new municipality, add its `slug`/`name` to [`_data/municipalities.yml`](_data/municipalities.yml) first; grades live in the topic columns and must be one of `A`, `B`, `C`, `C-`, `F`. The sheet's `Incumbent?` column is role-specific (`Incumbent Councillor`, `Ex-Incumbent Mayor`, `Challenger, …`); to support new wording there, add an entry to [`_data/standings.yml`](_data/standings.yml) and map it in `normalize_standing()`. Preview locally:

```bash
CANDIDATES_CSV_URL="…" python3 scripts/sync-candidates.py --dry-run
```

### Slates

The sheet's optional `Slate` column names the electoral organization a candidate runs with. Listing a slate is a factual public-record field, not an endorsement. It surfaces in three places:

- The scorecard **meta line** under each name — `Councillor · Incumbent · Sooke First`.
- The **search box**, which matches slate as well as name, so typing `sooke first` narrows to that slate. There is deliberately no slate filter group: the filter bar already carries four controls, and since most candidates run unaffiliated, pills would cost every reader vertical space to filter a minority of rows. Note search matches name and slate only — not municipality, which has its own filter.
- An opt-in **row tint**, one colour per slate, toggled by a *Highlight Slate Candidates* checkbox in each municipality's heading — see below.
- Each **candidate page**, on its own labelled line (`Running with Sooke First`) with a dot in that slate's colour, which also prints on the leaflet. Kept off that page's uppercase meta line on purpose: beside the standing, a bare slate name read as another attribute of the same kind.

#### Colour coding

Slates get one colour each, defined as `.slate-c1` … `.slate-c8` in [`_sass/_slates.scss`](_sass/_slates.scss) and assigned to slates by `slate_classes` in [`_plugins/candidate_pages.rb`](_plugins/candidate_pages.rb). That map is published as `site.data.slate_classes`, so the table, the legends and the candidate pages all colour from one source and cannot disagree.

- **Assigned alphabetically by slate name**, not by order of appearance in the sheet. Spreadsheet row order changes whenever someone sorts it, and a colour that silently jumped between slates on a nightly sync would be worse than no colour.
- **Off by default, and scoped per municipality.** The checkbox sits in the municipality heading band, because a slate contests one council — a table-wide legend would list entries irrelevant to every group but one. Only municipalities that actually have slates get a control.
- **Colour is never the only carrier** (WCAG 1.4.1): the row already names its slate in text and each legend labels its swatch. That is also what keeps things readable past eight slates, where colours start repeating.
- The tint class goes on the **row**, not the municipality's `<tbody>`, so a row keeps its colour when `favourites.js` moves it into the pinned group.
- Palette hues deliberately avoid the letter-grade colours, so a tinted row never reads as a grade. Worst-case measured contrast: body text 12.6:1, meta text 5.8:1, swatches 4.4:1.

Unlike municipality and standing, [`_data/slates.yml`](_data/slates.yml) is **not an allowlist** — the sheet's own text is the label, and a slate missing from that file is published as written with a warning. Add an entry only to tidy up the sheet's wording:

```yaml
- id: together-victoria     # slugified sheet text
  label: Together Victoria  # what the scorecard shows instead
```

Behaviour worth knowing:

- **Every spelling that slugifies alike publishes one label**, so `Together Victoria` and `together victoria` produce a single filter pill. A `slates.yml` label wins; otherwise the first spelling in the sheet does.
- **A blank cell publishes no slate** and shows nothing. `Independent` is treated as a real, publishable answer — if you want candidates labelled that way, write it in the sheet rather than leaving the cell empty.
- **No `Slate` column at all** is fine: the job warns once and no slate is published.

### Grades come from a separate sheet

As of August 2026 the tracking sheet no longer has the per-topic grade columns (`Housing`, `Transit`, …) — grades are moving to a sheet of their own. The sync job handles this without failing: every topic publishes as pending (`—`) and the run **warns once listing the missing columns**, because an absent grade column is otherwise indistinguishable from "nobody has been graded yet". Wiring up the new grades sheet means adding its columns back to `SCORE_MAP` in [`scripts/sync-candidates.py`](scripts/sync-candidates.py), or fetching it as a second source.

## Questionnaire committee tooling

[`scripts/questionnaire/`](scripts/questionnaire/) builds the working sheet the committee uses to choose which questions make the questionnaire: it collects every submitted question into one categorised master list and generates a per-member voting tab so scoring can happen asynchronously. See [`scripts/questionnaire/README.md`](scripts/questionnaire/README.md).

These scripts only touch that working Google Sheet — never the site or `_data/`. They need `gspread` and interactive Google auth, so unlike the rest of `scripts/` they are run locally, not in CI. The spreadsheet key comes from `QUESTIONNAIRE_SHEET_ID`; it is kept out of source because the sheet holds submitter email addresses.

## Adding content later

- **Municipalities**: [`_data/municipalities.yml`](_data/municipalities.yml)
- **Candidates**: auto-generated from the sheet — see [Candidate data sync](#candidate-data-sync)
- **Questions**: [`_data/questions.yml`](_data/questions.yml)
- **Grading scale**: [`_data/grades.yml`](_data/grades.yml), [`_data/subjects.yml`](_data/subjects.yml)
- **Partners**: [`_data/partners.yml`](_data/partners.yml)

Contact email is set in [`_config.yml`](_config.yml) (`email` key).

## License

Content © Livable CRD coalition. Adjust as needed for your governance model.
