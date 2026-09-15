---
layout: default
title: Scorecard stats
permalink: /stats/
description: >-
  The 2026 Capital Regional District municipal election scorecard in numbers:
  how many candidates are confirmed, how many have returned the coalition
  questionnaire, and how the published grades are distributed.
---

{%- comment -%}
  The scorecard, counted. Every figure comes from site.data.scorecard_stats,
  which _plugins/scorecard_stats.rb derives at build time from the same files
  the scorecard, the candidate pages and /questionnaire/ render: nothing on this
  page is typed in, so it cannot drift from the pages it describes and it moves
  on its own with the nightly syncs.

  A separate page rather than a band at the top of /scorecard/. The scorecard
  answers "where does my candidate stand", and a reader who arrives with that
  question should not have to scroll past a page of aggregate charts to reach
  the one row they came for. This is the page for the other reader — a
  journalist, a partner organization, a volunteer deciding which municipality
  needs chasing.

  Charts are plain HTML and CSS: a table of real rows with a bar drawn in the
  value cell. No chart library, no canvas, nothing that needs JavaScript to
  paint a number that was known at build time. Every bar's value is printed
  beside it as text, so the bars can fail to load, fail to print or be invisible
  to a reader and the page still says everything it knows.
{%- endcomment -%}
{%- assign stats = site.data.scorecard_stats -%}
{%- assign grades_released = site.data.deadlines | where: "id", "grades-released" | first -%}

<div class="page-header">
  <div class="container">
    <h1>Scorecard stats</h1>
    <p class="page-header__note">
      The <a href="{{ '/scorecard/' | relative_url }}">2026 candidate scorecard</a>
      in numbers. This data is updated in-tandem with the main scorecard page.
    </p>
  </div>
</div>

<div class="container page-content stats">
  {%- comment -%}
    The release-date sentences, on the same terms as the ones in the intro to
    /scorecard/: they answer the question a reader arrives with before the
    release, and afterwards they answer a question nobody is asking any more,
    so they are dropped once the date has passed. The same end-of-day sum as
    _includes/deadline-list.html and scorecard/index.md — 24 hours to the end
    of the day plus 8 for PST — so the three never disagree about whether the
    date has passed.
  {%- endcomment -%}
  {%- assign release_end = grades_released.date | date: "%s" | plus: 115200 -%}
  {%- assign now_ts = site.time | date: "%s" | plus: 0 -%}
  <p>
    The <a href="{{ '/scorecard/' | relative_url }}">2026 candidate scorecard</a>
    as numbers: who is confirmed, who has replied, how the field splits, and how
    the grades fall once they are published. Every figure is counted from the
    same data the scorecard is built from. No candidate is named here; for how
    one person answered, open their own page from the scorecard.
    {%- if now_ts < release_end %}
    <strong>The grade figures stay empty until the release date.</strong> We
    publish responses and grades together on
    {{ grades_released.date | date: "%B %-d, %Y" }}, so until then these counts
    are about who has replied, not how anyone scored.
    {%- endif %}
  </p>

  {%- comment -%}
    The reply rate as a hero figure rather than as one tile among four: it is
    the number this page exists to report, it is the one that moves between
    builds, and it is the one a reader can do something about. The tiles below
    it are context for it — they are the denominators.
  {%- endcomment -%}
  <section class="stats-section" aria-labelledby="participation">
    {%- comment -%}
      The section heading lives inside the box rather than above it: the box is
      the section's headline figure, and a heading sitting outside it read as a
      label for everything below, tiles and municipality table included.
    {%- endcomment -%}
    {%- comment -%}
      One panel, built like the scorecard matrix it summarises: an inky header
      band over a white body inside the same heavy frame, with hairline rules
      between the counts.

      It was four separate boxes: the rate in a big one and the three
      denominators in small ones below it, which drew four things of equal
      weight and left the figure that matters competing with its own context.
      The three counts are inside it now, under a rule, where they read as what
      the rate is measured against.
    {%- endcomment -%}
    <div class="stat-hero">
      <h2 class="stat-hero__title" id="participation">Questionnaire replies</h2>
      <div class="stat-hero__body">
        <p class="stat-hero__figure">{{ stats.returned_percent | round }}%</p>

        <div class="stat-hero__detail">
          <p class="stat-hero__caption">
            of confirmed candidates have returned the coalition questionnaire:
            <strong>{{ stats.returned_count }}</strong> of
            <strong>{{ stats.candidate_count }}</strong>, with
            {{ stats.outstanding_count }} still outstanding.
          </p>
          {%- comment -%}
            A meter, not a two-slice pie: one ratio against one limit. Track and
            fill are the same two colours every bar further down the page uses,
            so "the rest of the field" is not drawn as a second thing with a
            meaning of its own.
          {%- endcomment -%}
          <span class="stat-meter" aria-hidden="true">
            <span class="stat-meter__fill" style="width: {{ stats.returned_percent }}%"></span>
          </span>
        </div>

        <ul class="stat-tiles">
          <li class="stat-tile">
            <span class="stat-tile__figure">{{ stats.candidate_count }}</span>
            <span class="stat-tile__label">confirmed candidates</span>
          </li>
          <li class="stat-tile">
            <span class="stat-tile__figure">{{ stats.municipalities.size }}</span>
            <span class="stat-tile__label">municipalities with candidates</span>
          </li>
          <li class="stat-tile">
            <span class="stat-tile__figure">{{ stats.questions.total }}</span>
            <span class="stat-tile__label">questions asked, {{ stats.questions.graded }} graded</span>
          </li>
        </ul>
      </div>
    </div>

    <h3>Replies by municipality</h3>
    <p>
      Ordered by reply rate. A municipality is listed once it has confirmed
      candidates, whether or not any of them have replied; the four electoral
      areas elect a regional director rather than a council and are outside the
      scorecard's scope.
    </p>
    {%- comment -%}
      A real table, with the bar drawn inside the value cell. The table view a
      chart is supposed to have a twin of is the chart here, which is why there
      is no toggle: a screen reader gets the row header and the numbers, and the
      bar is aria-hidden decoration on top of them.
    {%- endcomment -%}
    <table class="statbars">
      <caption class="sr-only">Questionnaires returned by municipality, of confirmed candidates</caption>
      <thead class="sr-only">
        <tr>
          <th scope="col">Municipality</th>
          <th scope="col">Questionnaires returned</th>
        </tr>
      </thead>
      <tbody>
        {%- for row in stats.municipalities %}
        <tr>
          <th scope="row" class="statbars__label">
            <a href="{{ '/scorecard/' | append: row.slug | append: '/' | relative_url }}">{{ row.name }}</a>
          </th>
          <td class="statbars__cell">
            <span class="statbars__track" aria-hidden="true">
              <span class="statbars__fill" style="width: {{ row.percent }}%"></span>
            </span>
            <span class="statbars__value">
              {{ row.returned }} <span class="statbars__unit">of {{ row.total }}</span>
              <span class="statbars__pct">{{ row.percent | round }}%</span>
            </span>
          </td>
        </tr>
        {%- endfor %}
      </tbody>
    </table>
  </section>

  {%- comment -%}
    The grade distribution. Keyed off published_count rather than off the
    release date: the date says when grades are meant to appear, the count says
    whether any actually have, and only one of those two is a fact about this
    build. A calendar check would announce grades on a day the sheet had not
    released them.
  {%- endcomment -%}
  <section class="stats-section" aria-labelledby="grades">
    <h2 class="section-title" id="grades">Grades</h2>
    {%- if stats.grades.total == 0 %}
    <div class="callout">
      <p>
        <strong>No grades are published yet.</strong> Responses and grades are
        released together on
        <strong>{{ grades_released.date | date: "%B %-d, %Y" }}</strong>, so
        until then every returned questionnaire shows an hourglass rather than a
        letter and there is no distribution to draw. The reply counts above are
        live in the meantime.
        <a href="{{ '/faq/#methodology' | relative_url }}">How the grading works</a>
        explains what happens between a reply arriving and a letter appearing.
      </p>
    </div>
    {%- else %}
    <p>
      Every published letter on the scorecard, counted once per candidate per
      topic: <strong>{{ stats.grades.total }}</strong> grades across
      {{ stats.published_count }} candidates. Only the seven topics the coalition
      grades are counted — General and Healthcare access carry no graded
      question, so no letter is ever awarded in them.
    </p>
    <table class="statbars statbars--grades">
      <caption class="sr-only">Distribution of published letter grades</caption>
      <thead class="sr-only">
        <tr>
          <th scope="col">Grade</th>
          <th scope="col">Grades awarded</th>
        </tr>
      </thead>
      <tbody>
        {%- for row in stats.grades.letters %}
        <tr>
          <th scope="row" class="statbars__label statbars__label--grade">
            {% include grade-badge.html grade=row.letter %}
            <span class="statbars__grade-name">{{ row.label }}</span>
          </th>
          <td class="statbars__cell">
            {%- comment -%}
              The letter's own colour, which is the colour the same grade wears
              in every cell of the scorecard matrix. A grade is the one thing on
              this site whose colour already carries meaning, and repainting it
              here in the brand purple would make the reader learn a second
              scale for the same five marks.
            {%- endcomment -%}
            {%- assign grade_class = row.letter | downcase -%}
            {%- if row.letter == 'C-' -%}{%- assign grade_class = 'c-minus' -%}{%- endif -%}
            <span class="statbars__track" aria-hidden="true">
              <span class="statbars__fill statbars__fill--{{ grade_class }}" style="width: {{ row.percent }}%"></span>
            </span>
            <span class="statbars__value">
              {{ row.count }}
              <span class="statbars__pct">{{ row.percent | round }}%</span>
            </span>
          </td>
        </tr>
        {%- endfor %}
      </tbody>
    </table>

    <h3>By topic</h3>
    <p>
      The same grades, split by the topic they were awarded in. Each bar is one
      topic's full set of grades, so the segments read left to right from the
      best mark to the worst.
    </p>
    <table class="statbars statbars--stacked">
      <caption class="sr-only">Distribution of published letter grades by topic</caption>
      <thead class="sr-only">
        <tr>
          <th scope="col">Topic</th>
          <th scope="col">Grades awarded, by letter</th>
        </tr>
      </thead>
      <tbody>
        {%- for subject in stats.grades.subjects %}
        <tr>
          <th scope="row" class="statbars__label">{{ subject.name }}</th>
          <td class="statbars__cell">
            <span class="statbars__stack" aria-hidden="true">
              {%- for row in subject.letters -%}
              {%- if row.count > 0 -%}
              {%- assign grade_class = row.letter | downcase -%}
              {%- if row.letter == 'C-' -%}{%- assign grade_class = 'c-minus' -%}{%- endif -%}
              <span class="statbars__seg statbars__seg--{{ grade_class }}" style="width: {{ row.percent }}%"></span>
              {%- endif -%}
              {%- endfor -%}
            </span>
            {%- comment -%}
              The counts spelled out rather than labelled inside the segments. A
              segment holding one grade out of thirty is a few pixels wide and
              cannot carry a legible label, and a label that only appears on the
              wide segments tells the reader the narrow ones are worth less than
              they are.
            {%- endcomment -%}
            <span class="statbars__value statbars__value--counts">
              {%- for row in subject.letters -%}
              {%- if row.count > 0 %}<span class="statbars__count">{{ row.letter }} {{ row.count }}</span>{% endif -%}
              {%- endfor -%}
            </span>
          </td>
        </tr>
        {%- endfor %}
      </tbody>
    </table>
    {%- endif %}
  </section>

  <section class="stats-section" aria-labelledby="field">
    <h2 class="section-title" id="field">Who is running</h2>
    <p>
      The confirmed field, as the coalition's candidate tracking records it.
      "Not stated" is exactly that — the tracking sheet does not say, and this
      site does not guess.
    </p>

    <h3>Office sought</h3>
    <table class="statbars">
      <caption class="sr-only">Confirmed candidates by office sought</caption>
      <thead class="sr-only">
        <tr>
          <th scope="col">Office</th>
          <th scope="col">Candidates</th>
        </tr>
      </thead>
      <tbody>
        {%- for row in stats.offices %}
        <tr>
          <th scope="row" class="statbars__label">{{ row.label }}</th>
          <td class="statbars__cell">
            <span class="statbars__track" aria-hidden="true">
              <span class="statbars__fill" style="width: {{ row.percent }}%"></span>
            </span>
            <span class="statbars__value">
              {{ row.count }}
              <span class="statbars__pct">{{ row.percent | round }}%</span>
            </span>
          </td>
        </tr>
        {%- endfor %}
      </tbody>
    </table>

    <h3>Incumbency</h3>
    <p>
      Grouped by whether a candidate holds elected office now, used to, or is
      standing for the first time. Incumbency is role-specific on a candidate's
      own row — a sitting councillor running for mayor is not the incumbent
      mayor — and those two land in the same bucket here.
    </p>
    <table class="statbars">
      <caption class="sr-only">Confirmed candidates by incumbency</caption>
      <thead class="sr-only">
        <tr>
          <th scope="col">Standing</th>
          <th scope="col">Candidates</th>
        </tr>
      </thead>
      <tbody>
        {%- for row in stats.standings %}
        <tr>
          <th scope="row" class="statbars__label">{{ row.label }}</th>
          <td class="statbars__cell">
            <span class="statbars__track" aria-hidden="true">
              <span class="statbars__fill" style="width: {{ row.percent }}%"></span>
            </span>
            <span class="statbars__value">
              {{ row.count }}
              <span class="statbars__pct">{{ row.percent | round }}%</span>
            </span>
          </td>
        </tr>
        {%- endfor %}
      </tbody>
    </table>

    {%- if stats.slates.size > 0 %}
    <h3>Electoral organizations</h3>
    <p>
      Slates, as a share of the whole field rather than of each other: most
      candidates in this region have no slate recorded, and a chart of slate
      against slate would imply an election organized into them. Naming a slate
      is not an endorsement.
    </p>
    <table class="statbars">
      <caption class="sr-only">Confirmed candidates by electoral organization, as a share of all candidates</caption>
      <thead class="sr-only">
        <tr>
          <th scope="col">Electoral organization</th>
          <th scope="col">Candidates</th>
        </tr>
      </thead>
      <tbody>
        {%- for row in stats.slates %}
        <tr>
          <th scope="row" class="statbars__label">{{ row.label }}</th>
          <td class="statbars__cell">
            <span class="statbars__track" aria-hidden="true">
              <span class="statbars__fill" style="width: {{ row.percent }}%"></span>
            </span>
            <span class="statbars__value">
              {{ row.count }}
              <span class="statbars__pct">{{ row.percent | round }}%</span>
            </span>
          </td>
        </tr>
        {%- endfor %}
      </tbody>
    </table>
    {%- endif %}
  </section>

  <p class="content-follow-up">
    Back to <a href="{{ '/scorecard/' | relative_url }}">the scorecard</a>, or
    read <a href="{{ '/questionnaire/' | relative_url }}">the questionnaire</a>
    and <a href="{{ '/faq/#methodology' | relative_url }}">how the grading works</a>.
  </p>
</div>
