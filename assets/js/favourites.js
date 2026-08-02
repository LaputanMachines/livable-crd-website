// Scorecard favourites: pin candidates to a group above every municipality,
// put them in whatever order the reader wants, and remember both for next time.
//
// Progressive enhancement, the same contract as scorecard.js: the toggle
// buttons ship `hidden` and the pinned group ships `hidden`, so with JS off the
// matrix reads exactly as it did before this feature existed. Rows are MOVED
// into the pinned group, never copied — a copy would be counted twice by
// #candidate-count and filtered twice by scorecard.js.
(function () {
  // ---------------------------------------------------------------------------
  // Pure helpers — no DOM, no storage.
  //
  // This repo has no test framework, no npm, and no browser that can be driven
  // here, so the list arithmetic (ordering, pruning, where an unpinned row goes
  // back to) is deliberately separated from the DOM work below: it is the part
  // that can still be exercised directly in node. See the export seam at the
  // end of this section.
  // ---------------------------------------------------------------------------

  // Candidate keys always contain a "/", so they can never collide with a name
  // on Object.prototype — but a plain `map[key]` truth test would still be a
  // trap for whoever changes the key format later.
  function has(map, key) {
    return Object.prototype.hasOwnProperty.call(map, key);
  }

  // Stored value → array of keys. Anything unexpected (a hand-edited value, a
  // truncated write, a format from a future version) reads as "no favourites"
  // rather than throwing on a page the reader is trying to use.
  function parseKeys(raw) {
    if (!raw) return [];
    var parsed;
    try {
      parsed = JSON.parse(raw);
    } catch (e) {
      return [];
    }
    return Object.prototype.toString.call(parsed) === '[object Array]' ? parsed : [];
  }

  // Storage holds keys that were valid when they were written. Candidates come
  // and go from the tracking sheet between visits, so drop every key with no row
  // on this page — and any duplicate, which would otherwise try to place the
  // same row in two slots. `known` is a map of the keys that do exist.
  function pruneKeys(keys, known) {
    var out = [];
    var seen = {};
    if (!keys) return out;
    for (var i = 0; i < keys.length; i++) {
      var key = keys[i];
      if (typeof key !== 'string') continue;
      if (!has(known, key)) continue;
      if (has(seen, key)) continue;
      seen[key] = true;
      out.push(key);
    }
    return out;
  }

  // New favourites land at the bottom. Adding at the top would silently
  // renumber a list the reader may have arranged by hand, which is the one
  // thing a manual order must never do.
  function withKey(keys, key) {
    if (keys.indexOf(key) !== -1) return keys.slice();
    return keys.concat([key]);
  }

  function withoutKey(keys, key) {
    return keys.filter(function (k) { return k !== key; });
  }

  // Move `key` to `index`, where `index` counts positions in the list *after*
  // the key has been lifted out of it — the same frame of reference both callers
  // (arrow keys, drop target) naturally work in. Out-of-range indexes clamp to
  // the ends, so a move off either boundary is a no-op the caller can detect by
  // comparing indexOf() before and after.
  function moveKeyTo(keys, key, index) {
    var out = keys.slice();
    var from = out.indexOf(key);
    if (from === -1) return out;
    out.splice(from, 1);
    var to = Math.max(0, Math.min(index, out.length));
    out.splice(to, 0, key);
    return out;
  }

  // Where a row goes when it stops being a favourite: back into its own
  // municipality group, in the exact slot it started in — not appended to the
  // end of it. `homeIndex` maps every key to its original position among its
  // group's rows, captured before anything moved. `presentKeys` is what is left
  // in that group right now, since the reader's other favourites are elsewhere
  // in the table and cannot be used as insertion references.
  //
  // Returns the key to insert before, or null to append.
  function restoreBefore(presentKeys, homeIndex, key) {
    var home = homeIndex[key];
    for (var i = 0; i < presentKeys.length; i++) {
      var other = presentKeys[i];
      if (other !== key && homeIndex[other] > home) return other;
    }
    return null;
  }

  // Node has no `document`. When this file is loaded there — by a throwaway
  // script checking the helpers above — hand them over and stop before the DOM
  // work starts. In a browser `module` is undefined, so this costs one guard.
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
      parseKeys: parseKeys,
      pruneKeys: pruneKeys,
      withKey: withKey,
      withoutKey: withoutKey,
      moveKeyTo: moveKeyTo,
      restoreBefore: restoreBefore
    };
    return;
  }

  // ---------------------------------------------------------------------------
  // Storage
  //
  // The feature was specced as "cookie-based". It is localStorage instead. This
  // is a static site on GitHub Pages: there is no server that could ever read a
  // cookie, so one would only add its own bytes to every request for every page
  // and asset, inside a ~4KB cap, for nothing. localStorage has the same scope
  // (this browser, this origin), the same lifetime, and is never transmitted.
  //
  // If that ever has to change, readKeys/writeKeys are the only two functions in
  // the file that know where the list lives — nothing else touches storage.
  // ---------------------------------------------------------------------------

  // Versioned: a future format change can then be ignored by this reader
  // instead of being mis-parsed into a wrong order.
  var STORAGE_KEY = 'livable-crd:favourites:v1';

  // Safari in private mode throws on any localStorage access, as does a browser
  // with site data blocked. Falling back to a variable keeps the feature working
  // for the length of the visit instead of taking the page down with it.
  var memory = null;

  function readKeys() {
    try {
      return parseKeys(window.localStorage.getItem(STORAGE_KEY));
    } catch (e) {
      return parseKeys(memory);
    }
  }

  function writeKeys(keys) {
    var raw = JSON.stringify(keys);
    memory = raw;
    try {
      window.localStorage.setItem(STORAGE_KEY, raw);
    } catch (e) {
      // Nothing to do and nothing to tell the reader: the list still works,
      // it just will not outlive the tab.
    }
  }

  // ---------------------------------------------------------------------------
  // DOM
  // ---------------------------------------------------------------------------

  var table = document.getElementById('candidate-grid');
  var favGroup = document.getElementById('favourites-group');
  if (!table || !favGroup) return;

  var status = document.getElementById('favourites-status');
  var hint = document.getElementById('favourites-hint');

  var entries = [];   // one record per candidate row, in document order
  var byKey = {};     // key → record
  var homeIndex = {}; // key → the row's original position within its own group
  var order = [];     // favourite keys, in the reader's chosen order

  function rowsIn(container) {
    return Array.prototype.slice.call(container.querySelectorAll('.scorecard-row'));
  }

  function keysOf(rows) {
    return rows.map(function (row) { return row.getAttribute('data-candidate'); });
  }

  // Walk group by group rather than row by row: a row's home position is only
  // meaningful relative to its own municipality, and this runs before anything
  // has moved, which is the only moment those positions are true.
  Array.prototype.slice.call(table.querySelectorAll('.scorecard-matrix__group')).forEach(function (group) {
    if (group === favGroup) return;
    rowsIn(group).forEach(function (row, position) {
      var key = row.getAttribute('data-candidate');
      var star = row.querySelector('.fav-toggle');
      var name = row.querySelector('.scorecard-matrix__cand');
      // A row with no key, no button, or a key some other row already claimed
      // (the page generator warns about that case too) cannot be pinned and
      // unpinned unambiguously. Skipping leaves it an ordinary, working row.
      if (!key || !star || has(byKey, key)) return;
      var entry = {
        key: key,
        row: row,
        group: group,
        star: star,
        handle: null, // built on first pin, see ensureHandle()
        name: name ? name.textContent.trim() : key
      };
      homeIndex[key] = position;
      byKey[key] = entry;
      entries.push(entry);
    });
  });

  if (!entries.length) return;

  // Keys for candidates who have since left the sheet are dropped here and
  // written back out the next time the reader changes anything (writeKeys always
  // persists this pruned array). Pruning on read alone, with an immediate write,
  // would mean a storage write on every single page view for no benefit.
  order = pruneKeys(readKeys(), byKey);

  // --- The seam with scorecard.js -------------------------------------------
  // Row and group visibility belong entirely to the filter script, which
  // recomputes both from the DOM every time it runs — including for the pinned
  // group, which it treats as an ordinary candidate group and hides whenever
  // nothing inside it is visible. So after moving a row all this has to do is
  // ask for another pass. One-way on purpose: that script knows nothing about
  // favourites, and this one knows nothing about filters.
  function refilter() {
    var event;
    try {
      event = new CustomEvent('scorecard:refilter');
    } catch (e) {
      // Older engines cannot construct events.
      event = document.createEvent('CustomEvent');
      event.initCustomEvent('scorecard:refilter', false, false, null);
    }
    table.dispatchEvent(event);
  }

  function announce(message) {
    if (status) status.textContent = message;
  }

  function isFavourite(key) {
    return order.indexOf(key) !== -1;
  }

  // The reorder handle only exists for as long as it is useful, which is why it
  // is built here rather than shipped in the markup 66 times: outside the pinned
  // group there is nothing to reorder, and 66 spare buttons would be 66 extra
  // stops for anyone tabbing through the table.
  function ensureHandle(entry) {
    if (entry.handle) return entry.handle;

    var handle = document.createElement('button');
    handle.type = 'button';
    handle.className = 'fav-handle';
    // Names the row, nothing more. What the handle *does* — drag, or arrow keys
    // — is stated once in the group heading and pulled in as the description,
    // rather than repeated inside every label the reader tabs past.
    handle.setAttribute('aria-label', 'Reorder ' + entry.name);
    if (hint && hint.id) handle.setAttribute('aria-describedby', hint.id);
    handle.title = 'Drag to reorder, or use the up and down arrow keys';

    // Grip glyph as real content rather than a CSS ::before: an identical-to
    // sign is the only widely-drawn grip character in this font stack, and
    // generated content can be read out by some screen readers, which the
    // aria-label above is there to prevent.
    var glyph = document.createElement('span');
    glyph.setAttribute('aria-hidden', 'true');
    glyph.textContent = '≡';
    handle.appendChild(glyph);

    handle.addEventListener('pointerdown', function (e) { onHandleDown(entry, e); });
    handle.addEventListener('pointermove', function (e) { onHandleMove(entry, e); });
    handle.addEventListener('pointerup', function (e) { onHandleUp(entry, e); });
    handle.addEventListener('pointercancel', function () { cancelDrag(); });
    // Capture can be taken away (a browser gesture, the element being moved),
    // and losing it silently mid-drag would leave the indicator painted on.
    handle.addEventListener('lostpointercapture', function () { cancelDrag(); });
    handle.addEventListener('keydown', function (e) { onHandleKey(entry, e); });

    entry.star.parentNode.insertBefore(handle, entry.star.nextSibling);
    entry.handle = handle;
    return handle;
  }

  function syncControls(entry) {
    var on = isFavourite(entry.key);
    entry.star.hidden = false;
    entry.star.setAttribute('aria-pressed', on ? 'true' : 'false');
    entry.star.title = on
      ? 'Remove ' + entry.name + ' from your favourites'
      : 'Add ' + entry.name + ' to your favourites';
    if (on) ensureHandle(entry);
    // Hidden rather than removed: `hidden` is enough to take it out of the tab
    // order, and keeping the node means re-pinning does not rebuild it.
    if (entry.handle) entry.handle.hidden = !on;
  }

  function restoreHome(entry) {
    var siblings = rowsIn(entry.group);
    var before = restoreBefore(keysOf(siblings), homeIndex, entry.key);
    entry.group.insertBefore(entry.row, before ? byKey[before].row : null);
  }

  // Single place that touches the table: `order` is changed first, then this
  // makes the DOM say the same thing.
  function render() {
    // Anything sitting in the pinned group that is no longer a favourite goes
    // home first, so the loop below only has to place what belongs here.
    rowsIn(favGroup).forEach(function (row) {
      var key = row.getAttribute('data-candidate');
      if (has(byKey, key) && !isFavourite(key)) restoreHome(byKey[key]);
    });

    // Place each favourite in `order` sequence. insertBefore() on a node that is
    // already in the right slot still detaches and re-inserts it, which blurs
    // whatever inside it had focus — so compare first and only move what has to
    // move. The live list is re-read after each move because the move changes it.
    var live = rowsIn(favGroup);
    for (var i = 0; i < order.length; i++) {
      var row = byKey[order[i]].row;
      if (live[i] !== row) {
        favGroup.insertBefore(row, live[i] || null);
        live = rowsIn(favGroup);
      }
    }

    entries.forEach(syncControls);

    // Set this here rather than leaving it to the filter pass below: if
    // scorecard.js ever fails to load, rows moved into a `hidden` tbody would
    // disappear from the page altogether. refilter() then refines it — the group
    // hides again when a search or filter leaves nothing visible inside it.
    favGroup.hidden = order.length === 0;
    refilter();
  }

  function toggle(entry) {
    var on = !isFavourite(entry.key);
    order = on ? withKey(order, entry.key) : withoutKey(order, entry.key);
    writeKeys(order);
    render();
    announce(on
      ? entry.name + ' pinned to favourites, position ' + (order.indexOf(entry.key) + 1) + ' of ' + order.length + '.'
      : entry.name + ' removed from favourites.');
  }

  // `index` is a position in the list with this key lifted out of it — see
  // moveKeyTo(). Everything that reorders goes through here so that storage,
  // focus and the announcement are handled in exactly one place.
  function moveTo(entry, index) {
    var from = order.indexOf(entry.key);
    if (from === -1) return;

    var next = moveKeyTo(order, entry.key, index);
    var to = next.indexOf(entry.key);
    if (to === from) {
      // Silence would read as a broken key, so say why nothing happened —
      // naming the boundary when that is the reason, since "already first" is
      // the answer to "why did my arrow key do nothing".
      if (from === 0) {
        announce(entry.name + ' is already first in your favourites.');
      } else if (from === order.length - 1) {
        announce(entry.name + ' is already last in your favourites.');
      } else {
        announce(entry.name + ' stayed at position ' + (from + 1) + ' of ' + order.length + '.');
      }
      return;
    }

    // The row is detached and re-inserted by render(), and a focused element
    // inside a detached node loses focus — which would strand a keyboard user
    // at the top of the document mid-reorder.
    var refocus = entry.handle && document.activeElement === entry.handle;
    order = next;
    writeKeys(order);
    render();
    if (refocus) entry.handle.focus();
    announce(entry.name + ' moved to position ' + (to + 1) + ' of ' + order.length + '.');
  }

  // --- Dragging --------------------------------------------------------------
  // Pointer Events, no library, and deliberately no dragged-row preview. A table
  // row is `display: table-row`: it cannot be lifted, transformed or floated
  // without leaving the table's box model, at which point its cells stop
  // tracking the column widths and the whole grid twitches on every move. So
  // nothing moves during the drag. The dragged row is dimmed, a line is drawn at
  // the place it would land, and the actual reorder happens once on release —
  // robust at any column width, and identical on touch, mouse and pen.
  var drag = null;
  var DRAG_THRESHOLD = 4; // px of travel before a press counts as a drag

  function favRowsForDrop() {
    // Hidden rows are hidden by a filter the reader has set. They keep their
    // place in `order`, but they cannot be dropped against something invisible.
    return rowsIn(favGroup).filter(function (row) { return !row.hidden; });
  }

  function clearIndicator() {
    rowsIn(favGroup).forEach(function (row) {
      row.classList.remove('is-fav-drop-before');
      row.classList.remove('is-fav-drop-after');
    });
  }

  // The row the dragged one would land in front of, or null for "past the end".
  function dropTarget(clientY, dragged) {
    var rows = favRowsForDrop();
    for (var i = 0; i < rows.length; i++) {
      if (rows[i] === dragged) continue;
      var rect = rows[i].getBoundingClientRect();
      if (clientY < rect.top + rect.height / 2) return rows[i];
    }
    return null;
  }

  function endDrag() {
    if (!drag) return;
    var entry = drag.entry;
    try {
      if (entry.handle.hasPointerCapture(drag.pointerId)) {
        entry.handle.releasePointerCapture(drag.pointerId);
      }
    } catch (e) {}
    entry.row.classList.remove('is-fav-dragging');
    favGroup.classList.remove('is-fav-reordering');
    clearIndicator();
    drag = null;
  }

  function cancelDrag() {
    if (!drag) return;
    var name = drag.entry.name;
    endDrag();
    announce('Reordering cancelled. ' + name + ' stayed where it was.');
  }

  function onHandleDown(entry, e) {
    if (drag || !isFavourite(entry.key)) return;
    if (e.button > 0) return; // right- and middle-click are not drags
    drag = { entry: entry, pointerId: e.pointerId, startY: e.clientY, moved: false, before: null };
    entry.row.classList.add('is-fav-dragging');
    favGroup.classList.add('is-fav-reordering');
    try { entry.handle.setPointerCapture(e.pointerId); } catch (err) {}
    // Stops the browser starting a text selection or its own native drag, both
    // of which fight the pointer capture for the rest of the gesture.
    e.preventDefault();
    // preventDefault() also suppresses the focus a mousedown would normally
    // give a button, so take it deliberately: it is what lets someone start
    // with the mouse and finish with the arrow keys, and it is what keeps
    // focus on this row after the drop.
    entry.handle.focus();
  }

  function onHandleMove(entry, e) {
    if (!drag || drag.entry !== entry || e.pointerId !== drag.pointerId) return;
    // A press that never travels is a click, not a drag — a touch in
    // particular reports a few pixels of jitter just from the finger settling.
    // Below the threshold nothing is marked, and pointerup does nothing at all.
    if (!drag.moved && Math.abs(e.clientY - drag.startY) < DRAG_THRESHOLD) return;
    drag.moved = true;

    var target = dropTarget(e.clientY, entry.row);
    drag.before = target;
    clearIndicator();
    if (target) {
      target.classList.add('is-fav-drop-before');
    } else {
      // Past the last row: mark the bottom edge of whatever that row is.
      var rows = favRowsForDrop().filter(function (row) { return row !== entry.row; });
      if (rows.length) rows[rows.length - 1].classList.add('is-fav-drop-after');
    }
  }

  function onHandleUp(entry, e) {
    if (!drag || drag.entry !== entry || e.pointerId !== drag.pointerId) return;
    if (!drag.moved) {
      // A click, not a drag. pointerdown already put focus on the handle, which
      // is exactly the state the arrow keys need, so leave the order alone.
      endDrag();
      return;
    }
    var before = drag.before;
    var visible = favRowsForDrop().filter(function (row) { return row !== entry.row; });
    endDrag();

    // Map the dropped-on row back to a position in `order`. Working through the
    // neighbours' keys rather than through screen positions is what keeps this
    // correct while a filter is hiding some of the favourites: rows nobody can
    // see keep their place relative to the row they are pinned next to.
    var rest = withoutKey(order, entry.key);
    var index;
    if (before) {
      index = rest.indexOf(before.getAttribute('data-candidate'));
    } else if (visible.length) {
      index = rest.indexOf(visible[visible.length - 1].getAttribute('data-candidate')) + 1;
    } else {
      index = rest.length;
    }
    if (index < 0) index = rest.length;
    moveTo(entry, index);
  }

  function onHandleKey(entry, e) {
    if (e.altKey || e.ctrlKey || e.metaKey) return;
    var key = e.key;
    var from = order.indexOf(entry.key);
    if (from === -1) return;

    if (key === 'Escape' && drag) {
      e.preventDefault();
      cancelDrag();
      return;
    }
    // Arrow keys scroll the page by default, which would drag the reader away
    // from the row they are moving.
    if (key === 'ArrowUp' || key === 'Up') {
      e.preventDefault();
      moveTo(entry, from - 1);
    } else if (key === 'ArrowDown' || key === 'Down') {
      e.preventDefault();
      moveTo(entry, from + 1);
    } else if (key === 'Home') {
      e.preventDefault();
      moveTo(entry, 0);
    } else if (key === 'End') {
      e.preventDefault();
      moveTo(entry, order.length);
    }
  }

  // --- Wiring ----------------------------------------------------------------

  entries.forEach(function (entry) {
    entry.star.addEventListener('click', function () { toggle(entry); });
  });

  render();
})();
