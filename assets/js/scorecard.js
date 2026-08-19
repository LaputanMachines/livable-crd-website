// Scorecard matrix: client-side search (by name or slate) + filters (minimum
// grade, office, municipality). Progressive enhancement: without JS, all
// candidate rows remain visible.
(function () {
  // Open a collapsed <details> panel when it (or an element inside it) is the
  // link target. Covers #methodology, #who-grades, #categories, and the
  // #category-<id> rows the homepage topic cards deep-link to. Without this,
  // jumping to an anchor inside a closed <details> scrolls to hidden content.
  function revealHashTarget() {
    var hash = location.hash;
    if (!hash || hash.length < 2) return;
    var id = hash.slice(1);
    try { id = decodeURIComponent(id); } catch (e) {}
    var target = document.getElementById(id);
    if (!target) return;
    for (var el = target; el; el = el.parentElement) {
      if (el.tagName && el.tagName.toLowerCase() === 'details') el.open = true;
    }
    target.scrollIntoView();
  }
  revealHashTarget();
  window.addEventListener('hashchange', revealHashTarget);

  var table = document.getElementById('candidate-grid');
  if (!table) return;

  // The matrix's topic header row sticks below the site header (see the
  // min-width: 60rem block in _components.scss), so it needs that header's
  // height as an offset. It is not a constant worth hardcoding: the nav wraps
  // at some widths and every part of it is sized in rem, so a literal drifts
  // the moment either changes and leaves either a strip of rows above the
  // stuck header or a gap of page showing through under it. Measure it, and
  // remeasure whenever it changes size.
  var siteHeader = document.querySelector('.site-header');
  if (siteHeader) {
    var publishHeaderHeight = function () {
      var h = Math.round(siteHeader.getBoundingClientRect().height);
      document.documentElement.style.setProperty('--site-header-h', h + 'px');
    };
    publishHeaderHeight();
    if (window.ResizeObserver) new ResizeObserver(publishHeaderHeight).observe(siteHeader);
  }

  var search = document.getElementById('candidate-search');
  var count = document.getElementById('candidate-count');
  var empty = document.getElementById('candidate-empty');
  var topicSelect = document.getElementById('topic-filter');
  var rows = Array.prototype.slice.call(table.querySelectorAll('.scorecard-row'));
  var groups = Array.prototype.slice.call(table.querySelectorAll('.scorecard-matrix__group'));
  // Municipalities with no confirmed candidates: heading-only groups that have no
  // rows to filter, so they are shown or hidden as a whole (see apply()).
  var emptyGroups = groups.filter(function (g) { return g.hasAttribute('data-empty'); });
  var candidateGroups = groups.filter(function (g) { return !g.hasAttribute('data-empty'); });
  var muniPills = Array.prototype.slice.call(document.querySelectorAll('[data-muni]'));
  var gradePills = Array.prototype.slice.call(document.querySelectorAll('[data-grade]'));
  // Scoped to the office filter container: rows also carry data-office.
  var officePills = Array.prototype.slice.call(document.querySelectorAll('#office-filters [data-office]'));
  var total = rows.length;

  var activeMuni = 'all';
  var activeGrade = 'all'; // 'all' or a minimum rank as a string ('2' = C or better)
  var activeTopic = 'all'; // 'all' (any topic) or a subject id
  var activeOffice = 'all'; // 'all', 'mayor', or 'councillor'
  var query = '';

  // Letter grade → numeric rank for the "minimum grade" filter. Pending ("—",
  // empty) ranks below F so it never satisfies a threshold.
  var RANK = { A: 4, B: 3, C: 2, D: 1, F: 0 };
  function rankOf(text) {
    if (!text) return -1;
    var base = text.trim().toUpperCase().charAt(0);
    return RANK.hasOwnProperty(base) ? RANK[base] : -1;
  }

  // Highest grade rank a row reaches, scoped to one topic or across all of them.
  function bestRank(row, topic) {
    var selector = topic === 'all'
      ? '.scorecard-matrix__cell'
      : '.scorecard-matrix__cell[data-topic="' + topic + '"]';
    var cells = row.querySelectorAll(selector);
    var best = -1;
    for (var i = 0; i < cells.length; i++) {
      var badge = cells[i].querySelector('.grade');
      best = Math.max(best, rankOf(badge && badge.textContent));
    }
    return best;
  }

  function apply() {
    var minRank = activeGrade === 'all' ? null : parseInt(activeGrade, 10);
    var visible = 0;
    rows.forEach(function (row) {
      var muniOk = activeMuni === 'all' || row.getAttribute('data-municipality') === activeMuni;
      var officeOk = activeOffice === 'all' || row.getAttribute('data-office') === activeOffice;
      // Slate is searched rather than filtered by pills (see scorecard/index.md),
      // so it shares the query with the name: typing "sooke first" narrows to
      // that slate, and a slate name can never collide with a person's name in
      // a way that matters: both are things a reader might reasonably type.
      var nameOk = query === '' ||
        (row.getAttribute('data-name') || '').indexOf(query) !== -1 ||
        (row.getAttribute('data-slate') || '').indexOf(query) !== -1;
      var gradeOk = minRank === null || bestRank(row, activeTopic) >= minRank;
      var show = muniOk && officeOk && nameOk && gradeOk;
      row.hidden = !show;
      if (show) visible++;
    });

    // Hide a municipality block (and its heading) when none of its rows show.
    candidateGroups.forEach(function (group) {
      group.hidden = !group.querySelector('.scorecard-row:not([hidden])');
    });

    // Empty municipalities exist to show the region is fully covered, so they
    // stay put in the default view. Once the reader narrows by name, grade, or
    // office they are only noise (nothing in them could ever match) so drop
    // them. The municipality filter still applies: picking one keeps only it.
    // Topic is excluded because it does nothing on its own, only alongside grade.
    var narrowed = query !== '' || activeGrade !== 'all' || activeOffice !== 'all';
    var emptyShown = 0;
    emptyGroups.forEach(function (group) {
      var muniOk = activeMuni === 'all' || group.getAttribute('data-municipality') === activeMuni;
      var show = !narrowed && muniOk;
      group.hidden = !show;
      if (show) emptyShown++;
    });

    // The placeholder inside a shown empty group already says nobody has
    // announced there, so the page-level "no matches" line would just repeat it.
    if (empty) empty.hidden = visible !== 0 || emptyShown > 0;
    if (count) {
      count.textContent = visible === total
        ? 'Showing all ' + total + ' candidates'
        : 'Showing ' + visible + ' of ' + total + ' candidates';
    }
  }

  if (search) {
    search.addEventListener('input', function () {
      query = this.value.trim().toLowerCase();
      apply();
    });
  }

  // Wire a group of mutually-exclusive filter pills sharing one data attribute.
  function wirePills(pills, attr, onPick) {
    pills.forEach(function (pill) {
      pill.addEventListener('click', function () {
        onPick(this.getAttribute(attr));
        pills.forEach(function (p) {
          var on = p === pill;
          p.classList.toggle('is-active', on);
          p.setAttribute('aria-pressed', on ? 'true' : 'false');
        });
        apply();
      });
    });
  }

  wirePills(muniPills, 'data-muni', function (v) { activeMuni = v; });
  wirePills(gradePills, 'data-grade', function (v) { activeGrade = v; });
  wirePills(officePills, 'data-office', function (v) { activeOffice = v; });

  if (topicSelect) {
    topicSelect.addEventListener('change', function () {
      activeTopic = this.value;
      apply();
    });
  }

  // --- Slate highlighting ---------------------------------------------------
  // Per-municipality tint, one colour per slate, toggled from that
  // municipality's heading. The palette classes are already on the rows (see
  // scorecard/index.md); all this does is decide whether they paint anything,
  // so nothing here knows a colour.
  //
  // The controls ship hidden and are revealed here because the tint needs this
  // script: a box that could never do anything is worse than no box.
  //
  // Independent of every filter above: highlighting changes how rows look, not
  // which rows show, so it deliberately does not touch apply().
  // Only the checkbox is revealed here. Each municipality's slate legend renders
  // visible from the start: which slates are running there is worth knowing
  // whether or not the reader wants the rows coloured, and it needs no script.
  var slateToggles = Array.prototype.slice.call(document.querySelectorAll('[data-slate-toggle]'));
  slateToggles.forEach(function (toggle) {
    var muni = toggle.getAttribute('data-slate-toggle');
    var label = document.querySelector('[data-slate-control="' + muni + '"]');
    if (label) label.hidden = false;

    function paint(on) {
      // Marked on the rows themselves rather than on the municipality's tbody,
      // because favourites.js MOVES rows out of that tbody into the pinned
      // group. A class on the container would drop the tint the moment a
      // reader starred a row; a class on the row travels with it.
      rows.forEach(function (row) {
        if (row.getAttribute('data-municipality') === muni) {
          row.classList.toggle('is-slate-lit', on);
        }
      });
    }

    // The box ships `checked`, so the tint has to be painted once here: a
    // checkbox that is already on fires no change event. Read the live property
    // rather than assuming true, so a browser restoring the reader's unchecked
    // state across a reload is honoured instead of overridden.
    paint(toggle.checked);

    toggle.addEventListener('change', function () {
      paint(this.checked);
    });
  });

  apply();

  // --- Seam: assets/js/favourites.js ---------------------------------------
  // That script moves rows between tbodies at runtime (into and out of the
  // pinned favourites group, which is an ordinary candidate group as far as
  // everything above is concerned). Every decision in apply() is recomputed
  // from the DOM, so it stays correct across a move, but only if something
  // re-runs it, and only this file may decide what "visible" means.
  //
  // Deliberately one-way and event-shaped: nothing here knows what a favourite
  // is, and nothing there reaches into this closure.
  table.addEventListener('scorecard:refilter', apply);
})();
