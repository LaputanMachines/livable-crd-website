# frozen_string_literal: true

# Counts the scorecard for /stats/, once per build, into
# `site.data.scorecard_stats`.
#
# Everything here is derived from data the site already publishes —
# _data/candidates.yml, _data/scores.yml, _data/questions.yml and the small
# lookup files beside them — so the stats page cannot report a number the pages
# it describes do not show. Nothing is entered by hand and nothing is cached
# between builds: the two nightly syncs move these figures on their own.
#
# In Ruby rather than in Liquid because most of these figures are a group-and-
# count, which Liquid can only do by walking the candidate list once per bucket:
# the municipality table alone would be thirteen passes over 189 rows, and the
# grade distribution would be one pass per letter per topic. It is also where
# sorting lives — Liquid can sort an array of hashes by a key it already has,
# but not by a ratio it would have to compute first.
#
# Runs at :low so it sees what questionnaire_scores.rb (:high) attached to each
# candidate: `questionnaire_returned` is what "has replied" counts here, and the
# merged `scores` map is what the grade distribution reads.
module LivableCrd
  class ScorecardStats < Jekyll::Generator
    safe true
    priority :low

    NOT_STATED = "Not stated"

    def generate(site)
      candidates = array(site.data["candidates"])
      returned = candidates.count { |c| c.is_a?(Hash) && c["questionnaire_returned"] }

      site.data["scorecard_stats"] = {
        "candidate_count" => candidates.size,
        "returned_count" => returned,
        "outstanding_count" => candidates.size - returned,
        "returned_percent" => percent(returned, candidates.size),
        # Set by questionnaire_scores.rb: how many of the repliers have anything
        # published. Zero until the coalition's release date, which is what the
        # page keys its empty state off — not the calendar, which would announce
        # grades on a day the sheet had not in fact released.
        "published_count" => site.data["published_candidate_count"].to_i,
        "municipalities" => municipality_rows(site, candidates),
        "offices" => office_rows(candidates),
        "standings" => standing_rows(site, candidates),
        "slates" => slate_rows(candidates),
        "questions" => question_rows(site),
        "grades" => grade_rows(site, candidates)
      }
    end

    private

    # One row per municipality that has candidates, ordered by reply rate.
    #
    # Municipalities with nobody running are dropped rather than shown at 0 of 0:
    # the four electoral areas elect a regional director rather than a council
    # and are not in the scorecard's scope, and a municipality whose nominations
    # have not closed yet has nothing to report. A municipality with candidates
    # and no replies is kept, at zero — that is a fact about the region, and
    # hiding it would flatter the totals.
    def municipality_rows(site, candidates)
      by_slug = Hash.new { |h, k| h[k] = { "total" => 0, "returned" => 0 } }
      candidates.each do |candidate|
        next unless candidate.is_a?(Hash)

        bucket = by_slug[candidate["municipality"]]
        bucket["total"] += 1
        bucket["returned"] += 1 if candidate["questionnaire_returned"]
      end

      rows = array(site.data["municipalities"]).filter_map do |muni|
        next unless muni.is_a?(Hash)

        bucket = by_slug[muni["slug"]]
        next if bucket["total"].zero?

        {
          "slug" => muni["slug"],
          "name" => muni["name"],
          "total" => bucket["total"],
          "returned" => bucket["returned"],
          "percent" => percent(bucket["returned"], bucket["total"])
        }
      end

      # Rate first, then the bigger race, then alphabetically, so the order is
      # total and the table does not reshuffle between builds on a tie.
      rows.sort_by { |row| [-row["percent"], -row["total"], row["name"].to_s] }
    end

    # Mayor / councillor. `office` is null where the tracking sheet does not say,
    # and that bucket is published as "Not stated" rather than folded into the
    # larger one: this site does not guess what somebody is running for.
    def office_rows(candidates)
      tally(candidates, candidates.size) { |c| c["office"].to_s.strip.empty? ? NOT_STATED : c["office"] }
    end

    # Incumbency, grouped by the standing's own `label` rather than by its id, so
    # the six ids in _data/standings.yml land in the three buckets a reader
    # counts in: a sitting mayor and a sitting councillor are both "Incumbent".
    #
    # `role_label`, which distinguishes them, is what a candidate's own row uses,
    # where the office they are seeking is beside it to give it meaning. It would
    # only split this chart into buckets of two and three.
    def standing_rows(site, candidates)
      labels = array(site.data["standings"]).each_with_object({}) do |standing, acc|
        acc[standing["id"]] = standing["label"] if standing.is_a?(Hash)
      end

      tally(candidates, candidates.size) { |c| labels[c["standing"]] || NOT_STATED }
    end

    # Electoral organizations, counted only among the candidates who have one.
    #
    # The denominator is deliberately the whole field: "7 of 189" is the true
    # weight of a slate in this election, and a chart of slate against slate
    # would imply the region is organized into them when four candidates in five
    # have no slate recorded at all.
    def slate_rows(candidates)
      slated = candidates.select { |c| c.is_a?(Hash) && !c["slate"].to_s.strip.empty? }
      tally(slated, candidates.size) { |c| c["slate"] }
    end

    # Questions per topic, and how many of them carry a grade.
    #
    # Counted off _data/questions.yml rather than off the subject list, the same
    # way /questionnaire/ counts them: the site lists topics the questionnaire
    # has no questions for, and a row of zeroes here would read as a bug in the
    # sync rather than as a topic nobody asked about.
    def question_rows(site)
      questions = site.data["questions"]
      items = array(questions.is_a?(Hash) ? questions["items"] : nil)
      names = array(site.data["subjects"]).each_with_object({}) do |subject, acc|
        acc[subject["id"]] = subject["name"] if subject.is_a?(Hash)
      end

      buckets = Hash.new { |h, k| h[k] = { "total" => 0, "graded" => 0 } }
      items.each do |item|
        next unless item.is_a?(Hash)

        bucket = buckets[item["subject"]]
        bucket["total"] += 1
        bucket["graded"] += 1 if item["graded"]
      end

      rows = buckets.map do |id, bucket|
        {
          "id" => id,
          "name" => names[id] || id.to_s,
          "total" => bucket["total"],
          "graded" => bucket["graded"],
          "percent" => percent(bucket["total"], items.size)
        }
      end

      {
        "total" => items.size,
        "graded" => rows.sum { |row| row["graded"] },
        "subjects" => rows.sort_by { |row| [-row["total"], row["name"]] }
      }
    end

    # The distribution of published letter grades: once over every published
    # grade on the site, and once per topic.
    #
    # Empty — every count zero — until publication is switched on, because until
    # then no candidate carries a letter. The page checks `total` and draws its
    # empty state rather than a chart of five zero-length bars.
    #
    # Only the topics the coalition grades are counted. General and Healthcare
    # access carry no graded question, so including them would add two topics
    # that can never hold a letter and read as two topics nobody has got to yet.
    def grade_rows(site, candidates)
      scores = site.data["scores"]
      graded_ids = array(scores.is_a?(Hash) ? scores["graded_subjects"] : nil)
      letters = array(site.data["grades"]).filter_map { |g| g["letter"] if g.is_a?(Hash) }
      names = array(site.data["subjects"]).each_with_object({}) do |subject, acc|
        acc[subject["id"]] = subject["name"] if subject.is_a?(Hash)
      end

      overall = Hash.new(0)
      per_subject = graded_ids.each_with_object({}) { |id, acc| acc[id] = Hash.new(0) }

      candidates.each do |candidate|
        next unless candidate.is_a?(Hash)

        candidate_scores = candidate["scores"]
        next unless candidate_scores.is_a?(Hash)

        graded_ids.each do |id|
          letter = normalize_letter(candidate_scores[id])
          next unless letters.include?(letter)

          overall[letter] += 1
          per_subject[id][letter] += 1
        end
      end

      total = overall.values.sum

      {
        "total" => total,
        # Every letter on the scale, including the ones nobody scored: a
        # distribution that lists only the letters awarded hides the shape of
        # the scale, and "no candidate got an A" is the most interesting thing
        # such a chart can say.
        "letters" => letters.map { |letter| letter_row(site, letter, overall[letter], total) },
        "subjects" => graded_ids.map do |id|
          subject_total = per_subject[id].values.sum
          {
            "id" => id,
            "name" => names[id] || id.to_s,
            "total" => subject_total,
            "letters" => letters.map { |letter| letter_row(site, letter, per_subject[id][letter], subject_total) }
          }
        end
      }
    end

    def letter_row(site, letter, count, total)
      label = array(site.data["grades"]).find { |g| g.is_a?(Hash) && g["letter"] == letter }
      {
        "letter" => letter,
        "label" => label ? label["label"] : nil,
        "count" => count,
        "percent" => percent(count, total)
      }
    end

    # "C−" with a minus sign and "C-" with a hyphen are the same grade; the sheet
    # has typed both. Matching the scorecard's own chip, which folds them too.
    def normalize_letter(value)
      value.to_s.strip.upcase.tr("−", "-")
    end

    # {label, count, percent} per bucket, largest first, ties alphabetical.
    def tally(rows, denominator)
      counts = Hash.new(0)
      rows.each do |row|
        next unless row.is_a?(Hash)

        counts[yield(row)] += 1
      end

      counts.map { |label, count| { "label" => label, "count" => count, "percent" => percent(count, denominator) } }
           .sort_by { |row| [-row["count"], row["label"].to_s] }
    end

    # One decimal place. The bar widths are a percentage of the container and
    # the labels round to whole numbers, so this is finer than either needs —
    # but rounding to whole numbers here would draw two visibly different bars
    # at the same width.
    def percent(count, total)
      return 0.0 if total.nil? || total.zero?

      ((count.to_f / total) * 1000).round / 10.0
    end

    def array(value)
      value.is_a?(Array) ? value : []
    end
  end
end
