# frozen_string_literal: true

# Per-candidate scorecard pages, one for every entry in _data/candidates.yml.
#
# Checked-in Markdown files were rejected: candidates.yml is itself regenerated
# from the coalition tracking sheet by scripts/sync-candidates.py (see the header
# comment in that file), so a hand-maintained page per candidate would go stale
# the moment a new name is confirmed, and nobody would notice until a link 404s.
# Generating the pages keeps the sheet the single source of truth for who exists.
#
# This file runs because .github/workflows/deploy.yml builds the site with
# `bundle exec jekyll build` rather than handing the repo to GitHub Pages' own
# builder: the latter runs Jekyll in safe mode and silently ignores _plugins/.
module LivableCrd
  # A page Jekyll writes straight from `data`; there is no source file on disk.
  # `index.html` inside a per-candidate directory gives the pretty URL the rest
  # of the site uses (/scorecard/saanich/jane-doe/) without a `permalink` key.
  class CandidatePage < Jekyll::PageWithoutAFile
    def initialize(site, dir, candidate, municipality_name, standing_label, slate_class = nil)
      super(site, site.source, dir, "index.html")

      name = candidate["name"]
      office = candidate["office"]

      data["layout"] = "candidate"
      # Read by _layouts/default.html. The print leaflet has to hide the site
      # header and footer, which live outside this layout's content, and those
      # rules must not apply when any other page is printed.
      data["body_class"] = "page-candidate"
      data["candidate"] = candidate
      data["municipality_name"] = municipality_name
      data["standing_label"] = standing_label

      # One pre-joined subtitle rather than three fields the template has to
      # stitch together with separators: every part is optional in the source
      # data, and getting the middots right in Liquid takes more conditionals
      # than it is worth. Same string is reused by the print leaflet.
      data["subtitle"] = [office, municipality_name, standing_label].compact.join(" · ")

      # Slate stays out of that line and gets its own labelled one in the
      # template. Dropped into the middots it read as a fourth attribute of the
      # same kind as the standing beside it: "Newcomer · Sooke First" gives a
      # reader no way to tell that the last part is an electoral organization.
      # Normalized to nil here because a blank sheet cell arrives as "".
      slate = candidate["slate"].to_s.strip
      data["slate"] = slate.empty? ? nil : slate
      data["slate_class"] = slate.empty? ? nil : slate_class

      # jekyll-seo-tag renders `title` as "<title> | Livable CRD", so qualify the
      # name here: a bare "Jane Doe" is meaningless in a search result, and two
      # candidates in different municipalities would be indistinguishable.
      data["title"] = office ? "#{name}, #{office}, #{municipality_name}" : "#{name}, #{municipality_name}"
      data["description"] = description_for(name, office, municipality_name)

      # og:image intentionally falls through to the site-wide default set in
      # _config.yml's `defaults:`. A per-candidate share card is out of scope:
      # it needs 66 rendered images and there is no image pipeline in this
      # build. Once one exists, setting `data["image"]` here (same
      # {path,width,height,alt} shape as the default) is all seo-tag needs.
    end

    private

    # Kept under ~160 characters so search engines and link previews show the
    # whole thing. Deliberately says nothing about the grades themselves: every
    # candidate is pending until the questionnaire comes back, and a description
    # promising grades that are not there yet reads as a bait-and-switch.
    def description_for(name, office, municipality_name)
      seeking = office ? "candidate for #{office} in #{municipality_name}" : "candidate in #{municipality_name}"
      "#{name}, #{seeking}. See the Livable CRD coalition scorecard on transit, housing, climate, arts, and more."
    end
  end

  class CandidatePages < Jekyll::Generator
    safe true
    priority :normal

    # Palette slots defined in _sass/_candidate.scss / _components.scss as
    # .slate-c1 … .slate-c8. Slates beyond the eighth wrap around and share a
    # colour, which is why the legend always spells the slate out in text.
    SLATE_PALETTE_SIZE = 8

    def generate(site)
      candidates = site.data["candidates"]
      return unless candidates.is_a?(Array)

      # Published so scorecard/index.md can colour its rows from the same map
      # these pages use. Computing it twice (once here, once in Liquid) is how
      # the two would drift into disagreeing about which slate is which colour.
      site.data["slate_classes"] = slate_classes(candidates)

      municipalities = index_by(site.data["municipalities"], "slug")
      standings = index_by(site.data["standings"], "id")
      seen = {}

      candidates.each do |candidate|
        next unless candidate.is_a?(Hash)

        name = candidate["name"].to_s.strip
        muni_slug = candidate["municipality"].to_s.strip

        # Both halves of the URL come from the data, so an entry missing either
        # has nowhere to live. The scorecard table groups strictly by
        # municipality slug and does not list these entries either, so skipping
        # keeps the table and the pages describing the same set of people.
        if name.empty? || muni_slug.empty?
          log_data_warning("skipping candidate with no name or municipality: #{candidate.inspect}")
          next
        end

        # A non-empty name can still slugify to nothing: "—" or "???" survive
        # .strip but reduce to "". That would build the page at .../<muni>//,
        # i.e. the municipality directory itself, and scorecard/index.md would
        # link somewhere that does not exist. The template suppresses the link
        # on the same condition, so both sides skip the same entries.
        name_slug = Jekyll::Utils.slugify(name)
        if name_slug.to_s.empty?
          log_data_warning("skipping candidate whose name has no URL-safe characters: #{name.inspect}")
          next
        end

        dir = File.join("scorecard", muni_slug, name_slug)

        # Candidate names are unique across the region today, so name +
        # municipality is a stable id. Should that ever change, both pages would
        # render to the same path and the later one would win silently. Warn
        # rather than disambiguate: the URL stays purely derived from the data,
        # which is what lets scorecard/index.md rebuild the same href in Liquid.
        log_data_warning("duplicate candidate URL /#{dir}/: a later entry overwrites an earlier one") if seen.key?(dir)
        seen[dir] = true

        municipality = municipalities[muni_slug]
        # An unrecognized slug is a data error upstream, not a reason to fail the
        # build. Fall back to a readable form of the slug so the page still says
        # something true, and leave the warning for whoever fixes the sheet.
        log_data_warning("candidate #{name} has unknown municipality '#{muni_slug}'") unless municipality
        municipality_name = municipality ? municipality["name"] : humanize(muni_slug)

        site.pages << CandidatePage.new(
          site,
          dir,
          candidate,
          municipality_name,
          standing_label(standings[candidate["standing"]], candidate["office"]),
          site.data["slate_classes"][candidate["slate"].to_s.strip]
        )
      end
    end

    private

    # {slate label => palette class}. Assigned by alphabetical order of the
    # label, deliberately not by first appearance in the sheet: row order in a
    # spreadsheet changes whenever someone sorts it, and a colour that silently
    # moves from one slate to another between two nightly syncs is worse than no
    # colour at all. Alphabetical means the mapping only shifts when the set of
    # slates itself changes.
    def slate_classes(candidates)
      labels = candidates.map { |c| c.is_a?(Hash) ? c["slate"].to_s.strip : "" }
                         .reject(&:empty?)
                         .uniq
                         .sort

      labels.each_with_object({}).with_index do |(label, acc), i|
        acc[label] = "slate-c#{(i % SLATE_PALETTE_SIZE) + 1}"
      end
    end

    # Mirrors the role-qualified logic in scorecard/index.md: when the standing
    # names a role different from the office being sought, use the role-qualified
    # label, so a sitting councillor running for mayor reads "Incumbent
    # Councillor" rather than a misleading bare "Incumbent".
    def standing_label(standing, office)
      return nil unless standing.is_a?(Hash)

      if standing["role"] && standing["role"] != office
        standing["role_label"]
      else
        standing["label"]
      end
    end

    def index_by(rows, key)
      return {} unless rows.is_a?(Array)

      rows.each_with_object({}) do |row, acc|
        acc[row[key]] = row if row.is_a?(Hash)
      end
    end

    def humanize(slug)
      slug.split("-").map(&:capitalize).join(" ")
    end

    def log_data_warning(message)
      Jekyll.logger.warn "Candidate pages:", message
    end
  end
end
