#!/usr/bin/env python3
"""Regenerate _data/candidates.yml from the coalition candidate-tracking sheet.

Fetches the Google Sheet as CSV (public export URL), keeps only the columns we
publish, validates the data, and writes a byte-stable _data/candidates.yml that
matches the existing hand-authored format (documented header + "# --- City ---"
group comments). The sheet is the single source of truth; this file is meant to
run in CI (see .github/workflows/sync-candidates.yml).

Stdlib only — no third-party deps (matches scripts/gen-social-assets.py).

Usage:
  CANDIDATES_CSV_URL=... python3 scripts/sync-candidates.py
  python3 scripts/sync-candidates.py --csv-file sample.csv --dry-run
"""

import argparse
import csv
import io
import os
import sys
import urllib.request
import urllib.error

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MUNI_YML = os.path.join(ROOT, "_data", "municipalities.yml")
SUBJECTS_YML = os.path.join(ROOT, "_data", "subjects.yml")
OUT_DEFAULT = os.path.join(ROOT, "_data", "candidates.yml")

# Sheet column -> subject id (in _data/subjects.yml). "general" has no column.
SCORE_MAP = [
    ("Housing", "housing"),
    ("Transit", "transit"),
    ("Climate", "climate"),
    ("Arts", "arts"),
    ("Cycling", "rolling-cycling"),
    ("Walking", "walking"),
    ("Health", "healthcare-access"),
]

# Grades with a corresponding CSS class in _sass/_components.scss. Anything else
# (incl. "D", which has no style) is rejected so a typo can't ship an unstyled badge.
VALID_GRADES = {"A", "B", "C", "C-", "F"}

REQUIRED_COLUMNS = ("Candidate Name", "Municipality", "Running?")

# Reproduced (and updated for the automation) from the original hand-authored file.
HEADER = """\
# Confirmed municipal election candidates, grouped by municipality.
#
# AUTO-GENERATED — do not edit by hand.
# Regenerated from the coalition candidate-tracking sheet by
# scripts/sync-candidates.py (CI: .github/workflows/sync-candidates.yml).
# Edit the source spreadsheet, not this file — manual changes are overwritten.
#
# Includes ONLY candidates whose status is confirmed ("Yes Confirmed") as running.
# Suspected, declined, and unconfirmed entries are intentionally omitted.
#
# Subjective tracking notes (political "vibe", commentary, character assessments)
# are intentionally NOT published here — the scorecard evaluates positions, not
# people. Only factual public-record fields are stored.
#
# Fields:
#   name         Candidate's name as listed ("First Last").
#   display_name Same name rendered "Last, First" for the scorecard, with
#                surname particles ("de", "van", ...) kept on the last name.
#   municipality Slug matching _data/municipalities.yml.
#   office       "Mayor", "Councillor", or null if not specified in the source.
#   incumbent    true = incumbent, false = challenger, null = unspecified.
#   scores       Map of per-topic letter grades, keyed by the topic ids in
#                _data/subjects.yml. Any topic left blank renders as pending ("—").
#
# Within each municipality, candidates are ordered alphabetically by last name."""


def norm(s):
    """Lowercase, trim, and collapse internal whitespace."""
    return " ".join((s or "").split()).lower()


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


def load_subject_ids(path):
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


def normalize_incumbent(value, name, warnings):
    low = norm(value)
    if low == "":
        return None
    if low.startswith("incumbent"):
        return True
    if low.startswith("challenger"):
        return False
    warnings.append(f"{name}: unrecognized incumbent {value!r} → null")
    return None


def normalize_grade(value):
    """Return a valid grade string, or None if blank. Raise ValueError if invalid."""
    g = (value or "").strip().upper().replace("−", "-")  # U+2212 minus → hyphen
    if g == "":
        return None
    if g not in VALID_GRADES:
        raise ValueError(g)
    return g


# --- Build records -----------------------------------------------------------

def build_records(rows, muni_lookup, errors, warnings):
    records = []
    skipped = 0
    seen = set()
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

        records.append({
            "name": name,
            "municipality": slug,
            "office": normalize_office(row.get("Position Sought"), name, warnings),
            "incumbent": normalize_incumbent(row.get("Incumbent?"), name, warnings),
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


def split_name(name):
    """Split "First Middle Last" into (last, first) for "Last, First" display.

    The last name is the final token, extended leftward to absorb any surname
    particles ("de", "van", ...). Everything before it is the given name(s).
    A single-token name yields ("Name", "").
    """
    parts = (name or "").split()
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
        f"  incumbent: {'true' if rec['incumbent'] is True else 'false' if rec['incumbent'] is False else 'null'}",
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
    subject_ids = load_subject_ids(SUBJECTS_YML)
    subject_order = [sid for _, sid in SCORE_MAP]
    missing = [sid for sid in subject_order if sid not in subject_ids]
    if missing:
        sys.exit(f"FATAL: score map targets not in subjects.yml: {missing}")

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
    records, skipped = build_records(list(reader), muni_lookup, errors, warnings)

    for w in warnings:
        print(f"WARN: {w}", file=sys.stderr)

    if errors:
        for e in errors:
            print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(f"FATAL: {len(errors)} validation error(s); candidates.yml not written.")

    if not records and not args.allow_empty:
        sys.exit("FATAL: zero confirmed candidates parsed — refusing to overwrite "
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
