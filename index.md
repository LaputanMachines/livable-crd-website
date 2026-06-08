---
layout: default
title: Home
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
      <a class="btn btn-primary" href="{{ '/methodology/' | relative_url }}">How we grade</a>
      <a class="btn btn-secondary" href="{{ '/scorecard/' | relative_url }}">View scorecard</a>
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
    <div class="status-banner">
      <p><strong>Scorecard in development.</strong> Municipality and candidate pages are coming soon.</p>
    </div>
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
        <p class="org-name">{{ partner.name }}</p>
        <p class="org-note">{{ partner.note }}</p>
      </li>
      {% endfor %}
    </ul>
    <p style="margin-top:1.5rem;">
      Interested in joining the coalition or supporting this work?
      <a href="{{ '/about/#contact' | relative_url }}">Contact us</a>.
    </p>
  </div>
</section>

<section class="section section--topics">
  <div class="container">
    <h2 class="section-title">Policy areas we evaluate</h2>
    <p>
      The questionnaire covers nine topics, from transit and housing to climate, arts, walking, cycling, youth, healthcare, and general livability. Each candidate receives an overall
      letter grade; detailed responses are organized by area so voters can compare
      positions at a glance.
    </p>
    <div class="card-grid">
      {% for subject in site.data.subjects %}
      {% include topic-card.html subject=subject %}
      {% endfor %}
    </div>
  </div>
</section>
