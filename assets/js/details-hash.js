// Open a collapsed <details> when it, an element inside it, or an element
// holding one is the link target. Three callers:
//
//   /faq/                 the panels (#methodology, #who-grades, #categories,
//                         #how-candidates-are-added, #deadlines) and the
//                         #category-<id> rows the homepage topic cards link to,
//                         which sit inside a panel
//   a candidate's page    #topic-<subject>, linked from every grade chip on the
//                         scorecard matrix. The id is on the row rather than on
//                         the disclosure inside it, because a topic with nothing
//                         published has no disclosure and still has to be a
//                         target
//
// Without this, jumping to an anchor inside a closed <details> scrolls to
// hidden content, and jumping to one wrapped around a closed <details> scrolls
// to a topic the reader then has to open themselves.
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
    // The other direction: the target wraps the disclosure. Only the first one,
    // and only where the target is not itself a <details>, so a link into a
    // panel of several cannot open all of them.
    if (target.tagName.toLowerCase() !== 'details') {
      var inner = target.querySelector('details');
      if (inner) inner.open = true;
    }
    // Scrolled after opening, not before: the browser's own jump happened while
    // the target was still closed, and everything below it has moved since.
    // Both pages give their targets a scroll-margin-top to clear whatever is
    // stuck above them, and this honours it.
    target.scrollIntoView();
  }
  revealHashTarget();
  window.addEventListener('hashchange', revealHashTarget);
})();
