---
layout: default
# No `title` here: it is set in _config.yml's `defaults:` for this one path,
# beside the note explaining why the homepage leads with the words rather than
# with the brand. Setting it there keeps the string in the same file as the rest
# of the site-wide SEO configuration.
description: >-
  Livable CRD is a non-partisan coalition scoring Capital Regional District
  municipal candidates on transit, housing, climate, arts, and other livability
  issues.
---

<section class="hero hero--home">
  <div class="hero-inner animate-in">
    <p class="badge">Easy, Informed Election Decisions</p>
    <h1>Candidate scorecard for a livable capital region</h1>
    <p class="lead">
      <strong>Livable CRD</strong> is a coalition of community groups preparing a
      transparent scorecard for municipal election candidates across the Capital
      Regional District, so voters can see where candidates stand on the issues
      that shape daily life here.
    </p>
    {%- comment -%}
      One call to action, not four. The hero's job is to send a visitor to the
      thing they came for, and a row of four equal-weight pills asked them to
      choose between reading, viewing, joining and donating before they had
      seen anything the site is about. The other three are all still one click
      away in the nav, and donate and join are highlighted there.
    {%- endcomment -%}
    <div class="btn-group">
      <a class="btn btn-hero" href="{{ '/scorecard/' | relative_url }}">View All Candidates &amp; Scores</a>
    </div>
  </div>
  <div class="grade-strip" aria-label="Grading scale">
    {% for grade in site.data.grades %}
    <div class="grade-strip__item">
      <span class="grade-strip__letter grade-{{ grade.letter | downcase }}">{{ grade.letter }}</span>
      <span class="grade-strip__label">{{ grade.label }}</span>
    </div>
    {% endfor %}
  </div>
</section>

{%- comment -%}
  Every municipality index, linked from the homepage.

  These pages answer the question this site is most often searched for - who is
  running where I live - and until now the only route to any of them was a
  heading inside the scorecard's table, which put every one of them two clicks
  from the front page and left the homepage without a single municipality name
  in its text. A crawler arriving at the root had one link into a tree of 129
  pages.

  Built from the same source and the same guard the scorecard's table headings
  use (scorecard/index.md): a municipality with nobody confirmed gets no page
  from _plugins/candidate_pages.rb, so linking one here would be a link to a
  404. It is named rather than linked instead, which is also the honest thing to
  show - "nobody has announced here yet" is a real answer to the question this
  section asks.
{%- endcomment -%}
<section class="section section--under-hero">
  <div class="container">
    <h2 class="section-title">Find your municipality</h2>
    <p>
      Every confirmed candidate for the
      {% if site.election_year %}{{ site.election_year }} {% endif %}municipal
      election, grouped by where they are running.
      {%- if site.election_day %}
      General voting day across the Capital Region is
      {{ site.election_day | date: "%A, %B %-d, %Y" }}.
      {%- endif %}
    </p>
    {%- comment -%}
      Address lookup. Ships `hidden` and is unhidden by assets/js/muni-finder.js,
      the same progressive-enhancement contract the questionnaire search and the
      favourite stars use: the list below is the page, and this only narrows it.

      Worth the network call because the boundaries are not where people think
      they are — 3400 Douglas St has a Victoria mailing address and is in
      Saanich, and half of "Victoria" in conversation is Saanich, Esquimalt or
      Oak Bay. Someone who picks the wrong index reads the wrong ballot.
    {%- endcomment -%}
    <form class="muni-finder" id="muni-finder" hidden>
      <label class="muni-finder__label" for="muni-finder-input">
        Not sure which one you vote in? Enter your address.
      </label>
      <div class="muni-finder__row">
        <input class="muni-finder__input" id="muni-finder-input" type="search" name="address"
               placeholder="e.g. 3400 Douglas St, Victoria" autocomplete="street-address"
               enterkeyhint="search" spellcheck="false">
        <button class="btn btn-secondary muni-finder__submit" type="submit">Find mine</button>
      </div>
      {%- comment -%}
        role="status" so the answer is announced: for a screen-reader user the
        result of this form is a visual change to a list further down the page,
        which is no result at all unless it is also said.
      {%- endcomment -%}
      <p class="muni-finder__status" role="status" aria-live="polite"></p>
      <p class="muni-finder__note">
        Your address is sent to the Province of B.C.'s public
        <a href="https://www2.gov.bc.ca/gov/content?id=118DD57CD9674D57BDBD511C2E78DC0D" target="_blank" rel="noopener">address geocoder</a>
        to work out the municipality, and nowhere else. We do not store it.
      </p>
    </form>
    <ul class="muni-index" id="muni-index">
      {%- for muni in site.data.municipalities %}
      {%- assign mc = site.data.candidates | where: "municipality", muni.slug %}
      {%- comment -%}
        data-muni-name is what the finder matches the geocoder's answer against,
        after both sides are stripped to letters and digits. That stripping is
        the whole alias table: the geocoder returns "Saltspring Island" for what
        this file calls "Salt Spring Island", and resolves "Saanichton" to
        "Central Saanich" before we ever see it.
      {%- endcomment -%}
      <li class="muni-index__item" data-muni-name="{{ muni.name }}">
        {%- if mc.size > 0 %}
        <a class="muni-index__link" href="{{ '/scorecard/' | append: muni.slug | append: '/' | relative_url }}">
          <span class="muni-index__name">{{ muni.name }}</span>
          <span class="muni-index__count">{{ mc.size }} candidate{% if mc.size != 1 %}s{% endif %}</span>
        </a>
        {%- else %}
        <span class="muni-index__link muni-index__link--empty">
          <span class="muni-index__name">{{ muni.name }}</span>
          <span class="muni-index__count">None confirmed yet</span>
        </span>
        {%- endif %}
      </li>
      {%- endfor %}
    </ul>
    <p class="content-follow-up">
      <a href="{{ '/scorecard/' | relative_url }}">Compare every candidate in the region <span aria-hidden="true">&rarr;</span></a>
    </p>
  </div>
</section>

{%- comment -%}
  --under-hero, not --alt: the two carry the same background, but --alt also
  draws a top border, and the hero already closes with a heavy one. The
  modifier names the slot rather than the content because the alternating
  background belongs to the position on the page: whatever section is put
  here next keeps the rhythm by keeping the class.
{%- endcomment -%}
<section class="section section--under-hero">
  <div class="container">
    <h2 class="section-title">What we are building</h2>
    <p>
      Municipal councils shape transit, housing, climate, arts, streets safe for
      walking and cycling, healthcare access, and more. This
      scorecard will survey candidates, publish their responses, and rate their
      positions using a clear letter-grade system across the topics our coalition
      evaluates. Several participating organizations are building a shared
      questionnaire; the timeline below shows where it stands.
      Once candidates are surveyed, ratings will be published by municipality ahead
      of{% if site.election_day %} general voting day,
      {{ site.election_day | date: "%A, %B %-d, %Y" }}{% else %} election day{% endif %}.
    </p>
    {% include sponsor-notice.html %}
  </div>
</section>

{%- comment -%}
  The schedule comes early, straight after the explanation of what the project
  is: it is the only thing on this page that expires, and the readers who have
  to act on it (candidates) mostly arrive from a link rather than scrolling
  the whole homepage.

  One timeline rather than a block of coalition milestones and a block of
  candidate cut-offs: the two were the same schedule split in half, and split
  they answered "what are the dates" without answering "where are we now".
{%- endcomment -%}
<section class="section">
  <div class="container">
    <h2 class="section-title">Project timeline</h2>
    <p>
      Where the scorecard is in its schedule, from the coalition drafting the
      questionnaire through to the day the grades are published.
    </p>
    {% include deadline-timeline.html %}
    <p class="content-follow-up">
      <a href="{{ '/faq/#deadlines' | relative_url }}">Learn more about project timelines <span aria-hidden="true">→</span></a>
    </p>
  </div>
</section>

{%- comment -%}
  What other organizations are doing in this election, in a section of its own
  rather than tucked under "What we are building": three cards sitting under a
  paragraph about our own questionnaire read as three more things we are doing,
  which is the one thing they must not read as.

  Directly before the coalition partners, so the two lists of organizations sit
  together and a reader who wonders which of them we work with reads the answer
  in the next section. The lead paragraph below states it outright rather than
  leaving it to that adjacency, and has to: the heading does not say it. These
  organizations are not coalition partners (see _data/partners.yml for those)
  and none of this work is ours.

  Below the sponsor notice rather than above it, which is the trade this move
  makes. That notice says election advertising on this site is authorized by
  Livable CRD, and it now sits several sections higher with the paragraph it
  belongs to, far enough away that it no longer reads as covering these cards.

  --alt because this is the slot for it: the timeline above is on the page's
  own background, so the lavender band and its rules are what separate the two.
  The coalition partners below take --above-topics for the same reason in
  reverse. Neither modifier is named for its contents, so this pair can be
  reordered again without either section losing its edges.
{%- endcomment -%}
<section class="section section--alt">
  <div class="container">
    <h2 class="section-title">Partner initiatives</h2>
    <p>
      Other organizations are putting their own questions to candidates in this
      election, and running the campaigns that decide how many people vote in
      it. None of it is Livable CRD's work and none of these organizations is a
      coalition partner: we are listing them because a voter comparing
      candidates here should know what else is being asked and organized.
    </p>
    {% include other-orgs-notice.html %}
  </div>
</section>

<section class="section section--above-topics">
  <div class="container">
    <h2 class="section-title">Coalition partners</h2>
    <p>
      Livable CRD is a joint project between organizers and advocates across the region.
    </p>
    {% include partner-list.html %}
    <p class="content-follow-up">
      Interested in joining the coalition or supporting this work?
      <a href="{{ '/donate/' | relative_url }}">Donate</a>
      or <a href="mailto:{{ site.email }}">contact us</a>.
    </p>
  </div>
</section>

<section class="section section--topics">
  <div class="container">
    <h2 class="section-title">Policy areas we evaluate</h2>
    <p>
      The questionnaire covers eight policy areas, from transit and housing to climate, arts, walking, cycling, healthcare, and governance. Most carry a letter
      grade, and where a question is published unscored the candidate's own answer is shown in full, so voters can compare positions topic by topic at a glance.
    </p>
    {%- comment -%}
      Every topic except `general`. This block is the reader's map of the policy
      areas a candidate is judged on, and General is not one: it is the two
      cross-cutting questions (GEN-01 and GEN-02), published unscored and
      belonging to no area. Carding it beside Transit and Housing promised a
      ninth policy area that the scorecard then has no column for.

      Filtered here rather than dropped from _data/subjects.yml, which still
      needs the entry: the questionnaire page groups the GEN-* questions under
      it, and the scorecard renders its answers once a candidate's are released.
    {%- endcomment -%}
    <div class="card-grid">
      {% assign policy_areas = site.data.subjects | where_exp: "s", "s.id != 'general'" %}
      {% for subject in policy_areas %}
      {% include topic-card.html subject=subject %}
      {% endfor %}
    </div>
    <p class="content-follow-up">
      Curious how candidates earn their letter grades? See
      <a href="{{ '/faq/#methodology' | relative_url }}">how we grade</a>
      for our methodology and a breakdown of each topic, or
      <a href="{{ '/questionnaire/' | relative_url }}">read the questionnaire</a>
      itself: every question we put to every candidate, in full.
    </p>
  </div>
</section>

<script src="{{ '/assets/js/muni-finder.js' | asset_url }}" defer></script>
