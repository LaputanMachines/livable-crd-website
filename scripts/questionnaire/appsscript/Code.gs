/**
 * Fans candidate questionnaire submissions out into the per-subject grading tabs.
 *
 * Lives inside the submission spreadsheet ("Submissions - 2026 Municipal
 * Elections"), not in CI. `scripts/questionnaire/grading_tabs.py` creates the tabs
 * this fills; the two share their column layout and their rules for reading a
 * question's answer columns, so they change together.
 *
 * Three ways in, in order of how fast they land:
 *
 *   doPost()       Tally's webhook, ~1s after a candidate submits. Builds the rows
 *                  from the webhook's own JSON, so it never waits on Tally's
 *                  separate write to `Raw Submissions`.
 *   timerSync()    Every 5 minutes: reconciles what the webhook wrote against the
 *                  sheet, and appends anything the webhook missed entirely. Exits
 *                  in well under a second when there is nothing to do.
 *   Grading > Sync now   Menu item, for a human who doesn't want to wait.
 *
 * Both paths are append-only: they add rows for (submission, question) pairs that
 * have none, and never rewrite, reorder or delete an existing row. That is what
 * keeps a typed grade welded to its question when new submissions and new
 * questions arrive.
 *
 * The two build the answer text from different sources - the webhook from its
 * payload, the timer from the spreadsheet - so the sheet is made authoritative to
 * stop them disagreeing forever. A webhook row is written with an EMPTY hash,
 * which marks it unreconciled; the next sweep recomputes that row's answer from
 * the sheet, corrects the cell and stamps the hash. Only a row with a hash is
 * eligible for drift flagging, so reconciliation is silent and drift is not.
 *
 * Setup: run Grading > Set up (installs triggers, prompts for the webhook token),
 * then deploy as a web app and give Tally the URL with ?token=... appended.
 */

var RAW_TAB = '2026 Municipal Elections';
var REGISTRY_TAB = 'Question Registry';
var LOG_TAB = 'Sync Log';
var GRADE_PREFIX = 'Grade - ';

// Raw-sheet columns identifying the candidate, 1-based. grading_tabs.py repeats
// these; change both together.
var COL_SUBMISSION_ID = 1;
var COL_FIRST_NAME = 4;
var COL_LAST_NAME = 5;
var COL_MUNICIPALITY = 8;

// Grading tab columns, 1-based. grading_tabs.py writes the same layout; the two
// change together. Owner and Weight are lookups into the registry rather than
// copies, so a correction there reaches every grading row.
var G_KEY = 1, G_CANDIDATE = 2, G_MUNICIPALITY = 3, G_LABEL = 4, G_QUESTION = 5,
    G_ANSWER = 6, G_OWNER = 7, G_GRADE = 8, G_WEIGHT = 9, G_RATIONALE = 10,
    G_GRADER = 11, G_GRADED_AT = 12, G_HASH = 13;
var G_WIDTH = 13;

// Script properties.
var PROP_TOKEN = 'WEBHOOK_TOKEN';     // shared secret in the webhook URL's query string
var PROP_LAST_ROW = 'RAW_LAST_ROW';   // cheap change detector for the timer
var PROP_PENDING = 'RECONCILE_PENDING';  // webhook rows are awaiting a sheet-side check

// Cell values a Tally checkbox writes when the option was NOT chosen.
var FALSEY = ['', 'false', 'no', '0', 'off', 'unchecked', 'n'];

// Tally field labels carrying the candidate's identity, matched case-insensitively
// on a normalised prefix so light rewording of the form doesn't break them.
var FIELD_FIRST_NAME = "what's your first name";
var FIELD_LAST_NAME = "what's your last name";
var FIELD_MUNICIPALITY = 'which municipality are you running in';

// A question column's header, and equally a Tally field label: "HFL-01: ...",
// "HFL-11-Victoria: ...".
var LABEL_RE = /^([A-Z]{2,4}-(?:\d{2}|GEN)(?:-[A-Za-z]+)?):\s*([\s\S]*)$/;
var VARIANT_RE = /^([A-Z]{2,4}-\d{2})-[A-Za-z]+$/;

var DRIFT_COLOR = '#fff2cc';


/** Menu, so graders and admins never need the script editor. */
function onOpen() {
  try {
    SpreadsheetApp.getUi()
      .createMenu('Grading')
      .addItem('Sync now', 'menuSync')
      .addItem('Check setup', 'menuCheckSetup')
      .addSeparator()
      .addItem('Set up (triggers + webhook token)', 'menuSetup')
      .addToUi();
  } catch (err) {
    // Menu creation failure shouldn't break the sheet. Log and continue.
  }
}


/* ------------------------------------------------------------------ entry points */

/**
 * Tally's webhook. The URL carries a token because Apps Script web apps cannot
 * read request headers, so Tally's `tally-signature` header is unverifiable here;
 * the query-string secret is the whole of the authentication. Treat the deployed
 * URL as a capability.
 */
function doPost(e) {
  var expected = PropertiesService.getScriptProperties().getProperty(PROP_TOKEN);
  var given = e && e.parameter ? e.parameter.token : '';
  if (!expected || given !== expected) {
    log('webhook', 'rejected', 'bad or missing token');
    return json({ ok: false });
  }

  var data;
  try {
    data = (JSON.parse(e.postData.contents) || {}).data || {};
  } catch (err) {
    log('webhook', 'rejected', 'unparseable payload: ' + err);
    return json({ ok: false });
  }

  try {
    var result = syncFromPayload(data);
    log('webhook', 'synced', result.submissionId + ': ' + result.appended +
        ' row(s) appended across ' + result.tabs + ' tab(s)' +
        (result.skipped ? ', ' + result.skipped + ' already present' : ''));
    return json({ ok: true, appended: result.appended });
  } catch (err) {
    // Always log the failure: a webhook that dies silently looks identical to one
    // that was never delivered, and the timer's catch-up hides the difference.
    log('webhook', 'failed', String(err && err.stack ? err.stack : err).slice(0, 400));
    return json({ ok: false, error: String(err) });
  }
}


/**
 * Append one submission's rows straight from the webhook payload.
 *
 * Nothing here reads `Raw Submissions`, which is the point: Tally posts the
 * webhook and writes that tab independently, and waiting for the row cost 20
 * seconds on every submission.
 *
 * Rows are written with an empty hash, marking them unreconciled. syncAll()
 * recomputes each one from the sheet on its next pass, so the two paths cannot
 * disagree about an answer for longer than five minutes.
 */
function syncFromPayload(data) {
  var lock = LockService.getScriptLock();
  if (!lock.tryLock(30000)) throw new Error('another sync still running');

  try {
    var submissionId = String(data.submissionId || data.responseId || data.id || '').trim();
    if (!submissionId) throw new Error('payload carries no submission id');

    var fields = data.fields || [];
    var ss = SpreadsheetApp.getActive();
    var questions = readRegistry(null);
    var answers = payloadAnswers(fields);
    var candidate = payloadCandidate(fields);

    var pending = {}, byTab = {}, skipped = 0;

    for (var q = 0; q < questions.length; q++) {
      var question = questions[q];
      var tabName = GRADE_PREFIX + question.category;
      if (!byTab[tabName]) {
        var target = ss.getSheetByName(tabName);
        if (!target) {
          log('webhook', 'skipped', 'no tab "' + tabName + '" for ' + question.label);
          continue;
        }
        byTab[tabName] = { sheet: target, existing: existingRows(target) };
        pending[tabName] = [];
      }

      var key = submissionId + '|' + question.label;
      if (byTab[tabName].existing[key]) {
        skipped++;
        continue;
      }

      pending[tabName].push({
        key: key,
        candidate: candidate.name,
        municipality: candidate.municipality,
        label: question.label,
        question: question.text,
        answer: answers[question.label] || '',
        hash: ''   // unreconciled: syncAll() fills this in from the sheet
      });
    }

    var appended = 0, tabs = 0;
    for (var name in pending) {
      if (!pending[name].length) continue;
      writeRows(byTab[name].sheet, pending[name]);
      appended += pending[name].length;
      tabs++;
    }
    if (appended) PropertiesService.getScriptProperties().setProperty(PROP_PENDING, '1');
    return { submissionId: submissionId, appended: appended, tabs: tabs, skipped: skipped };
  } finally {
    lock.releaseLock();
  }
}


/**
 * Answer text per question label, read from the webhook payload's fields.
 *
 * Tally sends one field per form question, labelled exactly as the spreadsheet
 * column is headed ("HFL-01: What kinds of housing..."), which is what lets the
 * registry's labels line up without any column arithmetic. Choice fields carry
 * their selected option ids in `value` and the id-to-text mapping in `options`.
 *
 * Mirrors buildAnswer()'s output format deliberately: municipality variants
 * prefixed with the variant they came from, written follow-ups after the first
 * part, chosen options on a "Selected:" line.
 */
function payloadAnswers(fields) {
  var byLabel = {};

  for (var i = 0; i < fields.length; i++) {
    var field = fields[i] || {};
    var match = LABEL_RE.exec(String(field.label || '').trim());
    if (!match) continue;

    var fullLabel = match[1];
    var variantMatch = VARIANT_RE.exec(fullLabel);
    var label = variantMatch ? variantMatch[1] : fullLabel;
    var text = fieldText(field);
    if (!text) continue;

    if (!byLabel[label]) byLabel[label] = [];
    byLabel[label].push({ fullLabel: fullLabel, text: text, chosen: isMultiSelect(field) });
  }

  var out = {};
  for (var label in byLabel) {
    var parts = byLabel[label];
    // A candidate answers exactly one municipality variant; keep the one that
    // came back with content and say which it was.
    var variant = parts[0].fullLabel;
    var prefix = variant !== label ? '[' + variant + '] ' : '';

    var lines = [], selected = [], written = 0;
    for (var p = 0; p < parts.length; p++) {
      if (parts[p].fullLabel !== variant) continue;
      if (parts[p].chosen) {
        selected.push(parts[p].text);
      } else {
        lines.push(written === 0 ? parts[p].text : 'Follow-up: ' + parts[p].text);
        written++;
      }
    }
    if (selected.length) lines.push('Selected: ' + selected.join('; '));
    out[label] = prefix + lines.join('\n');
  }
  return out;
}


function isChoiceField(field) {
  return !!(field.options && field.options.length);
}


/**
 * True for a question that can take several answers at once.
 *
 * Only these get a "Selected:" line. A single-choice field is one written answer
 * and reads as one, which also keeps a question with a follow-up part
 * (GOV-01, CLI-01, ART-01, ROL-01) in the order the candidate answered it.
 */
function isMultiSelect(field) {
  if (!isChoiceField(field)) return false;
  var type = String(field.type || '').toUpperCase();
  // Named explicitly rather than pattern-matched: Tally's single-select type is
  // MULTIPLE_CHOICE, which any /MULTI/ test would wrongly claim.
  if (type === 'CHECKBOXES' || type === 'MULTI_SELECT') return true;
  // Unknown type: several ids came back, so several answers were possible.
  return Array.isArray(field.value) && field.value.length > 1;
}


/** One field's answer as text, resolving choice ids to their option text. */
function fieldText(field) {
  var value = field.value;
  if (value === null || value === undefined || value === '') return '';

  if (isChoiceField(field)) {
    var ids = Array.isArray(value) ? value : [value];
    var texts = [];
    for (var i = 0; i < ids.length; i++) {
      for (var o = 0; o < field.options.length; o++) {
        if (field.options[o].id === ids[i]) {
          texts.push(String(field.options[o].text || '').trim());
          break;
        }
      }
    }
    return texts.join('; ');
  }

  if (Array.isArray(value)) return value.join('; ');
  return String(value).trim();
}


/** Candidate name and municipality, from the payload's identity fields. */
function payloadCandidate(fields) {
  var first = '', last = '', municipality = '';
  for (var i = 0; i < fields.length; i++) {
    var label = String((fields[i] || {}).label || '').toLowerCase().trim();
    var text = fieldText(fields[i]);
    if (label.indexOf(FIELD_FIRST_NAME) === 0) first = text;
    else if (label.indexOf(FIELD_LAST_NAME) === 0) last = text;
    else if (label.indexOf(FIELD_MUNICIPALITY) === 0) municipality = text;
  }
  return { name: (first + ' ' + last).trim(), municipality: municipality };
}


/** Five-minute safety net. Cheap when nothing changed. */
function timerSync() {
  var props = PropertiesService.getScriptProperties();
  var grew = String(sheet(RAW_TAB).getLastRow()) !== props.getProperty(PROP_LAST_ROW);
  if (!grew && props.getProperty(PROP_PENDING) !== '1') return;
  syncAll('timer');
}


function menuSync() {
  var result = syncAll('menu');
  SpreadsheetApp.getUi().alert(
    'Appended ' + result.appended + ' row(s) across ' + result.tabs + ' tab(s).' +
    (result.drifted ? '\n\n' + result.drifted + ' answer(s) changed since grading - see Sync Log.' : ''));
}


/** Grader bookkeeping: stamp who graded a row and when. Installable, so it can read the user. */
function onGradeEdit(e) {
  var range = e.range;
  var sh = range.getSheet();
  if (sh.getName().indexOf(GRADE_PREFIX) !== 0) return;
  if (range.getRow() === 1) return;

  var col = range.getColumn();
  if (col !== G_GRADE && col !== G_RATIONALE) return;

  var row = range.getRow();
  var who = '';
  try {
    who = Session.getActiveUser().getEmail() || '';
  } catch (err) {
    who = '';
  }
  sh.getRange(row, G_GRADER).setValue(who);
  sh.getRange(row, G_GRADED_AT).setValue(new Date());
}


/* ------------------------------------------------------------------ the sync */

/**
 * Append every (submission, question) row that doesn't exist yet.
 *
 * Existing rows are only ever touched to refresh an answer that changed under a
 * grade already given, and even then the grade, weight and rationale are left
 * alone and the row is flagged for a human.
 */
function syncAll(trigger) {
  var lock = LockService.getScriptLock();
  if (!lock.tryLock(30000)) {
    log(trigger, 'skipped', 'another sync still running');
    return { appended: 0, tabs: 0, drifted: 0 };
  }

  try {
    var ss = SpreadsheetApp.getActive();
    var raw = ss.getSheetByName(RAW_TAB);
    var rawValues = raw.getDataRange().getValues();
    if (rawValues.length < 2) {
      log(trigger, 'nothing to do', 'no submissions');
      return { appended: 0, tabs: 0, drifted: 0 };
    }

    var header = rawValues[0];
    var questions = readRegistry(header);
    var appended = 0, tabs = 0, drifted = 0, reconciled = 0;

    // Group the rows to append by target tab, so each tab is one write.
    var pending = {};
    var byTab = {};

    for (var q = 0; q < questions.length; q++) {
      var question = questions[q];
      var tabName = GRADE_PREFIX + question.category;
      if (!byTab[tabName]) {
        var target = ss.getSheetByName(tabName);
        if (!target) {
          log(trigger, 'skipped', 'no tab "' + tabName + '" for ' + question.label);
          continue;
        }
        byTab[tabName] = {
          sheet: target, existing: existingRows(target), reconcile: [], drift: []
        };
        pending[tabName] = [];
      }
      var tab = byTab[tabName];

      for (var r = 1; r < rawValues.length; r++) {
        var row = rawValues[r];
        var submissionId = String(row[COL_SUBMISSION_ID - 1] || '').trim();
        if (!submissionId) continue;

        var key = submissionId + '|' + question.label;
        var answer = buildAnswer(header, row, question);
        var hash = digest(answer);

        var known = tab.existing[key];
        if (!known) {
          pending[tabName].push({
            key: key,
            candidate: candidateName(row),
            municipality: String(row[COL_MUNICIPALITY - 1] || '').trim(),
            label: question.label,
            question: question.text,
            answer: answer,
            hash: hash
          });
          continue;
        }

        // Row exists, for one of two reasons.
        if (!known.hash) {
          // Written by the webhook from its payload and never checked against the
          // sheet. Correct it quietly: the sheet is the authority, and the two
          // sources phrase a handful of answers differently.
          tab.reconcile.push({ row: known.row, answer: answer, hash: hash });
          reconciled++;
        } else if (known.hash !== hash) {
          // Tally changed the answer underneath a grade already given. Refresh the
          // text, flag it, and leave the grade alone for a human to re-check.
          tab.drift.push({ row: known.row, answer: answer, hash: hash });
          log(trigger, 'answer changed', key + ' (grade left as "' + known.grade + '")');
          drifted++;
        }
      }
    }

    for (var name in pending) {
      var rows = pending[name];
      if (rows.length) {
        writeRows(byTab[name].sheet, rows);
        appended += rows.length;
        tabs++;
      }
      flushAnswers(byTab[name].sheet, byTab[name].reconcile, null);
      flushAnswers(byTab[name].sheet, byTab[name].drift, DRIFT_COLOR);
    }

    var props = PropertiesService.getScriptProperties();
    props.setProperty(PROP_LAST_ROW, String(raw.getLastRow()));
    // Rows appended by this sweep already carry their hash, so the only thing
    // still awaiting reconciliation is whatever the webhook writes next.
    props.setProperty(PROP_PENDING, '0');

    if (appended || drifted || reconciled) {
      log(trigger, 'synced', appended + ' row(s) appended across ' + tabs +
          ' tab(s); ' + reconciled + ' reconciled; ' + drifted + ' answer(s) changed');
    }
    return { appended: appended, tabs: tabs, drifted: drifted, reconciled: reconciled };
  } finally {
    lock.releaseLock();
  }
}


/** Append rows in one write, with the owner and weight lookups pointing at the registry. */
function writeRows(sheet, rows) {
  var first = Math.max(sheet.getLastRow() + 1, 2);
  var values = rows.map(function (r, i) {
    var line = first + i;
    return [
      r.key, r.candidate, r.municipality, r.label, r.question, r.answer,
      "=IFERROR(VLOOKUP($D" + line + ",'" + REGISTRY_TAB + "'!$A:$I,9,FALSE),\"\")",
      '',  // grade, typed by a grader
      "=IFERROR(VLOOKUP($D" + line + ",'" + REGISTRY_TAB + "'!$A:$F,6,FALSE),\"\")",
      '',  // rationale
      '',  // grader
      '',  // graded at
      r.hash
    ];
  });
  sheet.getRange(first, 1, values.length, G_WIDTH).setValues(values);
}


/** Existing keys on a grading tab: key -> {row, hash, grade}. */
function existingRows(sheet) {
  var last = sheet.getLastRow();
  var out = {};
  if (last < 2) return out;
  var values = sheet.getRange(2, 1, last - 1, G_WIDTH).getValues();
  for (var i = 0; i < values.length; i++) {
    var key = String(values[i][G_KEY - 1] || '').trim();
    if (!key) continue;
    out[key] = {
      row: i + 2,
      hash: String(values[i][G_HASH - 1] || ''),
      grade: String(values[i][G_GRADE - 1] || '')
    };
  }
  return out;
}


/* ------------------------------------------------------------------ the registry */

/**
 * The graded questions, as the registry defines them.
 *
 * Each entry carries the raw columns holding its answer, already grouped by
 * municipality variant, with the option columns identified. Rows without a
 * category, or with Graded set to anything but Yes, are ignored.
 */
function readRegistry(header) {
  try {
    var sh = SpreadsheetApp.getActive().getSheetByName(REGISTRY_TAB);
    if (!sh) {
      log('system', 'warning', 'Question Registry tab missing — no questions to sync');
      return [];
    }
    var last = sh.getLastRow();
    if (last < 2) return [];

    var values = sh.getRange(2, 1, last - 1, 8).getValues();
    var questions = [];

    for (var i = 0; i < values.length; i++) {
      var label = String(values[i][0] || '').trim();
      var category = String(values[i][1] || '').trim();
      var text = String(values[i][2] || '').trim();
      var graded = String(values[i][4] || '').trim().toLowerCase();
      var span = String(values[i][6] || '').trim();
      if (!label || !category || graded !== 'yes' || !span) continue;

      var bounds = span.split('-');
      var from = parseInt(bounds[0], 10);
      var to = parseInt(bounds[bounds.length - 1], 10);
      if (!from || !to) continue;

      questions.push({
        label: label,
        category: category,
        text: text,
        // The payload path matches on labels and never touches raw columns, so it
        // passes no header and gets no variant grouping.
        variants: header ? groupVariants(header, from, to) : []
      });
    }
    return questions;
  } catch (err) {
    try {
      SpreadsheetApp.getUi().alert('Question Registry read failed: ' + err);
    } catch (e2) {}
    return [];
  }
}


/**
 * Split a question's columns into its municipality variants, and each variant
 * into its question column, its written follow-up parts and its options.
 *
 * A multi-select option column is the question's own text with " (the option)"
 * appended, so the shortest text in a variant is the question and anything
 * extending it is an option. Matching on a trailing parenthesis instead would
 * misread options that contain their own brackets ("Small homes (< 500 sq. ft.)").
 * grading_tabs.py uses the same rule.
 */
function groupVariants(header, from, to) {
  var byLabel = {};
  var order = [];

  for (var c = from; c <= to; c++) {
    var cell = String(header[c - 1] || '').trim();
    var split = cell.indexOf(':');
    if (split < 0) continue;
    var label = cell.substring(0, split).trim();
    var text = cell.substring(split + 1).replace(/\s+/g, ' ').trim();
    if (!byLabel[label]) {
      byLabel[label] = [];
      order.push(label);
    }
    byLabel[label].push({ column: c, text: text });
  }

  return order.map(function (label) {
    var cols = byLabel[label];
    var base = cols[0].text;
    for (var i = 1; i < cols.length; i++) {
      if (cols[i].text.length < base.length) base = cols[i].text;
    }

    var plain = [], options = [];
    for (var j = 0; j < cols.length; j++) {
      var t = cols[j].text;
      if (t !== base && t.indexOf(base) === 0 && /\)$/.test(t)) {
        options.push({
          column: cols[j].column,
          text: t.substring(base.length).trim().replace(/^\(/, '').replace(/\)$/, '').trim()
        });
      } else {
        plain.push(cols[j]);
      }
    }
    return { label: label, plain: plain, options: options };
  });
}


/**
 * One candidate's answer to one question, as a single cell of text.
 *
 * Municipality variants: the candidate answered exactly one, so the first
 * variant with anything in it wins. Multi-selects list the options actually
 * chosen. A question with a written follow-up (GOV-01, CLI-01, ART-01, ROL-01)
 * keeps both parts, because they earn one grade between them.
 */
function buildAnswer(header, row, question) {
  for (var v = 0; v < question.variants.length; v++) {
    var variant = question.variants[v];
    var parts = [];

    for (var p = 0; p < variant.plain.length; p++) {
      var value = String(row[variant.plain[p].column - 1] || '').trim();
      if (value) parts.push(p === 0 ? value : 'Follow-up: ' + value);
    }

    var chosen = [];
    for (var o = 0; o < variant.options.length; o++) {
      if (isTicked(row[variant.options[o].column - 1])) chosen.push(variant.options[o].text);
    }
    if (chosen.length) parts.push('Selected: ' + chosen.join('; '));

    if (parts.length) {
      // Name the variant, so a Housing grader can see which municipality's
      // version of the question this candidate actually answered.
      var prefix = question.variants.length > 1 ? '[' + variant.label + '] ' : '';
      return prefix + parts.join('\n');
    }
  }
  return '';
}


function isTicked(value) {
  var v = String(value === null || value === undefined ? '' : value).trim().toLowerCase();
  return FALSEY.indexOf(v) === -1;
}


/* ------------------------------------------------------------------ setup + checks */

function menuSetup() {
  var ui = SpreadsheetApp.getUi();
  var props = PropertiesService.getScriptProperties();

  var answer = ui.prompt(
    'Webhook token',
    'Paste a long random string. It goes in the webhook URL you give Tally, and is ' +
    'the only thing standing between that URL and anyone who guesses it.\n\n' +
    'Leave blank to keep the current one.',
    ui.ButtonSet.OK_CANCEL);
  if (answer.getSelectedButton() !== ui.Button.OK) return;

  var token = answer.getResponseText().trim();
  if (token) props.setProperty(PROP_TOKEN, token);
  if (!props.getProperty(PROP_TOKEN)) {
    ui.alert('No token set. The webhook will reject every request until there is one.');
    return;
  }

  installTriggers();
  ui.alert('Set up.\n\nTriggers installed: 5-minute safety net and the grader stamp.\n\n' +
           'Next: Deploy > New deployment > Web app, then give Tally the URL with ' +
           '?token=<your token> on the end.');
}


function installTriggers() {
  var existing = ScriptApp.getProjectTriggers();
  for (var i = 0; i < existing.length; i++) {
    var fn = existing[i].getHandlerFunction();
    if (fn === 'timerSync' || fn === 'onGradeEdit') ScriptApp.deleteTrigger(existing[i]);
  }
  ScriptApp.newTrigger('timerSync').timeBased().everyMinutes(5).create();
  ScriptApp.newTrigger('onGradeEdit').forSpreadsheet(SpreadsheetApp.getActive()).onEdit().create();
}


/** Everything that has to be true before a submission can land correctly. */
function menuCheckSetup() {
  var ss = SpreadsheetApp.getActive();
  var problems = [];
  var props = PropertiesService.getScriptProperties();

  if (!props.getProperty(PROP_TOKEN)) problems.push('No webhook token set (Grading > Set up).');

  var header = ss.getSheetByName(RAW_TAB).getDataRange().getValues()[0];
  var questions = readRegistry(header);
  if (!questions.length) problems.push('Question Registry lists no graded questions.');

  var weights = {}, counts = {};
  var reg = sheet(REGISTRY_TAB);
  var rows = reg.getRange(2, 1, Math.max(reg.getLastRow() - 1, 1), 8).getValues();
  for (var i = 0; i < rows.length; i++) {
    var category = String(rows[i][1] || '').trim();
    if (!category) continue;
    weights[category] = (weights[category] || 0) + (Number(rows[i][5]) || 0);
    counts[category] = (counts[category] || 0) + 1;
  }

  for (var c in counts) {
    if (!ss.getSheetByName(GRADE_PREFIX + c)) problems.push('No tab "' + GRADE_PREFIX + c + '".');
    var total = Math.round(weights[c] * 1000) / 1000;
    if (total !== 1) problems.push(c + ' weights total ' + Math.round(total * 100) + '%, not 100%.');
  }

  var triggers = ScriptApp.getProjectTriggers().map(function (t) { return t.getHandlerFunction(); });
  if (triggers.indexOf('timerSync') === -1) problems.push('No 5-minute timer (Grading > Set up).');
  if (triggers.indexOf('onGradeEdit') === -1) problems.push('No grader-stamp trigger (Grading > Set up).');

  SpreadsheetApp.getUi().alert(problems.length
    ? 'Problems:\n\n- ' + problems.join('\n- ')
    : 'All good.\n\n' + questions.length + ' graded questions across ' +
      Object.keys(counts).length + ' subjects.');
}


/* ------------------------------------------------------------------ helpers */

/**
 * Write corrected answers back, batching contiguous rows into one call each.
 *
 * Only the answer and its hash are touched: Grade, Weight, Rationale, Grader and
 * Graded at belong to whoever typed them. `color` tints the answer cell, for
 * drift a human needs to look at; pass null for a silent correction.
 */
function flushAnswers(sheet, items, color) {
  if (!items.length) return;
  items.sort(function (a, b) { return a.row - b.row; });

  var run = [items[0]];
  for (var i = 1; i <= items.length; i++) {
    if (i < items.length && items[i].row === run[run.length - 1].row + 1) {
      run.push(items[i]);
      continue;
    }
    var answers = run.map(function (item) { return [item.answer]; });
    var hashes = run.map(function (item) { return [item.hash]; });
    var target = sheet.getRange(run[0].row, G_ANSWER, run.length, 1);
    target.setValues(answers);
    if (color) target.setBackground(color);
    sheet.getRange(run[0].row, G_HASH, run.length, 1).setValues(hashes);
    if (i < items.length) run = [items[i]];
  }
}


function candidateName(row) {
  var first = String(row[COL_FIRST_NAME - 1] || '').trim();
  var last = String(row[COL_LAST_NAME - 1] || '').trim();
  return (first + ' ' + last).trim();
}


function digest(text) {
  var bytes = Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256, text || '');
  return bytes.slice(0, 8).map(function (b) {
    return ((b & 0xff) + 0x100).toString(16).slice(1);
  }).join('');
}


function sheet(name) {
  var sh = SpreadsheetApp.getActive().getSheetByName(name);
  if (!sh) throw new Error('Missing tab: ' + name);
  return sh;
}


function log(trigger, event, detail) {
  try {
    var sh = SpreadsheetApp.getActive().getSheetByName(LOG_TAB);
    if (!sh) return;  // Sync Log missing; don't crash, just skip logging.
    sh.appendRow([new Date(), trigger, event, detail]);
  } catch (err) {
    // Logging is a convenience; never let it take the sync down with it.
  }
}


function json(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}
