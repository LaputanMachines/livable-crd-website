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

Pushes to `main` run [.github/workflows/jekyll.yml](.github/workflows/jekyll.yml), which builds and deploys via GitHub Actions.

1. Repo **Settings → Pages → Build and deployment → Source**: GitHub Actions
2. **Settings → Pages → Custom domain**: `livablecrd.ca`
3. Enable **Enforce HTTPS** after DNS and the certificate are ready

### DNS at your registrar

| Host | Type | Value |
|------|------|--------|
| `@` (apex) | `A` | `185.199.108.153`, `185.199.109.153`, `185.199.110.153`, `185.199.111.153` |
| `www` (optional) | `CNAME` | `laputanmachines.github.io` |

The repo root [`CNAME`](CNAME) file must contain `livablecrd.ca` (already committed).

## Adding content later

- **Municipalities**: [`_data/municipalities.yml`](_data/municipalities.yml)
- **Candidates**: [`_data/candidates.yml`](_data/candidates.yml)
- **Questions**: [`_data/questions.yml`](_data/questions.yml)
- **Grading scale**: [`_data/grades.yml`](_data/grades.yml), [`_data/subjects.yml`](_data/subjects.yml)
- **Partners**: [`_data/partners.yml`](_data/partners.yml)

Contact email is set in [`_config.yml`](_config.yml) (`email` key).

## License

Content © Livable CRD coalition. Adjust as needed for your governance model.
