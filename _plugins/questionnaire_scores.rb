# frozen_string_literal: true

# Joins _data/scores.yml onto _data/candidates.yml at build time.
#
# The two files come from two different spreadsheets on two different schedules:
# candidates.yml is regenerated nightly from the coalition tracking sheet by
# scripts/sync-candidates.py, and scores.yml from the grading sheet by
# scripts/sync-questionnaire.py. Writing grades into candidates.yml would put
# them in the path of a file that is overwritten wholesale, so they stay apart
# on disk and are joined here instead.
#
# Three things are attached to each candidate the grading sheet knows about:
#
#   questionnaire_returned  true, unless the entry carries `returned: false`.
#                    Almost every candidate listed in scores.yml has a row on
#                    the grading sheet because they returned the questionnaire,
#                    and this is set even when nothing has been published for
#                    them yet, which is the whole point of it: the scorecard
#                    draws "returned it, still being graded" differently from
#                    "never replied", and before this the two were the same
#                    dash. The exception is a sitting incumbent on the sheet
#                    only because Homes for Living scored their housing record;
#                    they never replied, their grades still publish, and the
#                    flag stays off so the scorecard says the true thing about
#                    them.
#   scores           the top-level letter per published subject, merged into the
#                    map the scorecard matrix and the candidate page already
#                    read as `c.scores[subject.id]`. Nothing downstream had to
#                    change to start showing real grades.
#   published_subjects  the per-question detail behind those letters, keyed by
#                    subject id, which _layouts/candidate.html renders under each
#                    subject. Empty for a candidate with nothing published.
#
# A fourth thing is attached from a second, hand-written source. _data/declined.yml
# names the candidates who told the coalition they were not taking part and
# carries the statement their page shows instead; an entry there attaches
# `declined_statement` and strips their published grades back to the ones that
# were never theirs to give. That overlay is applied here rather than in a
# generator of its own because this is the file that decides what a candidate
# publishes, and a second generator undoing this one's work would depend on the
# order Jekyll happens to run two plugins of equal priority in.
#
# Two things about the overlay are deliberate and neither is obvious:
#
#   It waits for the release. Nothing is applied until something is published,
#   the same test the municipality indexes use to decide whether to draw a grade
#   distribution: the release date says when grades are meant to appear, the
#   published count says whether any have. Before that a declined candidate's
#   page is what it always was - a row of dashes, and no statement - so a
#   decline recorded weeks early does not go up weeks early.
#
#   An incumbent record survives it. Homes for Living score a sitting
#   incumbent's housing record from council votes, on the `HFL-INC` row of the
#   grading sheet, and that score needs nothing from the candidate: it is a
#   reading of what they have already done in office, and declining does not
#   withdraw it. So a published subject carried by the record alone - `share:
#   100`, no questionnaire in it anywhere - keeps its letter and its panel, and
#   every other topic they have carries the bubble. A blended record, worth 30%
#   beside a returned questionnaire, is dropped with the rest: a candidate who
#   declined cannot have one, and publishing the 70% that is their answers
#   would be publishing the thing the decline was about.
#
# Note the difference between that last one and `site.data.scores.graded_subjects`,
# which is a flat list of the topics the grading sheet grades at all. A topic in
# the second and not the first is being graded and has not been released; a topic
# in neither is one nobody grades, and the site must not imply a result is coming.
#
# The detail rows arrive carrying only a question label, because the question's
# own text belongs to _data/questions.yml and storing it twice is how the
# questionnaire page and a candidate's page would end up quoting two different
# wordings of the same question. The text is joined on here instead, once per
# build rather than once per candidate page.
#
# Runs at :high priority so candidate_pages.rb, at :normal, builds its pages from
# candidates that already carry their grades.
module LivableCrd
  class QuestionnaireScores < Jekyll::Generator
    safe true
    priority :high

    def generate(site)
      candidates = site.data["candidates"]
      return unless candidates.is_a?(Array)

      results = index_results(site.data["scores"])
      declined = index_declined(site.data["declined"])
      # Published so the scorecard can say how many candidates have replied, and
      # how many of those have anything published, without walking every row in
      # Liquid twice to find out.
      site.data["returned_candidate_count"] = 0
      site.data["published_candidate_count"] = 0
      # Declined entries are checked too: a decline still has a page to change
      # even on a build where the grading sheet published nothing at all.
      return if results.empty? && declined.empty?

      attach_questions(site, results)

      returned = 0
      published = 0
      # Collected rather than handled in place: the overlay is gated on whether
      # anything published at all, and that is not known until this loop has
      # finished counting.
      declines = []
      candidates.each do |candidate|
        next unless candidate.is_a?(Hash)

        key = join_key(candidate["name"], candidate["municipality"])
        statement = declined.delete(key)
        declines << [candidate, statement] if statement
        result = results.delete(key)
        next unless result

        # A declined candidate is never counted as having replied, whatever the
        # grading sheet says: they are on it because somebody's record is being
        # scored, not because a questionnaire came back. Without this the reply
        # rate on the municipality indexes would count somebody who told us they
        # were not taking part.
        replied = result["returned"] != false && statement.nil?
        if replied
          returned += 1
          candidate["questionnaire_returned"] = true
        end
        # Merge rather than replace: a subject the grading sheet has not
        # published keeps whatever candidates.yml said about it, which is how a
        # grade sourced from the tracking sheet would still show through.
        scores = candidate["scores"]
        candidate["scores"] = (scores.is_a?(Hash) ? scores : {}).merge(result["scores"] || {})
        candidate["published_subjects"] = index_by(result["subjects"], "id")
        published += 1 unless candidate["published_subjects"].empty?
      end

      site.data["returned_candidate_count"] = returned
      site.data["published_candidate_count"] = published

      # The declines, once there is a release for them to be part of. See the
      # header: before anything is published this is a no-op, and a candidate
      # written into _data/declined.yml today looks exactly as they did
      # yesterday until the grades go up.
      apply_declines(declines) if published.positive?

      # Which of the three empty chips the key has to name, derived from what
      # the pages actually draw rather than from a hand-kept list.
      #
      # The key is one include on two pages, and naming a mark that appears
      # nowhere below it sends a reader hunting for a state the site does not
      # use. Both of the marks this decides are temporary in their own way: N/A
      # is a per-question answer nobody has had to give yet, and the hourglass
      # is gone the day everything is published. Deriving it means a grader
      # typing N/A into ROL-05 puts that chip back in the key on the next build,
      # and the last topic being released takes the hourglass out of it, with
      # nobody having to remember either.
      site.data["legend_states"] = legend_states(site, candidates)

      # An unmatched entry means the grading sheet knows a candidate the tracking
      # sheet does not list as confirmed. sync-questionnaire.py already drops
      # those, so reaching here means the two files were generated against
      # different candidate lists: a real reply, and possibly real grades, are
      # silently not being shown. Worth a line in the log.
      results.each_key do |key|
        Jekyll.logger.warn "Questionnaire scores:",
                           "no candidate in _data/candidates.yml matches #{key.inspect}; " \
                           "their questionnaire reply is not being shown"
      end

      # Louder, because the failure is worse. An unmatched grading row hides a
      # result; an unmatched decline leaves a candidate's page showing dashes and
      # no statement, which is the page reading as "never replied" about somebody
      # who told us why they were not taking part.
      declined.each_key do |key|
        Jekyll.logger.warn "Questionnaire scores:",
                           "_data/declined.yml names #{key.inspect}, who is not in " \
                           "_data/candidates.yml; their statement is not being shown"
      end
    end

    private

    # Strip a declined candidate back to what they did not choose to give us,
    # and attach the statement their page shows in place of the rest.
    #
    # What survives is a subject whose whole grade is an incumbent record -
    # `share: 100`, which sync-questionnaire.py writes only where no
    # questionnaire came back. Those are scored from council votes on the
    # `HFL-INC` row and are a reading of the candidate's own record in office,
    # so the decline has nothing to do with them; everything else goes, letter
    # and per-question detail together, because the templates decide what a
    # topic draws from these two and anything left here would draw a grade.
    #
    # A record blended with a questionnaire (share 30) is dropped and said out
    # loud. It cannot happen - a candidate who declined returned nothing - so
    # reaching it means either the decline or the sheet is wrong about the same
    # person, and the safe reading of that disagreement is the one that
    # publishes less.
    def apply_declines(entries)
      entries.each do |candidate, statement|
        candidate["declined_statement"] = statement

        detail = candidate["published_subjects"]
        detail = {} unless detail.is_a?(Hash)

        kept = detail.select do |id, subject|
          next false unless subject.is_a?(Hash)

          share = subject.dig("score", "record", "share")
          next false if share.nil?
          next true if share == 100

          Jekyll.logger.warn "Questionnaire scores:",
                             "#{candidate['name']} declined, but #{id} is scored " \
                             "#{share}% on their record and the rest on a questionnaire; " \
                             "the topic is not being published"
          false
        end

        candidate["published_subjects"] = kept
        scores = candidate["scores"]
        scores = {} unless scores.is_a?(Hash)
        candidate["scores"] = scores.select { |id, _| kept.key?(id) }
      end
    end

    # A grade cell the grading sheet wrote as "not applicable" rather than as a
    # letter. Mirrors NOT_APPLICABLE in scripts/sync-questionnaire.py, which is
    # what normalizes the sheet's spellings before they get here.
    def not_applicable?(grade)
      %w[N/A NA N.A. N/A.].include?(grade.to_s.strip.upcase)
    end

    # {"na" =>, "answers" =>, "declined" =>}: whether any page draws that chip.
    #
    # The rule has to be the one the templates use, or the key will name a chip
    # nothing draws or miss one something does. A subject with a letter shows
    # that letter; a subject without one shows the speech bubble where the topic
    # is ungraded and the candidate's answers are published, the hourglass where
    # the candidate replied, and the dash otherwise. See the cell blocks in
    # scorecard/index.md and _layouts/candidate.html.
    #
    # The hourglass is not among these. It is still drawn by those cell blocks,
    # and the key deliberately does not name it, so there is nothing here to
    # decide about it.
    #
    # The declined bubble is drawn on a candidate in _data/declined.yml and
    # nowhere else, so an empty file takes it out of the key - as does a build
    # before the release, where apply_declines has not run and nobody carries
    # `declined_statement` yet.
    def legend_states(site, candidates)
      subjects = site.data["subjects"]
      subjects = [] unless subjects.is_a?(Array)
      graded = site.data.dig("scores", "graded_subjects")
      graded = [] unless graded.is_a?(Array)

      states = { "na" => false, "answers" => false, "declined" => false }
      candidates.each do |candidate|
        next unless candidate.is_a?(Hash)

        states["declined"] ||= !candidate["declined_statement"].to_s.strip.empty?

        scores = candidate["scores"].is_a?(Hash) ? candidate["scores"] : {}
        detail = candidate["published_subjects"].is_a?(Hash) ? candidate["published_subjects"] : {}

        # Per topic, and per question inside a published topic: the same chip
        # is rendered in both places by the same include.
        states["na"] ||= scores.any? { |_, letter| not_applicable?(letter) }
        states["na"] ||= detail.any? do |_, subject|
          rows = subject["questions"]
          rows.is_a?(Array) && rows.any? { |row| not_applicable?(row["grade"]) }
        end

        subjects.each do |subject|
          id = subject["id"]
          next unless scores[id].to_s.strip.empty?

          unscored = detail.dig(id, "unscored")
          if !graded.include?(id) && unscored.is_a?(Array) && !unscored.empty?
            states["answers"] = true
          end
        end
      end
      states
    end

    # Copy each question's wording, answer shape and owner from
    # _data/questions.yml onto the grade rows that reference it by label.
    #
    # A row whose label is not in the registry is dropped rather than rendered
    # with a blank where the question should be: a grade with no question beside
    # it tells a reader nothing and looks like a bug. sync-questionnaire.py drops
    # these too and says so, so this is the second line of defence, not the first.
    def attach_questions(site, results)
      questions = index_by(site.data.dig("questions", "items"), "label")

      results.each_value do |result|
        subjects = result["subjects"]
        next unless subjects.is_a?(Array)

        subjects.each do |subject|
          rows = subject["questions"]
          next unless rows.is_a?(Array)

          subject["questions"] = rows.filter_map do |row|
            question = questions[row["label"]]
            unless question
              Jekyll.logger.warn "Questionnaire scores:",
                                 "#{result['name']} has a grade for #{row['label']}, " \
                                 "which _data/questions.yml does not list; row dropped"
              next
            end

            row.merge(
              "question" => question["question"],
              "type_label" => question["type_label"],
              "owner" => question["owner"]
            )
          end
        end
      end
    end

    # {join key => statement}, from the hand-written _data/declined.yml. Same
    # join as index_results below, so a name typed there matches a candidate on
    # the same terms a name on the grading sheet does. An entry with no statement
    # is dropped, and says so: the whole of what the page shows in place of the
    # grades is that text, so an entry with none would render an empty box, and
    # dropping it silently leaves the candidate looking like somebody who never
    # replied on a build where a person had just written them down as declining.
    def index_declined(rows)
      return {} unless rows.is_a?(Array)

      rows.each_with_object({}) do |row, acc|
        next unless row.is_a?(Hash)

        statement = row["statement"].to_s.strip
        if statement.empty?
          Jekyll.logger.warn "Questionnaire scores:",
                             "_data/declined.yml has no statement for " \
                             "#{row['name'].inspect}; the entry is ignored and their " \
                             "page still shows the grading sheet"
          next
        end

        acc[join_key(row["name"], row["municipality"])] = statement
      end
    end

    # {join key => result}. Keyed on name and municipality rather than on the
    # URL slug: the slug is Jekyll's to compute, and a Python script deriving it
    # independently is a second implementation that only has to disagree once.
    def index_results(scores)
      rows = scores.is_a?(Hash) ? scores["candidates"] : nil
      return {} unless rows.is_a?(Array)

      rows.each_with_object({}) do |row, acc|
        next unless row.is_a?(Hash)

        acc[join_key(row["name"], row["municipality"])] = row
      end
    end

    def join_key(name, municipality)
      [name.to_s.split.join(" ").downcase, municipality.to_s.strip]
    end

    def index_by(rows, key)
      return {} unless rows.is_a?(Array)

      rows.each_with_object({}) do |row, acc|
        acc[row[key]] = row if row.is_a?(Hash)
      end
    end
  end
end
