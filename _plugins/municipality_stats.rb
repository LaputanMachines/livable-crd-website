# frozen_string_literal: true

# Counts each municipality's own field, once per build, into
# `site.data.municipality_stats` keyed by municipality slug.
#
# This replaces a single site-wide /stats/ page. The region-wide figures it drew
# — the reply rate, the grade distribution, the shape of the field — are more
# use where a reader is already standing: somebody on /scorecard/saanich/ wants
# to know how Saanich is replying and how Saanich is scoring, and a regional
# average tells them about twelve other places at the same time. The region is
# still here, but as context for the municipality rather than as the subject:
# each municipality's block carries a `region` hash so its page can say what the
# regional rate is and where this municipality sits against it.
#
# Everything is derived from data the site already publishes —
# _data/candidates.yml, _data/scores.yml, _data/questions.yml and the small
# lookup files beside them — so a municipality page cannot report a number the
# rows below it do not show. Nothing is entered by hand and nothing is cached
# between builds: the two nightly syncs move these figures on their own.
#
# In Ruby rather than in Liquid because most of these figures are a group-and-
# count, which Liquid can only do by walking the candidate list once per bucket:
# the grade distribution alone would be one pass per letter per topic per
# municipality. It is also where sorting and ranking live — Liquid can sort an
# array of hashes by a key it already has, but not by a ratio it would have to
# compute first.
#
# Keyed by slug and read from the template as
# `site.data.municipality_stats[page.municipality_slug]` rather than handed to
# MunicipalityPage at construction time: that page is built by
# candidate_pages.rb at :normal and this generator runs at :low, so it sees what
# questionnaire_scores.rb (:high) attached to each candidate —
# `questionnaire_returned` is what "has replied" counts here, the merged
# `scores` map is what the grade distribution reads, and `published_subjects` is
# what says whether anything has been released. Liquid renders after every
# generator has run, so the lookup cannot race the data.
module LivableCrd
  class MunicipalityStats < Jekyll::Generator
    safe true
    priority :low

    NOT_STATED = "Not stated"

    def generate(site)
      candidates = array(site.data["candidates"]).select { |c| c.is_a?(Hash) }

      # Grouped by the slug on the candidate rather than by _data/
      # municipalities.yml, exactly as candidate_pages.rb groups them: a
      # candidate carrying a slug that file does not list still gets a page, and
      # a page without its own figures would render a hole where every other
      # municipality has a section.
      by_slug = candidates.group_by { |c| c["municipality"].to_s.strip }
      by_slug.delete("")

      region = region_stats(site, candidates, by_slug)

      site.data["municipality_stats"] = by_slug.each_with_object({}) do |(slug, rows), acc|
        acc[slug] = municipality_stats(site, rows, region)
      end
    end

    private

    def municipality_stats(site, rows, region)
      returned = rows.count { |c| c["questionnaire_returned"] }

      {
        "candidate_count" => rows.size,
        "returned_count" => returned,
        "outstanding_count" => rows.size - returned,
        "returned_percent" => percent(returned, rows.size),
        # How many of this municipality's repliers have anything published.
        # Zero until the coalition's release date, which is what the page keys
        # its empty state off — not the calendar, which would announce grades on
        # a day the sheet had not in fact released.
        "published_count" => rows.count { |c| published?(c) },
        # Where this municipality sits among the others on reply rate, and the
        # regional rate it is sitting against. Both are the one kind of figure a
        # municipality page cannot work out for itself, and they are the reason
        # the region is still counted at all.
        "rank" => rank_for(region, rows.size, returned),
        "standings" => standing_rows(site, rows),
        "slates" => slate_rows(rows),
        "grades" => grade_rows(site, rows),
        "region" => region
      }
    end

    # The region, as context for one municipality rather than as a subject of its
    # own: the rate every municipality's rate is read against, how many
    # municipalities there are to be ranked among, how long the questionnaire is,
    # and which topics carry no grade.
    def region_stats(site, candidates, by_slug)
      returned = candidates.count { |c| c["questionnaire_returned"] }
      questions = question_counts(site)
      graded_ids = graded_subject_ids(site)
      names = subject_names(site)

      {
        "candidate_count" => candidates.size,
        "returned_count" => returned,
        "returned_percent" => percent(returned, candidates.size),
        "municipality_count" => by_slug.size,
        # Every municipality's reply rate, highest first, which is the ladder
        # `rank_for` places one municipality on. Computed once here rather than
        # once per municipality: thirteen municipalities would otherwise each
        # re-count all thirteen.
        "reply_rates" => by_slug.values.map { |rows| percent(rows.count { |c| c["questionnaire_returned"] }, rows.size) }
                                .sort.reverse,
        "questions" => questions,
        "graded_subject_count" => graded_ids.size,
        # The topics nobody grades, named from the registry rather than spelled
        # out in the template: a topic gaining its first graded question should
        # drop out of that sentence on the next build, not wait for somebody to
        # notice the page still says it can never hold a letter.
        "ungraded_subjects" => (names.keys - graded_ids).map { |id| names[id] }.compact
      }
    end

    # Competition ranking: 1 plus however many municipalities reply at a strictly
    # better rate, so two municipalities tied at 40% are both third and the next
    # one down is fifth. Ties are common here — a municipality with four
    # candidates can only land on five rates — and breaking them by name would
    # invent a difference the data does not have.
    def rank_for(region, total, returned)
      rate = percent(returned, total)
      place = region["reply_rates"].count { |other| other > rate } + 1

      { "place" => place, "label" => ordinal(place), "of" => region["municipality_count"] }
    end

    # Incumbency, grouped by the standing's own `label` rather than by its id, so
    # the six ids in _data/standings.yml land in the three buckets a reader
    # counts in: a sitting mayor and a sitting councillor are both "Incumbent".
    #
    # `role_label`, which distinguishes them, is what a candidate's own row uses,
    # where the office they are seeking is beside it to give it meaning. It would
    # only split this chart into buckets of one and two.
    #
    # Office sought is deliberately not counted. It is the one breakdown the
    # municipality page already states twice — in the "Confirmed candidates"
    # line at the top and again in the heading over each list of names — and a
    # third rendering of it as a two-bar chart says nothing the reader has not
    # just read.
    def standing_rows(site, candidates)
      labels = array(site.data["standings"]).each_with_object({}) do |standing, acc|
        acc[standing["id"]] = standing["label"] if standing.is_a?(Hash)
      end

      tally(candidates, candidates.size) { |c| labels[c["standing"]] || NOT_STATED }
    end

    # Electoral organizations, counted only among the candidates who have one.
    #
    # The denominator is deliberately the whole municipality: "3 of 23" is the
    # true weight of a slate in this race, and a chart of slate against slate
    # would imply the municipality is organized into them when four candidates
    # in five have no slate recorded at all.
    def slate_rows(candidates)
      slated = candidates.select { |c| !c["slate"].to_s.strip.empty? }
      tally(slated, candidates.size) { |c| c["slate"] }
    end

    # How long the questionnaire is, and how much of it carries a grade.
    #
    # Counted off _data/questions.yml rather than off the subject list, the same
    # way /questionnaire/ counts them, and regional because the questionnaire is:
    # every candidate in the region is sent the same one.
    def question_counts(site)
      questions = site.data["questions"]
      items = array(questions.is_a?(Hash) ? questions["items"] : nil).select { |item| item.is_a?(Hash) }

      { "total" => items.size, "graded" => items.count { |item| item["graded"] } }
    end

    # The distribution of published letter grades for one municipality: once over
    # every published grade its candidates carry, and once per topic.
    #
    # Empty — every count zero — until publication is switched on, because until
    # then no candidate carries a letter. The page checks `total` and draws its
    # empty state rather than a chart of five zero-length bars.
    #
    # Only the topics the coalition grades are counted. General and Healthcare
    # access carry no graded question, so including them would add two topics
    # that can never hold a letter and read as two topics nobody has got to yet.
    def grade_rows(site, candidates)
      graded_ids = graded_subject_ids(site)
      letters = array(site.data["grades"]).filter_map { |g| g["letter"] if g.is_a?(Hash) }
      names = subject_names(site)

      overall = Hash.new(0)
      per_subject = graded_ids.each_with_object({}) { |id, acc| acc[id] = Hash.new(0) }

      candidates.each do |candidate|
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
        # Every letter on the scale, including the ones nobody here scored: a
        # distribution that lists only the letters awarded hides the shape of
        # the scale, and "no candidate in this municipality got an A" is the
        # most interesting thing such a chart can say.
        "letters" => letters.map { |letter| letter_row(site, letter, overall[letter], total) },
        # Topics with nothing published in this municipality are dropped rather
        # than drawn as an empty row. Region-wide there was always something in
        # every graded topic; in one municipality of four candidates there may
        # not be, and an empty bar beside six full ones reads as a topic that
        # went missing rather than as one nobody here has been graded on yet.
        "subjects" => graded_ids.filter_map do |id|
          subject_total = per_subject[id].values.sum
          next if subject_total.zero?

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

    # The topics the grading sheet grades at all, which is not the same as the
    # topics it has published: see the note in questionnaire_scores.rb.
    def graded_subject_ids(site)
      scores = site.data["scores"]
      array(scores.is_a?(Hash) ? scores["graded_subjects"] : nil)
    end

    def subject_names(site)
      array(site.data["subjects"]).each_with_object({}) do |subject, acc|
        acc[subject["id"]] = subject["name"] if subject.is_a?(Hash)
      end
    end

    # Whether anything has been released for this candidate. `published_subjects`
    # is attached by questionnaire_scores.rb to every candidate the grading sheet
    # has a row for, and is empty for one whose reply is still being graded.
    def published?(candidate)
      subjects = candidate["published_subjects"]
      subjects.is_a?(Hash) && !subjects.empty?
    end

    # "C−" with a minus sign and "C-" with a hyphen are the same grade; the sheet
    # has typed both. Matching the scorecard's own chip, which folds them too.
    def normalize_letter(value)
      value.to_s.strip.upcase.tr("−", "-")
    end

    # {label, count, percent} per bucket, largest first, ties alphabetical.
    def tally(rows, denominator)
      counts = Hash.new(0)
      rows.each { |row| counts[yield(row)] += 1 }

      counts.map { |label, count| { "label" => label, "count" => count, "percent" => percent(count, denominator) } }
           .sort_by { |row| [-row["count"], row["label"].to_s] }
    end

    # "1st", "2nd", "13th". Written out here because Liquid has no ordinal filter
    # and the alternative is a `case` over ten cases in a template.
    def ordinal(number)
      return "#{number}th" if (11..13).cover?(number % 100)

      case number % 10
      when 1 then "#{number}st"
      when 2 then "#{number}nd"
      when 3 then "#{number}rd"
      else "#{number}th"
      end
    end

    # One decimal place. The bar widths are a percentage of the container and
    # the labels round to whole numbers, so this is finer than either needs —
    # but rounding to whole numbers here would draw two visibly different bars
    # at the same width, and it is what the ranking compares on.
    def percent(count, total)
      return 0.0 if total.nil? || total.zero?

      ((count.to_f / total) * 1000).round / 10.0
    end

    def array(value)
      value.is_a?(Array) ? value : []
    end
  end
end
