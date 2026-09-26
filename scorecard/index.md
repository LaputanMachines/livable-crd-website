---
layout: default
title: 2026 Candidate Scorecard
permalink: /scorecard/
description: >-
  Where Capital Regional District municipal candidates stand on transit,
  housing, climate, and arts in the 2026 election. Search or filter by
  municipality.
---

<div class="page-header">
  <div class="container">
    <h1>2026 candidate scorecard</h1>
    {%- comment -%}
      The correction line, in the header rather than in a banner further down.
      It is the one thing on this page that asks the reader for something, and
      the ask is about the list as a whole, so it belongs beside the title of
      the list rather than in a box the reader meets after the intro copy.

      Kept to a request rather than an announcement: the only thing this line is
      for is catching the errors a reader can see and we cannot. Everything it
      used to say about how the list is built lives in the
      /faq/#how-candidates-are-added panel, which is still linked from the
      deadlines FAQ and still reachable by its own heading.
    {%- endcomment -%}
    <p class="page-header__note">
      Someone missing or listed incorrectly?
      <a href="mailto:{{ site.email }}?subject=Scorecard%20correction">Tell us</a>
      by emailing {{ site.email }}.
    </p>
  </div>
</div>

<div class="container page-content">
  {%- comment -%}
    Two paragraphs: what this is, and how to work it. They used to be one, which
    ran what the page is into how to search it into when the grades appear, and
    a reader looking for any of the three read all three.

    The release date stays in the first, rather than only in the #deadlines panel
    at the foot of the page: a reader arriving at a table of hourglasses asks
    when the grades appear before they ask anything else, and the answer was
    three screens below them. It is dropped once the date has gone, because
    after the release it answers a question nobody on this page is asking any
    more and the grades themselves are the answer. The same end-of-day sum as
    _includes/deadline-list.html — 24 hours to the end of the day plus 8 for PST
    — so the two never disagree about whether the date has passed.
  {%- endcomment -%}
  {%- assign grades_released = site.data.deadlines | where: "id", "grades-released" | first -%}
  {%- assign release_end = grades_released.date | date: "%s" | plus: 115200 -%}
  {%- assign now_ts = site.time | date: "%s" | plus: 0 -%}
  <p>
    Every confirmed candidate in the Capital Regional District, and where they
    stand across nine policy areas. All of them were sent
    <a href="{{ '/questionnaire/' | relative_url }}">the same questionnaire</a>.
    {%- if now_ts < release_end %}
    Responses and grades are published together on
    {{ grades_released.date | date: "%B %-d, %Y" }}.
    {%- endif %}
  </p>

  {%- comment -%}
    How to use the page, in the order a reader meets the controls below it:
    search, then the filters, then the table, then a candidate's own page. The
    star is last and named plainly — it is the one control here whose icon does
    not say what it does, and the only one that changes what the reader sees on
    a later visit.

    Deliberately not a list. Five short bullets above a filter bar and a
    115-row table is a page that opens with instructions; a sentence each,
    read once and never again, is what this needs to be.
  {%- endcomment -%}
  <p>
    <strong>How to use this page.</strong> Search by name or slate, or narrow
    the table with the filters: a minimum grade overall or in one topic, office, and
    municipality. Every row is one candidate and every column one topic, and the
    key under the filters says what each mark means. Open a candidate's name for
    their full answers, how each one was graded, and a scorecard you can print.
    The star pins a candidate to the top of the table on this device.
  </p>

  <div class="scorecard-controls">
    <label for="candidate-search" class="sr-only">Search candidates by name or slate</label>
    <input type="search" id="candidate-search" class="scorecard-search" placeholder="Search by name or slate…" autocomplete="off">
  </div>

  <div class="scorecard-filterbar">
    <div class="scorecard-filtergroup">
      <span class="scorecard-filtergroup__label" id="grade-filter-label">Minimum grade</span>
      <div class="scorecard-gradefilter">
        <div class="scorecard-filters" role="group" aria-labelledby="grade-filter-label">
          <button type="button" class="filter-pill is-active" data-grade="all" aria-pressed="true">All</button>
          <button type="button" class="filter-pill" data-grade="2" aria-pressed="false">C or better</button>
          <button type="button" class="filter-pill" data-grade="3" aria-pressed="false">B or better</button>
          <button type="button" class="filter-pill" data-grade="4" aria-pressed="false">A only</button>
        </div>
        {%- comment -%}
          Where the minimum applies. "Overall" (the default) asks it of every
          topic the candidate has a letter in, so "B or better overall" means
          no topic below a B. "In" asks it of one topic, picked in the second
          select, which only shows while "in" is chosen.
        {%- endcomment -%}
        <select id="grade-scope" class="scorecard-topic-select" aria-label="Where the minimum grade applies">
          <option value="overall">overall</option>
          <option value="topic">in</option>
        </select>
        <select id="topic-filter" class="scorecard-topic-select" aria-label="Topic" hidden>
          {% for subject in site.data.subjects %}
          <option value="{{ subject.id }}">{{ subject.name }}</option>
          {% endfor %}
        </select>
      </div>
    </div>

    <div class="scorecard-filtergroup">
      <span class="scorecard-filtergroup__label" id="office-filter-label">Office</span>
      <div class="scorecard-filters" id="office-filters" role="group" aria-labelledby="office-filter-label">
        <button type="button" class="filter-pill is-active" data-office="all" aria-pressed="true">All</button>
        <button type="button" class="filter-pill" data-office="mayor" aria-pressed="false">Mayor</button>
        <button type="button" class="filter-pill" data-office="councillor" aria-pressed="false">Councillor</button>
      </div>
    </div>

    {%- comment -%}
      Narrows the table to the candidates who returned the questionnaire,
      hiding everyone who sent nothing back. On by default; the script presses
      it on load, so without scripting the button is unpressed over a table
      that is showing everyone, which is what it says. Drawn from the same
      questionnaire_returned flag as the reply count in each heading, so the
      two cannot disagree. Needs assets/js/scorecard.js, like every pill here.
    {%- endcomment -%}
    <div class="scorecard-filtergroup">
      <span class="scorecard-filtergroup__label" id="participating-filter-label">Responses</span>
      <div class="scorecard-filters" role="group" aria-labelledby="participating-filter-label">
        <button type="button" class="filter-pill" id="participating-only" aria-pressed="false">Only show participating candidates</button>
      </div>
    </div>

    {%- comment -%}
      Colours every slated candidate's row by slate, across all municipalities
      at once; each municipality's band carries the key. A highlight, not a
      filter: it hides nothing. Ships `hidden` and is revealed by
      assets/js/scorecard.js, because without the script it could do nothing.
    {%- endcomment -%}
    <div class="scorecard-filtergroup" id="slate-filtergroup" hidden>
      <span class="scorecard-filtergroup__label" id="slate-filter-label">Slates</span>
      <div class="scorecard-filters" role="group" aria-labelledby="slate-filter-label">
        <button type="button" class="filter-pill" id="slate-highlight" aria-pressed="false">Highlight slate candidates</button>
      </div>
    </div>

    {%- comment -%}
      No slate filter here on purpose, only the highlight above. Slate reaches the reader through
      the search box (which matches slate as well as name), the per-municipality
      tint and its labelled legend below, and each candidate's own page, rather
      than through a fourth row of pills.

      Two reasons. The filter bar already carries grade, topic, office and
      municipality, and slate would be the least load-bearing of them: most
      candidates run unaffiliated, so the pills would cover a small minority of
      rows while every reader paid the vertical space. And because a blank slate
      is "the sheet does not say" rather than "independent", there is no honest
      pill for the majority: selecting any slate would silently hide most of
      the region.
    {%- endcomment -%}
    <div class="scorecard-filtergroup">
      <span class="scorecard-filtergroup__label" id="muni-filter-label">Municipality</span>
      {%- comment -%}
        Alphabetical, not the table's reply-count order: a reader reaching for
        a pill is looking for a place they already have in mind, and scans for
        it by name. The table below keeps its own order.
      {%- endcomment -%}
      {%- assign pill_munis = site.data.municipalities | sort: "name" -%}
      <div class="scorecard-filters" role="group" aria-labelledby="muni-filter-label">
        <button type="button" class="filter-pill is-active" data-muni="all" aria-pressed="true">All</button>
        {% for muni in pill_munis %}
          {% assign mc = site.data.candidates | where: "municipality", muni.slug %}
          {% if mc.size > 0 %}
          <button type="button" class="filter-pill" data-muni="{{ muni.slug }}" aria-pressed="false">{{ muni.name }} ({{ mc.size }})</button>
          {% endif %}
        {% endfor %}
      </div>
    </div>
  </div>

  <p class="scorecard-count" id="candidate-count" role="status" aria-live="polite"></p>

  {%- comment -%}
    Directly above the grid rather than up near the intro. Most cells in the
    table are one of the three states that are not letters, and a key read
    several screens earlier is a key nobody still has in mind by the time they
    reach the thing it describes.

    Without the declined X: a candidate who declined gets one full-width link to
    their statement on this grid rather than a mark per topic, so the key would
    be naming something the table below never draws.
  {%- endcomment -%}
  {% include grade-legend.html omit="declined" %}

  {%- comment -%}
    Every full-width row in the matrix spans this. Derived rather than typed:
    the columns are the name column plus one per topic, so a topic added to or
    dropped from _data/subjects.yml has to move it. A stale literal here is not
    a cosmetic bug — a colspan wider than the header row invents a column the
    <thead> never declared, and it renders as an empty band inside the table
    border for the whole length of the page.
  {%- endcomment -%}
  {%- assign matrix_columns = site.data.subjects.size | plus: 1 -%}
  <div class="table-scroll scorecard-matrix-scroll">
    <table class="scorecard-matrix" id="candidate-grid">
      <thead>
        <tr>
          <th scope="col" class="scorecard-matrix__name-h">Candidate</th>
          {% for subject in site.data.subjects %}
          <th scope="col" class="scorecard-matrix__col" title="{{ subject.name }}">
            <img class="scorecard-matrix__icon" src="{{ '/assets/images/icons/' | append: subject.icon | relative_url }}" alt="" width="22" height="22" loading="lazy">
            {%- comment -%}
              `abbr` wins wherever a topic defines one: the columns are equal
              width, so a long label would either overflow its column or force
              every other column wider. The full name stays on the `title`
              tooltip above and in the .sr-only span below.
            {%- endcomment -%}
            <span class="scorecard-matrix__th-label" aria-hidden="true">{{ subject.abbr | default: subject.short | default: subject.name }}</span>
            <span class="sr-only">{{ subject.name }}</span>
          </th>
          {% endfor %}
        </tr>
      </thead>
      {% comment %}
        Favourites: a pinned group above every municipality, filled at runtime by
        assets/js/favourites.js, which MOVES rows here out of the municipality
        groups below (never copies them; a copy would count twice in
        #candidate-count and be filtered twice).

        Ships empty and `hidden` on purpose. Without JS there is nothing to pin,
        and an empty band headed "Your favourites" would promise a feature that
        is not there. The same rule holds once the script is running: with no
        favourites saved the group stays hidden rather than carrying a "click a
        star to pin someone" hint, because the stars are already visible on
        every row of the table: the hint would be a permanent second copy of an
        affordance the reader can see. Hiding it needs no extra code either: the
        group has no data-empty attribute, so scorecard.js treats it like any
        other candidate group and hides it whenever no visible row is inside.
      {% endcomment %}
      <tbody class="scorecard-matrix__group scorecard-matrix__group--fav" id="favourites-group" hidden>
        <tr class="scorecard-matrix__group-row">
          <th scope="colgroup" colspan="{{ matrix_columns }}" class="scorecard-matrix__group-head scorecard-matrix__group-head--fav">
            {%- comment -%}
              The same inner flex row as the municipality headings below, so the
              hint sits beside the label with the gap those put between a name
              and its slates.
            {%- endcomment -%}
            <span class="scorecard-matrix__group-inner">
              <span class="scorecard-matrix__group-name">Your favourites</span>
              {%- comment -%}
                Also the accessible description of every reorder handle
                (aria-describedby), so it is stated once here instead of being
                repeated inside 66 button labels.
              {%- endcomment -%}
              <span class="scorecard-matrix__group-hint" id="favourites-hint">Saved to browser. Drag to reorder.</span>
            </span>
          </th>
        </tr>
      </tbody>
      {% comment %}
        Every municipality and electoral area gets a heading, including those with
        no confirmed candidates yet: an absent heading reads as an oversight
        rather than as "nobody has announced here". Empty groups are marked
        data-empty so the filter script can hide them once a search or filter
        narrows the view.

        Ordered by how many candidates there returned the questionnaire, most
        first, rather than by the order of _data/municipalities.yml - which is
        roughly by size, and buried a small municipality where everybody replied
        under a large one where few did. The count each heading already states
        on its right-hand end is the number sorted on, so the order and the
        figure beside it cannot disagree. Computed in
        _plugins/municipality_stats.rb, because Liquid can sort an array of
        hashes by a key it already has but not by a count it would have to make
        first; ties and the empty municipalities are handled there.

        Everywhere else on the site a municipality list is something a reader
        scans for a place they already have in mind, and those keep the file's
        own order.
      {% endcomment %}
      {% for muni in site.data.municipalities_by_returned %}
        {% assign mc = site.data.candidates | where: "municipality", muni.slug %}
        <tbody class="scorecard-matrix__group" data-municipality="{{ muni.slug }}"{% if mc.size == 0 %} data-empty="true"{% endif %}>
          <tr class="scorecard-matrix__group-row">
            <th scope="colgroup" colspan="{{ matrix_columns }}" class="scorecard-matrix__group-head">
              {%- comment -%}
                The municipality name and its slate block sit on one flex row, so
                they share a vertical centre; as bare text beside an inline-flex
                box they aligned on mismatched baselines instead.

                The flex row is this inner span and not the <th>: giving a table
                cell `display: flex` takes it out of the table box model and the
                column widths collapse with it, the same reason the candidate
                name cell wraps its contents (see .scorecard-matrix__name-inner).
              {%- endcomment -%}
              <span class="scorecard-matrix__group-inner">
                {%- comment -%}
                  The municipality's own index, /scorecard/esquimalt/, generated
                  by _plugins/candidate_pages.rb. This heading is the one place
                  on the site that links to all of them, so it is what gets them
                  crawled; it is also the shortest way for a reader looking at
                  one municipality's rows to get the page that is only about
                  that municipality.

                  Only where there are candidates, matching the plugin: it
                  builds no index for a municipality with nobody confirmed, so
                  linking one here would be a link to a 404. The empty row below
                  says the same thing this link would have.
                {%- endcomment -%}
                <span class="scorecard-matrix__group-name">
                  {%- if mc.size > 0 -%}
                  <a class="scorecard-matrix__group-link" href="{{ '/scorecard/' | append: muni.slug | append: '/' | relative_url }}">{{ muni.name }}</a>
                  {%- else -%}
                  {{ muni.name }}
                  {%- endif -%}
                </span>
                {%- comment -%}
                  Slates, scoped to this municipality. A slate contests one
                  council, so its colour key belongs beside that municipality
                  rather than above the whole table, where every entry would be
                  irrelevant to all but one group. Absent from headings whose
                  municipality has no slates, which is most of them.

                  The legend is always visible: which slates are running here is
                  useful whether or not anyone wants the rows coloured, and it
                  needs no scripting, so it renders for a reader without JS too.

                  The switch that colours the rows is not here. It used to be a
                  checkbox in every band, which made the band two or three lines
                  tall on a phone, and a sticky band that tall covered much of
                  the screen while its group scrolled past. It is now a single
                  "Highlight slate candidates" pill in the filter bar above,
                  which colours every municipality at once.

                  The legend is what keeps the tint honest. Every swatch is
                  labelled with its slate and count, so the colours are decoded
                  in text rather than guessed at - which is also what keeps a
                  >8-slate region readable once two slates start sharing a
                  colour. The row itself no longer names its slate (the meta
                  line is office and standing only), so on this page the tint is
                  the only per-row cue; a reader who needs the name in text has
                  the legend, the search box, and the candidate's own page.
                {%- endcomment -%}
                {%- assign muni_slated = mc | where_exp: "c", "c.slate" -%}
                {%- if muni_slated.size > 0 -%}
                {%- assign muni_slates = muni_slated | group_by: "slate" | sort: "name" -%}
                <span class="slate-control">
                  <span class="slate-legend">
                    {%- for sg in muni_slates -%}
                    {%- if sg.name != "" -%}
                    {%- comment -%}
                      Both counts ride on the item, so scorecard.js can show the
                      one matching the table: how many of this slate the
                      "Only show participating candidates" filter keeps (those
                      who took part, and those who declined with a statement),
                      and the whole slate otherwise. The total is what prints without
                      the script.
                    {%- endcomment -%}
                    {%- assign sg_returned = sg.items | where_exp: "c", "c.questionnaire_returned or c.declined_statement" -%}
                    {%- comment -%}
                      data-slate matches the rows' own data-slate, which is how
                      scorecard.js turns this entry into a switch for that
                      slate's tint. Without the script it stays a plain key.
                    {%- endcomment -%}
                    <span class="slate-legend__item" data-slate="{{ sg.name | downcase }}" data-slate-total="{{ sg.size }}" data-slate-returned="{{ sg_returned.size }}">
                      <span class="slate-legend__swatch {{ site.data.slate_classes[sg.name] }}" aria-hidden="true"></span>{{ sg.name }} (<span class="slate-legend__count">{{ sg.size }}</span>)
                    </span>
                    {%- endif -%}
                    {%- endfor -%}
                  </span>
                </span>
                {%- endif -%}
                {%- comment -%}
                  How many of this municipality's candidates have returned the
                  questionnaire, on the right-hand end of the band. The matrix
                  answers it per row already, but only one topic at a time and
                  only in the shape of a badge, so a reader wanting "has anyone
                  here replied yet" had to read ten cells across every row of the
                  group and infer it.

                  `questionnaire_returned` is attached by
                  _plugins/questionnaire_scores.rb to every candidate the grading
                  sheet has a row for because they replied, which is the same
                  flag the hourglass badges are drawn from: the number here can
                  never disagree with the cells below it. A sitting incumbent on
                  that sheet only because Homes for Living scored their housing
                  record does not carry it, and is counted here among the
                  candidates who have not replied - which is what they are, grade
                  or no grade.

                  Static, like the slate counts and the municipality filter
                  pills: it describes the municipality, not the current search,
                  so it does not move when the filters narrow the table.
                {%- endcomment -%}
                {%- if mc.size > 0 -%}
                {%- assign muni_returned = mc | where_exp: "c", "c.questionnaire_returned" -%}
                <span class="scorecard-matrix__group-count">{{ muni_returned.size }} of {{ mc.size }} returned the questionnaire</span>
                {%- endif -%}
              </span>
            </th>
          </tr>
          {% if mc.size == 0 %}
          <tr class="scorecard-matrix__empty-row">
            <td colspan="{{ matrix_columns }}" class="scorecard-matrix__empty-cell">
              No candidates were publicly announced.
            </td>
          </tr>
          {% endif %}
          {% for c in mc %}
          {%- comment -%}
            The candidate's slug is used twice below: in the deep link and in
            data-candidate, so it is derived once, here, before the row opens.
          {%- endcomment -%}
          {%- assign cand_slug = c.name | slugify -%}
          {%- assign cand_display = c.display_name | default: c.name -%}
          {%- comment -%}
            data-candidate is the stable id assets/js/favourites.js stores. It is
            the per-candidate page's path minus the /scorecard/ prefix, so the
            saved list can be read against the URLs without parsing an href, and
            a candidate who changes municipality correctly reads as a different
            person (their page moves too).
          {%- endcomment -%}
          {%- comment -%}
            The slate palette class comes from site.data.slate_classes, built by
            _plugins/candidate_pages.rb so the row, the legend below and the
            candidate's own page all colour from one map. It only tints anything
            once the reader turns on highlighting for this municipality, which
            marks the row .is-slate-lit.
          {%- endcomment -%}
          {%- assign slate_class = site.data.slate_classes[c.slate] -%}
          <tr class="scorecard-row{% if slate_class %} {{ slate_class }}{% endif %}" data-candidate="{{ muni.slug }}/{{ cand_slug }}" data-name="{{ c.name | downcase }}" data-municipality="{{ muni.slug }}" data-office="{{ c.office | downcase }}" data-slate="{{ c.slate | downcase }}"{% if c.questionnaire_returned %} data-returned{% endif %}{% if c.declined_statement %} data-declined{% endif %}>
            <th scope="row" class="scorecard-matrix__name">
              {%- comment -%}
                The name cell holds a link, a meta line and (with JS) up to two
                controls, so it needs a flex row the <th> itself cannot be:
                giving a table cell `display: flex` takes it out of the table
                box model and the column widths collapse with it.
              {%- endcomment -%}
              <span class="scorecard-matrix__name-inner">
                <span class="scorecard-matrix__name-text">
                  {%- comment -%}
                    Deep link to the per-candidate page generated by
                    _plugins/candidate_pages.rb. The path is rebuilt here from the
                    same two fields the plugin slugifies (municipality slug + name),
                    so the two must be changed together.

                    The plugin skips any name that slugifies to nothing (a name of
                    only punctuation clears .strip but not slugify), so there would
                    be no page to point at. Fall back to plain text on the same
                    condition rather than emitting a link that 404s: the row still
                    shows the candidate, it just is not clickable.
                  {%- endcomment -%}
                  {%- if cand_slug != '' -%}
                  <a class="scorecard-matrix__cand-link" href="{{ '/scorecard/' | append: muni.slug | append: '/' | append: cand_slug | append: '/' | relative_url }}"><span class="scorecard-matrix__cand">{{ cand_display }}</span></a>
                  {%- else -%}
                  <span class="scorecard-matrix__cand">{{ cand_display }}</span>
                  {%- endif -%}
                  {%- comment -%}
                    Standing label comes from _data/standings.yml. Use the role-qualified
                    form whenever the standing's role differs from the office sought, so a
                    sitting councillor running for mayor reads "Incumbent councillor"
                    rather than a misleading bare "Incumbent".
                  {%- endcomment -%}
                  {%- assign status = "" -%}
                  {%- if c.standing -%}
                    {%- assign st = site.data.standings | where: "id", c.standing | first -%}
                    {%- if st -%}
                      {%- if st.role and st.role != c.office -%}{%- assign status = st.role_label -%}
                      {%- else -%}{%- assign status = st.label -%}{%- endif -%}
                    {%- endif -%}
                  {%- endif -%}
                  {%- comment -%}
                    Office and standing are each independently optional, so the
                    middot is placed by collecting whichever parts exist and
                    joining them, rather than by enumerating the combinations.

                    Captured with "|" and split because Liquid has no array
                    append: `split` drops the empty trailing field, so the
                    result is exactly the present parts.

                    Slate is deliberately not a part here. The matrix is a wide
                    grid whose name column is the narrowest thing on the page,
                    and a slate name is the longest of the three: it wrapped the
                    cell for the minority of candidates who run with one while
                    saying nothing about how they were graded. It still reaches
                    the reader four other ways - the row tint and its labelled
                    legend above, the search box (which matches slate), and the
                    candidate's own page, which names it in full.
                  {%- endcomment -%}
                  {%- capture meta_raw -%}
                  {%- if c.office %}{{ c.office }}|{% endif -%}
                  {%- if status != "" %}{{ status }}|{% endif -%}
                  {%- endcapture -%}
                  {%- assign meta_parts = meta_raw | split: "|" -%}
                  {%- if meta_parts.size > 0 -%}<span class="scorecard-matrix__meta">{{ meta_parts | join: " · " }}</span>{%- endif -%}
                </span>
                {%- comment -%}
                  The two row controls stack vertically rather than sitting side
                  by side: the name column is 7rem on a phone, and two 1.5rem
                  buttons in a row eat 3.25rem of it. Stacked they cost 1.5rem,
                  and a pinned row is already tall enough to hold both because
                  its name has wrapped.

                  This wrapper is also where the reorder handle lands:
                  favourites.js inserts it after the star, within whatever the
                  star's parent happens to be, so it follows this element.
                {%- endcomment -%}
                <span class="fav-controls">
                {%- comment -%}
                  Favourite toggle. Ships hidden and is revealed by
                  assets/js/favourites.js, so a reader without JS never sees a
                  control that could not remember anything. The label names the
                  candidate because "Favourite" alone is meaningless in a screen
                  reader's list of 66 buttons; the on/off state rides on
                  aria-pressed rather than on relabelling, and the title (set by
                  the script) spells the next action out for mouse users.
                {%- endcomment -%}
                <button type="button" class="fav-toggle" aria-pressed="false" hidden>
                  {%- comment -%}
                    Both stars ship; CSS shows one, keyed off aria-pressed. A
                    hollow star for off and a filled one for on means the state
                    is a shape and not only a colour (WCAG 1.4.1), and keying the
                    swap off the same attribute the script sets makes it
                    impossible for the icon and the state to disagree.
                  {%- endcomment -%}
                  <span class="fav-toggle__icon fav-toggle__icon--off" aria-hidden="true">☆</span>
                  <span class="fav-toggle__icon fav-toggle__icon--on" aria-hidden="true">★</span>
                  <span class="sr-only">Favourite {{ cand_display }}</span>
                </button>
                </span>
              </span>
            </th>
            {%- comment -%}
              A candidate who declined to take part gets one cell across every
              topic, pointing at the statement their page carries. It replaced
              a red X in each topic, which read as nine failures and said
              nothing about why; the statement is the whole of what the
              coalition has from them, so the row sends the reader to it.

              The whole row, housing included: a sitting incumbent's housing
              record outlives the decline and keeps its letter on their own
              page, but on this grid one cell of a letter beside eight of
              statement link would read as a candidate who answered one topic.
            {%- endcomment -%}
            {%- if c.declined_statement %}
            {%- assign cand_first = c.name | split: " " | first -%}
            <td class="scorecard-matrix__declined-cell" colspan="{{ site.data.subjects.size }}">
              {%- if cand_slug != '' -%}
              <a class="scorecard-matrix__declined-link" href="{{ '/scorecard/' | append: muni.slug | append: '/' | append: cand_slug | append: '/' | relative_url }}">Click here to read {{ cand_first }}'s provided statement</a>
              {%- else -%}
              {{ cand_first }} declined to take part and provided a statement.
              {%- endif -%}
            </td>
            {%- else %}
            {%- comment -%}
              An ungraded cell is one of three different things, and the table
              has to tell them apart:

                hourglass       returned, and this topic is being graded
                speech bubble   answered, and this topic is never graded, so
                                there is something to read and no letter coming
                dash            no reply, or nothing published

              A returned questionnaire means every topic is waiting on us, so
              the hourglass is the default for all ten of them, not only the
              ones that carry a letter. General and Healthcare access are not
              graded, but their answers are still unpublished until the sheet
              deploys them, and a dash there read as "nothing came back" for a
              candidate who had in fact answered.

              The bubble wins wherever it applies, which is only those two
              topics and only once their answers are published: at that point
              there is something to read and nothing left to wait for. A graded
              topic keeps its hourglass even when the candidate also wrote a
              comment on it, because the grade is the thing that is coming; the
              comment shows inside that topic on the candidate's own page, where
              it has room.
            {%- endcomment -%}
            {% for subject in site.data.subjects %}
            {% assign cell = c.scores[subject.id] %}
            {% assign cell_state = "" %}
            {% unless site.data.scores.graded_subjects contains subject.id %}
              {% assign published = c.published_subjects[subject.id] %}
              {% if published.unscored.size > 0 %}{% assign cell_state = "answers" %}{% endif %}
            {% endunless %}
            {% if cell_state == "" and c.questionnaire_returned %}{% assign cell_state = "review" %}{% endif %}
            {%- comment -%}
              The chip is a link into that candidate's page, at that topic, which
              opens on arrival (assets/js/candidate.js reads the fragment). A
              grade is the one thing on this page a reader wants the working for,
              and the row's name link landed them at the top of a page of nine
              topics with the one they clicked closed like the rest.

              Every cell links, not only the ones carrying a letter: a dash and
              an hourglass are answers to "how did they do on transit?" too, and
              a column where some cells are clickable and others are not is a
              table the reader has to test cell by cell. The fragment is the row
              on the candidate's page whether or not it opens.

              Same guard as the name link above: no page is generated for a name
              that slugifies to nothing, so those rows keep a bare chip rather
              than a link to a 404.

              No aria-label on the link. The chip inside it already carries one
              ("Grade A", "Awaiting response"), and naming the link would replace
              that with the topic and drop the grade - the one fact the cell is
              there to state. A screen reader reads the row and column headers
              with it; `title` is for the mouse.
            {%- endcomment -%}
            <td class="scorecard-matrix__cell" data-topic="{{ subject.id }}">
              {%- if cand_slug != '' -%}
              <a class="scorecard-matrix__cell-link" href="{{ '/scorecard/' | append: muni.slug | append: '/' | append: cand_slug | append: '/#topic-' | append: subject.id | relative_url }}" title="{{ subject.name }} for {{ cand_display }}">{% include grade-badge.html grade=cell state=cell_state %}</a>
              {%- else -%}
              {% include grade-badge.html grade=cell state=cell_state %}
              {%- endif -%}
            </td>
            {% endfor %}
            {%- endif %}
          </tr>
          {% endfor %}
        </tbody>
      {% endfor %}
    </table>
  </div>

  {%- comment -%}
    Pinning and reordering happen inside a table with no visible confirmation:
    a sighted reader watches the row jump, a screen-reader user gets nothing.
    This is where assets/js/favourites.js narrates those moves. Separate from
    #candidate-count above because that region is owned by the filter script and
    overwriting it would swallow the result count mid-search.
  {%- endcomment -%}
  <p class="sr-only" id="favourites-status" role="status" aria-live="polite"></p>

  {%- comment -%}
    The "missing a candidate" ask used to be a standing block below the table.
    It only ever applied to someone who looked and came up short, so it lives
    inside the empty state now and appears with it.
  {%- endcomment -%}
  <div class="candidate-empty" id="candidate-empty" role="status" hidden>
    <p class="candidate-empty__headline">No candidates match your search.</p>
    <p class="candidate-empty__cta">
      Missing a candidate?
      <a href="mailto:{{ site.email }}">Email us at {{ site.email }}</a> to let us know!
    </p>
  </div>

  {%- comment -%}
    The methodology, the category descriptions and the deadlines used to run as
    accordions from here to the bottom of the page. They now live on /faq/,
    with their anchors unchanged, so every deep link into them still resolves.
    What stays here is the one line down to them: the reader who came for the
    grades should not have to scroll a second page of prose to leave.
  {%- endcomment -%}
  {%- comment -%}
    The whole clause is the link, not the "here" inside it: a link read out of
    context — by a screen reader listing the page's links, or by anyone
    scanning — has to say where it goes, and "here" says nothing.
  {%- endcomment -%}
  <p class="content-follow-up scorecard-faq-link">
    Have any questions? We've got answers!
    <a href="{{ '/faq/' | relative_url }}">Click here to see our FAQ</a>.
  </p>
</div>

{%- comment -%}
  First-visit prompt: whether the table opens on the candidates who took part or
  on everyone. Opened by assets/js/scorecard.js with showModal() only when this
  browser has no saved answer, so without the script it never appears and the
  page is exactly what it was. The answer is saved in localStorage beside the
  favourites, and the "Only show participating candidates" pill changes it
  afterwards.

  The example is a three-topic slice of the matrix - the same classes and the same grade
  chips - so what the reader sees change here is what the table below will do:
  non-participating rows folded under a "Show N" row, or listed in place. Names
  are placeholders, never real candidates, and it is aria-hidden: the two
  choices say in words what it shows.
{%- endcomment -%}
<dialog class="responses-prompt" id="responses-prompt" aria-labelledby="responses-prompt-title" aria-describedby="responses-prompt-lede">
  <form method="dialog" class="responses-prompt__form">
    <h2 class="responses-prompt__title" id="responses-prompt-title">Which candidates should we show?</h2>
    <p class="responses-prompt__lede" id="responses-prompt-lede">Not every candidate returned the questionnaire. Choose how the scorecard lists the ones who didn't.</p>

    <div class="responses-prompt__example" aria-hidden="true">
      <table class="scorecard-matrix responses-prompt__table">
        <thead>
          <tr>
            <th scope="col" class="scorecard-matrix__name-h">Candidate</th>
            {%- assign example_topics = "general,governance,healthcare-access" | split: "," -%}
            {%- for id in example_topics -%}
            {%- assign subject = site.data.subjects | where: "id", id | first -%}
            <th scope="col" class="scorecard-matrix__col">
              <img class="scorecard-matrix__icon" src="{{ '/assets/images/icons/' | append: subject.icon | relative_url }}" alt="" width="22" height="22" loading="lazy">
              <span class="scorecard-matrix__th-label">{{ subject.abbr | default: subject.short | default: subject.name }}</span>
            </th>
            {%- endfor %}
          </tr>
        </thead>
        <tbody class="scorecard-matrix__group">
          <tr class="scorecard-matrix__group-row">
            <th colspan="4" class="scorecard-matrix__group-head">Example town</th>
          </tr>
          {%- comment -%}
            Per cell: a letter, "said" for the speech bubble an ungraded topic
            shows when the candidate answered it, or nothing for a dash.
          {%- endcomment -%}
          {%- assign example_rows = "Candidate A|Councillor · Incumbent|said,B,said;Candidate B|Councillor · Newcomer|,,;Candidate C|Mayor · Newcomer|said,A,said;Candidate D|Councillor · Newcomer|,," | split: ";" -%}
          {%- for er in example_rows -%}
          {%- assign parts = er | split: "|" -%}
          {%- assign grades = parts[2] | split: "," -%}
          <tr class="scorecard-row"{% if grades.size == 0 %} data-example-silent{% endif %}>
            <th scope="row" class="scorecard-matrix__name">
              <span class="scorecard-matrix__cand">{{ parts[0] }}</span>
              <span class="scorecard-matrix__meta">{{ parts[1] }}</span>
            </th>
            {%- for i in (0..2) %}
            {%- assign example_grade = grades[i] %}
            {%- if example_grade == "said" %}
            <td class="scorecard-matrix__cell">{% include grade-badge.html grade="" state="answers" %}</td>
            {%- else %}
            <td class="scorecard-matrix__cell">{% include grade-badge.html grade=example_grade %}</td>
            {%- endif %}
            {%- endfor %}
          </tr>
          {%- endfor %}
          <tr class="scorecard-matrix__more-row" data-example-fold>
            <td colspan="4" class="scorecard-matrix__more-cell"><span class="scorecard-matrix__more">Show 2 non-participating candidates</span></td>
          </tr>
        </tbody>
      </table>
    </div>

    <fieldset class="responses-prompt__choices">
      <legend class="sr-only">Candidates to show</legend>
      <label class="responses-prompt__choice">
        <input type="radio" name="responded" value="participating" checked>
        <span class="responses-prompt__choice-text">
          <strong>Only participating candidates</strong>
          <span>Everyone else is folded away under each municipality.</span>
        </span>
      </label>
      <label class="responses-prompt__choice">
        <input type="radio" name="responded" value="all">
        <span class="responses-prompt__choice-text">
          <strong>All candidates</strong>
          <span>Everyone running, whether or not they responded.</span>
        </span>
      </label>
    </fieldset>

    <p class="responses-prompt__note">Choice is saved to your browser. You can change this at any time using the filters at the top of the scorecard.</p>
    <button type="submit" class="btn btn-primary responses-prompt__submit">Show the scorecard</button>
  </form>
</dialog>

<script src="{{ '/assets/js/scorecard.js' | asset_url }}" defer></script>
{%- comment -%}
  Loaded after scorecard.js and, like it, deferred: favourites moves rows
  between groups and then asks the filter script to re-run, so the filters have
  to be listening by the time the first row moves. `defer` scripts execute in
  document order, which is what guarantees that.
{%- endcomment -%}
<script src="{{ '/assets/js/favourites.js' | asset_url }}" defer></script>
