# frozen_string_literal: true

require "cgi"

# `autolink`: plain text from a spreadsheet, with any web address in it turned
# into a link and everything else escaped.
#
# It exists for the Question Registry's `Methodology` column, which partner
# organizations write in their own words and which /questionnaire/ publishes
# under each question. Two of them cite a source, and a spreadsheet cell has no
# way to mark up a link: what arrives is the bare address in the middle of a
# sentence, which rendered as dead text on a page whose whole purpose there is
# to show a reader where a grading rule came from.
#
# Not a Markdown pass. The cell is prose typed by somebody who is not writing
# for a template, and running it through a Markdown converter would make every
# underscore, asterisk and hash in it a formatting instruction - the difference
# between publishing what a partner wrote and publishing what a parser made of
# it. This does one thing, to the one construct that cannot survive plain text.
#
# The text is escaped here rather than by the caller, because a filter that
# returns HTML has to be used with `| raw`-equivalent semantics in Liquid (no
# filter after it may escape again), and splitting the two would leave the
# escaping optional at every call site. Everything outside a matched address
# goes through CGI.escapeHTML, and both the href and the visible label are
# escaped as well, so a cell containing "<script>" publishes as those
# characters and nothing else.
#
# Only http, https and a bare "www." are recognized, so no other scheme can be
# introduced by editing a spreadsheet: no "javascript:", no "data:".
module LivableCrd
  module Autolink
    # Deliberately loose on what a URL may contain and strict about where one
    # starts. A cell is prose, so the end of an address is decided by
    # split_trailing below rather than by trying to write a pattern that knows
    # which full stop is part of a path and which ends the sentence.
    URL = %r{(?:https?://|www\.)[^\s<>"'`\\]+}i

    # What a sentence puts after an address, taken off the end of the match and
    # printed as ordinary text. The two curly forms are here because the cells
    # are typed in Google Sheets, which substitutes them as you type.
    TRAILING = [")", "]", "}", ">", ".", ",", ";", ":", "!", "?", "'", '"',
                "’", "”"].freeze

    # Past this the label drops to the bare domain. Same measure and the same
    # reasoning as WEBSITE_LABEL_MAX in _plugins/candidate_pages.rb: a link
    # inside a sentence is read as part of it, and a 90-character archive URL
    # with two dates and a slug in it is a wall the sentence does not recover
    # from.
    MAX_LABEL = 45

    def autolink(input)
      text = input.to_s
      out = +""
      cursor = 0

      text.scan(URL) do
        match = Regexp.last_match
        out << CGI.escapeHTML(text[cursor...match.begin(0)])
        url, tail = split_trailing(match[0])
        out << anchor(url)
        out << CGI.escapeHTML(tail)
        cursor = match.end(0)
      end

      out << CGI.escapeHTML(text[cursor..] || "")
      out
    end

    private

    # Split "strongtowns.org/article)." into the address and the punctuation the
    # sentence put after it.
    #
    # A closing bracket is kept when the address's own brackets balance with it
    # in place, which is what a Wikipedia URL looks like
    # (".../Parking_(urban)"): taking it off there would link to a page that
    # does not exist and leave a stray ")" behind. Counted over the whole
    # remaining address rather than tracked as a depth, because the only case
    # that matters is one pair. "(see https://example.org/x)" fails that test -
    # one ")" and no "(" - so there the bracket goes back to the sentence.
    def split_trailing(raw)
      url = raw.dup
      tail = +""

      while url.length > 1 && TRAILING.include?(url[-1])
        break if url[-1] == ")" && url.count("(") >= url.count(")")

        tail = url[-1] + tail
        url = url[0..-2]
      end

      [url, tail]
    end

    def anchor(url)
      href = url.match?(/\Awww\./i) ? "https://#{url}" : url
      safe = CGI.escapeHTML(href)

      # The arrow, and opening in a new tab, are what every other link that
      # leaves this site does - see the campaign link in the candidate hero.
      # `title` carries the address in full, because the visible label is often
      # only the domain and a reader deciding whether to follow a citation
      # should be able to see where it goes without following it.
      #
      # No rel="nofollow" here, unlike the candidate links. Those are 66
      # campaign pages this site takes no position on; this is a source a
      # partner organization chose to stand a grading rule on, and declining to
      # pass on any credit for it would be saying something we do not mean.
      %(<a href="#{safe}" target="_blank" rel="noopener" title="#{safe}">) +
        %(#{CGI.escapeHTML(label_for(href))} <span aria-hidden="true">&#8594;</span></a>)
    end

    # What the link says: the address without the scheme, without a "www." that
    # tells a reader nothing, and without a trailing slash - then the domain
    # alone once that runs long, because inside a sentence the domain is the
    # part that says whether this is worth following.
    def label_for(href)
      bare = href.sub(%r{\Ahttps?://}i, "").sub(/\Awww\./i, "").sub(%r{/\z}, "")
      return bare if bare.length <= MAX_LABEL

      bare.split("/", 2).first
    end
  end
end

Liquid::Template.register_filter(LivableCrd::Autolink)
