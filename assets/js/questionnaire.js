// Questionnaire page: the "Print the questionnaire" button.
//
// The printed sheet is entirely CSS (@media print in _sass/_questionnaire.scss),
// so this script exists only to save the reader a trip to the browser menu.
// The button ships hidden and is revealed here: progressive enhancement, the
// same way the candidate leaflet's print button works. Readers without JS still
// get the sheet from their browser's own print command.
(function () {
  var btn = document.getElementById('print-questionnaire');
  if (!btn) return;

  btn.hidden = false;
  btn.addEventListener('click', function () {
    window.print();
  });
})();
