# frozen_string_literal: true

# Joins _data/results.yml onto the candidates, as a `result` hash on each one
# who was on the ballot:
#
#   votes      votes received, or nil for an acclamation
#   percent    one decimal place, or nil for an acclamation
#   elected    true for a winner
#   acclaimed  true for a candidate elected without a vote
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
# Joined on municipality and name together, because the same name could stand in
# two places. Runs at :high so candidate_pages.rb, at :normal, builds its pages
# from candidates that already carry their result.
module LivableCrd
  class ElectionResults < Jekyll::Generator
    safe true
    priority :high

    def generate(site)
      data = site.data["results"]
      return unless data.is_a?(Hash) && data["municipalities"].is_a?(Hash)

      site.data["results_status"] = data["status"].to_s

      index = {}
      data["municipalities"].each do |slug, muni|
        next unless muni.is_a?(Hash)

        mayor = array(muni["mayor"])
        index_race(index, slug, mayor, mayor.sum { |row| row["votes"].to_i })
        index_race(index, slug, array(muni["councillor"]), muni["ballots"].to_i)
      end

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

    def index_race(index, slug, rows, denominator)
      rows.each do |row|
        next unless row.is_a?(Hash)

        acclaimed = row["acclaimed"] == true
        votes = acclaimed ? nil : row["votes"].to_i
        index[[slug.to_s, row["name"].to_s.strip]] = {
          "votes" => votes,
          "percent" => acclaimed ? nil : percent(votes, denominator),
          "elected" => row["elected"] == true,
          "acclaimed" => acclaimed
        }
      end
    end

    # One decimal place, as municipality_stats.rb rounds its own.
    def percent(count, total)
      return 0.0 if total.nil? || total.zero?

      ((count.to_f / total) * 1000).round / 10.0
    end

    def array(value)
      value.is_a?(Array) ? value : []
    end
  end
end
