// Scorecard matrix: client-side search (by name) + filters (minimum grade,
// municipality). Progressive enhancement — without JS, all candidate rows
// remain visible.
(function () {
  // Open a collapsed <details> panel when it — or an element inside it — is the
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

  var search = document.getElementById('candidate-search');
  var count = document.getElementById('candidate-count');
  var empty = document.getElementById('candidate-empty');
  var topicSelect = document.getElementById('topic-filter');
  var rows = Array.prototype.slice.call(table.querySelectorAll('.scorecard-row'));
  var groups = Array.prototype.slice.call(table.querySelectorAll('.scorecard-matrix__group'));
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
      var nameOk = query === '' || (row.getAttribute('data-name') || '').indexOf(query) !== -1;
      var gradeOk = minRank === null || bestRank(row, activeTopic) >= minRank;
      var show = muniOk && officeOk && nameOk && gradeOk;
      row.hidden = !show;
      if (show) visible++;
    });

    // Hide a municipality block (and its heading) when none of its rows show.
    groups.forEach(function (group) {
      group.hidden = !group.querySelector('.scorecard-row:not([hidden])');
    });

    if (empty) empty.hidden = visible !== 0;
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

  apply();
})();
