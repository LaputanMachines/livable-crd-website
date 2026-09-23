// Candidate page: the "Print scorecard" button, the control that opens or closes
// every topic at once, and the bar that keeps the candidate's name on screen
// once the hero has scrolled away.
//
// Arriving from a grade chip on the scorecard matrix (/scorecard/<muni>/<name>/
// #topic-<subject>) opens that topic on the way in. That is not here: it is
// assets/js/details-hash.js, the same script /faq/ uses to open a panel a link
// points into, loaded by this page for the same job.
//
// The leaflet itself is entirely CSS (@media print in _sass/_candidate.scss),
// so the print half exists only to save the reader a trip to the browser menu.
// Both buttons ship hidden and are revealed here: progressive enhancement, the
// same way the scorecard's filters leave every row visible without JS. The
// topics are a native <details> each, so a reader without scripting loses the
// shortcut and keeps the page.
(function () {
  var btn = document.getElementById('print-scorecard');
  if (!btn) return;

  btn.hidden = false;
  btn.addEventListener('click', function () {
    window.print();
  });
})();

(function () {
  var toggle = document.getElementById('toggle-all-topics');
  if (!toggle) return;

  var topics = Array.prototype.slice.call(
    document.querySelectorAll('.candidate-grade__disclosure')
  );
  // The button is only rendered where the page has more than one topic to open
  // (see _layouts/candidate.html), so an empty list here means the markup and
  // this script have come apart. Leaving it hidden is the safe half of that.
  if (topics.length === 0) return;

  var expandLabel = toggle.getAttribute('data-label-expand') || 'Expand all topics';
  var collapseLabel = toggle.getAttribute('data-label-collapse') || 'Collapse all topics';

  function allOpen() {
    return topics.every(function (topic) {
      return topic.open;
    });
  }

  // The mark is the state: it shows what pressing the button will do next, so
  // it is a minus exactly when everything is already open. The words it stands
  // for go to screen readers and the hover tooltip.
  function sync() {
    var open = allOpen();
    var label = open ? collapseLabel : expandLabel;
    toggle.textContent = open ? '\u2212' : '+';
    toggle.setAttribute('aria-label', label);
    toggle.title = label;
  }

  // Opening one row by hand is the common way for the page to stop matching the
  // button, and a "Expand all topics" that expands eight of nine and then has to
  // be pressed again to collapse them is worse than no button. Each row reports
  // its own state change, including the ones this script causes.
  topics.forEach(function (topic) {
    topic.addEventListener('toggle', sync);
  });

  toggle.addEventListener('click', function () {
    var open = !allOpen();
    topics.forEach(function (topic) {
      topic.open = open;
    });
    // The toggle events above have already run sync by here; calling it again
    // costs nothing and covers a browser that does not fire them on a
    // programmatic change.
    sync();
  });

  sync();
  toggle.hidden = false;
})();

// The bar that keeps the candidate's name on screen once the hero has scrolled
// off under the site header.
//
// Built here rather than in _layouts/candidate.html, from the hero's own name
// and meta line: a second copy of them in the template is two places to edit a
// candidate's standing, and the page already refuses that trade for the print
// leaflet. It also means the bar exists only where this runs, which is what the
// CSS assumes — without scripting the hero simply scrolls away, as it always
// did.
//
// Fixed, not sticky. See .candidate-stickybar in _sass/_candidate.scss for why:
// a sticky hero that shrinks is still in flow, and the shrinking pulls the page
// up under the reader.
(function () {
  var hero = document.querySelector('.candidate-hero');
  if (!hero) return;

  var name = hero.querySelector('.candidate-hero__name');
  if (!name) return;

  var meta = hero.querySelector('.candidate-hero__meta');
  var header = document.querySelector('.site-header');

  var bar = document.createElement('div');
  bar.className = 'candidate-stickybar';
  // The name in here is the page's <h1> said a second time, and the standing
  // line with it. Both are already read at the top of the page, so the bar is
  // decoration for a screen reader and hidden from it.
  bar.setAttribute('aria-hidden', 'true');

  var inner = document.createElement('div');
  inner.className = 'candidate-stickybar__inner';

  var barName = document.createElement('span');
  barName.className = 'candidate-stickybar__name';
  barName.textContent = name.textContent.trim();
  inner.appendChild(barName);

  if (meta) {
    var barMeta = document.createElement('span');
    barMeta.className = 'candidate-stickybar__meta';
    barMeta.textContent = meta.textContent.trim();
    inner.appendChild(barMeta);
  }

  // The slate, where the candidate runs with one. Just the organization's name:
  // the hero's "Running with" is a label for a line of its own and reads as
  // filler in a bar that is already a list of facts about one person.
  var slate = hero.querySelector('.candidate-hero__slate');
  var slateName = slate && slate.querySelector('strong');
  if (slateName) {
    var barSlate = document.createElement('span');
    barSlate.className = 'candidate-stickybar__slate';

    // The hero's slate-* class, which is what carries --slate-tint, so the dot
    // below keeps the colour this slate has in the scorecard's tinted rows. The
    // hero's own block class is not matched: `slate-` has to start a word, and
    // in `candidate-hero__slate` it does not.
    var tint = (slate.className.match(/\bslate-[\w-]+/g) || []);
    for (var i = 0; i < tint.length; i++) barSlate.classList.add(tint[i]);

    var dot = slate.querySelector('.slate-dot');
    if (dot) barSlate.appendChild(dot.cloneNode(true));
    barSlate.appendChild(document.createTextNode(slateName.textContent.trim()));

    inner.appendChild(barSlate);
  }

  bar.appendChild(inner);
  document.body.appendChild(bar);

  // The topic rows scroll-margin past both stuck things (see
  // .candidate-grade-row in _sass/_candidate.scss), so the bar's height has to
  // be readable from CSS. It is one line at any width, but which line-height
  // and which clamp step depends on the viewport.
  function publishHeight() {
    var h = Math.ceil(bar.getBoundingClientRect().height);
    if (h > 0) {
      document.documentElement.style.setProperty('--candidate-bar-h', h + 'px');
      // Only ever set here, so an open topic's sticky row (see
      // .candidate-grade__disclosure in _sass/_candidate.scss) leaves no gap
      // for a bar on a page where this never ran. Floored rather than ceiled,
      // like the heights site-header.js and scorecard.js publish for the rows
      // stuck under them: an overlap the bar paints over costs nothing, a gap
      // shows the page through the seam.
      var stuck = Math.floor(bar.getBoundingClientRect().height);
      document.documentElement.style.setProperty('--candidate-bar-live-h', stuck + 'px');
    }
  }

  var queued = false;

  function update() {
    queued = false;
    // The test is whether the hero has gone under the header: the bar takes
    // over exactly where the name it repeats stops being readable. Reading the
    // header's own box rather than a copy of its height means the nav wrapping
    // at some width cannot put the two out of step.
    var edge = header ? header.getBoundingClientRect().bottom : 0;
    var show = hero.getBoundingClientRect().bottom <= edge;
    if (show !== bar.classList.contains('is-visible')) {
      bar.classList.toggle('is-visible', show);
    }
  }

  function onScroll() {
    if (queued) return;
    queued = true;
    window.requestAnimationFrame(update);
  }

  publishHeight();
  update();
  window.addEventListener('scroll', onScroll, { passive: true });
  window.addEventListener('resize', onScroll);
  if (window.ResizeObserver) new ResizeObserver(publishHeight).observe(bar);
})();
