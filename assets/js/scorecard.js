// Scorecard matrix: client-side search (by name or slate) + filters (minimum
// grade, office, municipality). Every filter is mirrored into the query string
// so the address bar is always a shareable link to the current view, and a link
// that carries those params opens already filtered. Progressive enhancement:
// without JS, all candidate rows remain visible.
(function () {
  var table = document.getElementById('candidate-grid');
  if (!table) return;

  // The matrix's topic header row sticks below the site header, whose height is
  // measured and published as --site-header-h by assets/js/site-header.js. That
  // moved out of here when the candidate hero started sticking below the same
  // header: one measurement, on every page, rather than a copy per page that
  // needs it.

  // The municipality bands stick below the topic header row, so their offset is
  // the site header plus that row. Its height is no more a constant than the
  // header's: the row is icon-only on a phone and icon-plus-label from 52.5rem
  // up, so a literal is wrong on one side of that breakpoint or the other.
  var matrixHead = table.tHead;
  if (matrixHead) {
    var publishMatrixHeadHeight = function () {
      // Floored for the same reason as above: an overlap the row above paints
      // over costs nothing, a gap shows the page through the seam.
      var mh = Math.floor(matrixHead.getBoundingClientRect().height);
      document.documentElement.style.setProperty('--matrix-head-h', mh + 'px');
    };
    publishMatrixHeadHeight();
    if (window.ResizeObserver) new ResizeObserver(publishMatrixHeadHeight).observe(matrixHead);
  }

  var search = document.getElementById('candidate-search');
  var count = document.getElementById('candidate-count');
  var empty = document.getElementById('candidate-empty');
  var topicSelect = document.getElementById('topic-filter');
  var scopeSelect = document.getElementById('grade-scope');
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
  var participatingButton = document.getElementById('participating-only');

  var activeMuni = 'all';
  var activeGrade = 'all'; // 'all' or a minimum rank as a string ('2' = C or better)
  var activeTopic = 'all'; // 'all' (overall: every graded topic) or a subject id
  var activeOffice = 'all'; // 'all', 'mayor', or 'councillor'
  // Hide candidates who returned nothing. On by default: the table opens on the
  // candidates who took part, and ?responded=all is the link to everyone.
  var participatingOnly = true;
  var query = '';

  // Letter grade → numeric rank for the "minimum grade" filter. Pending ("—",
  // empty) ranks below F so it never satisfies a threshold.
  var RANK = { A: 4, B: 3, C: 2, D: 1, F: 0 };
  function rankOf(text) {
    if (!text) return -1;
    var base = text.trim().toUpperCase().charAt(0);
    return RANK.hasOwnProperty(base) ? RANK[base] : -1;
  }

  // Lowest grade rank across every topic the row has a letter in: "overall"
  // means no topic below the bar. Chips without a letter (pending, answered,
  // declined) are not grades and are skipped; a row with no letter at all
  // returns -1, so it never meets a threshold.
  function worstRank(row) {
    var cells = row.querySelectorAll('.scorecard-matrix__cell');
    var worst = null;
    for (var i = 0; i < cells.length; i++) {
      var badge = cells[i].querySelector('.grade');
      var rank = rankOf(badge && badge.textContent);
      if (rank < 0) continue;
      worst = worst === null ? rank : Math.min(worst, rank);
    }
    return worst === null ? -1 : worst;
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

  // --- Non-participating candidates, folded -------------------------------
  // With "Only show participating candidates" on, each municipality ends in a
  // row that says how many of its candidates the filter is hiding and opens
  // them in place, so the reader can tell they exist without the table
  // opening on them. Built here rather than in the page: the filter it
  // belongs to is this script's, so without the script there is nothing to
  // fold. Each municipality opens and closes on its own.
  var expandedMunis = {};
  var moreRows = [];
  // Each row's place as built (alphabetical within its municipality), so the
  // rows can be put back after arrange() below has moved them.
  var homeOrder = new Map();
  rows.forEach(function (row, i) { homeOrder.set(row, i); });

  // While the filter is on, the non-participating rows sit under the fold row,
  // so opening it reveals them beneath the button like an accordion rather
  // than scattered through the list above it. Otherwise every row is in home
  // order with the fold row last. Only rows out of place are moved:
  // insertBefore() on a row already in place still blurs anything focused in it.
  function arrange() {
    moreRows.forEach(function (m) {
      var live = Array.prototype.slice.call(m.group.querySelectorAll('.scorecard-row, .scorecard-matrix__more-row'));
      var own = live.filter(function (el) { return el !== m.row; });
      own.sort(function (a, b) { return homeOrder.get(a) - homeOrder.get(b); });
      var wanted;
      if (participatingOnly) {
        wanted = own.filter(function (r) { return r.hasAttribute('data-returned'); })
          .concat([m.row], own.filter(function (r) { return !r.hasAttribute('data-returned'); }));
      } else {
        wanted = own.concat([m.row]);
      }
      for (var i = 0; i < wanted.length; i++) {
        if (live[i] !== wanted[i]) {
          m.group.insertBefore(wanted[i], live[i]);
          live = Array.prototype.slice.call(m.group.querySelectorAll('.scorecard-row, .scorecard-matrix__more-row'));
        }
      }
    });
  }
  candidateGroups.forEach(function (group) {
    if (group.id === 'favourites-group') return;
    var muni = group.getAttribute('data-municipality');
    var head = group.querySelector('.scorecard-matrix__group-head');
    var tr = document.createElement('tr');
    tr.className = 'scorecard-matrix__more-row';
    tr.hidden = true;
    var td = document.createElement('td');
    td.colSpan = head ? head.colSpan : 1;
    td.className = 'scorecard-matrix__more-cell';
    var button = document.createElement('button');
    button.type = 'button';
    button.className = 'scorecard-matrix__more';
    button.setAttribute('aria-expanded', 'false');
    button.addEventListener('click', function () {
      expandedMunis[muni] = !expandedMunis[muni];
      apply();
    });
    td.appendChild(button);
    tr.appendChild(td);
    group.appendChild(tr);
    moreRows.push({ group: group, muni: muni, row: tr, button: button });
  });

  // Each municipality's slate key counts the slate's candidates the table is
  // built to show: those who took part while the participating filter is on,
  // everyone otherwise.
  var slateCounts = Array.prototype.slice.call(document.querySelectorAll('.slate-legend__item[data-slate-total]'));

  function apply() {
    arrange();
    slateCounts.forEach(function (item) {
      var count = item.querySelector('.slate-legend__count');
      if (count) {
        count.textContent = item.getAttribute(participatingOnly ? 'data-slate-returned' : 'data-slate-total');
      }
    });
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
      var gradeOk = minRank === null ||
        (activeTopic === 'all' ? worstRank(row) : bestRank(row, activeTopic)) >= minRank;
      // A starred row is the reader's own pick, so the pinned group shows it
      // whether or not the candidate took part.
      var folded = participatingOnly && !row.hasAttribute('data-returned') &&
        !(row.parentNode && row.parentNode.id === 'favourites-group');
      var otherOk = muniOk && officeOk && nameOk && gradeOk;
      row.setAttribute('data-folded', otherOk && folded ? 'true' : 'false');
      var show = otherOk && (!folded || expandedMunis[row.getAttribute('data-municipality')] === true);
      row.hidden = !show;
      if (show) visible++;
    });

    // Each municipality's fold row: shown while the filter is hiding anyone
    // there who would otherwise match, and naming how many.
    moreRows.forEach(function (m) {
      var n = m.group.querySelectorAll('.scorecard-row[data-folded="true"]').length;
      m.row.hidden = n === 0;
      if (n === 0) return;
      var open = expandedMunis[m.muni] === true;
      var noun = n === 1 ? 'candidate' : 'candidates';
      m.button.textContent = (open ? 'Hide ' : 'Show ') + n + ' non-participating ' + noun;
      m.button.setAttribute('aria-expanded', String(open));
    });

    // Hide a municipality block (and its heading) when nothing in it shows: no
    // row, and no fold row standing in for rows the filter is hiding.
    candidateGroups.forEach(function (group) {
      group.hidden = !group.querySelector('.scorecard-row:not([hidden]), .scorecard-matrix__more-row:not([hidden])');
    });

    // Empty municipalities exist to show the region is fully covered, so they
    // stay put in the default view. Once the reader narrows by name, grade,
    // office or response they are only noise (nothing in them could ever match) so drop
    // them. The municipality filter still applies: picking one keeps only it.
    // Topic is excluded because it does nothing on its own, only alongside grade.
    var narrowed = query !== '' || activeGrade !== 'all' || activeOffice !== 'all' || participatingOnly;
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

    syncUrl();
  }

  if (search) {
    search.addEventListener('input', function () {
      query = this.value.trim().toLowerCase();
      apply();
    });
  }

  // Paint one group of pills to match the state they represent. Shared by the
  // click handler below and by the URL reader above it, so a filter restored
  // from a link looks exactly like one the reader clicked.
  function setPillState(pills, attr, value) {
    pills.forEach(function (p) {
      var on = p.getAttribute(attr) === value;
      p.classList.toggle('is-active', on);
      p.setAttribute('aria-pressed', on ? 'true' : 'false');
    });
  }

  // --- Shareable filter links -----------------------------------------------
  // Every filter is mirrored into the query string, so the URL in the address
  // bar is always a link to what the reader is looking at: clicking Sooke gives
  // /scorecard/?muni=sooke, and that link opens on Sooke for whoever receives
  // it. replaceState rather than pushState: a filter bar is a view of one page,
  // not a series of pages, and eight taps on the pills should not cost eight
  // presses of Back to leave.

  // A value only counts if some control can express it, so a stale or hand-typed
  // link falls back to "all" instead of filtering the table down to nothing.
  function pillValue(pills, attr, value, fallback) {
    if (!value) return fallback;
    for (var i = 0; i < pills.length; i++) {
      if (pills[i].getAttribute(attr) === value) return value;
    }
    return fallback;
  }

  function readUrlFilters() {
    if (!window.URLSearchParams) return;
    var params = new URLSearchParams(location.search);
    activeMuni = pillValue(muniPills, 'data-muni', params.get('muni'), 'all');
    activeGrade = pillValue(gradePills, 'data-grade', params.get('grade'), 'all');
    activeOffice = pillValue(officePills, 'data-office', params.get('office'), 'all');
    setPillState(muniPills, 'data-muni', activeMuni);
    setPillState(gradePills, 'data-grade', activeGrade);
    setPillState(officePills, 'data-office', activeOffice);

    if (topicSelect) {
      // Checked by walking the options rather than by building a selector, so a
      // link carrying a junk topic cannot become a query the browser parses.
      var topic = params.get('topic') || 'all';
      var known = false;
      for (var i = 0; i < topicSelect.options.length; i++) {
        if (topicSelect.options[i].value === topic) known = true;
      }
      // A link naming a topic means "in" that topic; anything else, including
      // an old ?topic=all link, is overall.
      activeTopic = known ? topic : 'all';
    }

    participatingOnly = params.get('responded') !== 'all';

    var q = (params.get('q') || '').trim();
    if (search) search.value = q;
    query = q.toLowerCase();
  }

  function syncUrl() {
    if (!window.URLSearchParams || !window.history || !history.replaceState) return;
    // Seeded from the current query string rather than from empty, so anything
    // we did not put there (a utm_ tag on a shared link, say) survives.
    var params = new URLSearchParams(location.search);
    function put(key, value, fallback) {
      if (!value || value === fallback) params.delete(key);
      else params.set(key, value);
    }
    put('muni', activeMuni, 'all');
    put('grade', activeGrade, 'all');
    put('topic', activeTopic, 'all');
    put('office', activeOffice, 'all');
    put('responded', participatingOnly ? '' : 'all', '');
    // The reader's own casing, not the lowercased copy the filter matches on.
    put('q', search ? search.value.trim() : '', '');
    var qs = params.toString();
    try {
      history.replaceState(null, '', location.pathname + (qs ? '?' + qs : '') + location.hash);
    } catch (e) {
      // Some browsers refuse replaceState on file:// and other opaque origins.
      // Filtering still works; only the shareable URL is lost.
    }
  }

  // Wire a group of mutually-exclusive filter pills sharing one data attribute.
  function wirePills(pills, attr, onPick) {
    pills.forEach(function (pill) {
      pill.addEventListener('click', function () {
        var value = this.getAttribute(attr);
        onPick(value);
        setPillState(pills, attr, value);
        apply();
      });
    });
  }

  wirePills(muniPills, 'data-muni', function (v) { activeMuni = v; });
  wirePills(gradePills, 'data-grade', function (v) { activeGrade = v; });
  wirePills(officePills, 'data-office', function (v) { activeOffice = v; });

  if (participatingButton) {
    participatingButton.addEventListener('click', function () {
      participatingOnly = !participatingOnly;
      this.setAttribute('aria-pressed', String(participatingOnly));
      this.classList.toggle('is-active', participatingOnly);
      apply();
    });
  }

  // The two selects say one thing between them: "overall", or "in" plus the
  // topic. The topic select only shows while "in" is chosen.
  function paintScope() {
    var overall = activeTopic === 'all';
    if (scopeSelect) scopeSelect.value = overall ? 'overall' : 'topic';
    if (topicSelect) {
      topicSelect.hidden = overall;
      if (!overall) topicSelect.value = activeTopic;
    }
  }

  if (scopeSelect && topicSelect) {
    scopeSelect.addEventListener('change', function () {
      activeTopic = this.value === 'topic' ? topicSelect.value : 'all';
      paintScope();
      apply();
    });
  }

  if (topicSelect) {
    topicSelect.addEventListener('change', function () {
      activeTopic = this.value;
      apply();
    });
  }

  // --- Slate highlighting ---------------------------------------------------
  // One tint per slate, switched on for every municipality at once from the
  // "Highlight slate candidates" pill in the filter bar. The palette classes are
  // already on the rows (see scorecard/index.md); all this does is decide
  // whether they paint anything, so nothing here knows a colour. Each
  // municipality's band keeps its slate key, which needs no script.
  //
  // Independent of every filter above: highlighting changes how rows look, not
  // which rows show, so it deliberately does not touch apply(). Off by default.
  var slateButton = document.getElementById('slate-highlight');
  var slateGroup = document.getElementById('slate-filtergroup');
  if (slateButton && slateGroup) {
    slateGroup.hidden = false;
    slateButton.addEventListener('click', function () {
      var on = this.getAttribute('aria-pressed') !== 'true';
      this.setAttribute('aria-pressed', String(on));
      this.classList.toggle('is-active', on);
      // Marked on the rows themselves rather than on a tbody, because
      // favourites.js MOVES rows into the pinned group, and a class on the
      // row travels with it.
      rows.forEach(function (row) { row.classList.toggle('is-slate-lit', on); });
    });
  }

  readUrlFilters();
  paintScope();
  // Painted here, not in readUrlFilters(): the toggle starts pressed, so its
  // state must reach the button even where that function returns early.
  if (participatingButton) {
    participatingButton.setAttribute('aria-pressed', String(participatingOnly));
    participatingButton.classList.toggle('is-active', participatingOnly);
  }
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
