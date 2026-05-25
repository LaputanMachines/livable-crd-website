---
layout: default
title: Scorecard
permalink: /scorecard/
---

<div class="container">
  <h1>Candidate scorecard</h1>
  <p>
    Ratings and questionnaire responses for candidates in 16 participating municipalities across the Capital Regional District. Content is being prepared ahead of the election.
  </p>

  <div class="status-banner">
    <p><strong>In development.</strong> Candidate data has not been published yet. Check back soon.</p>
  </div>

  <h2>Municipalities</h2>
  <p>Select a municipality to view candidates once surveys are complete.</p>

  <div class="card-grid">
    {% for muni in site.data.municipalities %}
    {% include municipality-card.html municipality=muni %}
    {% endfor %}
  </div>

  <p style="margin-top:2rem;">
    See <a href="{{ '/methodology/' | relative_url }}">methodology</a> for how grades are calculated.
  </p>
</div>
