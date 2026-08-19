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
#   questionnaire_returned  true. Every candidate listed in scores.yml has a row
#                    on the grading sheet, and having one means they returned
#                    the questionnaire. This is set even when nothing has been
#                    published for them yet, which is the whole point of it: the
#                    scorecard draws "returned it, still being graded"
#                    differently from "never replied", and before this the two
#                    were the same dash.
#   scores           the top-level letter per published subject, merged into the
#                    map the scorecard matrix and the candidate page already
#                    read as `c.scores[subject.id]`. Nothing downstream had to
#                    change to start showing real grades.
#   published_subjects  the per-question detail behind those letters, keyed by
#                    subject id, which _layouts/candidate.html renders under each
#                    subject. Empty for a candidate with nothing published.
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
      # Published so the scorecard can say how many candidates have replied, and
      # how many of those have anything published, without walking every row in
      # Liquid twice to find out.
      site.data["returned_candidate_count"] = 0
      site.data["published_candidate_count"] = 0
      return if results.empty?

      attach_questions(site, results)

      returned = 0
      published = 0
      candidates.each do |candidate|
        next unless candidate.is_a?(Hash)

        result = results.delete(join_key(candidate["name"], candidate["municipality"]))
        next unless result

        returned += 1
        candidate["questionnaire_returned"] = true
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
    end

    private

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
