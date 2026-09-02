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
    def initialize(site, dir, candidate:, municipality_name:, municipality_slug:,
                   standing_label:, slate_class: nil, election_year: nil)
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
      # Carried so the hero can link up to the municipality index. It is the same
      # slug this page's own URL is built from rather than one re-slugified in the
      # template, so the breadcrumb cannot point at a directory the generator
      # below never created.
      data["municipality_slug"] = municipality_slug
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

      # The candidate's own campaign page, and the text the link shows. Both nil
      # when the tracking sheet lists no link; a blank cell arrives as "", the
      # same as the slate above. sync-candidates.py has already reduced whatever
      # was typed into the cell to an absolute http(s) URL, so nothing here has
      # to defend against a "javascript:" address.
      #
      # Pointing at a campaign page is signposting, not an endorsement, which is
      # also why the template links it rel="nofollow".
      website = candidate["website"].to_s.strip
      data["website"] = website.empty? ? nil : website
      data["website_label"] = website.empty? ? nil : website_label(website)

      # jekyll-seo-tag renders `title` as "<title> | Livable CRD", so qualify the
      # name here: a bare "Jane Doe" is meaningless in a search result, and two
      # candidates in different municipalities would be indistinguishable.
      #
      # The year is the last qualifier, and it is there for search rather than for
      # the reader: people look up "esquimalt candidates 2026", and a title that
      # never says which election this is has nothing to match on.
      #
      # Every qualifier fits inside the ~60 characters Google shows: the longest
      # of these in the region ("Kathleen Zimmerman, Councillor, Central Saanich
      # 2026") is 52. Four of them push past 60 once seo-tag appends its
      # " | Livable CRD", and are left to: the site name is the half a truncated
      # title can afford to lose, and shortening the name, the office or the
      # municipality to save it would cost the words the query is made of.
      qualifiers = [name, office, municipality_name].compact
      data["title"] = [qualifiers.join(", "), election_year].compact.join(" ")
      data["description"] = description_for(name, office, municipality_name, election_year)

      # og:image intentionally falls through to the site-wide default set in
      # _config.yml's `defaults:`. A per-candidate share card is out of scope:
      # it needs 66 rendered images and there is no image pipeline in this
      # build. Once one exists, setting `data["image"]` here (same
      # {path,width,height,alt} shape as the default) is all seo-tag needs.
    end

    private

    # Longest link text this page draws in full. Past it the path is dropped and
    # only the domain is shown: the label sits under the candidate's name in the
    # hero and is what the print leaflet spells out in place of a clickable link,
    # and a Facebook group URL carrying two 15-digit ids is neither readable
    # there nor typeable off paper.
    WEBSITE_LABEL_MAX = 45

    # What the link says: the address without the scheme, without a "www." that
    # tells a reader nothing, and without a trailing slash. The path is kept
    # where it is short, because for a candidate whose only page is a social
    # profile ("instagram.com/noah4saanich") the path is the half that identifies
    # them, and the leaflet's reader has to be able to type what they see.
    def website_label(url)
      bare = url.sub(%r{\Ahttps?://}i, "").sub(/\Awww\./i, "").sub(%r{/\z}, "")
      return bare if bare.length <= WEBSITE_LABEL_MAX

      bare.split("/", 2).first
    end

    # Kept under ~160 characters so search engines and link previews show the
    # whole thing, with the longest name in the region ("Kathleen Zimmerman",
    # Central Saanich) landing at 157. Deliberately says nothing about the grades
    # themselves: every candidate is pending until the questionnaire comes back,
    # and a description promising grades that are not there yet reads as a
    # bait-and-switch.
    def description_for(name, office, municipality_name, election_year)
      seeking = office ? "running for #{office} in #{municipality_name}" : "running in #{municipality_name}"
      election = election_year ? " in the #{election_year} municipal election" : ""
      "#{name}, #{seeking}#{election}. See the Livable CRD scorecard on transit, housing, and climate."
    end
  end

  # A municipality's own index of who is running there, with that municipality's
  # candidate pages hanging off it.
  #
  # It exists because it was the hole in the middle of this section:
  # /scorecard/esquimalt/ was a bare directory holding nine candidate pages and
  # 404ing on its own, so the question a voter actually types — who is running in
  # my municipality — had no page here to answer it, and those nine pages had no
  # parent to be found from. The scorecard's own /scorecard/?muni=esquimalt view
  # answers it for a reader who is already on the site, but a query string on a
  # table that JavaScript filters is not a page a search engine can offer anyone.
  class MunicipalityPage < Jekyll::PageWithoutAFile
    def initialize(site, dir, municipality_name:, municipality_slug:, office_groups:,
                   candidate_count:, siblings:, election_year: nil)
      super(site, site.source, dir, "index.html")

      data["layout"] = "municipality"
      data["municipality_name"] = municipality_name
      data["municipality_slug"] = municipality_slug
      data["office_groups"] = office_groups
      data["candidate_count"] = candidate_count
      data["siblings"] = siblings
      data["election_year"] = election_year

      # "Esquimalt Candidates 2026": the words in the order they get typed. The
      # longest name in _data/municipalities.yml still leaves seo-tag's appended
      # " | Livable CRD" inside the ~60 characters Google displays.
      data["title"] = [municipality_name, "Candidates", election_year].compact.join(" ")
      data["description"] = description_for(municipality_name, election_year)
    end

    private

    # Under ~160 characters, and as silent about grades as the candidate pages
    # are, for the same reason: most of the list it describes is pending until
    # the questionnaires come back.
    def description_for(municipality_name, election_year)
      election = election_year ? "the #{election_year} municipal election" : "the coming municipal election"
      "Every confirmed candidate running in #{municipality_name} in #{election}, " \
        "with the Livable CRD scorecard on transit, housing, and climate."
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
      election_year = site.config["election_year"]
      seen = {}

      # {municipality slug => {name, entries}}, filled as the candidate pages are
      # built and turned into the municipality indexes below. Accumulated on this
      # pass rather than re-derived from site.data["candidates"] on a second one,
      # so an entry the loop skips (no name, no municipality, a name that
      # slugifies to nothing) is absent from both, and the index never lists
      # somebody whose page was never written.
      groups = {}

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

        label = standing_label(standings[candidate["standing"]], candidate["office"])

        site.pages << CandidatePage.new(
          site,
          dir,
          candidate: candidate,
          municipality_name: municipality_name,
          municipality_slug: muni_slug,
          standing_label: label,
          slate_class: site.data["slate_classes"][candidate["slate"].to_s.strip],
          election_year: election_year
        )

        slate = candidate["slate"].to_s.strip
        group = groups[muni_slug] ||= { "name" => municipality_name, "entries" => [] }
        group["entries"] << {
          "name" => name,
          "display_name" => candidate["display_name"] || name,
          # Path only, no baseurl: the template passes it through `relative_url`
          # the way every other link on the site is written.
          "url" => "/#{dir}/",
          "office" => candidate["office"],
          "standing_label" => label,
          "slate" => slate.empty? ? nil : slate
        }
      end

      build_municipality_pages(site, groups, election_year)
    end

    private

    # One index per municipality that has at least one confirmed candidate.
    #
    # Nothing is generated for a municipality with nobody confirmed yet. The
    # scorecard already covers those: it keeps a heading for every municipality
    # in the region precisely so an empty one reads as "nobody has announced
    # here" rather than as an oversight, and it carries the line inviting a
    # reader to name a candidate we have missed. A page of its own whose entire
    # content is that sentence would be a thin result competing with the pages
    # that do answer the question.
    def build_municipality_pages(site, groups, election_year)
      # Every index links to all the others, so each one is reachable from any of
      # them rather than only from the scorecard. Sorted by name because the
      # reader scans this list for a place, and `groups` is in the order the
      # candidate rows happened to arrive in.
      slugs = groups.keys.sort_by { |slug| groups[slug]["name"] }
      directory = slugs.map { |slug| { "name" => groups[slug]["name"], "url" => "/scorecard/#{slug}/" } }

      slugs.each do |slug|
        entries = groups[slug]["entries"]

        site.pages << MunicipalityPage.new(
          site,
          File.join("scorecard", slug),
          municipality_name: groups[slug]["name"],
          municipality_slug: slug,
          office_groups: office_groups(entries),
          candidate_count: entries.size,
          siblings: directory.reject { |m| m["url"] == "/scorecard/#{slug}/" },
          election_year: election_year
        )
      end
    end

    # Offices in the order a ballot puts them: mayor, then council, then whatever
    # else a place elects (an electoral area's director, say) alphabetically, and
    # last the candidates whose office the tracking sheet does not record.
    #
    # Ordered here rather than in Liquid because `group_by` there returns groups
    # in the order the rows arrived in, and row order in a spreadsheet is not a
    # running order: a sort of the sheet would silently reshuffle every page.
    BALLOT_ORDER = ["Mayor", "Councillor"].freeze

    # What each group's heading says. An office not named here is titled from its
    # own label, so a new office appearing on a ballot needs no code change.
    OFFICE_HEADINGS = {
      "Mayor" => "Candidates for mayor",
      "Councillor" => "Candidates for council"
    }.freeze

    def office_groups(entries)
      by_office = entries.group_by do |entry|
        office = entry["office"].to_s.strip
        office.empty? ? nil : office
      end

      ordered = BALLOT_ORDER.select { |office| by_office.key?(office) }
      ordered += (by_office.keys - BALLOT_ORDER).compact.sort
      ordered << nil if by_office.key?(nil)

      ordered.map do |office|
        { "office" => office, "heading" => heading_for(office), "candidates" => by_office[office] }
      end
    end

    # "Other candidates" and not "Candidates for an unknown office": a blank
    # office cell means the sheet does not record what they are running for, and
    # the heading should not turn that into a statement about the candidate.
    def heading_for(office)
      return "Other candidates" unless office

      OFFICE_HEADINGS[office] || "Candidates for #{office.downcase}"
    end

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
