# frozen_string_literal: true

require "shellwords"
require "time"

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
                   standing_label:, slate_class: nil, election_year: nil,
                   last_modified_at: nil)
      super(site, site.source, dir, "index.html")

      # jekyll-sitemap takes <lastmod> from a source file's mtime, and these
      # pages have no source file, so all of them shipped without one. The
      # generator hands down the mtime of the data files the page is built from
      # instead; see data_mtime in CandidatePages for why that is the honest
      # date. Without it the twice-daily sync rebuilds the whole site and tells
      # a crawler nothing has changed, which matters most on the day the grades
      # land and 117 pages gain their content at once.
      data["last_modified_at"] = last_modified_at if last_modified_at

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
                   candidate_count:, siblings:, race_counts: {}, municipality: {},
                   election_day: nil, election_year: nil, last_modified_at: nil)
      super(site, site.source, dir, "index.html")

      # See the note on CandidatePage: no source file, so no mtime, so no
      # <lastmod> in the sitemap unless the generator supplies one.
      data["last_modified_at"] = last_modified_at if last_modified_at

      data["layout"] = "municipality"
      data["municipality_name"] = municipality_name
      data["municipality_slug"] = municipality_slug
      data["office_groups"] = office_groups
      data["candidate_count"] = candidate_count
      data["race_counts"] = race_counts
      data["siblings"] = siblings
      data["election_year"] = election_year

      # Election day, and what this municipality actually elects. Both are
      # optional and the template draws neither when they are missing: the
      # date lives in _data/deadlines.yml and the seat counts in
      # _data/municipalities.yml, and a page that has to wait for one of them
      # is better than a page that guesses. Seat counts especially: this is an
      # elections site, and a wrong number of council seats is worse than no
      # number at all.
      data["election_day"] = election_day
      data["election_day_label"] = format_election_day(election_day)
      data["council_seats"] = municipality["council_seats"]
      data["mayor_seats"] = municipality["mayor_seats"]
      data["elections_url"] = municipality["elections_url"]
      data["summary"] = municipality["summary"]

      # "Esquimalt Municipal Election 2026": the words in the order they get
      # typed. This page used to be titled "Esquimalt Candidates 2026", which
      # matches "esquimalt candidates 2026" and nothing else; the query people
      # actually type is the name of the election, and the head term for it was
      # the one word the title never said. "Candidates" is not lost - it is in
      # the h2 over the list, in every office heading, and in the description
      # below - and "election" is the word this page was losing on.
      #
      # The longest name in _data/municipalities.yml that has a page (Central
      # Saanich, 39 characters here) still leaves seo-tag's appended
      # " | Livable CRD" inside the ~60 characters Google displays.
      data["title"] = [municipality_name, "Municipal Election", election_year].compact.join(" ")
      data["description"] = description_for(municipality_name, election_year, data["election_day_label"])
    end

    private

    # The one date on this page a voter cannot look up faster somewhere else,
    # written the way it is spoken. nil when _config.yml sets no `election_day`,
    # which is what keeps the date out of the description and off the page
    # rather than printing a guess: this is an elections site, and a wrong
    # general voting day is the single worst fact it could publish.
    def format_election_day(date)
      return nil unless date.respond_to?(:strftime)

      date.strftime("%A, %B %-d, %Y")
    end

    # Under ~160 characters, and as silent about grades as the candidate pages
    # are, for the same reason: most of the list it describes is pending until
    # the questionnaires come back.
    #
    # Leads with the date because that is the question behind the query: someone
    # searching "saanich municipal election 2026" wants to know when it is
    # before they want to know who is on the ballot. Falls back to the wording
    # this description carried before the date existed, so a missing
    # election-day entry costs a sentence rather than the description.
    def description_for(municipality_name, election_year, election_day_label)
      if election_day_label
        "#{municipality_name} municipal election, #{election_day_label}. Every confirmed " \
          "candidate, with the Livable CRD scorecard on transit, housing, and climate."
      else
        election = election_year ? "the #{election_year} municipal election" : "the coming municipal election"
        "Every confirmed candidate running in #{municipality_name} in #{election}, " \
          "with the Livable CRD scorecard on transit, housing, and climate."
      end
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

      # Stat'd once here rather than per page: 129 pages would otherwise stat
      # the same two files 129 times to arrive at the same two answers.
      candidates_mtime = data_mtime(site, "candidates")
      # A candidate page's content is the join of both files, so its <lastmod>
      # is the later of the two. sync-questionnaire.yml rewrites scores.yml
      # half an hour after sync-candidates.yml rewrites candidates.yml, and it
      # is the grades landing in the former that a crawler needs to come back
      # for.
      candidate_mtime = [candidates_mtime, data_mtime(site, "scores")].compact.max

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
          election_year: election_year,
          last_modified_at: candidate_mtime
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
          # Whether this person holds elected office right now, straight from
          # _data/standings.yml's `current` rather than matched off the id or
          # the label: a former mayor and a sitting one both read "Incumbent"
          # in one and carry "incumbent" in the other, and only `current`
          # separates them. Counted on the municipality index.
          "incumbent" => standings.dig(candidate["standing"], "current") == true,
          "slate" => slate.empty? ? nil : slate
        }
      end

      build_municipality_pages(site, groups, election_year, candidates_mtime)
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
    def build_municipality_pages(site, groups, election_year, last_modified_at)
      # Every index links to all the others, so each one is reachable from any of
      # them rather than only from the scorecard. Sorted by name because the
      # reader scans this list for a place, and `groups` is in the order the
      # candidate rows happened to arrive in.
      slugs = groups.keys.sort_by { |slug| groups[slug]["name"] }
      directory = slugs.map { |slug| { "name" => groups[slug]["name"], "url" => "/scorecard/#{slug}/" } }
      municipalities = index_by(site.data["municipalities"], "slug")
      election_day = election_day(site)

      slugs.each do |slug|
        entries = groups[slug]["entries"]

        site.pages << MunicipalityPage.new(
          site,
          File.join("scorecard", slug),
          municipality_name: groups[slug]["name"],
          municipality_slug: slug,
          office_groups: office_groups(entries),
          candidate_count: entries.size,
          # Counted here rather than in Liquid: the template would have to
          # filter the same list twice more, and these two numbers are the only
          # sentence on the page that is not a name or a shared template.
          race_counts: race_counts(entries),
          municipality: municipalities[slug] || {},
          election_day: election_day,
          siblings: directory.reject { |m| m["url"] == "/scorecard/#{slug}/" },
          election_year: election_year,
          last_modified_at: last_modified_at
        )
      end
    end

    # How many are seeking each office, and how many of the whole field already
    # hold elected office somewhere. "23 confirmed candidates, 4 running for
    # mayor, 6 of them incumbents" is the one line on a municipality index that
    # is true of that municipality and no other, which is the whole reason it is
    # computed.
    def race_counts(entries)
      {
        "total" => entries.size,
        "mayor" => entries.count { |e| e["office"] == "Mayor" },
        "councillor" => entries.count { |e| e["office"] == "Councillor" },
        "incumbent" => entries.count { |e| e["incumbent"] }
      }
    end

    # Election day, from `election_day` in _config.yml beside `election_year`.
    #
    # Deliberately not an entry in _data/deadlines.yml, which is the coalition's
    # own schedule: every date in that file is something this project does, the
    # homepage draws it under the heading "Project timeline", and commit 3503fe4
    # settled that it ends on the day the grades are published. General voting
    # day is not a project milestone, it is a fact about the election, and
    # filing it there would reopen that decision and put a date nobody here
    # controls in a list of dates this coalition owns.
    #
    # nil when the key is absent or unparseable, and every template that uses it
    # draws nothing rather than a gap - the same contract the rest of this file
    # keeps with `election_year`.
    def election_day(site)
      raw = site.config["election_day"]
      return nil if raw.to_s.strip.empty?

      Date.parse(raw.to_s)
    rescue ArgumentError
      log_data_warning("election_day #{raw.inspect} in _config.yml is not a date; omitting it")
      nil
    end

    # When the data behind a generated page last changed.
    #
    # The commit date, NOT the file's mtime. actions/checkout writes every file
    # at checkout time, so in CI an mtime says "changed just now" on every
    # build, and a sitemap that claims all 129 pages changed every day is worth
    # less than one that claims nothing - a crawler learns to ignore it, which
    # is the opposite of the point. The commit date is the same on every
    # machine and moves only when the sync workflow actually commits new data.
    #
    # This needs full history: .github/workflows/deploy.yml sets fetch-depth: 0
    # for exactly this reason. Falls back to the mtime if git cannot answer (a
    # shallow clone, a tarball, no git at all), which is right locally and
    # merely unhelpful in CI - never wrong enough to fail a build over.
    def data_mtime(site, name)
      path = site.in_source_dir("_data", "#{name}.yml")
      return nil unless File.exist?(path)

      @data_mtimes ||= {}
      @data_mtimes[path] ||= git_commit_time(site, path) || begin
        log_data_warning("no git history for _data/#{name}.yml; <lastmod> falls back to the file mtime")
        File.mtime(path)
      end
    end

    # Last commit to touch one path, as a Time, or nil if git cannot say.
    # Deliberately swallows everything: a sitemap timestamp is not worth failing
    # a build for, and every caller above already handles nil.
    def git_commit_time(site, path)
      output = Dir.chdir(site.source) do
        `git log -1 --format=%cI -- #{Shellwords.escape(path)} 2>/dev/null`
      end
      return nil unless $?&.success?

      stamp = output.to_s.strip
      stamp.empty? ? nil : Time.parse(stamp)
    rescue StandardError
      nil
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
