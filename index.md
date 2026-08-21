---
layout: default
# No `title` here: jekyll-seo-tag renders the homepage <title> as
# "Livable CRD | <site.tagline>", which is more descriptive than "Home".
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
    <div class="btn-group">
      <a class="btn btn-primary" href="{{ '/questionnaire/' | relative_url }}">Read the questions</a>
      <a class="btn btn-secondary" href="{{ '/scorecard/' | relative_url }}">View scorecard</a>
      <a class="btn btn-newsletter" href="{{ '/signup/' | relative_url }}">Join the mailing list</a>
      <a class="btn btn-donate" href="{{ '/donate/' | relative_url }}">Support us</a>
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
      of election day.
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
      questionnaire through to the last day a candidate can respond.
    </p>
    {% include deadline-timeline.html %}
    <p class="content-follow-up">
      <a href="{{ '/scorecard/#deadlines' | relative_url }}">Learn more about project timelines <span aria-hidden="true">→</span></a>
    </p>
  </div>
</section>

<section class="section section--alt">
  <div class="container">
    <h2 class="section-title">Coalition partners</h2>
    <p>
      Livable CRD is a joint project between organizers and advocates across the region.
    </p>
    <ul class="partner-list">
      {% for partner in site.data.partners %}
      <li>
        {% if site.partner_logos and partner.logo %}
        {% if partner.logo contains "/" %}{% assign partner_logo_src = partner.logo %}{% else %}{% assign partner_logo_src = partner.logo | prepend: '/assets/images/partners/' %}{% endif %}
        <img class="partner-logo" src="{{ partner_logo_src | relative_url }}" alt="{{ partner.name }} logo" loading="lazy">
        {% endif %}
        {% if partner.category %}
        {% assign cat = site.data.subjects | where: "id", partner.category | first %}
        {% if cat %}{% assign cat_label = cat.name %}{% else %}{% assign cat_label = partner.category %}{% endif %}
        <p class="org-category"><span class="category-pill category-pill--{{ partner.category | slugify }}">{{ cat_label }}</span></p>
        {% endif %}
        <p class="org-name">{{ partner.name }}</p>
        {% if partner.note %}<p class="org-note">{{ partner.note }}</p>{% endif %}
        {% if partner.url %}<p class="org-link"><a href="{{ partner.url }}" target="_blank" rel="noopener">Visit website →</a></p>{% endif %}
      </li>
      {% endfor %}
    </ul>
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
      The questionnaire covers ten topics, from transit and housing to climate, arts, reconciliation, walking, cycling, healthcare, governance, and general livability. Each candidate is graded
      in every area, so voters can compare positions topic by topic at a glance.
    </p>
    {%- comment -%}
      Between the section's description and the ten topic cards: the sentence
      above says what the questionnaire covers, so this is where "food systems
      is not one of them, and here is who is covering it" reads as part of the
      same answer rather than as a footnote under the grid.
    {%- endcomment -%}
    {% include other-scorecard-notice.html %}
    <div class="card-grid">
      {% for subject in site.data.subjects %}
      {% include topic-card.html subject=subject %}
      {% endfor %}
    </div>
    <p class="content-follow-up">
      Curious how candidates earn their letter grades? See
      <a href="{{ '/scorecard/#methodology' | relative_url }}">how we grade</a>
      for our methodology and a breakdown of each topic, or
      <a href="{{ '/questionnaire/' | relative_url }}">read the questionnaire</a>
      itself: every question we put to every candidate, in full.
    </p>
  </div>
</section>
