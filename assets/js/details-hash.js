// Open a collapsed <details> when it (or an element inside it) is the link
// target. Covers the FAQ panels (#methodology, #who-grades, #categories,
// #how-candidates-are-added, #deadlines) and the #category-<id> rows the
// homepage topic cards deep-link to. Without this, jumping to an anchor inside
// a closed <details> scrolls to hidden content.
//
// Its own file rather than a block in scorecard.js: the panels moved to /faq/,
// which has no matrix to filter, and scorecard.js is the matrix.
(function () {
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
})();
