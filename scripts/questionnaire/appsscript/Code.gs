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
 *   timerSync()    Daily: reconciles what the webhook wrote against the sheet,
 *                  and appends anything the webhook missed entirely. Exits in
 *                  well under a second when there is nothing to do.
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
 * Both paths also keep `Category Grades` current: one row per candidate (not
 * per question), added the first time any of their answers sync in. Each
 * category is a (grade, deploy checkbox) pair of columns: the grade cell
 * starts as a weighted-average rollup of that category's question-level
 * grades, which a partner org can type a letter over to record their own
 * top-level call instead; the checkbox starts unchecked and gates that
 * category's grade and detailed scoring going out to the website (see
 * ensureCategoryRows/categoryFormula).
 *
 * Setup: run Grading > Set up (installs triggers, prompts for the webhook token),
 * then deploy as a web app and give Tally the URL with ?token=... appended.
 */

var RAW_TAB = '2026 Municipal Elections';
var REGISTRY_TAB = 'Question Registry';
var LOG_TAB = 'Sync Log';
var GRADE_PREFIX = 'Grade - ';
var CATEGORY_TAB = 'Category Grades';

// The same grid as Category Grades, holding the figure each letter was banded
// from rather than the letter. A band is a wide thing to be inside - two
// candidates both reading A on housing can be 85% and 99% - and the tab that
// decides the grade cannot show the difference. Nothing here is published or
// gates anything, so it carries no deploy checkboxes. grading_tabs.py creates
// it and backfills the candidates already on the sheet; this appends each new
// one. See statsFormula().
var STATS_TAB = 'Category Stats';

// How many letters the scale has, so a letter-graded subject's average can be
// read as a share of the top of it. Mirrors VALID_GRADES in grading_tabs.py and
// sync-candidates.py: A, B, C, C-, F and nothing else.
var VALID_GRADE_COUNT = 5;
// Categories whose graders type a number in H rather than a letter, and what
// that number is out of. Two partner orgs score rather than grade, and they do
// it differently enough to need a map each.
//
// Housing - Homes for Living. Each question is worth a stated number of points,
// so H is a score out of the Max points in I, and the topic grade is the share
// of the points the candidate had available to them. Housing questions carry no
// Weight: the points are the weighting. A housing score can be negative - their
// rubric has options that cost a candidate points - and it is the only kind of
// score that can. grading_tabs.py's SCORE_FLOOR is what the column accepts.
//
// Arts - Victori'us. Each question is scored 0-3 and carries a Weight exactly as
// on a letter tab, so I is the same weight lookup as everywhere else and only H
// changes meaning. The topic grade is the weighted average of those scores read
// as a percentage.
//
// grading_tabs.py holds both; change them together.
var POINTS_CATEGORIES = { 'Housing': true };
var SCALE_CATEGORIES = { 'Arts': 3 };

// The incumbent record: one more row on Grade - Housing, and the only row on any
// grading tab that no candidate answered.
//
// Homes for Living wanted a sitting councillor's record on housing scored
// alongside what they say they will do next term, so this row carries their
// judgement of the term itself. It is scored in points in column H like every
// other housing row, out of a Max points they set on its registry row.
//
// What it is worth is not its points. RECORD_SHARE of the housing grade is the
// record and the rest is the questionnaire, whatever each is scored out of - see
// pointsCategoryFormula(). grading_tabs.py holds the same two constants and
// renders the same formula; change them together.
var RECORD_LABEL = 'HFL-INC';
var RECORD_SHARE = 0.3;

// Column F on a record row. Every other row holds what the candidate wrote, and
// a blank cell there would read as an unanswered question rather than as a row
// that never had a question to answer.
var RECORD_ANSWER = 'No candidate answer. Homes for Living score this ' +
    "incumbent's record on housing during their current term.";

// Who is an incumbent, and where that is read from.
//
// Nothing in this spreadsheet says. The coalition tracks it in the candidate
// tracking sheet, whose id is a capability over contact details and has no
// business in a grading script, and the website republishes the same fact as
// `standing` in _data/candidates.yml - a public file in a public repository,
// regenerated from that sheet daily by CI. So the roster is read from there:
// no credential, no second sheet, and it follows the tracking sheet on its own.
//
// A sitting incumbent's standing starts "incumbent"; "ex-incumbent-councillor"
// is a former one and is not scored on a record they are no longer making.
//
// If the fetch or the parse fails, incumbentIndex() returns null and the sync
// creates NO record rows at all that run. Appending them to everybody on a bad
// read would be far worse than appending them late: the rows are append-only,
// so a wrong one has to be deleted by hand.
var ROSTER_URL = 'https://raw.githubusercontent.com/LaputanMachines/' +
    'livable-crd-website/main/_data/candidates.yml';
var ROSTER_CACHE_KEY = 'roster-standing-v1';
var ROSTER_CACHE_SECONDS = 21600;  // six hours; the file is rewritten daily
var ROSTER_INCUMBENT_RE = /^incumbent(-|$)/;

// Registry column holding what a points-scored question is worth, 1-based.
// grading_tabs.py writes the header and seeds the values.
var REGISTRY_MAX_COLUMN = 13;

// Each org's grade bands, as a share of what was available, with the letters
// they band into. Ascending, because MATCH with a 1 finds the last threshold at
// or below the value.
//
// Not the same bands: Homes for Living's C- runs from 50% to 60%, and
// Victori'us have no C- at all and start A a point higher, at 86%.
var POINTS_BANDS = '{0;0.5;0.6;0.7;0.85}';
var POINTS_LETTERS = '{"F";"C-";"C";"B";"A"}';
var SCALE_BANDS = '{0;0.6;0.7;0.86}';
var SCALE_LETTERS = '{"F";"C";"B";"A"}';

// Category Grades columns, 1-based: identity, then a (grade, deploy checkbox)
// pair per category in whatever order grading_tabs.py wrote the header - read
// from the sheet itself rather than hardcoded, so a category added or dropped
// there needs no script change here.
var CG_KEY = 1, CG_CANDIDATE = 2, CG_MUNICIPALITY = 3;

// Suffix marking a header cell as a deploy-gate checkbox rather than a grade
// column. grading_tabs.py writes the same suffix.
var CATEGORY_DEPLOY_SUFFIX = ' - Deploy to website';

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
        (result.skipped ? ', ' + result.skipped + ' already present' : '') +
        (result.category ? ', category row added' : ''));
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
 * recomputes each one from the sheet on its next pass (daily), so the two paths
 * cannot disagree about an answer for longer than a day.
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

    // Whether this one submitter is a sitting incumbent, on the same roster the
    // sweep reads. Unknown - roster unreadable, or a name it does not list -
    // means no record row now; the next sweep adds it if the answer changes.
    var roster = incumbentIndex();
    var isIncumbent = !!(roster &&
        roster[rosterKey(candidate.name, candidate.municipality)]);

    var pending = {}, byTab = {}, skipped = 0;

    for (var q = 0; q < questions.length; q++) {
      var question = questions[q];
      if (question.record && !isIncumbent) continue;
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
        answer: question.record ? RECORD_ANSWER : (answers[question.label] || ''),
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

    var one = [{ key: submissionId, candidate: candidate.name,
                 municipality: candidate.municipality }];
    var categoryRow = ensureCategoryRows(ss, one, 'webhook');
    var statsRow = ensureStatsRows(ss, one, 'webhook');

    return { submissionId: submissionId, appended: appended, tabs: tabs, skipped: skipped,
             category: categoryRow, stats: statsRow };
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

    // Alongside the consolidated field (options + chosen ids), Tally also sends
    // one boolean field per option ("HFL-01: ... (Market rate rental housing.)",
    // value true/false) with no `options` array of its own. The consolidated
    // field already produces the "Selected:" line, so these carry nothing new -
    // without this they read as a wall of "Follow-up: false".
    if (String(field.type || '').toUpperCase() === 'CHECKBOXES' && !isChoiceField(field)) continue;

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

    // Who gets a record row, worked out once for the whole sweep rather than
    // per question: the roster is one fetch, and the answer is the same on
    // every pass down the submissions. A null index means the roster could not
    // be read, and standing[] stays empty, so no record row is created at all.
    var roster = incumbentIndex();
    var standing = {}, unrostered = [];
    if (roster) {
      for (var d = 1; d < rawValues.length; d++) {
        var who = rosterKey(candidateName(rawValues[d]),
                            String(rawValues[d][COL_MUNICIPALITY - 1] || ''));
        if (!(who in roster)) {
          if (unrostered.indexOf(who) === -1) unrostered.push(who);
          continue;
        }
        standing[d] = roster[who];
      }
    }
    if (unrostered.length) {
      // Not an error in itself - a submission can arrive before the tracking
      // sheet confirms the candidate - but while it lasts, nothing here knows
      // whether that person is an incumbent, so they get no record row.
      log(trigger, 'not on the roster', unrostered.length + ' submission(s) match ' +
          'no confirmed candidate, so no ' + RECORD_LABEL + ' row: ' +
          unrostered.join(', '));
    }

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

        // The record row exists for sitting incumbents and nobody else. A
        // challenger has no term to be scored on, and somebody the roster does
        // not list yet cannot be told apart from one.
        if (question.record && !standing[r]) continue;

        var key = submissionId + '|' + question.label;
        var answer = question.record ? RECORD_ANSWER : buildAnswer(header, row, question);
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

    // One row per submission, not per question - collect distinct submissions
    // once rather than re-deriving them inside the per-question loop above.
    var submissions = [], seenSubs = {};
    for (var s = 1; s < rawValues.length; s++) {
      var srow = rawValues[s];
      var subId = String(srow[COL_SUBMISSION_ID - 1] || '').trim();
      if (!subId || seenSubs[subId]) continue;
      seenSubs[subId] = true;
      submissions.push({
        key: subId,
        candidate: candidateName(srow),
        municipality: String(srow[COL_MUNICIPALITY - 1] || '').trim()
      });
    }
    var categoryRows = ensureCategoryRows(ss, submissions, trigger);
    var statsRows = ensureStatsRows(ss, submissions, trigger);

    var props = PropertiesService.getScriptProperties();
    props.setProperty(PROP_LAST_ROW, String(raw.getLastRow()));
    // Rows appended by this sweep already carry their hash, so the only thing
    // still awaiting reconciliation is whatever the webhook writes next.
    props.setProperty(PROP_PENDING, '0');

    if (appended || drifted || reconciled || categoryRows || statsRows) {
      log(trigger, 'synced', appended + ' row(s) appended across ' + tabs +
          ' tab(s); ' + reconciled + ' reconciled; ' + drifted + ' answer(s) changed; ' +
          categoryRows + ' category row(s) added; ' + statsRows + ' stats row(s) added');
    }
    return { appended: appended, tabs: tabs, drifted: drifted, reconciled: reconciled,
             category: categoryRows, stats: statsRows };
  } finally {
    lock.releaseLock();
  }
}


/** Append rows in one write, with the owner and weight lookups pointing at the registry. */
function writeRows(sheet, rows) {
  var first = Math.max(sheet.getLastRow() + 1, 2);
  var category = String(sheet.getName()).slice(GRADE_PREFIX.length);
  var values = rows.map(function (r, i) {
    var line = first + i;
    return [
      r.key, r.candidate, r.municipality, r.label, r.question, r.answer,
      "=IFERROR(VLOOKUP($D" + line + ",'" + REGISTRY_TAB + "'!$A:$I,9,FALSE),\"\")",
      '',  // grade on a letter tab, score on a scored one. Typed by a grader.
      columnIFormula(category, line),
      '',  // rationale
      '',  // grader
      '',  // graded at
      r.hash
    ];
  });
  sheet.getRange(first, 1, values.length, G_WIDTH).setValues(values);
}


/** Column I on a letter-graded tab, and on a scale tab: this question's share
 *  of its subject. */
function weightFormula(line) {
  return "=IFERROR(VLOOKUP($D" + line + ",'" + REGISTRY_TAB + "'!$A:$F,6,FALSE),\"\")";
}


/**
 * Column I on a points tab: what this question is worth.
 *
 * The same shape as the weight lookup it replaces - a VLOOKUP into the registry
 * rather than a copy, so correcting a maximum there corrects every candidate's
 * row at once - just pointed at Max points instead. grading_tabs.py renders the
 * same string for the rows that predate the rubric.
 */
function maxPointsFormula(line) {
  return "=IFERROR(VLOOKUP($D" + line + ",'" + REGISTRY_TAB + "'!$A:$" +
      columnLetter(REGISTRY_MAX_COLUMN) + "," + REGISTRY_MAX_COLUMN + ",FALSE),\"\")";
}


/**
 * Column I: what the question is worth, in the units its tab grades in.
 *
 * A maximum on a points tab, and a weight on every other kind - a scale tab's
 * column I is the one a letter tab has, untouched. Mirrors column_i_formula()
 * in grading_tabs.py.
 */
function columnIFormula(category, line) {
  return POINTS_CATEGORIES[category] ? maxPointsFormula(line) : weightFormula(line);
}


/** 1-based column index to its A1 letters. */
function columnLetter(index) {
  var letters = '';
  while (index > 0) {
    var rem = (index - 1) % 26;
    letters = String.fromCharCode(65 + rem) + letters;
    index = (index - 1 - rem) / 26;
  }
  return letters;
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
      // Not `|| ''`: on a scored tab this cell is a number, and a score of 0 is
      // a real grade that `||` would report as an empty one in the drift log.
      grade: values[i][G_GRADE - 1] === '' || values[i][G_GRADE - 1] == null
        ? '' : String(values[i][G_GRADE - 1])
    };
  }
  return out;
}


/**
 * Append one Category Grades row per submission that doesn't have one yet.
 *
 * One row per candidate, not per question: a partner org's top-level grade for
 * a whole category, separate from (and starting from a rollup of) the
 * per-question grades in that category's Grade tab. Which categories get a
 * pair of columns, and in what order, is read from the tab's own header
 * rather than hardcoded - grading_tabs.py owns that list, built from which
 * categories currently have a Graded=Yes registry row.
 *
 * Each category is a pair of columns: the grade itself, then a
 * "<Category> - Deploy to website" checkbox gating publication of that
 * category's top-level grade and its detailed scoring. A header cell is told
 * apart as one or the other by CATEGORY_DEPLOY_SUFFIX, not position, so a
 * category inserted or reordered in the sheet needs no script change.
 *
 * Both kinds of cell are written once. A partner typing a letter over the
 * rollup formula, or checking the box, replaces that for good - that is the
 * intended override, not a bug, so nothing here ever re-touches an existing
 * cell.
 */
function ensureCategoryRows(ss, submissions, trigger) {
  var sheet = ss.getSheetByName(CATEGORY_TAB);
  if (!sheet) {
    log(trigger, 'skipped', 'no tab "' + CATEGORY_TAB + '"');
    return 0;
  }

  var lastCol = sheet.getLastColumn();
  if (lastCol < 4) return 0;  // header has no category columns yet
  var header = sheet.getRange(1, 1, 1, lastCol).getValues()[0];

  var existing = {};
  var lastRow = sheet.getLastRow();
  if (lastRow >= 2) {
    var keys = sheet.getRange(2, CG_KEY, lastRow - 1, 1).getValues();
    for (var i = 0; i < keys.length; i++) {
      var k = String(keys[i][0] || '').trim();
      if (k) existing[k] = true;
    }
  }

  var toAdd = [];
  for (var s = 0; s < submissions.length; s++) {
    var sub = submissions[s];
    if (existing[sub.key]) continue;
    existing[sub.key] = true;  // guard duplicates within this same batch
    toAdd.push(sub);
  }
  if (!toAdd.length) return 0;

  var first = Math.max(sheet.getLastRow() + 1, 2);
  var values = toAdd.map(function (sub, i) {
    var line = first + i;
    var out = new Array(lastCol).fill('');
    out[CG_KEY - 1] = sub.key;
    out[CG_CANDIDATE - 1] = sub.candidate;
    out[CG_MUNICIPALITY - 1] = sub.municipality;
    for (var c = 4; c <= lastCol; c++) {
      var label = String(header[c - 1] || '').trim();
      if (!label) continue;
      if (label.endsWith(CATEGORY_DEPLOY_SUFFIX)) {
        out[c - 1] = false;  // unchecked until a partner org signs off
      } else {
        out[c - 1] = categoryFormula(label, line);
      }
    }
    return out;
  });
  sheet.getRange(first, 1, values.length, lastCol).setValues(values);

  // Checkbox rendering is applied only to the rows just written, never to a
  // wide empty range: Sheets auto-fills a BOOLEAN-validated range with FALSE
  // the moment the rule is set, even where nothing was written, which is
  // exactly what corrupted getLastRow() into thinking this tab ran 2000 rows
  // deep the first time this was tried tab-wide from grading_tabs.py.
  var checkboxRule = SpreadsheetApp.newDataValidation().requireCheckbox().build();
  for (var dc = 4; dc <= lastCol; dc++) {
    if (String(header[dc - 1] || '').trim().endsWith(CATEGORY_DEPLOY_SUFFIX)) {
      sheet.getRange(first, dc, values.length, 1).setDataValidation(checkboxRule);
    }
  }

  return values.length;
}


/**
 * One Category Stats row per submission, appended as Category Grades' rows are.
 *
 * Deliberately a second pass over the same submissions rather than more columns
 * on Category Grades: that tab is what a partner org types their own call into,
 * and a percentage beside a letter they overrode would sit there contradicting
 * them. Here every cell is computed, and the tab says so.
 *
 * Append-only and keyed, exactly like ensureCategoryRows: a row already carrying
 * this submission's key is left alone, formula and all. The tab is created by
 * grading_tabs.py, which also backfills the candidates already on the sheet; if
 * it is missing, this does nothing and says so rather than inventing a header.
 */
function ensureStatsRows(ss, submissions, trigger) {
  var sheet = ss.getSheetByName(STATS_TAB);
  if (!sheet) {
    log(trigger, 'skipped', 'no tab "' + STATS_TAB + '" (run grading_tabs.py)');
    return 0;
  }

  var lastCol = sheet.getLastColumn();
  if (lastCol < 4) return 0;  // header has no subject columns yet
  var header = sheet.getRange(1, 1, 1, lastCol).getValues()[0];

  var existing = {};
  var lastRow = sheet.getLastRow();
  if (lastRow >= 2) {
    var keys = sheet.getRange(2, CG_KEY, lastRow - 1, 1).getValues();
    for (var i = 0; i < keys.length; i++) {
      var k = String(keys[i][0] || '').trim();
      if (k) existing[k] = true;
    }
  }

  var toAdd = [];
  for (var s = 0; s < submissions.length; s++) {
    var sub = submissions[s];
    if (existing[sub.key]) continue;
    existing[sub.key] = true;  // guard duplicates within this same batch
    toAdd.push(sub);
  }
  if (!toAdd.length) return 0;

  var first = Math.max(sheet.getLastRow() + 1, 2);
  var values = toAdd.map(function (sub, i) {
    var line = first + i;
    var out = new Array(lastCol).fill('');
    out[CG_KEY - 1] = sub.key;
    out[CG_CANDIDATE - 1] = sub.candidate;
    out[CG_MUNICIPALITY - 1] = sub.municipality;
    for (var c = 4; c <= lastCol; c++) {
      var label = String(header[c - 1] || '').trim();
      if (label) out[c - 1] = statsFormula(label, line);
    }
    return out;
  });
  sheet.getRange(first, 1, values.length, lastCol).setValues(values);

  return values.length;
}


/**
 * One candidate's Category Grades cell, in whatever the category's rubric is.
 * Two of them score rather than grade and hand off below; this is the letter
 * rollup every other category uses.
 *
 * Weighted-average letter grade from the graded question rows in that
 * category's Grade tab. Question grades map onto an even 0-4 scale
 * (F=0 ... A=4); the weighted average rounds to the nearest whole point and
 * back to a letter. Ungraded rows (blank Grade cell) drop out of both the
 * numerator and the weight used to normalise it, so a partly-graded candidate
 * isn't pulled toward F by the questions nobody has graded yet.
 */
function categoryFormula(category, row) {
  var tab = "'" + GRADE_PREFIX + category + "'";
  if (POINTS_CATEGORIES[category]) return pointsCategoryFormula(tab, row);
  if (SCALE_CATEGORIES[category]) return scaleCategoryFormula(tab, row, SCALE_CATEGORIES[category]);
  return '=IFERROR(INDEX({"F";"C-";"C";"B";"A"},ROUND(' +
      letterAverage(tab, row) + ',0)+1),"")';
}


/**
 * The weighted average of a letter-graded subject's grades, 0 (F) to 4 (A).
 *
 * The letter above rounds it; Category Stats divides it by the top of the scale
 * and shows it. Split out so the two cannot drift, the same reason the scored
 * rubrics' ratios are their own functions.
 */
function letterAverage(tab, row) {
  var scale = '{"F","C-","C","B","A"}';
  var candidateCol = tab + '!$B$2:$B', municipalityCol = tab + '!$C$2:$C';
  var gradeCol = tab + '!$H$2:$H', weightCol = tab + '!$I$2:$I';

  var filter = '(' + candidateCol + '=$B' + row + ')*(' + municipalityCol + '=$C' + row + ')*(' +
      gradeCol + '<>"")';
  var value = 'IFERROR(MATCH(' + gradeCol + ',' + scale + ',0)-1,0)';
  var numerator = 'SUMPRODUCT(' + filter + '*' + value + '*' + weightCol + ')';
  var denominator = 'SUMPRODUCT(' + filter + '*' + weightCol + ')';
  return numerator + '/' + denominator;
}


/**
 * Cumulative letter for a category scored in points.
 *
 * Homes for Living grade a candidate on their share of the points available to
 * them, not on an average of per-question grades: sum the points, divide by the
 * maximum for the questions their municipality was actually asked, and band the
 * ratio at 85/70/60/50. A question nobody has scored yet has no points and no
 * maximum, so it leaves both sums alone - the same courtesy the letter rollup
 * pays a partly-graded candidate.
 *
 * The ratio is floored at 0 before it is banded, because housing scores can be
 * negative and so can their total. MATCH against a band table starting at 0
 * returns #N/A below it, IFERROR would blank the cell, and a blank cell here
 * means "not graded yet" - so the candidate who had most clearly earned an F
 * would be the one showing no grade. MAX pins them to the bottom band. The
 * points and the percentage the website publishes are untouched; only the
 * letter stops, at the F it would have stopped at anyway.
 *
 * The incumbent record is the one row not summed in with the rest. It carries
 * RECORD_SHARE of the topic whatever it is scored out of, so the two shares are
 * worked out against their own maxima and blended 70/30. Summing it in would
 * instead give it the share its points happen to be of the total, which is a
 * different number on every candidate and none of them 30%.
 *
 * An unscored record leaves its maximum at 0 and the blend collapses to the
 * questionnaire alone: the whole of the rule for a challenger, and the right
 * reading for an incumbent nobody has scored yet. A record scored with no Max
 * points collapses the same way rather than dividing by zero and blanking the
 * grade; Grading > Check setup reports it.
 *
 * Typed-over-able, exactly as the letter rollup is: the partner org replacing
 * this with their own call is the intended use, not a mistake.
 */
function pointsCategoryFormula(tab, row) {
  return '=' + bandExpression(pointsRatio(tab, row), POINTS_LETTERS, POINTS_BANDS);
}


/** The share of the available points, blend and floor included, as a fragment. */
function pointsRatio(tab, row) {
  var where = tab + '!$B:$B,$B' + row + ',' + tab + '!$C:$C,$C' + row;
  var asked = tab + '!$D:$D,"<>' + RECORD_LABEL + '"';
  var record = tab + '!$D:$D,"' + RECORD_LABEL + '"';
  var scored = tab + '!$H:$H,"<>"';

  var points = 'SUMIFS(' + tab + '!$H:$H,' + where + ',' + asked + ')';
  var max = 'SUMIFS(' + tab + '!$I:$I,' + where + ',' + asked + ',' + scored + ')';
  var recordPoints = 'SUMIFS(' + tab + '!$H:$H,' + where + ',' + record + ')';
  var recordMax = 'SUMIFS(' + tab + '!$I:$I,' + where + ',' + record + ',' + scored + ')';

  var questionnaire = points + '/' + max;
  var blended = (1 - RECORD_SHARE) + '*' + questionnaire + '+' +
      RECORD_SHARE + '*' + recordPoints + '/' + recordMax;
  return 'MAX(IF(' + recordMax + '=0,' + questionnaire + ',' + blended + '),0)';
}


/**
 * A ratio banded into a letter, as a formula fragment.
 *
 * One shape for both rubrics, which is the point: the thresholds and the
 * letters are the org's own, and they disagree. Mirrors band_expression() in
 * grading_tabs.py; the two render the same string.
 */
function bandExpression(ratio, letters, bands) {
  return 'IFERROR(INDEX(' + letters + ',MATCH(' + ratio + ',' + bands + ',1)),"")';
}


/**
 * Cumulative letter for a category scored on a fixed 0-N scale.
 *
 * Victori'us score every arts question 0-3 and weight the questions against
 * each other, so the topic grade is the weighted average of those scores as a
 * share of a straight 3, banded at 86/70/60. A question nobody has scored yet
 * drops out of the total and out of the weight it is divided by, the same
 * courtesy the letter rollup pays a partly-graded candidate.
 *
 * Two things about the shape are deliberate. The score is read through MATCH
 * rather than multiplied, exactly as the letter rollup reads a letter through
 * MATCH: SUMPRODUCT evaluates the whole column, and a column of mostly-empty
 * cells cannot be multiplied - one "" in it and the arithmetic is #VALUE!
 * before the filter gets a say. And ISNUMBER, not <>"", is what decides whether
 * a row counts, so a letter left behind from before the rubric changed drops
 * out of the weight as well as the total instead of scoring a silent zero.
 *
 * Typed-over-able, exactly as the letter rollup is: the partner org replacing
 * this with their own call is the intended use, not a mistake.
 */
function scaleCategoryFormula(tab, row, ceiling) {
  return '=' + bandExpression(scaleRatio(tab, row, ceiling), SCALE_LETTERS, SCALE_BANDS);
}


/** The weighted average as a share of the scale, as a formula fragment. */
function scaleRatio(tab, row, ceiling) {
  var scoreCol = tab + '!$H$2:$H', weightCol = tab + '!$I$2:$I';
  var scale = [];
  for (var n = 0; n <= ceiling; n++) scale.push(n);

  var rows = '(' + tab + '!$B$2:$B=$B' + row + ')*(' + tab + '!$C$2:$C=$C' + row +
      ')*ISNUMBER(' + scoreCol + ')';
  var value = 'IFERROR(MATCH(' + scoreCol + ',{' + scale.join(';') + '},0)-1,0)';
  var earned = 'SUMPRODUCT(' + rows + '*' + value + '*' + weightCol + ')';
  var available = '(' + ceiling + '*SUMPRODUCT(' + rows + '*' + weightCol + '))';

  return earned + '/' + available;
}


/**
 * One cell of Category Stats: the figure the letter beside it was banded from.
 *
 * Three rubrics, three meanings, one column: a share of the points available on
 * a points subject, a share of the scale on a scale subject, and a position on
 * the A-F scale on a letter-graded one, which is why the tab's own header says
 * the columns are not all the same measure. Mirrors subject_ratio() and
 * stats_formula() in grading_tabs.py; the two render the same string.
 *
 * IFERROR and no floor: a candidate nobody has graded on this subject divides by
 * zero, and blank is the honest answer. Housing's floor is inside pointsRatio(),
 * where the letter reads it too.
 */
function statsFormula(category, row) {
  var tab = "'" + GRADE_PREFIX + category + "'";
  var ratio;
  if (POINTS_CATEGORIES[category]) {
    ratio = pointsRatio(tab, row);
  } else if (SCALE_CATEGORIES[category]) {
    ratio = scaleRatio(tab, row, SCALE_CATEGORIES[category]);
  } else {
    ratio = letterAverage(tab, row) + '/' + (VALID_GRADE_COUNT - 1);
  }
  return '=IFERROR(' + ratio + ',"")';
}



/**
 * Points-scored questions with no maximum on their registry row.
 *
 * A blank maximum divides nothing by nothing: the question's score still counts
 * towards the total while contributing zero to what that total is out of, so
 * every candidate who answered it reads better than they are. Worth catching
 * from a menu item rather than from a candidate's page.
 */
function maxPointsProblems(category) {
  var problems = [];
  var reg = sheet(REGISTRY_TAB);
  var last = reg.getLastRow();
  if (last < 2) return problems;

  var rows = reg.getRange(2, 1, last - 1, REGISTRY_MAX_COLUMN).getValues();
  for (var i = 0; i < rows.length; i++) {
    var label = String(rows[i][0] || '').trim();
    if (!label || String(rows[i][1] || '').trim() !== category) continue;
    if (String(rows[i][4] || '').trim().toLowerCase() !== 'yes') continue;
    if (!Number(rows[i][REGISTRY_MAX_COLUMN - 1])) {
      // The record row fails differently: it is not summed into the total, so a
      // missing maximum does not flatter anybody. It just stops the record
      // counting at all, and every incumbent is quietly graded on the
      // questionnaire alone.
      problems.push(label === RECORD_LABEL
        ? label + ' has no Max points, so no incumbent\'s record counts towards ' +
          'their ' + category + ' grade. Homes for Living set that number.'
        : label + ' has no Max points, so it counts towards the ' + category +
          ' score without adding to what that score is out of.');
    }
  }
  return problems;
}

/* --------------------------------------------------------------------- roster */

/**
 * Every confirmed candidate, keyed name|municipality, to whether they are sitting.
 *
 * A boolean per candidate rather than a set of incumbents, so the caller can
 * tell "on the roster, a challenger" from "not on the roster at all". The
 * second is worth knowing: it means a submission's name or municipality does
 * not match what the coalition publishes, and until it does, nobody can tell
 * from here whether that person is an incumbent.
 *
 * Returns null when the roster could not be read, which the callers treat as
 * "create no record rows this run" rather than as "nobody is an incumbent".
 * Cached for ROSTER_CACHE_SECONDS: the file changes daily at most, and every
 * sweep of a 60-row sheet would otherwise fetch it again.
 */
function incumbentIndex() {
  var cache = CacheService.getScriptCache();
  var cached = cache.get(ROSTER_CACHE_KEY);
  if (cached) {
    try { return JSON.parse(cached); } catch (err) { /* refetch below */ }
  }

  var text;
  try {
    var response = UrlFetchApp.fetch(ROSTER_URL, {
      muteHttpExceptions: true, followRedirects: true
    });
    if (response.getResponseCode() !== 200) {
      log('system', 'roster unavailable', 'HTTP ' + response.getResponseCode() +
          ' from the published candidate roster; no ' + RECORD_LABEL +
          ' rows created this run');
      return null;
    }
    text = response.getContentText();
  } catch (err) {
    log('system', 'roster unavailable', 'could not read the published candidate ' +
        'roster (' + err + '); no ' + RECORD_LABEL + ' rows created this run');
    return null;
  }

  var index = parseRoster(text);
  if (!index) {
    log('system', 'roster unavailable', 'the published candidate roster parsed ' +
        'to no candidates; no ' + RECORD_LABEL + ' rows created this run');
    return null;
  }
  cache.put(ROSTER_CACHE_KEY, JSON.stringify(index), ROSTER_CACHE_SECONDS);
  return index;
}


/**
 * _data/candidates.yml as {name|municipality: is a sitting incumbent}.
 *
 * Line-based rather than a YAML parser, because Apps Script has none and the
 * file is a flat list of "- name:" blocks with two-space keys under each. The
 * same shape load_candidate_index() in sync-questionnaire.py reads, and the
 * file's own header comment promises it stays that way.
 *
 * Null rather than an empty object when nothing parsed: an empty index would be
 * indistinguishable from a roster in which nobody is an incumbent.
 */
function parseRoster(text) {
  var lines = String(text || '').split(/\r?\n/);
  var index = {}, current = null, total = 0;

  var flush = function () {
    if (!current || !current.name || !current.municipality) return;
    index[rosterKey(current.name, current.municipality)] =
        ROSTER_INCUMBENT_RE.test(current.standing || '');
    total++;
  };

  for (var i = 0; i < lines.length; i++) {
    var trimmed = lines[i].replace(/^\s+/, '');
    if (!trimmed || trimmed.charAt(0) === '#') continue;

    if (trimmed.indexOf('- name:') === 0) {
      flush();
      current = { name: yamlValue(trimmed.substring('- name:'.length)) };
    } else if (!current) {
      continue;
    } else if (trimmed.indexOf('municipality:') === 0) {
      current.municipality = yamlValue(trimmed.substring('municipality:'.length));
    } else if (trimmed.indexOf('standing:') === 0) {
      current.standing = yamlValue(trimmed.substring('standing:'.length));
    }
  }
  flush();

  return total ? index : null;
}


/** A scalar YAML value: quotes off, and `null` read as absent. */
function yamlValue(text) {
  var value = String(text || '').trim().replace(/^["']|["']$/g, '');
  return (value === 'null' || value === '~') ? '' : value;
}


/**
 * How a candidate is looked up in the roster.
 *
 * The two sides spell a municipality differently - the submission sheet holds
 * what the form offered ("View Royal"), the roster holds the site's slug
 * ("view-royal") - so both are slugged rather than compared as written. The
 * name is only case- and space-normalised, which is what sync-questionnaire.py
 * matches Category Grades on, and it matches all 63 submissions today.
 */
function rosterKey(name, municipality) {
  return normText(name) + '|' + slugify(municipality);
}


function normText(value) {
  return String(value || '').replace(/\s+/g, ' ').trim().toLowerCase();
}


function slugify(value) {
  return normText(value).replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '');
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
      if (!label || !category || graded !== 'yes') continue;

      // The incumbent record is the one graded row with no columns behind it:
      // nobody was asked it, so there is no answer to read and no variants to
      // group. Every other row without a span is a half-filled registry row and
      // is skipped, which is what stops it fanning empty answers out to
      // everybody.
      var isRecord = (label === RECORD_LABEL);
      var variants = [];
      if (!isRecord) {
        if (!span) continue;
        var bounds = span.split('-');
        var from = parseInt(bounds[0], 10);
        var to = parseInt(bounds[bounds.length - 1], 10);
        if (!from || !to) continue;
        // The payload path matches on labels and never touches raw columns, so it
        // passes no header and gets no variant grouping.
        variants = header ? groupVariants(header, from, to) : [];
      }

      questions.push({
        label: label,
        category: category,
        text: text,
        record: isRecord,
        variants: variants
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
 * chosen, and a ticked "Other" carries what was written beside it rather than
 * its own label. A question with a written follow-up (GOV-01, CLI-01, ART-01,
 * ROL-01) keeps both parts, because they earn one grade between them.
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
      var opt = variant.options[o];
      if (!isTicked(row[opt.column - 1])) continue;
      if (/^other\b/i.test(opt.text) && variant.plain.length) {
        var written = otherText(row[variant.plain[0].column - 1], variant, row, opt.column);
        chosen.push(written ? 'Other: ' + written : opt.text);
      } else {
        chosen.push(opt.text);
      }
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


/**
 * What a candidate wrote beside a ticked "Other".
 *
 * Tally gives an "Other" option no column of its own. The checkbox column says
 * only that it was ticked; the text itself is joined into the question's own
 * column, comma-separated, among the labels of every other option ticked and in
 * no fixed position. So subtract those labels and what is left is what they
 * wrote: HFL-04, ART-05 and ART-08 are the three questions this applies to.
 *
 * Returns '' when the subtraction leaves nothing - a candidate who ticked
 * "Other" and typed nothing - so the caller can fall back to the bare label.
 */
function otherText(summary, variant, row, otherColumn) {
  var rest = String(summary === null || summary === undefined ? '' : summary);

  for (var i = 0; i < variant.options.length; i++) {
    var opt = variant.options[i];
    if (opt.column === otherColumn || !isTicked(row[opt.column - 1])) continue;
    // First occurrence only: a label that also appears inside the written text
    // should lose the standalone copy, which Tally joins in first.
    var at = rest.indexOf(opt.text);
    if (at >= 0) rest = rest.substring(0, at) + rest.substring(at + opt.text.length);
  }

  return rest.replace(/\s*,\s*/g, ', ').replace(/^[\s,]+/, '').replace(/[\s,]+$/, '');
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
  ScriptApp.newTrigger('timerSync').timeBased().everyDays(1).create();
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
    // A category scored in points has no weights to total: the points are the
    // weighting. What it needs instead is a maximum on every one of its
    // questions, because a blank one silently drops that question out of the
    // denominator and flatters every candidate who answered it.
    //
    // A category scored on a scale is checked like any other: its questions
    // carry ordinary weights, and those weights still have to total 100%.
    if (POINTS_CATEGORIES[c]) {
      problems = problems.concat(maxPointsProblems(c));
      continue;
    }
    var total = Math.round(weights[c] * 1000) / 1000;
    if (total !== 1) problems.push(c + ' weights total ' + Math.round(total * 100) + '%, not 100%.');
  }

  if (!ss.getSheetByName(CATEGORY_TAB)) problems.push('No tab "' + CATEGORY_TAB + '".');

  var triggers = ScriptApp.getProjectTriggers().map(function (t) { return t.getHandlerFunction(); });
  if (triggers.indexOf('timerSync') === -1) problems.push('No daily timer (Grading > Set up).');
  if (triggers.indexOf('onGradeEdit') === -1) problems.push('No grader-stamp trigger (Grading > Set up).');

  // The record row depends on a file this spreadsheet does not own, so say what
  // that file currently says rather than leaving it to be discovered when the
  // rows do not appear.
  var roster = incumbentIndex();
  var summary = '';
  if (!roster) {
    problems.push('The published candidate roster could not be read, so no ' +
                  RECORD_LABEL + ' row is being created for anybody. See Sync Log.');
  } else {
    var listed = 0, sitting = 0, missing = [];
    for (var who in roster) {
      listed++;
      if (roster[who]) sitting++;
    }
    var raw = ss.getSheetByName(RAW_TAB).getDataRange().getValues();
    for (var r = 1; r < raw.length; r++) {
      var key = rosterKey(candidateName(raw[r]),
                          String(raw[r][COL_MUNICIPALITY - 1] || ''));
      if (!(key in roster) && missing.indexOf(key) === -1) missing.push(key);
    }
    if (missing.length) {
      problems.push(missing.length + ' submission(s) match no confirmed candidate ' +
                    'on the roster, so nothing here knows whether they are ' +
                    'incumbents: ' + missing.join(', '));
    }
    summary = '\n\nRoster: ' + listed + ' confirmed candidates, ' + sitting +
        ' sitting incumbents. Each of those who has submitted gets a ' +
        RECORD_LABEL + ' row worth ' + Math.round(RECORD_SHARE * 100) +
        '% of their housing grade.';
  }

  SpreadsheetApp.getUi().alert(problems.length
    ? 'Problems:\n\n- ' + problems.join('\n- ')
    : 'All good.\n\n' + questions.length + ' graded questions across ' +
      Object.keys(counts).length + ' subjects.' + summary);
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
