// Questionnaire page: the "Print the questionnaire" button, and the popup that
// tells candidates this page is not the form.
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

  // ---------------------------------------------------------------------------
  // The candidate popup
  //
  // Shown once per browser. The dismissal was specced as a cookie and is
  // localStorage instead, for the same reason favourites.js gives: this is a
  // static site on GitHub Pages, so no server exists that could read a cookie,
  // and one would add its bytes to every request for every page and asset in
  // exchange for nothing. localStorage has the same scope (this browser, this
  // origin) and the same lifetime, and is never transmitted.
  //
  // dismissed()/dismiss() are the only two functions that know where the flag
  // lives, so swapping in document.cookie is a change to those two.
  // ---------------------------------------------------------------------------

  // Versioned, so that reworking the popup later can ship as :v2 and be seen
  // again by people who dismissed the first one.
  var STORAGE_KEY = 'livable-crd:candidate-popup-dismissed:v1';

  var modal = document.getElementById('candidate-modal');
  // `showModal` guards the browsers that parse <dialog> as an unknown element:
  // there the dialog is visible markup with no way to close it, and doing
  // nothing leaves it hidden by the CSS below instead.
  if (!modal || typeof modal.showModal !== 'function') return;

  // Safari in private mode throws on any localStorage access, as does a browser
  // with site data blocked. Both branches treat a throw as "not dismissed": the
  // popup is worth showing to somebody we cannot remember, and the alternative
  // is a reader who can never see it.
  function dismissed() {
    try {
      return window.localStorage.getItem(STORAGE_KEY) === '1';
    } catch (e) {
      return false;
    }
  }

  function dismiss() {
    try {
      window.localStorage.setItem(STORAGE_KEY, '1');
    } catch (e) {
      // Nothing to do and nothing to tell the reader: the popup still closes,
      // it just comes back next visit.
    }
  }

  if (dismissed()) return;

  // Every route out of the dialog is a dismissal — the button, Esc, a click on
  // the backdrop. Somebody who closed this has answered the question it asked,
  // and asking again next visit because they used the wrong exit would be the
  // rude version of a popup.
  //
  // `close` fires for all of them, so the flag is written here once rather than
  // on each of them.
  modal.addEventListener('close', function () {
    modal.classList.remove('is-closing');
    dismiss();
  });

  // The close animation. `.is-closing` runs the keyframes in
  // _sass/_questionnaire.scss while the dialog is still open, and the real
  // close() waits for them: calling it straight away would take the element
  // out of the top layer mid-frame and there would be nothing left to animate.
  //
  // The timer is the safety net, not the mechanism. `animationend` does not
  // fire when the animation was never applied — a browser that ignores the
  // keyframes, or a reduced-motion reader whose animation is `none` — and a
  // popup that will not close is far worse than one that closes unanimated.
  var closing = false;

  function closeWithAnimation() {
    if (closing) return;
    closing = true;

    var done = false;
    function finish() {
      if (done) return;
      done = true;
      closing = false;
      modal.close();
    }

    modal.addEventListener('animationend', finish, { once: true });
    window.setTimeout(finish, 300);
    modal.classList.add('is-closing');
  }

  Array.prototype.slice.call(
    modal.querySelectorAll('[data-candidate-modal-close]')
  ).forEach(function (el) {
    el.addEventListener('click', closeWithAnimation);
  });

  // A modal <dialog> has no light-dismiss of its own, and the backdrop is a
  // pseudo-element that cannot take a listener, so a click that lands on the
  // dialog itself rather than on anything inside it is the backdrop click.
  modal.addEventListener('click', function (event) {
    if (event.target === modal) closeWithAnimation();
  });

  // Esc. The browser's own handling closes the dialog outright, which skips the
  // animation, so the default is cancelled and the same path taken as every
  // other exit. Esc still closes — it just closes the way the button does.
  modal.addEventListener('cancel', function (event) {
    event.preventDefault();
    closeWithAnimation();
  });

  // The mailto is the point of the popup. Following it should not leave the
  // page under a dialog the reader has to close on the way back. Closed
  // outright rather than animated: the mail client is opening over this, and
  // an animation nobody is looking at is a delay on the thing they clicked.
  var mail = modal.querySelector('a[href^="mailto:"]');
  if (mail) {
    mail.addEventListener('click', function () {
      modal.close();
    });
  }

  modal.showModal();
})();
