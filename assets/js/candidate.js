// Candidate page: the "Print scorecard" button.
//
// The leaflet itself is entirely CSS (@media print in _sass/_candidate.scss),
// so this script exists only to save the reader a trip to the browser menu.
// The button ships hidden and is revealed here: progressive enhancement, the
// same way the scorecard's filters leave every row visible without JS.
(function () {
  var btn = document.getElementById('print-scorecard');
  if (!btn) return;

  btn.hidden = false;
  btn.addEventListener('click', function () {
    window.print();
  });
})();
