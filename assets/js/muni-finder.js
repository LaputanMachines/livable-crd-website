// "Find your municipality" address lookup on the homepage.
//
// Type a street address, and the one municipality it is in stays lit while the
// other fifteen go dim and stop being links. This exists because the boundaries
// are not where people think they are: 3400 Douglas St is addressed "Victoria"
// and votes in Saanich, and a reader who opens the wrong index is reading a
// ballot they cannot cast.
//
// The address goes to the Province of B.C.'s public address geocoder
// (geocoder.api.gov.bc.ca), which is free, keyless, CORS-enabled and the
// authority on B.C. civic addresses. Nothing is stored: this is a static site
// with no server of its own, and the request goes from the reader's browser
// straight to the Province. An API key would raise the anonymous rate limit if
// this ever needs one; it is deliberately not wired up.
//
// The form ships `hidden` in index.md and is revealed here, the same
// progressive-enhancement contract as the questionnaire search and the
// favourite stars: with no JS the reader still gets the full list of links,
// which is the thing this only narrows.
(function () {
  var form = document.getElementById('muni-finder');
  var list = document.getElementById('muni-index');
  if (!form || !list) return;

  var input = document.getElementById('muni-finder-input');
  var status = form.querySelector('.muni-finder__status');
  var submit = form.querySelector('.muni-finder__submit');
  if (!input || !status || !submit) return;
  if (typeof window.fetch !== 'function') return;

  var ENDPOINT = 'https://geocoder.api.gov.bc.ca/addresses.json';

  // The geocoder always answers. Ask it for a Toronto street and it returns its
  // closest B.C. guess with a score in the forties, so a floor is what separates
  // "you are in Colwood" from "we found something, somewhere". 60 sits above
  // every junk match seen in testing and below a street-level match on a real
  // address (a bare street with no civic number scores 77).
  var MIN_SCORE = 60;

  // The Capital Regional District's own prefix in the geocoder's electoralArea
  // field, e.g. "CAPRD Juan de Fuca Electoral Area". Addresses in the three
  // electoral areas come back with a locality that is a community name (Shirley,
  // Mayne Island) rather than anything on our list, so the electoral area is the
  // field that answers for them.
  var CRD_PREFIX = 'CAPRD ';

  // Strip to letters and digits, which is the entire alias table. The geocoder
  // writes "Saltspring Island" where this site writes "Salt Spring Island", and
  // it has already resolved the harder aliases itself before answering:
  // "Saanichton" comes back as Central Saanich, "Brentwood Bay" likewise.
  function key(value) {
    return String(value == null ? '' : value).toLowerCase().replace(/[^a-z0-9]/g, '');
  }

  var items = [];
  var byKey = {};
  var nodes = list.querySelectorAll('.muni-index__item');
  for (var i = 0; i < nodes.length; i++) {
    var li = nodes[i];
    items.push(li);
    var k = key(li.getAttribute('data-muni-name'));
    if (k) byKey[k] = li;
  }
  if (!items.length) return;

  // Added to the markup here rather than in index.md so a reader without JS is
  // never shown a button that clears a filter nothing applied.
  var reset = document.createElement('button');
  reset.type = 'button';
  reset.className = 'btn muni-finder__reset';
  reset.textContent = 'Clear';
  reset.hidden = true;
  form.querySelector('.muni-finder__row').appendChild(reset);

  function setFiltered(match) {
    list.classList.add('muni-index--filtered');
    for (var i = 0; i < items.length; i++) {
      var li = items[i];
      var on = li === match;
      var link = li.querySelector('.muni-index__link');
      if (on) li.classList.add('muni-index__item--match');
      else li.classList.remove('muni-index__item--match');
      if (!link) continue;
      // CSS drops pointer events on the dimmed ones; aria-disabled and the
      // removal from the tab order are what make that true for a keyboard or a
      // screen reader too, which the opacity alone is not.
      if (on) {
        link.removeAttribute('aria-disabled');
        link.removeAttribute('tabindex');
      } else {
        link.setAttribute('aria-disabled', 'true');
        link.setAttribute('tabindex', '-1');
      }
    }
    reset.hidden = false;
    if (match && match.scrollIntoView) match.scrollIntoView({ block: 'nearest' });
  }

  function clearFilter() {
    list.classList.remove('muni-index--filtered');
    for (var i = 0; i < items.length; i++) {
      items[i].classList.remove('muni-index__item--match');
      var link = items[i].querySelector('.muni-index__link');
      if (!link) continue;
      link.removeAttribute('aria-disabled');
      link.removeAttribute('tabindex');
    }
    reset.hidden = true;
  }

  function say(message, kind) {
    status.textContent = message || '';
    status.className = 'muni-finder__status' + (kind ? ' muni-finder__status--' + kind : '');
  }

  // Resolve the geocoder's answer to one of our list items, or to null.
  // Electoral area first: for Shirley or Mayne Island the locality is a
  // community and only the electoral area names something we publish.
  function resolve(props) {
    var area = String(props.electoralArea || '');
    if (area.indexOf(CRD_PREFIX) === 0) {
      var name = area.slice(CRD_PREFIX.length).replace(/\s*Electoral Area\s*$/i, '');
      var hit = byKey[key(name)];
      if (hit) return hit;
    }
    return byKey[key(props.localityName)] || null;
  }

  // Only the newest request may write to the page. Someone who searches, edits
  // and searches again should not have the slower first answer land on top of
  // the second.
  var latest = 0;

  function lookup(query) {
    var ticket = ++latest;
    var url = ENDPOINT +
      '?addressString=' + encodeURIComponent(query + ', BC') +
      '&maxResults=1&outputSRS=4326&locationDescriptor=any';

    submit.disabled = true;
    say('Looking up that address…');

    fetch(url, { headers: { Accept: 'application/json' } })
      .then(function (response) {
        if (!response.ok) throw new Error('HTTP ' + response.status);
        return response.json();
      })
      .then(function (data) {
        if (ticket !== latest) return;
        var features = (data && data.features) || [];
        if (!features.length) {
          clearFilter();
          say('No address matched that. Try a street number and a city.', 'warn');
          return;
        }
        var props = features[0].properties || {};
        if (typeof props.score === 'number' && props.score < MIN_SCORE) {
          clearFilter();
          say('No confident match for that address. Try a street number and a city.', 'warn');
          return;
        }
        var match = resolve(props);
        if (!match) {
          clearFilter();
          var place = props.localityName || 'that address';
          say(place + ' is outside the Capital Regional District, so it is not on this list.', 'warn');
          return;
        }
        setFiltered(match);
        say(
          (props.fullAddress || query) + ' is in ' +
          match.getAttribute('data-muni-name') + '.',
          'ok'
        );
      })
      .catch(function () {
        if (ticket !== latest) return;
        clearFilter();
        say('The address lookup is unavailable right now. Pick your municipality from the list below.', 'warn');
      })
      .then(function () {
        if (ticket === latest) submit.disabled = false;
      });
  }

  form.addEventListener('submit', function (event) {
    event.preventDefault();
    var query = input.value.replace(/\s+/g, ' ').trim();
    if (!query) {
      latest++;
      clearFilter();
      say('');
      return;
    }
    lookup(query);
  });

  reset.addEventListener('click', function () {
    latest++;
    submit.disabled = false;
    clearFilter();
    say('');
    input.value = '';
    input.focus();
  });

  // Emptying the box (the native clear "x" on a search input fires this) puts
  // the whole list back rather than leaving a stale municipality lit next to an
  // empty field.
  input.addEventListener('input', function () {
    if (input.value.trim() !== '') return;
    latest++;
    clearFilter();
    say('');
  });

  form.hidden = false;
})();
