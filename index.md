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
    {%- comment -%}
      The release announcement. Shown on the strength of what the build actually
      has rather than on the date: published_candidate_count comes from
      _plugins/questionnaire_scores.rb and is zero until PUBLISH_GRADES is
      flipped, so the day's copy cannot go up ahead of the grades it announces.
      Plain text at the size of the badge under it, not a link: the button
      below is the way to the scorecard. The confetti is decoration and hidden
      from assistive tech; it bursts once on load and falls away, and a reader
      who asked for reduced motion never sees it at all.
    {%- endcomment -%}
    {%- if site.data.published_candidate_count > 0 %}
    <p class="hero-release">
      <span class="hero-release__confetti" aria-hidden="true">
      <i class="hero-release__bit hero-release__bit--a" style="--x: -105px; --y: -21px; --r: -40deg; --d: 0.00s"></i>
      <i class="hero-release__bit hero-release__bit--w" style="--x: -83px; --y: 16px; --r: 25deg; --d: 0.03s"></i>
      <i class="hero-release__bit hero-release__bit--b" style="--x: -64px; --y: -29px; --r: 70deg; --d: 0.06s"></i>
      <i class="hero-release__bit hero-release__bit--c" style="--x: -49px; --y: 22px; --r: -15deg; --d: 0.09s"></i>
      <i class="hero-release__bit hero-release__bit--f" style="--x: -28px; --y: -32px; --r: 35deg; --d: 0.12s"></i>
      <i class="hero-release__bit hero-release__bit--w" style="--x: -8px; --y: 25px; --r: -60deg; --d: 0.15s"></i>
      <i class="hero-release__bit hero-release__bit--a" style="--x: 13px; --y: -33px; --r: 15deg; --d: 0.18s"></i>
      <i class="hero-release__bit hero-release__bit--b" style="--x: 31px; --y: 24px; --r: 80deg; --d: 0.21s"></i>
      <i class="hero-release__bit hero-release__bit--c" style="--x: 50px; --y: -28px; --r: -30deg; --d: 0.24s"></i>
      <i class="hero-release__bit hero-release__bit--w" style="--x: 69px; --y: 21px; --r: 45deg; --d: 0.27s"></i>
      <i class="hero-release__bit hero-release__bit--f" style="--x: 87px; --y: -22px; --r: -70deg; --d: 0.30s"></i>
      <i class="hero-release__bit hero-release__bit--a" style="--x: 105px; --y: 15px; --r: 20deg; --d: 0.33s"></i>
      <i class="hero-release__bit hero-release__bit--b" style="--x: 120px; --y: -14px; --r: 55deg; --d: 0.36s"></i>
      <i class="hero-release__bit hero-release__bit--c" style="--x: -120px; --y: 14px; --r: -25deg; --d: 0.39s"></i>
      </span>
      Grades are released!
    </p>
    {%- endif %}
    <p class="badge">Easy, Informed Election Decisions</p>
    <h1>Get Ready For The Election</h1>
    <p class="lead">
      <strong>Livable CRD</strong> has all the information you need before you vote on October 17th. Candidates, their views, and their scores.
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
  {%- comment -%}
    The strip shows the scale's shape, not its every step. C- is still a grade
    the coalition awards and still appears in the legend on the scorecard and
    candidate pages, where a reader is looking at real grades and needs the key
    to cover all of them. Here, in the hero, a fourth chip between C and F only
    crowded the row without telling a first-time visitor anything the four
    remaining marks do not. Filtered by letter rather than dropped from
    _data/grades.yml so the grade keeps its label, description and colour
    everywhere else.
  {%- endcomment -%}
  {%- assign strip_grades = site.data.grades | where_exp: "grade", "grade.letter != 'C-'" -%}
  <div class="grade-strip" aria-label="Grading scale">
    {% for grade in strip_grades %}
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
    {% include muni-finder.html %}
    <p class="content-follow-up">
      <a href="{{ '/scorecard/' | relative_url }}">Compare every candidate in the region <span aria-hidden="true">&rarr;</span></a>
    </p>
  </div>
</section>

{%- comment -%}
  No modifier: the page's own background. The band above is lavender, so this
  slot is the light one, and the sections below alternate from here. The
  modifiers name slots rather than contents for exactly this reason - the
  rhythm belongs to the position on the page, so reordering these sections
  means moving the classes with the slots, not with the headings.
{%- endcomment -%}
<section class="section">
  <div class="container">
    <h2 class="section-title">What we are building</h2>
    {%- comment -%}
      The publication date comes from _data/deadlines.yml, like every other date
      on this page: the timeline below prints the same milestone, and a date
      written out here in prose would be a second copy to keep in sync with it.
    {%- endcomment -%}
    {%- assign grades_released = site.data.deadlines | where: "id", "grades-released" | first -%}
    <p>
      Municipal councils shape transit, housing, climate, arts, streets safe for
      walking and cycling, healthcare access, and more. This
      scorecard will survey candidates, publish their responses, and rate their
      positions using a clear letter-grade system across the topics our coalition
      evaluates. Several participating organizations are building a shared
      questionnaire; the timeline below shows where it stands.
      Responses and ratings are not posted as they come in: they are released
      together on {{ grades_released.date | date: "%B %-d, %Y" }}, by
      municipality, ahead
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
<section class="section section--alt">
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
  leaving it to that adjacency, and has to: the heading does not say it.

  What the section claims is that none of this work is ours. It used to claim
  more than that — that no organization in it was a coalition partner — and that
  broke when RUSH's maps landed at the foot of it. Membership is not what this
  band is sorted by; authorship is. Keep the wording on authorship, and let each
  entry say where it comes from.

  Below the sponsor notice rather than above it, which is the trade this move
  makes. That notice says election advertising on this site is authorized by
  Livable CRD, and it now sits several sections higher with the paragraph it
  belongs to, far enough away that it no longer reads as covering these cards.

  No modifier, so this sits on the page's own background between two lavender
  bands: the timeline above and the coalition partners below both take --alt,
  and their rules are what separate this section from each. Neither modifier is
  named for its contents, so this pair can be reordered again as long as the
  classes stay with the slots and the backgrounds keep alternating.
{%- endcomment -%}
<section class="section">
  <div class="container">
    <h2 class="section-title">Partner initiatives</h2>
    <p>
      Other organizations are putting their own questions to candidates in this
      election, running the campaigns that decide how many people vote in it,
      and collecting what residents know about the places they live. None of it
      is Livable CRD's work: some of these organizations are coalition partners
      and some are not, and either way what follows is theirs. We list it
      because a voter comparing candidates here should know what else is being
      asked and organized.
    </p>
    {% include other-orgs-notice.html %}

    {%- comment -%}
      RUSH's mapping surveys, under the cards above rather than beside them.

      They are the odd set in this section and the paragraph has to say so: the
      cards above are things being put to candidates or to voters before
      October, and these are open year-round to anyone, from an organization
      that is in the coalition. Everything else in the band is one card per
      organization, so three cards carrying no organization name between them
      would read as three more groups.

      A <strong> lead rather than an <h3>: this is the same set of things the
      heading above already names, and a second heading inside the section
      would put it in the page outline as a section of its own.
    {%- endcomment -%}
    <p class="rush-surveys-note">
      <strong>Resilient Urban Systems &amp; Habitat (RUSH)</strong>, a coalition
      partner, runs three public maps that anyone here can add to. No candidate
      answers them and nobody is graded on them: you drop a pin on a place you
      know and say what is there. The questionnaire asks candidates about these
      same streets, habitat and gathering places.
    </p>
    {% include rush-surveys.html %}
    <p class="content-follow-up">
      <a href="https://whatstherush.earth/" target="_blank" rel="noopener">More about RUSH's mapping platform <span aria-hidden="true">&rarr;</span></a>
    </p>
  </div>
</section>

{%- comment -%}
  The last lavender band before the topic cards, which carry $color-surface.
  --alt rather than a bare .section: $color-bg and $color-surface are two hairs
  apart, so on the page's own background this section and the one below it read
  as one band with two headings in it.
{%- endcomment -%}
<section class="section section--alt">
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
