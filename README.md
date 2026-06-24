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
2. Keeps only confirmed-running candidates and the published fields (name, municipality, office, incumbent, per-topic grades) — subjective columns are never read;
3. Commits the regenerated file to `main` and redeploys — only when something changed.

The job **fails without writing** if the sheet can't be fetched, isn't valid CSV, has zero confirmed candidates, or contains an unknown municipality or an invalid grade — so bad data can't reach the live site.

### One-time setup

1. **Secret** — add repo secret `CANDIDATES_CSV_URL` (**Settings → Secrets and variables → Actions → New repository secret**), set to the sheet's CSV export URL:
   `https://docs.google.com/spreadsheets/d/<SHEET_ID>/export?format=csv&gid=<GID>`
   The sheet must be shared as "Anyone with the link can view."
2. **Workflow permissions** — **Settings → Actions → General → Workflow permissions → Read and write permissions** (lets the action commit `candidates.yml` to `main`).

### Editing the data

Edit the **source spreadsheet**, not the YAML. To support a new municipality, add its `slug`/`name` to [`_data/municipalities.yml`](_data/municipalities.yml) first; grades live in the topic columns and must be one of `A`, `B`, `C`, `C-`, `F`. Preview locally:

```bash
CANDIDATES_CSV_URL="…" python3 scripts/sync-candidates.py --dry-run
```

## Adding content later

- **Municipalities**: [`_data/municipalities.yml`](_data/municipalities.yml)
- **Candidates**: auto-generated from the sheet — see [Candidate data sync](#candidate-data-sync)
- **Questions**: [`_data/questions.yml`](_data/questions.yml)
- **Grading scale**: [`_data/grades.yml`](_data/grades.yml), [`_data/subjects.yml`](_data/subjects.yml)
- **Partners**: [`_data/partners.yml`](_data/partners.yml)

Contact email is set in [`_config.yml`](_config.yml) (`email` key).

## License

Content © Livable CRD coalition. Adjust as needed for your governance model.
