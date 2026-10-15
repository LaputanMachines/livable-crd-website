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

  // New Songhees 1A, the Songhees Nation reserve between Craigflower and
  // Admirals roads. A reserve is in no municipality, and its residents vote in
  // Esquimalt, but the geocoder answers "View Royal" for its addresses. They are
  // not in its address database, so it interpolates a point on the road and
  // takes the locality of that side of the street, and the odd side of
  // Craigflower Rd is labelled View Royal. A reader at 1445 Craigflower Rd
  // followed that to the View Royal polls and was sent on to Esquimalt.
  //
  // So a point inside the reserve is answered Esquimalt whatever the locality
  // says. SETBACK is what makes that test work: an interpolated point sits on
  // the road's centreline, a few metres outside the reserve boundary, and
  // asking the geocoder to move it 15 m off the street puts it on the side the
  // civic number is on, which is inside the reserve for the odd side and well
  // outside it for the Esquimalt houses opposite. It does not move a point
  // matched to an actual parcel.
  //
  // Rings are [longitude, latitude], from the Province's Indian Reserves
  // boundary layer (WHSE_ADMIN_BOUNDARIES.ADM_INDIAN_RESERVES_BANDS_SP,
  // CLAB_ID 06839) simplified to within 1 m. The reserve has three parts and no
  // holes.
  var SETBACK = 15;
  var RESERVE_MUNI = 'Esquimalt';
  var NEW_SONGHEES_1A = [
    [
      [-123.416895, 48.448101], [-123.417373, 48.448231], [-123.418489, 48.448337],
      [-123.419043, 48.448486], [-123.419457, 48.448686], [-123.420731, 48.449640],
      [-123.422495, 48.449998], [-123.423733, 48.450382], [-123.424717, 48.450903],
      [-123.425732, 48.449655], [-123.425972, 48.449243], [-123.426087, 48.448776],
      [-123.426238, 48.446961], [-123.426703, 48.446144], [-123.426737, 48.444394],
      [-123.426788, 48.441711], [-123.427570, 48.441717], [-123.427014, 48.441321],
      [-123.412577, 48.446587], [-123.414593, 48.447474], [-123.416895, 48.448101]
    ],
    [
      [-123.428461, 48.440793], [-123.427260, 48.441231], [-123.427945, 48.441720],
      [-123.429249, 48.441730], [-123.429387, 48.441201], [-123.429405, 48.440843],
      [-123.429335, 48.440474], [-123.428461, 48.440793]
    ],
    [
      [-123.433336, 48.441885], [-123.433596, 48.442005], [-123.433796, 48.442217],
      [-123.433849, 48.442333], [-123.433937, 48.442436], [-123.433936, 48.442517],
      [-123.433866, 48.442591], [-123.433871, 48.442677], [-123.433968, 48.442767],
      [-123.434049, 48.442709], [-123.434300, 48.442667], [-123.434503, 48.442556],
      [-123.434541, 48.442416], [-123.434690, 48.442274], [-123.434758, 48.442269],
      [-123.434877, 48.442217], [-123.435208, 48.442145], [-123.435294, 48.442101],
      [-123.435434, 48.442077], [-123.435879, 48.441805], [-123.435880, 48.441745],
      [-123.435990, 48.441673], [-123.436087, 48.441564], [-123.436220, 48.441536],
      [-123.436448, 48.441603], [-123.436619, 48.441609], [-123.436712, 48.441528],
      [-123.436827, 48.441390], [-123.436818, 48.441292], [-123.436850, 48.441218],
      [-123.436819, 48.441207], [-123.436799, 48.441104], [-123.436562, 48.441057],
      [-123.436487, 48.441004], [-123.436475, 48.440619], [-123.436304, 48.440512],
      [-123.436161, 48.440502], [-123.436106, 48.440464], [-123.435470, 48.440409],
      [-123.435267, 48.440492], [-123.435067, 48.440521], [-123.434952, 48.440567],
      [-123.434899, 48.440614], [-123.434815, 48.440643], [-123.434722, 48.440720],
      [-123.434644, 48.440828], [-123.434615, 48.440935], [-123.434523, 48.440908],
      [-123.434473, 48.440947], [-123.434264, 48.440961], [-123.434019, 48.440891],
      [-123.432671, 48.440210], [-123.432276, 48.439914], [-123.432170, 48.439867],
      [-123.432131, 48.439757], [-123.432002, 48.439635], [-123.431927, 48.439583],
      [-123.431845, 48.439557], [-123.429524, 48.440405], [-123.429607, 48.440796],
      [-123.429613, 48.440999], [-123.429594, 48.441202], [-123.429459, 48.441731],
      [-123.432032, 48.441751], [-123.432028, 48.441895], [-123.432141, 48.441904],
      [-123.432572, 48.441822], [-123.432772, 48.441850], [-123.432856, 48.441894],
      [-123.433030, 48.441867], [-123.433336, 48.441885]
    ]
  ];

  // Even-odd ray cast. At this scale longitude and latitude can be treated as
  // flat coordinates without any error that matters.
  function inRing(x, y, ring) {
    var inside = false;
    for (var i = 0, j = ring.length - 1; i < ring.length; j = i++) {
      var xi = ring[i][0], yi = ring[i][1], xj = ring[j][0], yj = ring[j][1];
      if ((yi > y) !== (yj > y) && x < (xj - xi) * (y - yi) / (yj - yi) + xi) inside = !inside;
    }
    return inside;
  }

  function onReserve(coords) {
    if (!coords || typeof coords[0] !== 'number' || typeof coords[1] !== 'number') return false;
    for (var i = 0; i < NEW_SONGHEES_1A.length; i++) {
      if (inRing(coords[0], coords[1], NEW_SONGHEES_1A[i])) return true;
    }
    return false;
  }

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

  // `extra`, when given, is a node appended after the message inside the live
  // region, so it is announced with the answer rather than after it.
  function say(message, kind, extra) {
    status.textContent = message || '';
    status.className = 'muni-finder__status' + (kind ? ' muni-finder__status--' + kind : '');
    if (extra) status.appendChild(extra);
  }

  // The answer for a reserve address is our reading of a boundary, not a record
  // the Province holds, so it says so and points to the municipality's own
  // election office. The Nation is named and the answer is put as what we
  // understand, not as fact: a site that has just sent someone to the wrong
  // polling station has not earned more confidence than that.
  function reserveCaveat(match) {
    var caveat = document.createElement('span');
    caveat.className = 'muni-finder__caveat';
    var name = match.getAttribute('data-muni-name');
    var href = match.getAttribute('data-elections-url');
    caveat.appendChild(document.createTextNode(
      'The Province\'s address lookup does not list addresses on reserve land, so ' +
      'this answer comes from our own reading of the reserve boundary, and we may ' +
      'have it wrong. Before you vote, please confirm with '
    ));
    if (href) {
      var link = document.createElement('a');
      link.href = href;
      link.target = '_blank';
      link.rel = 'noopener';
      link.textContent = name + '\'s election office';
      caveat.appendChild(link);
    } else {
      caveat.appendChild(document.createTextNode(name + '\'s election office'));
    }
    caveat.appendChild(document.createTextNode('.'));
    return caveat;
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
      '&maxResults=1&outputSRS=4326&locationDescriptor=any&setBack=' + SETBACK;

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
        var geometry = features[0].geometry || {};
        var reserve = onReserve(geometry.coordinates);
        var match = reserve ? byKey[key(RESERVE_MUNI)] : resolve(props);
        if (!match) {
          clearFilter();
          var place = props.localityName || 'that address';
          say(place + ' is outside the Capital Regional District, so it is not on this list.', 'warn');
          return;
        }
        setFiltered(match);
        // Not fullAddress on the reserve: it ends "View Royal, BC", and saying
        // that address is in Esquimalt would read as a contradiction.
        if (reserve) {
          say(
            'That address is on New Songhees 1A, a Songhees Nation reserve. ' +
            'We understand residents there vote in ' + match.getAttribute('data-muni-name') + '.',
            'ok',
            reserveCaveat(match)
          );
          return;
        }
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
