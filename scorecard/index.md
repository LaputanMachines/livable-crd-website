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
  <p>
    Confirmed candidates for the upcoming municipal elections across the Capital
    Regional District. Each candidate is graded across the policy areas the
    coalition evaluates. Search by name or slate, filter by municipality or
    office, or narrow to candidates who meet a minimum grade in a given topic.
    Every candidate is sent
    <a href="{{ '/questionnaire/' | relative_url }}">the same questionnaire</a>,
    and a candidate's own page shows how each of their answers was graded.
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
        <label class="scorecard-topic-label" for="topic-filter">in</label>
        <select id="topic-filter" class="scorecard-topic-select">
          <option value="all">any topic</option>
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
      No slate filter group here on purpose. Slate reaches the reader through
      the search box (which matches slate as well as name) and the meta line
      under each candidate, rather than through a fourth row of pills.

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
      <div class="scorecard-filters" role="group" aria-labelledby="muni-filter-label">
        <button type="button" class="filter-pill is-active" data-muni="all" aria-pressed="true">All</button>
        {% for muni in site.data.municipalities %}
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
  {%- endcomment -%}
  {% include grade-legend.html %}

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
            Your favourites
            {%- comment -%}
              Also the accessible description of every reorder handle
              (aria-describedby), so it is stated once here instead of being
              repeated inside 66 button labels.
            {%- endcomment -%}
            <span class="scorecard-matrix__group-hint" id="favourites-hint">Saved to browser. Drag and re-order favourites by grabbing the handle below the star icon.</span>
          </th>
        </tr>
      </tbody>
      {% comment %}
        Every municipality and electoral area gets a heading, including those with
        no confirmed candidates yet: an absent heading reads as an oversight
        rather than as "nobody has announced here". Empty groups are marked
        data-empty so the filter script can hide them once a search or filter
        narrows the view.
      {% endcomment %}
      {% for muni in site.data.municipalities %}
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

                  The checkbox is the part that needs JS (it applies a class the
                  script toggles), so it alone ships `hidden` and is revealed by
                  assets/js/scorecard.js, the same contract as the favourite star.

                  Highlighting is on by default, so the box ships `checked` and
                  the script paints the rows on load rather than waiting for a
                  change event. A reader who does not want slate colour can turn
                  it off per municipality; the swatches in the legend stay either
                  way, so nothing is lost by unchecking it.

                  Colour is never the only carrier (WCAG 1.4.1): the row names its
                  slate in the meta line and the legend labels every swatch, which
                  is also what keeps a >8-slate region readable once two slates
                  start sharing a colour.
                {%- endcomment -%}
                {%- assign muni_slated = mc | where_exp: "c", "c.slate" -%}
                {%- if muni_slated.size > 0 -%}
                {%- assign muni_slates = muni_slated | group_by: "slate" | sort: "name" -%}
                <span class="slate-control">
                  <span class="slate-legend">
                    {%- for sg in muni_slates -%}
                    {%- if sg.name != "" -%}
                    <span class="slate-legend__item">
                      <span class="slate-legend__swatch {{ site.data.slate_classes[sg.name] }}" aria-hidden="true"></span>{{ sg.name }} ({{ sg.size }})
                    </span>
                    {%- endif -%}
                    {%- endfor -%}
                  </span>
                  <label class="slate-toggle" for="slate-highlight-{{ muni.slug }}" data-slate-control="{{ muni.slug }}" hidden>
                    <input type="checkbox" id="slate-highlight-{{ muni.slug }}" data-slate-toggle="{{ muni.slug }}">
                    <span>Highlight Slate Candidates</span>
                  </label>
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
                  sheet has a row for, which is the same flag the hourglass
                  badges are drawn from: the number here can never disagree with
                  the cells below it.

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
              No candidates have publicly announced here yet. Check back, or
              <a href="mailto:{{ site.email }}?subject=Candidate%20in%20{{ muni.name | url_encode }}">tell us about one</a>.
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
          <tr class="scorecard-row{% if slate_class %} {{ slate_class }}{% endif %}" data-candidate="{{ muni.slug }}/{{ cand_slug }}" data-name="{{ c.name | downcase }}" data-municipality="{{ muni.slug }}" data-office="{{ c.office | downcase }}" data-slate="{{ c.slate | downcase }}">
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
                    Office, standing and slate are each independently optional,
                    so the middots are placed by collecting whichever parts
                    exist and joining them, rather than by enumerating the
                    combinations: three optional parts is seven branches, and
                    the old two-part version was already the whole conditional.

                    Captured with "|" and split because Liquid has no array
                    append: `split` drops the empty trailing field, so the
                    result is exactly the present parts. sync-candidates.py
                    rewrites any literal "|" in a slate name to "/" so a slate
                    cannot inject an extra part here.
                  {%- endcomment -%}
                  {%- capture meta_raw -%}
                  {%- if c.office %}{{ c.office }}|{% endif -%}
                  {%- if status != "" %}{{ status }}|{% endif -%}
                  {%- if c.slate %}{{ c.slate }}|{% endif -%}
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
            <td class="scorecard-matrix__cell" data-topic="{{ subject.id }}">{% include grade-badge.html grade=cell state=cell_state %}</td>
            {% endfor %}
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

<script src="{{ '/assets/js/scorecard.js' | asset_url }}" defer></script>
{%- comment -%}
  Loaded after scorecard.js and, like it, deferred: favourites moves rows
  between groups and then asks the filter script to re-run, so the filters have
  to be listening by the time the first row moves. `defer` scripts execute in
  document order, which is what guarantees that.
{%- endcomment -%}
<script src="{{ '/assets/js/favourites.js' | asset_url }}" defer></script>
