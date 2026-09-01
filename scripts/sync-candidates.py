#!/usr/bin/env python3
"""Regenerate _data/candidates.yml from the coalition candidate-tracking sheet.

Fetches the Google Sheet as CSV (public export URL), keeps only the columns we
publish, validates the data, and writes a byte-stable _data/candidates.yml that
matches the existing hand-authored format (documented header + "# --- City ---"
group comments). The sheet is the single source of truth; this file is meant to
run in CI (see .github/workflows/sync-candidates.yml).

Stdlib only, no third-party deps (matches scripts/gen-social-assets.py).

Usage:
  CANDIDATES_CSV_URL=... python3 scripts/sync-candidates.py
  python3 scripts/sync-candidates.py --csv-file sample.csv --dry-run
"""

import argparse
import csv
import io
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MUNI_YML = os.path.join(ROOT, "_data", "municipalities.yml")
SUBJECTS_YML = os.path.join(ROOT, "_data", "subjects.yml")
STANDINGS_YML = os.path.join(ROOT, "_data", "standings.yml")
SLATES_YML = os.path.join(ROOT, "_data", "slates.yml")
OUT_DEFAULT = os.path.join(ROOT, "_data", "candidates.yml")

# Sheet column -> subject id (in _data/subjects.yml). Subjects with no column in
# the tracking sheet are omitted here and render as pending ("—") until a column
# exists: "general" and "governance". Add the pair below once the
# coalition adds the matching column.
#
# As of the sheet's 2026-08 restructure NONE of these columns exist any more:
# grades live in a separate sheet, so every candidate syncs with no scores and
# renders fully pending. That is the expected steady state and is no longer
# warned about. The pairs stay listed so a column reappearing in the tracking
# sheet is picked up automatically.
SCORE_MAP = [
    ("Housing", "housing"),
    ("Transit", "transit"),
    ("Climate", "climate"),
    ("Arts", "arts"),
    ("Cycling", "rolling-cycling"),
    ("Walking", "walking"),
    ("Health", "healthcare-access"),
]

# Click-tracking query parameters, dropped from a published website (utm_* is
# matched by prefix, so it is not listed here).
TRACKING_PARAMS = {"fbclid", "gclid", "mc_cid", "mc_eid", "igshid"}

# Grades with a corresponding CSS class in _sass/_components.scss. Anything else
# (incl. "D", which has no style) is rejected so a typo can't ship an unstyled badge.
VALID_GRADES = {"A", "B", "C", "C-", "F"}

REQUIRED_COLUMNS = ("Candidate Name", "Municipality", "Running?")

# The sheet's electoral-organization column. Deliberately NOT in
# REQUIRED_COLUMNS: it is a newer addition, and a sheet that predates it (or a
# tab that omits it) must still sync rather than fail the whole job.
SLATE_COLUMN = "Slate"

# The sheet's campaign-website column. Optional for the same reason SLATE_COLUMN
# is: a tab that predates it must still sync rather than fail the whole job.
WEBSITE_COLUMN = "Website"

# Sheet wording that means "nobody filled this cell in", as distinct from a real
# answer. Shared by the slate and website columns. Blank publishes no slate at
# all; "Independent" is a genuine, factual answer and is published as written.
UNKNOWN_VALUES = {
    "", "-", "--", "---", "–", "—", "?", "n/a", "na", "none", "nil",
    "tbd", "tba", "unknown", "not applicable", "not known",
}

# Reproduced (and updated for the automation) from the original hand-authored file.
HEADER = """\
# Confirmed municipal election candidates, grouped by municipality.
#
# AUTO-GENERATED: do not edit by hand.
# Regenerated from the coalition candidate-tracking sheet by
# scripts/sync-candidates.py (CI: .github/workflows/sync-candidates.yml).
# Edit the source spreadsheet, not this file; manual changes are overwritten.
#
# Includes ONLY candidates whose status is confirmed ("Yes Confirmed") as running.
# Suspected, declined, and unconfirmed entries are intentionally omitted.
#
# Subjective tracking notes (political "vibe", commentary, character assessments)
# are intentionally NOT published here: the scorecard evaluates positions, not
# people. Only factual public-record fields are stored.
#
# Fields:
#   name         Candidate's name as listed ("First Last").
#   display_name Same name rendered "Last, First" for the scorecard, with
#                surname particles ("de", "van", ...) kept on the last name.
#   municipality Slug matching _data/municipalities.yml.
#   office       "Mayor", "Councillor", or null if not specified in the source.
#   standing     Id from _data/standings.yml describing what elected position the
#                candidate holds or held ("incumbent-councillor",
#                "ex-incumbent-mayor", "challenger", ...), or null if the sheet
#                does not say. Role-specific on purpose: a sitting councillor
#                running for mayor is not the incumbent mayor.
#   slate        Electoral organization the candidate runs with, as a display
#                label ("Together Victoria", "Independent"), or null if the sheet
#                does not say. Free text from the sheet, optionally tidied via
#                _data/slates.yml; an unrecognized slate is published as
#                written, not rejected. Naming a slate is not an endorsement.
#   website      The candidate's own campaign page as an absolute http(s) URL, or
#                null if the sheet does not list one. Whatever the sheet gives is
#                published, campaign site or social profile alike; click-tracking
#                query parameters are stripped. Linking to it is signposting, not
#                an endorsement.
#   scores       Map of per-topic letter grades, keyed by the topic ids in
#                _data/subjects.yml. Any topic left blank renders as pending ("—").
#
# Within each municipality, candidates are ordered alphabetically by last name."""


def norm(s):
    """Lowercase, trim, and collapse internal whitespace."""
    return " ".join((s or "").split()).lower()


def tidy(s):
    """Trim and collapse internal whitespace, preserving case."""
    return " ".join((s or "").split())


def slugify(s):
    """Lowercase slug: runs of non-alphanumerics become a single hyphen.

    Mirrors Jekyll's `slugify` closely enough for the slate ids in
    _data/slates.yml. The published data carries the label, not this slug, so
    the two implementations never have to agree byte-for-byte; only this
    file's slates.yml lookup depends on it.
    """
    out = []
    for ch in norm(s):
        if ch.isalnum():
            out.append(ch)
        elif out and out[-1] != "-":
            out.append("-")
    return "".join(out).strip("-")


# --- Minimal YAML readers (these files are simple "- key: value" blocks) -----

def load_municipalities(path):
    """Return (ordered [(slug, name)], {normalized-name-or-slug: slug})."""
    ordered = []
    with open(path, encoding="utf-8") as f:
        slug = None
        for line in f:
            stripped = line.strip()
            if stripped.startswith("- slug:"):
                slug = stripped.split(":", 1)[1].strip().strip("\"'")
            elif stripped.startswith("name:") and slug is not None:
                name = stripped.split(":", 1)[1].strip().strip("\"'")
                ordered.append((slug, name))
                slug = None
    lookup = {}
    for slug, name in ordered:
        lookup[norm(name)] = slug
        lookup[norm(slug)] = slug
        lookup[norm(slug.replace("-", " "))] = slug
    return ordered, lookup


def load_slates(path):
    """Return {slug: label-or-None} from _data/slates.yml.

    Key presence marks a slate as known; the value is an optional display label
    that replaces the sheet's own text. The file is optional and normally an
    empty list; see its header comment for why this is not an allowlist.
    """
    labels = {}
    if not os.path.exists(path):
        return labels
    with open(path, encoding="utf-8") as f:
        current = None
        for line in f:
            stripped = line.strip()
            if stripped.startswith("- id:"):
                current = stripped.split(":", 1)[1].strip().strip("\"'")
                labels.setdefault(current, None)
            elif stripped.startswith("label:") and current is not None:
                labels[current] = stripped.split(":", 1)[1].strip().strip("\"'") or None
                current = None
    return labels


def load_ids(path):
    """Collect every "- id: value" from one of our simple list-of-maps data files."""
    ids = set()
    with open(path, encoding="utf-8") as f:
        for line in f:
            stripped = line.strip()
            if stripped.startswith("- id:"):
                ids.add(stripped.split(":", 1)[1].strip().strip("\"'"))
    return ids


# --- Fetch -------------------------------------------------------------------

def fetch_csv(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": "livable-crd-sync/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
    # utf-8-sig strips a leading BOM that Google's CSV export sometimes includes.
    return raw.decode("utf-8-sig")


# --- Field normalizers -------------------------------------------------------

def is_confirmed(running):
    return norm(running) == "yes confirmed"


def normalize_office(value, name, warnings):
    low = norm(value)
    if low == "":
        return None
    if low.startswith("mayor"):
        return "Mayor"
    if low.startswith("councillor"):
        return "Councillor"
    warnings.append(f"{name}: unrecognized office {value!r} → null (office filter won't match)")
    return None


def normalize_standing(value, name, warnings):
    """Map the sheet's "Incumbent?" wording to a _data/standings.yml id.

    The sheet qualifies incumbency by role ("Incumbent Councillor", "Ex-Incumbent
    Mayor"), which matters because the role often differs from the office being
    sought: a sitting councillor running for mayor is not the incumbent mayor.
    Role is preserved here rather than flattened to a boolean.
    """
    low = norm(value)
    if low == "":
        return None

    if "councillor" in low:
        role = "councillor"
    elif "mayor" in low:
        role = "mayor"
    else:
        role = None

    # "Ex-" first: "Ex-Incumbent Mayor" also contains "incumbent".
    is_former = low.startswith(("ex-incumbent", "ex incumbent", "former incumbent"))
    if is_former:
        return f"ex-incumbent-{role}" if role else "ex-incumbent"
    if low.startswith("incumbent"):
        return f"incumbent-{role}" if role else "incumbent"
    if low.startswith("challenger"):
        # "Challenger, with past elected experience" vs "no current elected position".
        if "past" in low or "experience" in low or "former" in low:
            return "challenger-experienced"
        return "challenger"

    warnings.append(f"{name}: unrecognized Incumbent? value {value!r} → null (no standing shown)")
    return None


def normalize_slate(value, name, slate_labels, canonical, warnings):
    """Return the slate label to publish, or None if the sheet does not say.

    Unrecognized slates are published as written rather than rejected. New
    electoral organizations get announced mid-campaign, and making this fatal
    (as municipality and standing are) would stall the daily sync (and with it
    every grade update) until someone edited _data/slates.yml.

    Every spelling that slugifies alike publishes ONE label, so the scorecard's
    slate filter gets one pill per slate. Without this, a sheet holding both
    "Together Victoria" and "together victoria" produces two pills carrying the
    same data-slate value, each counting half the candidates and each selecting
    all of them. `canonical` accumulates slug -> label across the run; a
    _data/slates.yml label always wins, otherwise the first spelling the sheet
    happens to use does.
    """
    text = tidy(value)
    if norm(text) in UNKNOWN_VALUES:
        return None

    # scorecard/index.md joins the candidate meta line by splitting on "|", so a
    # literal pipe in a slate name would silently split it into two parts.
    text = tidy(text.replace("|", "/"))

    slug = slugify(text)
    if not slug:
        # Punctuation-only wording ("--", "??") that UNKNOWN_SLATE did not list.
        return None

    if slug in canonical:
        return canonical[slug]

    if slug in slate_labels:
        label = slate_labels[slug] or text
    else:
        # Once per slate, not once per candidate: a 30-candidate slate would
        # otherwise bury every other warning in the CI log.
        warnings.append(f"slate {text!r} (first seen on {name}) has no entry in "
                        f"_data/slates.yml → published as written")
        label = text

    canonical[slug] = label
    return label


def normalize_website(value, name, warnings):
    """Return the candidate's campaign link as an absolute URL, or None.

    The sheet is filled in by hand, so the column holds every shape a person
    types into a spreadsheet: bare domains ("bruceformayor.com"), full URLs,
    Instagram and Facebook profiles, deep links into a platform page, and the
    odd cell padded with spaces. All of those are published; what gets dropped
    is a cell nobody filled in and anything that is not an http(s) address, so a
    typo can never render as a "mailto:" or "javascript:" link on a candidate's
    page.

    Unpublishable wording warns rather than errors: the campaign link is a
    convenience, and a malformed cell must not stall the daily sync (and with it
    every grade update) the way an unknown municipality does.
    """
    text = tidy(value)
    if norm(text) in UNKNOWN_VALUES:
        return None

    if " " in text:
        # Two links in one cell, or a link with a note beside it. Publishing the
        # first half would be a guess at which part the writer meant.
        warnings.append(f"{name}: website {text!r} is not a single URL → no link shown")
        return None

    head = text.split("/", 1)[0]
    if "://" in text:
        scheme = text.split("://", 1)[0].lower()
    elif ":" in head:
        # "mailto:someone@example.ca", "javascript:...": a scheme, just not one
        # this column is for.
        scheme = head.split(":", 1)[0].lower()
    else:
        # The common case in the sheet: a bare domain. https, not http, because
        # every campaign host in the column serves it and a downgrade is ours to
        # avoid causing.
        text = "https://" + text
        scheme = "https"

    if scheme not in ("http", "https"):
        warnings.append(f"{name}: website {text!r} is not an http(s) address → no link shown")
        return None

    parts = urllib.parse.urlsplit(text)
    host = parts.netloc.lower()
    if "." not in host.split(":", 1)[0].strip("."):
        warnings.append(f"{name}: website {text!r} has no usable domain → no link shown")
        return None

    # Click-tracking that rode along when the link was copied out of somebody's
    # Instagram bio. It says nothing about where the link points, it is often
    # longer than the URL carrying it, and it would follow every reader who
    # clicked through from here.
    kept = [
        (k, v) for k, v in urllib.parse.parse_qsl(parts.query, keep_blank_values=True)
        if not (k.lower().startswith("utm_") or k.lower() in TRACKING_PARAMS)
    ]
    query = urllib.parse.urlencode(kept)

    return urllib.parse.urlunsplit((scheme, host, parts.path, query, parts.fragment))


def normalize_grade(value):
    """Return a valid grade string, or None if blank. Raise ValueError if invalid."""
    g = (value or "").strip().upper().replace("−", "-")  # U+2212 minus → hyphen
    if g == "":
        return None
    if g not in VALID_GRADES:
        raise ValueError(g)
    return g


# --- Build records -----------------------------------------------------------

def build_records(rows, muni_lookup, slate_labels, has_slate, has_website,
                  errors, warnings):
    records = []
    skipped = 0
    seen = set()
    # slug -> the one label published for it; see normalize_slate().
    slate_canonical = {}
    for row in rows:
        name = (row.get("Candidate Name") or "").strip()
        if not is_confirmed(row.get("Running?")):
            skipped += 1
            continue
        if not name:
            warnings.append("Confirmed row with blank candidate name → skipped")
            continue

        slug = muni_lookup.get(norm(row.get("Municipality")))
        if not slug:
            errors.append(f"{name}: unknown municipality {row.get('Municipality')!r} "
                          f"(not in _data/municipalities.yml)")
            continue

        key = (name.casefold(), slug)
        if key in seen:
            errors.append(f"Duplicate candidate {name!r} in {slug}")
            continue
        seen.add(key)

        scores = {}
        for column, subject_id in SCORE_MAP:
            try:
                grade = normalize_grade(row.get(column))
            except ValueError as bad:
                errors.append(f"{name}: invalid {column} grade {str(bad)!r} "
                              f"(allowed: {', '.join(sorted(VALID_GRADES))})")
                continue
            if grade is not None:
                scores[subject_id] = grade

        slate = None
        if has_slate:
            slate = normalize_slate(row.get(SLATE_COLUMN), name, slate_labels,
                                    slate_canonical, warnings)

        website = None
        if has_website:
            website = normalize_website(row.get(WEBSITE_COLUMN), name, warnings)

        records.append({
            "name": name,
            "municipality": slug,
            "office": normalize_office(row.get("Position Sought"), name, warnings),
            "standing": normalize_standing(row.get("Incumbent?"), name, warnings),
            "slate": slate,
            "website": website,
            "scores": scores,
        })
    return records, skipped


# --- YAML emission -----------------------------------------------------------

_SPECIAL = set(":#,{}[]&*!|>'\"%@`")


def scalar(value):
    """Emit a YAML scalar; double-quote only when the value isn't plainly safe."""
    s = str(value)
    plain = (
        s != ""
        and s == s.strip()
        and not (_SPECIAL & set(s))
        and s[0] not in "-?"
        and norm(s) not in {"null", "true", "false", "yes", "no", "~", "on", "off"}
    )
    if plain:
        return s
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def office_rank(office):
    return {"Mayor": 0, "Councillor": 1}.get(office, 2)


# Surname particles that belong to the last name rather than the given name(s),
# e.g. "Zac De Vrites" → last name "De Vrites". Matched case-insensitively.
SURNAME_PARTICLES = {
    "de", "da", "di", "del", "della", "dela", "dos", "das", "du",
    "van", "von", "der", "den", "ter", "ten",
    "la", "le", "el", "al", "bin", "ibn", "st", "st.",
}


# Names the particle heuristic below can't get right, e.g. multi-word surnames
# with no particle to key off of. Maps the full name to an explicit
# (last, first) split. Matched case-insensitively on collapsed whitespace.
NAME_SPLIT_OVERRIDES = {
    "teale phelps bondaroff": ("Phelps Bondaroff", "Teale"),
}


def split_name(name):
    """Split "First Middle Last" into (last, first) for "Last, First" display.

    The last name is the final token, extended leftward to absorb any surname
    particles ("de", "van", ...). Everything before it is the given name(s).
    A single-token name yields ("Name", ""). Names in NAME_SPLIT_OVERRIDES
    bypass the heuristic entirely.
    """
    parts = (name or "").split()
    override = NAME_SPLIT_OVERRIDES.get(" ".join(parts).casefold())
    if override:
        return override
    if len(parts) <= 1:
        return (parts[0] if parts else ""), ""
    i = len(parts) - 1
    # Pull particles into the surname, but never consume the whole given name.
    while i > 1 and parts[i - 1].strip(".,").lower() in SURNAME_PARTICLES:
        i -= 1
    return " ".join(parts[i:]), " ".join(parts[:i])


def display_name(name):
    last, first = split_name(name)
    return f"{last}, {first}" if first else last


def sort_key(rec):
    last, first = split_name(rec["name"])
    return (last.casefold(), first.casefold(), office_rank(rec["office"]))


def render_record(rec, subject_order):
    lines = [
        f"- name: {scalar(rec['name'])}",
        f"  display_name: {scalar(display_name(rec['name']))}",
        f"  municipality: {rec['municipality']}",
        f"  office: {rec['office'] if rec['office'] else 'null'}",
        f"  standing: {rec['standing'] if rec['standing'] else 'null'}",
        f"  slate: {scalar(rec['slate']) if rec['slate'] else 'null'}",
        f"  website: {scalar(rec['website']) if rec['website'] else 'null'}",
    ]
    if rec["scores"]:
        lines.append("  scores:")
        for sid in subject_order:
            if sid in rec["scores"]:
                lines.append(f"    {sid}: {rec['scores'][sid]}")
    return "\n".join(lines)


def render_yaml(records, ordered_munis, subject_order):
    parts = [HEADER]
    by_slug = {}
    for rec in records:
        by_slug.setdefault(rec["municipality"], []).append(rec)
    for slug, name in ordered_munis:
        group = by_slug.get(slug)
        if not group:
            continue
        group.sort(key=sort_key)
        parts.append("")
        parts.append(f"# --- {name} ---")
        for i, rec in enumerate(group):
            if i:
                parts.append("")
            parts.append(render_record(rec, subject_order))
    return "\n".join(parts) + "\n"


# --- Main --------------------------------------------------------------------

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--csv-url", default=os.environ.get("CANDIDATES_CSV_URL"))
    ap.add_argument("--csv-file", help="Read CSV from a local file instead of the URL (testing).")
    ap.add_argument("--out", default=OUT_DEFAULT)
    ap.add_argument("--dry-run", action="store_true", help="Print summary; do not write.")
    ap.add_argument("--allow-empty", action="store_true",
                    help="Permit zero confirmed candidates (default: fatal).")
    args = ap.parse_args(argv)

    # Subject ids order (for stable scores emission) + sanity-check SCORE_MAP.
    subject_ids = load_ids(SUBJECTS_YML)
    subject_order = [sid for _, sid in SCORE_MAP]
    missing = [sid for sid in subject_order if sid not in subject_ids]
    if missing:
        sys.exit(f"FATAL: score map targets not in subjects.yml: {missing}")

    standing_ids = load_ids(STANDINGS_YML)
    slate_labels = load_slates(SLATES_YML)

    ordered_munis, muni_lookup = load_municipalities(MUNI_YML)

    # Acquire CSV text.
    if args.csv_file:
        with open(args.csv_file, encoding="utf-8-sig") as f:
            text = f.read()
    elif args.csv_url:
        try:
            text = fetch_csv(args.csv_url)
        except (urllib.error.URLError, urllib.error.HTTPError, OSError) as e:
            sys.exit(f"FATAL: could not fetch CSV: {e}")
    else:
        sys.exit("FATAL: set CANDIDATES_CSV_URL (or pass --csv-url/--csv-file).")

    if text.lstrip()[:1] == "<":
        sys.exit("FATAL: response looks like HTML, not CSV "
                 "(check the sheet's sharing settings / export URL).")

    reader = csv.DictReader(io.StringIO(text))
    fields = reader.fieldnames or []
    missing_cols = [c for c in REQUIRED_COLUMNS if c not in fields]
    if missing_cols:
        sys.exit(f"FATAL: CSV missing expected columns {missing_cols}; got {fields}")

    errors, warnings = [], []

    # Optional column: warn once rather than per row, and publish no slates.
    has_slate = SLATE_COLUMN in fields
    if not has_slate:
        warnings.append(f"CSV has no {SLATE_COLUMN!r} column: no slate published "
                        f"for any candidate")

    # Grade columns are optional too, and their absence is deliberately NOT
    # warned about: the coalition moved grades to a separate sheet, so every
    # column in SCORE_MAP is expected to be missing and flagging it on every run
    # is pure noise. A grade that is present but unparseable still errors below.

    has_website = WEBSITE_COLUMN in fields
    if not has_website:
        warnings.append(f"CSV has no {WEBSITE_COLUMN!r} column: no campaign link "
                        f"published for any candidate")

    records, skipped = build_records(list(reader), muni_lookup, slate_labels,
                                     has_slate, has_website, errors, warnings)

    # A standing id with no entry in standings.yml would render as a blank label,
    # so treat it as fatal rather than shipping an unexplained gap.
    for rec in records:
        if rec["standing"] and rec["standing"] not in standing_ids:
            errors.append(f"{rec['name']}: standing {rec['standing']!r} has no entry in "
                          f"_data/standings.yml (add one, or fix normalize_standing)")

    for w in warnings:
        print(f"WARN: {w}", file=sys.stderr)

    if errors:
        for e in errors:
            print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(f"FATAL: {len(errors)} validation error(s); candidates.yml not written.")

    if not records and not args.allow_empty:
        sys.exit("FATAL: zero confirmed candidates parsed; refusing to overwrite "
                 "candidates.yml (use --allow-empty to override).")

    print(f"{len(records)} confirmed, {skipped} skipped, {len(warnings)} warning(s).")

    rendered = render_yaml(records, ordered_munis, subject_order)

    existing = ""
    if os.path.exists(args.out):
        with open(args.out, encoding="utf-8") as f:
            existing = f.read()
    if rendered == existing:
        print("No change to candidates.yml.")
        return 0

    if args.dry_run:
        print("--- candidates.yml would change (dry-run) ---")
        print(rendered)
        return 0

    with open(args.out, "w", encoding="utf-8") as f:
        f.write(rendered)
    print(f"Wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
