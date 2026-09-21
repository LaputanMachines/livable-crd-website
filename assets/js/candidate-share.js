// "Share to Facebook / Instagram / X" on a candidate's page: draws a square
// card of that candidate's grades and hands it to the platform the reader
// chose.
//
// The card is drawn in a canvas from the page's own rows — the name, the
// standing line, the slate, every topic with its chip and that chip's colour
// read off the live element — so it cannot show a grade the page does not. The
// alternative was an image per candidate generated at build time, which is 210
// files regenerated nightly against a sheet that changes under them.
//
// What each platform actually accepts is the whole shape of this file:
//
//   - None of the three takes an image from a web link. Facebook's sharer and
//     X's intent take a URL and show whatever that page's og:image is; Instagram
//     takes nothing at all, and has no addressable compose step either, so the
//     most a link can do there is open Instagram.
//   - Where the operating system has a share sheet that takes files
//     (navigator.share with `files`, which is most phones), the card goes
//     straight into it and the reader picks the app. That is the good path, and
//     the only one that reaches Instagram without a detour.
//   - Everywhere else the card is downloaded and the platform's composer opened,
//     for the reader to attach it. Said plainly in the status line rather than
//     left to be discovered.
//
// Nothing is uploaded and no platform SDK is loaded: no pixel, no tracking, and
// which candidate a reader was looking at does not leave the browser until they
// post it.
(function () {
  var buttons = Array.prototype.slice.call(document.querySelectorAll('[data-share]'));
  if (!buttons.length) return;

  var script = document.currentScript || document.querySelector('script[data-candidate]');
  var status = document.getElementById('share-status');
  var hero = document.querySelector('.candidate-hero');
  var rows = Array.prototype.slice.call(document.querySelectorAll('.candidate-grade-row'));
  if (!script || !hero || !rows.length) return;

  var candidate = script.getAttribute('data-candidate') || '';
  var municipality = script.getAttribute('data-municipality') || '';
  var pageUrl = script.getAttribute('data-url') || window.location.href;

  // Everything below is written against a 1080 square and drawn at that size.
  // Square rather than a per-platform aspect: 1080 is Instagram's own feed size,
  // Facebook shows it whole, and X crops it in the timeline to something that
  // still opens full. Three layouts for three crops would be three layouts to
  // keep true to the page.
  var SIZE = 1080;
  var PAD = 64;
  var INK = '#220940';
  var ACCENT = '#5c18a4';
  var MUTED = '#564a66';
  var KWETLAL = '#d5adff';
  var RULE = '#e7e0f2';

  function text(el) {
    return el ? el.textContent.replace(/\s+/g, ' ').trim() : '';
  }

  // The rows as the page has them: topic name, what its chip says, and the
  // chip's own colours. Reading the colours rather than restating the palette
  // means a grade recoloured in _variables.scss is recoloured here too.
  function readRows() {
    return rows.map(function (row) {
      var chip = row.querySelector('.grade');
      var style = chip ? window.getComputedStyle(chip) : null;
      var svg = chip ? chip.querySelector('svg') : null;
      return {
        name: text(row.querySelector('.candidate-grade__name')),
        label: chip ? text(chip) : '',
        state: chip && chip.className.indexOf('grade--answers') > -1 ? 'answers'
          : chip && chip.className.indexOf('grade--review') > -1 ? 'review'
          : chip && chip.className.indexOf('grade--pending') > -1 ? 'pending' : 'grade',
        svg: svg,
        fill: style ? style.backgroundColor : 'transparent',
        colour: style ? style.color : INK,
        border: style ? style.borderTopColor : 'transparent'
      };
    });
  }

  function loadImage(src) {
    return new Promise(function (resolve) {
      var img = new Image();
      img.onload = function () { resolve(img); };
      // A missing or unrenderable image is not worth failing a share over: the
      // card is drawn without it.
      img.onerror = function () { resolve(null); };
      img.src = src;
    });
  }

  // An hourglass or speech bubble chip carries no text, so the glyph itself has
  // to be drawn. Serialized out of the page and rendered as an image, which
  // keeps it the same mark the reader is looking at; `currentColor` inside it
  // resolves against the `color` set on the copy.
  function glyphImage(svg, colour) {
    var copy = svg.cloneNode(true);
    copy.setAttribute('xmlns', 'http://www.w3.org/2000/svg');
    copy.setAttribute('width', '64');
    copy.setAttribute('height', '64');
    copy.style.color = colour;
    var markup = new XMLSerializer().serializeToString(copy);
    return loadImage('data:image/svg+xml;charset=utf-8,' + encodeURIComponent(markup));
  }

  function fitFont(ctx, string, weight, start, min, max) {
    var size = start;
    while (size > min) {
      ctx.font = weight + ' ' + size + 'px Lexend, sans-serif';
      if (ctx.measureText(string).width <= max) break;
      size -= 2;
    }
    return size;
  }

  function roundedRect(ctx, x, y, w, h, r) {
    ctx.beginPath();
    ctx.moveTo(x + r, y);
    ctx.arcTo(x + w, y, x + w, y + h, r);
    ctx.arcTo(x + w, y + h, x, y + h, r);
    ctx.arcTo(x, y + h, x, y, r);
    ctx.arcTo(x, y, x + w, y, r);
    ctx.closePath();
  }

  function drawCard() {
    var canvas = document.createElement('canvas');
    canvas.width = SIZE;
    canvas.height = SIZE;
    var ctx = canvas.getContext('2d');
    var topics = readRows();

    var name = text(hero.querySelector('.candidate-hero__name'));
    var meta = text(hero.querySelector('.candidate-hero__meta'));
    var slateEl = hero.querySelector('.candidate-hero__slate strong');
    var slate = text(slateEl);

    // Lexend is a webfont, and a canvas drawn before it arrives is a canvas
    // drawn in Arial. The glyphs are loaded in the same pass.
    var work = [
      document.fonts ? document.fonts.ready : Promise.resolve(),
      loadImage('/assets/images/brand/logo-mark.svg')
    ];
    topics.forEach(function (topic) {
      work.push(topic.svg ? glyphImage(topic.svg, topic.colour) : Promise.resolve(null));
    });

    return Promise.all(work).then(function (loaded) {
      var mark = loaded[1];
      var glyphs = loaded.slice(2);

      ctx.fillStyle = '#ffffff';
      ctx.fillRect(0, 0, SIZE, SIZE);

      // Masthead, the same two ends as the print leaflet's: who made this, and
      // what it is.
      var bandH = 132;
      ctx.fillStyle = INK;
      ctx.fillRect(0, 0, SIZE, bandH);

      var wordmarkX = PAD;
      if (mark) {
        var markH = 52;
        var markW = markH * (mark.width && mark.height ? mark.width / mark.height : 2.2);
        ctx.drawImage(mark, PAD, (bandH - markH) / 2, markW, markH);
        wordmarkX = PAD + markW + 20;
      }

      ctx.textBaseline = 'middle';
      ctx.fillStyle = '#ffffff';
      ctx.font = '800 40px Lexend, sans-serif';
      ctx.fillText('LIVABLE CRD', wordmarkX, bandH / 2 + 2);

      ctx.textAlign = 'right';
      ctx.fillStyle = KWETLAL;
      ctx.font = '600 24px Lexend, sans-serif';
      ctx.fillText('2026 CANDIDATE SCORECARD', SIZE - PAD, bandH / 2 + 2);
      ctx.textAlign = 'left';

      // The candidate. Shrunk to fit rather than wrapped: two lines of a long
      // name would push the topics off the bottom of a fixed square.
      var y = bandH + 92;
      var nameSize = fitFont(ctx, name.toUpperCase(), '800', 76, 40, SIZE - PAD * 2);
      ctx.fillStyle = INK;
      ctx.font = '800 ' + nameSize + 'px Lexend, sans-serif';
      ctx.fillText(name.toUpperCase(), PAD, y);

      y += 46;
      ctx.fillStyle = ACCENT;
      ctx.font = '600 26px Lexend, sans-serif';
      ctx.fillText(meta.toUpperCase(), PAD, y);

      if (slate) {
        y += 38;
        ctx.fillStyle = MUTED;
        ctx.font = '400 26px Lexend, sans-serif';
        ctx.fillText('Running with ' + slate, PAD, y);
      }

      // The grades. Row height is what is left over, capped so nine rows on a
      // card with no slate line do not stretch into a ladder, and the block is
      // then centred in the space it did not use. A candidate with a slate line
      // gets slightly tighter rows rather than a card that overflows.
      var footerTop = SIZE - 112;
      var rowsTop = y + 44;
      var available = footerTop - rowsTop - 16;
      var rowH = Math.min(78, available / topics.length);
      rowsTop += (available - rowH * topics.length) / 2;
      var chip = Math.min(56, rowH - 14);

      topics.forEach(function (topic, i) {
        var top = rowsTop + i * rowH;
        var mid = top + rowH / 2;

        ctx.strokeStyle = RULE;
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.moveTo(PAD, top);
        ctx.lineTo(SIZE - PAD, top);
        ctx.stroke();

        // Upper-cased, as the page sets them: the card is a picture of those
        // rows, and a reader who has seen one should recognize the other.
        ctx.fillStyle = INK;
        ctx.font = '600 28px Lexend, sans-serif';
        if ('letterSpacing' in ctx) ctx.letterSpacing = '0.04em';
        ctx.textBaseline = 'middle';
        ctx.fillText(topic.name.toUpperCase(), PAD, mid);
        if ('letterSpacing' in ctx) ctx.letterSpacing = '0px';

        var chipX = SIZE - PAD - chip;
        var chipY = mid - chip / 2;
        if (topic.fill && topic.fill !== 'rgba(0, 0, 0, 0)' && topic.fill !== 'transparent') {
          ctx.fillStyle = topic.fill;
          roundedRect(ctx, chipX, chipY, chip, chip, 6);
          ctx.fill();
        } else {
          ctx.strokeStyle = topic.border || RULE;
          ctx.lineWidth = 3;
          roundedRect(ctx, chipX, chipY, chip, chip, 6);
          ctx.stroke();
        }

        var glyph = glyphs[i];
        if (glyph) {
          var inset = chip * 0.26;
          ctx.drawImage(glyph, chipX + inset, chipY + inset, chip - inset * 2, chip - inset * 2);
        } else if (topic.label) {
          ctx.fillStyle = topic.colour;
          ctx.font = '700 ' + (topic.label.length > 2 ? 20 : 28) + 'px Lexend, sans-serif';
          ctx.textAlign = 'center';
          ctx.fillText(topic.label, chipX + chip / 2, mid + 1);
          ctx.textAlign = 'left';
        }
      });

      // Closes the last row: every rule above is drawn on top of its own row, so
      // without this the block ends on a chip with nothing under it.
      ctx.strokeStyle = RULE;
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo(PAD, rowsTop + topics.length * rowH);
      ctx.lineTo(SIZE - PAD, rowsTop + topics.length * rowH);
      ctx.stroke();

      // Where to go for the part a picture cannot carry. What that is depends on
      // whether there is anything to read: a candidate who never replied has no
      // responses to send anybody to, and a card promising some would be the one
      // thing on it that is not true.
      // Something the candidate themselves wrote or ticked, which is narrower
      // than "this page has a .candidate-answer on it": the incumbent record is
      // drawn as one of those too, and it is scored from council votes rather
      // than from anything a candidate said.
      var answered = document.querySelector('.candidate-answer__text, .candidate-answer__options') !== null;
      ctx.fillStyle = '#f3edfb';
      ctx.fillRect(0, footerTop, SIZE, SIZE - footerTop);
      ctx.fillStyle = INK;
      ctx.font = '700 26px Lexend, sans-serif';
      ctx.fillText(answered ? 'Read their full responses' : 'The full scorecard, and how we grade',
        PAD, footerTop + 42);
      ctx.fillStyle = MUTED;
      ctx.font = '400 24px Lexend, sans-serif';
      ctx.fillText(pageUrl.replace(/^https?:\/\//, ''), PAD, footerTop + 78);

      // What the marks that are not letters mean, for a reader meeting this card
      // in a feed with no key above it. Only the ones this card actually uses,
      // and only in the footer, where they are a caption rather than a second
      // legend competing with the grades.
      var notes = [];
      if (topics.some(function (t) { return t.state === 'pending'; })) {
        notes.push('\u2014  no questionnaire returned');
      }
      if (topics.some(function (t) { return t.state === 'answers'; })) {
        notes.push('\u25CF  answered; this topic is not graded');
      }
      if (topics.some(function (t) { return t.state === 'review'; })) {
        notes.push('\u25CB  returned; not published yet');
      }
      ctx.textAlign = 'right';
      ctx.font = '400 20px Lexend, sans-serif';
      ctx.fillStyle = MUTED;
      notes.slice(0, 2).forEach(function (note, i) {
        ctx.fillText(note, SIZE - PAD, footerTop + 40 + i * 30);
      });
      ctx.textAlign = 'left';

      return new Promise(function (resolve, reject) {
        canvas.toBlob(function (blob) {
          if (blob) resolve(blob);
          else reject(new Error('canvas produced no image'));
        }, 'image/png');
      });
    });
  }

  var PLATFORMS = {
    facebook: {
      label: 'Facebook',
      composer: function (url) {
        return 'https://www.facebook.com/sharer/sharer.php?u=' + encodeURIComponent(url);
      },
      instruction: 'attach the image to your post.'
    },
    instagram: {
      label: 'Instagram',
      // The front door, and there is nothing deeper to aim at. Instagram takes
      // nothing from a link - no image, no caption, no pre-filled anything -
      // and its "new post" step is not addressable either: the first segment of
      // a path is a username, so /create/select/ serves the profile of a real
      // account called @create rather than the create flow. On a handheld this
      // address is a universal link and the app opens, with the saved image in
      // the camera roll.
      composer: function () {
        return 'https://www.instagram.com/';
      },
      instruction: 'start a post there and choose the saved image.'
    },
    x: {
      label: 'X',
      composer: function (url, message) {
        return 'https://x.com/intent/post?text=' + encodeURIComponent(message) +
          '&url=' + encodeURIComponent(url);
      },
      instruction: 'attach the image to your post.'
    }
  };

  function fileName() {
    return (candidate || 'candidate').toLowerCase().replace(/[^a-z0-9]+/g, '-')
      .replace(/^-|-$/g, '') + '-livable-crd-scorecard.png';
  }

  function message() {
    var where = municipality ? ' in ' + municipality : '';
    return candidate + "'s grades" + where +
      ' on the 2026 Livable CRD candidate scorecard.';
  }

  function say(words) {
    if (status) status.textContent = words;
  }

  function download(blob) {
    var url = URL.createObjectURL(blob);
    var link = document.createElement('a');
    link.href = url;
    link.download = fileName();
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    // Revoked late: Safari has not finished with the object URL when click()
    // returns, and an immediate revoke cancels the download.
    window.setTimeout(function () { URL.revokeObjectURL(url); }, 30000);
  }

  function share(platform, button) {
    var spec = PLATFORMS[platform];
    if (!spec) return;

    // Opened now, in the click, and pointed somewhere once the card is drawn: a
    // window.open that happens after an await is a popup as far as the browser
    // is concerned, and is blocked. Null back means a blocker took it anyway,
    // which the status line then has to say rather than leaving the reader
    // waiting for a tab.
    var composer = window.open('', '_blank');

    button.disabled = true;
    say('Drawing the card…');

    drawCard().then(function (blob) {
      var file = null;
      try {
        file = new File([blob], fileName(), { type: 'image/png' });
      } catch (e) {
        file = null;
      }

      // The share sheet, where the system has one that takes files. It is the
      // only route to Instagram that is not "save this and open the app", and
      // the reader picks the destination there, so the platform the button
      // named is a suggestion at this point rather than a guarantee.
      if (file && navigator.canShare && navigator.canShare({ files: [file] })) {
        if (composer) composer.close();
        return navigator.share({
          files: [file],
          text: message(),
          url: pageUrl
        }).then(function () {
          say('Shared.');
        }).catch(function (error) {
          // A reader who backs out of the sheet is not an error worth reporting
          // as one.
          if (error && error.name === 'AbortError') say('');
          else {
            download(blob);
            say('Image saved to your downloads. Post it to ' + spec.label + ' from there.');
          }
        });
      }

      download(blob);

      if (composer) {
        composer.location = spec.composer(pageUrl, message());
        say('Image saved to your downloads. ' + spec.label +
          ' is open in a new tab — ' + spec.instruction);
      } else {
        say('Image saved to your downloads. Your browser blocked the ' + spec.label +
          ' tab; open ' + spec.label + ' and ' + spec.instruction);
      }
      return null;
    }).catch(function (error) {
      if (composer) composer.close();
      say('Sorry — the image could not be drawn in this browser. ' +
        'The print button below makes the same scorecard as a PDF.');
      if (window.console) window.console.error(error);
    }).then(function () {
      button.disabled = false;
    });
  }

  // Revealed only where the browser can draw and hand over a file. A button that
  // cannot do what it says is worse than no button, which is the same rule the
  // print button follows.
  var canvasWorks = !!document.createElement('canvas').getContext;
  if (!canvasWorks || !window.URL || !URL.createObjectURL) return;

  buttons.forEach(function (button) {
    button.hidden = false;
    button.addEventListener('click', function () {
      share(button.getAttribute('data-share'), button);
    });
  });
})();
