// Publishes the sticky site header's height as --site-header-h, for anything
// that has to stick underneath it: the scorecard matrix's topic header row and
// municipality bands (_sass/_components.scss), and the candidate hero
// (_sass/_candidate.scss).
//
// Not a constant worth hardcoding. The nav wraps at some widths and every part
// of it is sized in rem, so a literal drifts the moment either changes and
// leaves either a strip of content above the stuck element or a gap of page
// showing through under it. Measure it, and remeasure whenever it changes size.
//
// Loaded from _layouts/default.html so the value is true on every page, rather
// than from the one page that first needed it. :root in _sass/_layout.scss
// declares the fallback: what a page gets before this runs, and if it never
// does.
(function () {
  var header = document.querySelector('.site-header');
  if (!header) return;

  function publish() {
    // Floored, not rounded. The height is fractional (the nav is sized in rem,
    // and a fractional device pixel ratio makes it fractional in CSS pixels
    // too), and rounding it up puts a stuck element a fraction below the header
    // with the page showing through the seam. Floor errs the other way, into an
    // overlap the header paints over; the -1px in the CSS covers the rest.
    var h = Math.floor(header.getBoundingClientRect().height);
    document.documentElement.style.setProperty('--site-header-h', h + 'px');
  }

  publish();
  if (window.ResizeObserver) new ResizeObserver(publish).observe(header);
})();
