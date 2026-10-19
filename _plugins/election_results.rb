# frozen_string_literal: true

# Joins _data/results.yml onto the candidates, as a `result` hash on each one
# who was on the ballot:
#
#   office       "Mayor" or "Councillor": the race this result is from
#   votes        votes received, or nil for an acclamation
#   votes_label  the same with thousands separators ("16,615"), or nil
#   percent      one decimal place, or nil for an acclamation
#   elected      true for a winner
#   acclaimed    true for a candidate elected without a vote
#   place        where they finished in their race, or nil for an acclamation
#   place_label  the same as an ordinal ("3rd"), or nil
#   field        how many were on that ballot
#   seats        how many that ballot elected
#
# A candidate with no entry in results.yml gets no `result` at all, and the
# scorecard prints nothing for them: they are confirmed in the tracking sheet
# but were not on the ballot, and a "0%" would say they ran and got no votes.
#
# The percentage is worked out here rather than copied from the source, so the
# data file holds one number per candidate. The two offices divide by different
# things, for the reason the header of results.yml gives: a mayor's share is of
# every vote cast for mayor, and a councillor's is of ballots cast, because a
# voter marks up to as many councillors as there are seats.
#
# Each municipality's ballots cast and source link are published as
# `site.data.election_turnout[<slug>]`, for the note above the municipality
# index's candidate list.
#
# Joined on municipality and name together, because the same name could stand in
# two places. Runs at :high so candidate_pages.rb, at :normal, builds its pages
# from candidates that already carry their result.
module LivableCrd
  class ElectionResults < Jekyll::Generator
    safe true
    priority :high

    # The ballot's two races, in the order a ballot puts them, and what each is
    # called in _data/candidates.yml's `office`.
    RACES = { "mayor" => "Mayor", "councillor" => "Councillor" }.freeze

    def generate(site)
      data = site.data["results"]
      return unless data.is_a?(Hash) && data["municipalities"].is_a?(Hash)

      site.data["results_status"] = data["status"].to_s

      index = {}
      turnout = {}
      data["municipalities"].each do |slug, muni|
        next unless muni.is_a?(Hash)

        mayor = array(muni["mayor"])
        denominators = {
          "mayor" => mayor.sum { |row| row["votes"].to_i },
          "councillor" => muni["ballots"].to_i
        }

        RACES.each do |key, office|
          index_race(index, slug, office, array(muni[key]), denominators[key])
        end

        turnout[slug.to_s] = {
          "ballots_label" => muni["ballots"] ? delimit(muni["ballots"].to_i) : nil,
          "source" => muni["source"]
        }
      end
      site.data["election_turnout"] = turnout

      unmatched = index.keys
      array(site.data["candidates"]).each do |candidate|
        next unless candidate.is_a?(Hash)

        key = [candidate["municipality"].to_s.strip, candidate["name"].to_s.strip]
        result = index[key]
        next unless result

        candidate["result"] = result
        unmatched.delete(key)
      end

      # A name in results.yml that matches nobody is a typo or a sheet rename,
      # and would otherwise drop that candidate's result without a word.
      unmatched.each do |slug, name|
        Jekyll.logger.warn "Election results:", "no candidate named #{name.inspect} in #{slug}"
      end
    end

    private

    # Indexes one race's rows by [slug, name].
    def index_race(index, slug, office, rows, denominator)
      rows = rows.select { |row| row.is_a?(Hash) }
      field = rows.size
      seats = rows.count { |row| row["elected"] == true }
      counted = rows.reject { |row| row["acclaimed"] == true }.map { |row| row["votes"].to_i }

      rows.each do |row|
        acclaimed = row["acclaimed"] == true
        votes = acclaimed ? nil : row["votes"].to_i
        # Competition ranking, as municipality_stats.rb ranks reply rates: two
        # candidates on the same count share a place and the next one down
        # skips it, rather than a tie being broken by the order the source
        # happened to list them in.
        place = acclaimed ? nil : counted.count { |other| other > votes } + 1
        result = {
          "office" => office,
          "votes" => votes,
          "votes_label" => acclaimed ? nil : delimit(votes),
          "percent" => acclaimed ? nil : percent(votes, denominator),
          "elected" => row["elected"] == true,
          "acclaimed" => acclaimed,
          "place" => place,
          "place_label" => place ? ordinal(place) : nil,
          "field" => field,
          "seats" => seats
        }
        index[[slug.to_s, row["name"].to_s.strip]] = result
      end
    end

    # One decimal place, as municipality_stats.rb rounds its own.
    def percent(count, total)
      return 0.0 if total.nil? || total.zero?

      ((count.to_f / total) * 1000).round / 10.0
    end

    # "16,615". Liquid has no number formatting, and a five-digit count with no
    # separator is hard to read against the one beside it.
    def delimit(number)
      number.to_s.reverse.scan(/\d{1,3}/).join(",").reverse
    end

    # "1st", "2nd", "13th", as in municipality_stats.rb.
    def ordinal(number)
      return "#{number}th" if (11..13).cover?(number % 100)

      case number % 10
      when 1 then "#{number}st"
      when 2 then "#{number}nd"
      when 3 then "#{number}rd"
      else "#{number}th"
      end
    end

    def array(value)
      value.is_a?(Array) ? value : []
    end
  end
end
