// Questionnaire page: the "Print the questionnaire" button and the question
// search. Both are enhancements; the page is complete without either.
(function () {
  // ---------------------------------------------------------------------------
  // Print
  //
  // The printed sheet is entirely CSS (@media print in _sass/_questionnaire.scss),
  // so this exists only to save the reader a trip to the browser menu. The button
  // ships hidden and is revealed here: progressive enhancement, the same way the
  // candidate leaflet's print button works. Readers without JS still get the
  // sheet from their browser's own print command.
  // ---------------------------------------------------------------------------
  var btn = document.getElementById('print-questionnaire');
  if (btn) {
    btn.hidden = false;
    btn.addEventListener('click', function () {
      window.print();
    });
  }

  // ---------------------------------------------------------------------------
  // Search
  //
  // Filters the questions already on the page. Nothing is fetched and no index
  // is shipped: the text is in the DOM, sixty-six questions of it, and reading
  // it once at load costs less than the request for an index file would.
  // ---------------------------------------------------------------------------
  (function () {
    var search = document.getElementById('questionnaire-search');
    var input = document.getElementById('questionnaire-search-input');
    var status = document.getElementById('questionnaire-search-status');
    if (!search || !input || !status) return;

    // Punctuation folded to spaces rather than stripped, so "GEN-02" and
    // "gen 02" are the same search, and so a curly apostrophe in the question
    // text cannot beat the straight one somebody types.
    function normalize(text) {
      return text
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, ' ')
        .replace(/^ | $/g, '');
    }

    var sections = Array.prototype.slice.call(
      document.querySelectorAll('.questionnaire-section')
    ).map(function (section) {
      var heading = section.querySelector('h2');
      // The section's own name joins each of its questions' haystacks, so
      // "housing" finds the housing questions rather than nothing: the word is
      // in the heading above them, not in the questions themselves.
      var sectionText = heading ? normalize(heading.textContent) : '';

      var items = Array.prototype.slice.call(
        section.querySelectorAll('.questionnaire-item')
      ).map(function (item) {
        // textContent takes the label, the question, the answer choices, the
        // twelve budget areas and the foot in one read — every word the reader
        // can see on that card, which is the only sensible thing for a search
        // over a page to match.
        return { el: item, text: normalize(item.textContent) + ' ' + sectionText };
      });

      return {
        el: section,
        items: items,
        // The jump pill that points here, so its count can follow the filter
        // instead of promising six questions in a section showing one.
        link: document.querySelector(
          '.questionnaire-jump__list a[href="#' + section.id + '"]'
        )
      };
    });

    if (!sections.length) return;

    var total = sections.reduce(function (sum, section) {
      return sum + section.items.length;
    }, 0);

    function questions(n) {
      return n + (n === 1 ? ' question' : ' questions');
    }

    function apply(query) {
      var terms = normalize(query).split(' ').filter(Boolean);
      var matches = 0;

      sections.forEach(function (section) {
        var shown = 0;

        section.items.forEach(function (item) {
          // Every term has to appear somewhere on the card. Two words entered
          // together are a reader narrowing, not widening.
          var hit = terms.every(function (term) {
            return item.text.indexOf(term) !== -1;
          });
          item.el.classList.toggle('is-filtered-out', !hit);
          if (hit) shown++;
        });

        matches += shown;
        section.el.classList.toggle('is-filtered-out', shown === 0);

        if (section.link) {
          section.link.classList.toggle('is-filtered-out', shown === 0);
          var count = section.link.querySelector('.questionnaire-jump__count');
          if (count) {
            // The unfiltered number, kept the first time it is needed: the
            // markup is the only place it exists, and overwriting it below
            // would lose it.
            if (!count.dataset.total) count.dataset.total = count.textContent.trim();
            count.textContent = terms.length ? '(' + shown + ')' : count.dataset.total;
          }
        }
      });

      // Phrased as the scorecard phrases its own count ("Showing all 84
      // candidates" / "Showing 12 of 84 candidates"), because it is now sitting
      // in the same place doing the same job. Always says something, so the
      // line does not appear and disappear under the controls as a reader
      // types, and so the page arrives stating its own size.
      var term = query.trim();
      if (!terms.length) {
        status.textContent = 'Showing all ' + questions(total);
      } else if (matches === 0) {
        status.textContent = 'No questions match “' + term + '” — clear the ' +
          'search to read all ' + total + '.';
      } else {
        status.textContent = 'Showing ' + matches + ' of ' + total +
          ' questions matching “' + term + '”';
      }
    }

    search.hidden = false;

    input.addEventListener('input', function () {
      apply(input.value);
    });

    // Enter in a lone text input submits the form it is in and reloads the
    // page. There is no form here, but the key is still worth swallowing: a
    // reader who types a word and hits Enter expects the result, not nothing.
    //
    // Escape resets. There is no clear button beside the box — type=search
    // draws its own affordance, and that fires `input` like any other edit —
    // so this is the keyboard half of the same thing. Handled on keyup as well
    // as here, because the browsers that clear the field on Escape themselves
    // do it after keydown, and reading .value too early filters to a word that
    // is already gone.
    input.addEventListener('keydown', function (event) {
      if (event.key === 'Enter') event.preventDefault();
      if (event.key === 'Escape') {
        input.value = '';
        apply('');
      }
    });

    input.addEventListener('keyup', function (event) {
      if (event.key === 'Escape') apply(input.value);
    });

    // Unconditional, for two reasons: it puts the count on the page at load,
    // and Firefox restores a typed value on reload without firing `input`,
    // which would otherwise leave the box holding a word and the page showing
    // every question.
    apply(input.value);
  })();
})();
