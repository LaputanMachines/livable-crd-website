---
layout: default
# No `title` here: jekyll-seo-tag renders the homepage <title> as
# "Livable CRD | <site.tagline>", which is more descriptive than "Home".
description: >-
  Livable CRD is a non-partisan coalition publishing a transparent scorecard
  that rates Capital Regional District municipal election candidates on transit,
  housing, climate, arts, walking, cycling, and other livability issues.
---

<section class="hero hero--home">
  <div class="hero-inner animate-in">
    <p class="badge">Launching ahead of municipal elections</p>
    <h1>A candidate scorecard for livable communities in the Capital Region</h1>
    <p class="lead">
      <strong>Livable CRD</strong> is a coalition of community groups preparing a
      transparent scorecard for municipal election candidates across the Capital
      Regional District — so voters can see where candidates stand on the issues
      that shape daily life here.
    </p>
    <div class="btn-group">
      <a class="btn btn-primary" href="{{ '/scorecard/' | relative_url }}#methodology">How we grade</a>
      <a class="btn btn-secondary" href="{{ '/scorecard/' | relative_url }}">View scorecard</a>
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

<section class="section">
  <div class="container">
    <h2 class="section-title">What we are building</h2>
    <p>
      Municipal councils shape transit, housing, climate, arts, streets safe for
      walking and cycling, youth opportunity, healthcare access, and more. This
      scorecard will survey candidates, publish their responses, and rate their
      positions using a clear letter-grade system across the topics our coalition
      evaluates.
    </p>
    <p>
      Several participating organizations are drafting a shared questionnaire now.
      Once candidates are surveyed, ratings will be published by municipality ahead
      of election day.
    </p>
  </div>
</section>

<section class="section section--alt">
  <div class="container">
    <h2 class="section-title">Coalition partners</h2>
    <p>
      Livable CRD brings together advocates from across the region. Partner names
      below are placeholders until the coalition finalizes its public roster.
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
      or <a href="{{ '/about/#contact' | relative_url }}">contact us</a>.
    </p>
  </div>
</section>

<section class="section section--topics">
  <div class="container">
    <h2 class="section-title">Policy areas we evaluate</h2>
    <p>
      The questionnaire covers nine topics, from transit and housing to climate, arts, walking, cycling, youth, healthcare, and general livability. Each candidate is graded
      in every area, so voters can compare positions topic by topic at a glance.
    </p>
    <div class="card-grid">
      {% for subject in site.data.subjects %}
      {% include topic-card.html subject=subject %}
      {% endfor %}
    </div>
    <p class="content-follow-up">
      Curious how candidates earn their letter grades? See
      <a href="{{ '/scorecard/#methodology' | relative_url }}">how we grade</a>
      for our methodology and a breakdown of each topic.
    </p>
  </div>
</section>
