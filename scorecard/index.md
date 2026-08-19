---
layout: default
title: Candidate Scorecard
permalink: /scorecard/
description: >-
  Compare where Capital Regional District municipal candidates stand on transit,
  housing, climate, arts, and cycling. Search by name or filter by municipality.
---

<div class="page-header">
  <div class="container">
    <h1>Candidate scorecard</h1>
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

  {%- comment -%}
    One line, and it is a request rather than an announcement: the only thing
    this band is for is catching the errors a reader can see and we cannot.
    Everything it used to say about how the list is built lives in the
    #how-candidates-are-added block at the foot of the page, which is still
    linked from the deadlines FAQ and still reachable by its own heading.
  {%- endcomment -%}
  <div class="status-banner">
    <p>Someone missing or listed incorrectly? <a href="mailto:{{ site.email }}?subject=Scorecard%20correction">Tell us</a> by emailing {{ site.email }}.</p>
  </div>

  {%- comment -%}
    Above the grading key, not below the table: a candidate landing here to
    check what is expected of them should not have to scroll past 66 rows to
    find the cut-off. Links down to #deadlines for the full schedule and for
    what a missed date actually costs.
  {%- endcomment -%}
  {% include deadline-notice.html
     class="deadline-notice--scorecard"
     heading="Candidate deadlines"
     lead="Grades on this page come from the coalition questionnaire. Candidates have to return it by these dates for their results to be published."
     more_url="#deadlines"
     more_label="Key dates, and what a missed deadline means" %}

  {%- comment -%}
    Below the candidate deadlines rather than above them: the deadline band is
    the one thing on this page a reader can miss at a cost, so nothing gets
    inserted ahead of it. Still above the table, because a voter who cares
    about food policy should see it while choosing what to compare, not after
    scrolling every municipality.
  {%- endcomment -%}
  {% include other-scorecard-notice.html %}

  {%- comment -%}
    The two empty states sit in the key next to the letters, because on a table
    this size most cells are one of them and a reader who cannot tell them apart
    reads a returned questionnaire as a no-show. Spelled out again under
    #methodology; this is the version that fits on one line.
  {%- endcomment -%}
  <div class="scorecard-legend" aria-label="Grading key">
    {% for grade in site.data.grades %}
    <span class="scorecard-legend__item">
      <span class="grade grade-{{ grade.letter | downcase }}">{{ grade.letter }}</span>{{ grade.label }}
    </span>
    {% endfor %}
    {%- comment -%}
      Both empty states come from the include rather than being written out
      here, so the key cannot end up showing a different mark from the table
      under it. An empty `grade` is what puts the include in an empty state;
      `state` picks which of the two.
    {%- endcomment -%}
    <span class="scorecard-legend__item">
      {% include grade-badge.html grade="" state="review" %}Being graded
    </span>
    <span class="scorecard-legend__item">
      {% include grade-badge.html grade="" state="answers" %}Answered, not graded
    </span>
    {%- comment -%}
      "Not graded" rather than "No reply": the dash also stands on topics the
      coalition does not grade at all, where it is not the candidate's silence
      being reported. Both readings are true of "not graded", and #methodology
      separates them.
    {%- endcomment -%}
    <span class="scorecard-legend__item">
      {% include grade-badge.html grade="" %}Not graded
    </span>
  </div>

  {%- comment -%}
    How far along the whole exercise is, in one line, directly under the key
    that just introduced the two empty states. Without it a reader scrolling a
    table of dashes has no way to tell a questionnaire that has barely gone out
    from one candidates are ignoring. Both counts come from
    _plugins/questionnaire_scores.rb rather than being counted here, so the
    sentence cannot disagree with the chips in the table.

    Absent entirely until the first reply comes back: "0 of 66 have returned it"
    is a true sentence that reads as an accusation, and early in a cycle it says
    nothing except that we sent the questionnaire out recently.
  {%- endcomment -%}
  {%- assign returned_count = site.data.returned_candidate_count | default: 0 %}
  {%- if returned_count > 0 %}
  <p class="scorecard-progress">
    <strong>{{ returned_count }}</strong> of {{ site.data.candidates.size }} candidates
    {% if returned_count == 1 %}has{% else %}have{% endif %} returned the questionnaire so far.
    {%- assign published_count = site.data.published_candidate_count | default: 0 %}
    {%- if published_count > 0 %}
    {{ published_count }} of them {% if published_count == 1 %}has{% else %}have{% endif %}
    at least one topic graded and published.
    {%- else %}
    No topic has finished grading yet.
    {%- endif %}
  </p>
  {%- endif %}

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
          <th scope="colgroup" colspan="11" class="scorecard-matrix__group-head scorecard-matrix__group-head--fav">
            Your favourites
            {%- comment -%}
              Also the accessible description of every reorder handle
              (aria-describedby), so it is stated once here instead of being
              repeated inside 66 button labels.
            {%- endcomment -%}
            <span class="scorecard-matrix__group-hint" id="favourites-hint">Saved in this browser only. Drag a row by its reorder handle to change the order.</span>
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
            <th scope="colgroup" colspan="11" class="scorecard-matrix__group-head">
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
                <span class="scorecard-matrix__group-name">{{ muni.name }}</span>
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
                    <input type="checkbox" id="slate-highlight-{{ muni.slug }}" data-slate-toggle="{{ muni.slug }}" checked>
                    <span>Highlight Slate Candidates</span>
                  </label>
                </span>
                {%- endif -%}
              </span>
            </th>
          </tr>
          {% if mc.size == 0 %}
          <tr class="scorecard-matrix__empty-row">
            <td colspan="11" class="scorecard-matrix__empty-cell">
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

                circular arrow  returned, and this topic is being graded
                speech bubble   answered, and this topic is never graded, so
                                there is something to read and no letter coming
                dash            no reply, or nothing published

              Which of the first two applies is decided by `graded_subjects`,
              the topics that carry a graded question at all. General and
              Healthcare access do not, so a returned candidate never appears to
              be waiting on them; what they can carry is a written answer, and
              that is what the bubble points at.

              The bubble is checked second on purpose. A graded topic keeps its
              arrow even when the candidate also wrote a comment on it, because
              the grade is the thing that is coming; the comment shows inside
              that topic on the candidate's own page, where it has room.
            {%- endcomment -%}
            {% for subject in site.data.subjects %}
            {% assign cell = c.scores[subject.id] %}
            {% assign cell_state = "" %}
            {% if site.data.scores.graded_subjects contains subject.id %}
              {% if c.questionnaire_returned %}{% assign cell_state = "review" %}{% endif %}
            {% else %}
              {% assign published = c.published_subjects[subject.id] %}
              {% if published.unscored.size > 0 %}{% assign cell_state = "answers" %}{% endif %}
            {% endif %}
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

  <p class="candidate-empty" id="candidate-empty" role="status" hidden>No candidates match your search.</p>

  <div class="callout scorecard-cta">
    <h2>Don’t see a candidate you care about?</h2>
    <p>
      Have a candidate you want represented on the scorecard?
      <a href="mailto:{{ site.email }}">Email us at {{ site.email }}</a> and let us know.
    </p>
  </div>

  <details class="methodology" id="methodology">
    <summary>How we grade: methodology</summary>
    <div class="methodology__body">
      <p>
        Livable CRD rates municipal election <strong>candidates</strong> on policy positions
        that shape how liveable the Capital Region is for everyone. Participating organizations
        are developing a shared questionnaire; responses and letter grades will be published
        before election day.
      </p>

      <div class="callout">
        <p>
          <strong>Note:</strong> We evaluate candidate <em>positions</em>, not municipal
          bylaws or past council votes. The topics below match the categories used in our
          coalition questionnaire.
        </p>
      </div>

      <h2>Letter grades</h2>
      <dl class="grade-defs">
        {% for grade in site.data.grades %}
        <div class="grade-def">
          <dt class="grade-def__term">
            {% include grade-badge.html grade=grade.letter %}
            <span class="grade-def__label">{{ grade.label }}</span>
          </dt>
          <dd class="grade-def__desc">{{ grade.description }}</dd>
        </div>
        {% endfor %}
      </dl>

      <p>
        Some ratings may use modifiers (for example, <strong>C−</strong>) when a
        candidate's positions fall between two levels.
      </p>

      {%- comment -%}
        The two empty states, spelled out. The legend at the top of the page has
        room for two words each; this is where a reader who wants to know what a
        dash costs a candidate can find out that sometimes it costs them nothing.
      {%- endcomment -%}
      <h2>When there is no letter</h2>
      <dl class="grade-defs">
        <div class="grade-def">
          <dt class="grade-def__term">
            {% include grade-badge.html grade="" state="review" %}
            <span class="grade-def__label">Being graded</span>
          </dt>
          <dd class="grade-def__desc">
            This candidate returned the questionnaire and this topic has not been
            published yet. Grading is done by the coalition organization that wrote
            the topic's questions, and each topic is published as that organization
            finishes it, so a candidate can show letters in one topic and this in
            another. It says nothing about how the topic is going.
          </dd>
        </div>
        <div class="grade-def">
          <dt class="grade-def__term">
            {% include grade-badge.html grade="" state="answers" %}
            <span class="grade-def__label">Answered, not graded</span>
          </dt>
          <dd class="grade-def__desc">
            The candidate answered, and this is a topic we do not assign a letter
            in. Two of them work this way: <strong>General</strong>, which asks
            what a candidate would change and how they would split a budget, and
            <strong>Healthcare access</strong>, which asks one question about
            primary care clinics. The coalition puts them to every candidate
            because the answers are worth reading, not because we score them.
            Open the candidate's page to read what they wrote.
          </dd>
        </div>
        <div class="grade-def">
          <dt class="grade-def__term">
            {% include grade-badge.html grade="" %}
            <span class="grade-def__label">Not graded</span>
          </dt>
          <dd class="grade-def__desc">
            Either no completed questionnaire has come back from this candidate
            yet, or the topic is one we do not assign a letter in. A dash is never
            a bad grade: the grades are <strong>A</strong> through <strong>F</strong>,
            and a candidate who scores poorly gets a letter saying so.
          </dd>
        </div>
      </dl>

      <h2>Questionnaire topics</h2>
      <p>
        Each candidate is graded in every policy area, including a <strong>general</strong>
        category for cross-cutting items. See
        <a href="#categories">what each category covers</a> for a description of every topic.
      </p>

      <h2>How grades are assigned</h2>
      <p>
        Participating organizations are finalizing the questionnaire. When complete, we
        will publish the full question set and weighting here. In general:
      </p>
      <ul>
        <li>Each participating group contributes the questions in its area of focus, and that same group grades candidates' responses to the questions it submitted.</li>
        <li>Points are awarded for positions that advance coalition goals within each topic.</li>
        <li>Each topic grade reflects the candidate's responses within that area, including general livability questions.</li>
        <li>Points are deducted for positions that would clearly undermine progress on housing, mobility, climate, healthcare access, or other priorities covered in the survey.</li>
      </ul>

      <p>
        Candidates will have an opportunity to review their published responses before
        grades are finalized, consistent with fair voter-information practices.
      </p>

      <p>
        Responses are published as written. The one exception is set out in our
        <a href="{{ '/code-of-conduct/' | relative_url }}">questionnaire code of conduct</a>:
        hateful, harassing, or threatening content is neither graded nor published.
        Disagreeing with the coalition is not covered by that: a low grade and a
        conduct decision are separate things, decided separately.
      </p>
    </div>
  </details>

  <details class="methodology" id="who-grades">
    <summary>Who writes, and grades, the questions?</summary>
    <div class="methodology__body">
      <p>
        Livable CRD is a <strong>coalition</strong>, and the questionnaire is built
        collaboratively. Each participating organization contributes the questions in
        its own area of focus: a transit group writes the transit questions, a housing
        group writes the housing questions, and so on across the policy areas we evaluate.
      </p>
      <p>
        <strong>The same group that submits a set of questions also grades candidates'
        responses to those questions.</strong> Each group grades only within its own area
        of focus, so no single organization assigns a candidate's full slate of grades
        alone. This keeps every topic in the hands of the people who understand it best,
        and keeps the overall scorecard a shared, coalition-wide effort.
      </p>
      <p>
        All grading follows our published <a href="#methodology">methodology</a> so the
        process stays transparent and reproducible. Candidates will have an opportunity to
        review their published responses before grades are finalized.
      </p>
    </div>
  </details>

  <details class="methodology category-faq" id="categories">
    <summary>What each category covers</summary>
    <div class="methodology__body">
      <p>
        Every candidate is graded across the policy areas below, the same categories used
        in the coalition questionnaire. Here's what each one means.
      </p>
      <dl class="topic-defs">
        {% for subject in site.data.subjects %}
        <div class="topic-def" id="category-{{ subject.id }}" style="--card-accent: {{ subject.accent }}">
          <dt class="topic-def__name">{{ subject.name }}</dt>
          <dd class="topic-def__desc">{{ subject.description }}</dd>
        </div>
        {% endfor %}
      </dl>
    </div>
  </details>

  <details class="methodology" id="how-candidates-are-added">
    <summary>How candidates get added to this scorecard</summary>
    <div class="methodology__body">
      <p>
        Our volunteers maintain a working spreadsheet of everyone running for municipal
        office across the Capital Regional District. A candidate's entry starts out
        internal to that sheet, and is marked <strong>confirmed</strong> only once they
        have <strong>publicly announced their candidacy</strong>. This page is generated
        from the confirmed entries, so a name appears here after that public announcement,
        not before.
      </p>
      <p>
        <strong>Every candidate is included in the Livable CRD project.</strong> We do not
        pick and choose who appears. Once confirmed, every candidate is added to this
        scorecard and every candidate is sent the coalition questionnaire, regardless of
        their platform, party affiliation, or whether we expect them to agree with us.
      </p>
      <p>
        If someone is missing, the most likely explanation is simply that we haven't
        updated their status on our back end yet. Tracking every announcement across
        thirteen municipalities and three electoral areas is volunteer work, and
        announcements do not arrive in a tidy list, so gaps happen.
      </p>
      <p>
        We genuinely welcome comments and suggestions from the public. If you know of a
        candidate we've missed, spot an error in an existing entry, or have a correction
        of any kind,
        <a href="mailto:{{ site.email }}?subject=Scorecard%20candidate%20update">email us at {{ site.email }}</a>.
        Public help is a real part of how this list stays accurate.
      </p>
    </div>
  </details>

  {%- comment -%}
    Every date below comes from _data/deadlines.yml, including the ones quoted
    mid-sentence: writing "September 11" into the prose would be a second copy
    to keep in sync with the list right above it.
  {%- endcomment -%}
  {%- assign print_cutoff = site.data.deadlines | where: "id", "print-cutoff" | first -%}
  {%- assign web_cutoff = site.data.deadlines | where: "id", "web-cutoff" | first -%}
  <details class="methodology" id="deadlines">
    <summary>Key dates, and what a missed deadline means</summary>
    <div class="methodology__body">
      <p>
        The grades on this page come from the coalition questionnaire, which goes
        to every confirmed candidate. The last two dates below are cut-offs a
        candidate can miss; the ones before them are the coalition milestones
        leading up to those, listed so the whole schedule is public. The same
        schedule runs as a timeline on the <a href="{{ '/' | relative_url }}">homepage</a>.
      </p>

      {% include deadline-list.html class="deadline-list--stacked" %}

      <h2>Why there are two candidate deadlines</h2>
      <p>
        Print runs and the website are produced on different schedules. Printed
        scorecards, stickers, and posters have to go to the printer well before
        election day, so
        <strong>{{ print_cutoff.date | date: "%B %-d" }}</strong> is the last day a
        response can still make it onto physical materials. The website can be
        updated later, which buys candidates until
        <strong>{{ web_cutoff.date | date: "%B %-d" }}</strong> to have their
        results published here.
      </p>
      <p>
        A response returned between those two dates is graded and published on this
        site, but arrives too late for anything printed.
      </p>

      <h2>What happens to a candidate who does not respond</h2>
      <p>
        A missed deadline never removes anyone from this scorecard. Every confirmed
        candidate stays listed with their row intact; their topic grades simply
        stay pending. We do not treat silence as a failing grade, and we do not
        drop the candidate from the list. See
        <a href="#how-candidates-are-added">how candidates get added</a> for why the
        list itself is not selective.
      </p>
      <p>
        If you are a candidate and the questionnaire has not reached you, or you
        want to confirm your response was received,
        <a href="mailto:{{ site.email }}?subject=Questionnaire%20deadline">email us at {{ site.email }}</a>.
      </p>
    </div>
  </details>
</div>

<script src="{{ '/assets/js/scorecard.js' | asset_url }}" defer></script>
{%- comment -%}
  Loaded after scorecard.js and, like it, deferred: favourites moves rows
  between groups and then asks the filter script to re-run, so the filters have
  to be listening by the time the first row moves. `defer` scripts execute in
  document order, which is what guarantees that.
{%- endcomment -%}
<script src="{{ '/assets/js/favourites.js' | asset_url }}" defer></script>
