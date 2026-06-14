// Scorecard: client-side search (by name) + filter (by municipality).
// Progressive enhancement — without JS, all candidate cards remain visible.
(function () {
  // Open the collapsed methodology panel when linked via #methodology.
  var methodology = document.getElementById('methodology');
  if (methodology) {
    var openMethodology = function () {
      if (location.hash === '#methodology') {
        methodology.open = true;
        methodology.scrollIntoView();
      }
    };
    openMethodology();
    window.addEventListener('hashchange', openMethodology);
  }

  var grid = document.getElementById('candidate-grid');
  if (!grid) return;

  var search = document.getElementById('candidate-search');
  var count = document.getElementById('candidate-count');
  var empty = document.getElementById('candidate-empty');
  var cards = Array.prototype.slice.call(grid.querySelectorAll('.candidate-card'));
  var pills = Array.prototype.slice.call(document.querySelectorAll('.filter-pill'));
  var total = cards.length;

  var activeMuni = 'all';
  var query = '';

  function apply() {
    var visible = 0;
    cards.forEach(function (card) {
      var muniOk = activeMuni === 'all' || card.getAttribute('data-municipality') === activeMuni;
      var nameOk = query === '' || (card.getAttribute('data-name') || '').indexOf(query) !== -1;
      var show = muniOk && nameOk;
      card.hidden = !show;
      if (show) visible++;
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

  pills.forEach(function (pill) {
    pill.addEventListener('click', function () {
      activeMuni = this.getAttribute('data-muni');
      pills.forEach(function (p) {
        var on = p === pill;
        p.classList.toggle('is-active', on);
        p.setAttribute('aria-pressed', on ? 'true' : 'false');
      });
      apply();
    });
  });

  apply();
})();
