---
layout: default
title: Scorecard
permalink: /scorecard/
---

<div class="page-header">
  <div class="container">
    <h1>Candidate scorecard</h1>
  </div>
</div>

<div class="container page-content">
  <p>
    Confirmed candidates for the upcoming municipal elections across the Capital
    Regional District. Each candidate receives an overall grade plus a breakdown
    across the policy areas the coalition evaluates. Search by name or filter by
    municipality below.
  </p>

  <div class="status-banner">
    <p><strong>Grading in progress.</strong> Candidates are being surveyed — grades show as “—” until questionnaire responses are published.</p>
  </div>

  <div class="scorecard-legend" aria-label="Grading key">
    {% for grade in site.data.grades %}
    <span class="scorecard-legend__item">
      <span class="grade grade-{{ grade.letter | downcase }}">{{ grade.letter }}</span>{{ grade.label }}
    </span>
    {% endfor %}
    <span class="scorecard-legend__item">
      <span class="grade grade--pending">—</span>Pending
    </span>
  </div>

  <div class="scorecard-controls">
    <label for="candidate-search" class="sr-only">Search candidates by name</label>
    <input type="search" id="candidate-search" class="scorecard-search" placeholder="Search candidates by name…" autocomplete="off">
    <div class="scorecard-filters" role="group" aria-label="Filter by municipality">
      <button type="button" class="filter-pill is-active" data-muni="all" aria-pressed="true">All</button>
      {% for muni in site.data.municipalities %}
        {% assign mc = site.data.candidates | where: "municipality", muni.slug %}
        {% if mc.size > 0 %}
        <button type="button" class="filter-pill" data-muni="{{ muni.slug }}" aria-pressed="false">{{ muni.name }} ({{ mc.size }})</button>
        {% endif %}
      {% endfor %}
    </div>
  </div>

  <p class="scorecard-count" id="candidate-count" role="status" aria-live="polite"></p>

  <div class="candidate-grid" id="candidate-grid">
    {% for muni in site.data.municipalities %}
      {% assign mc = site.data.candidates | where: "municipality", muni.slug %}
      {% for candidate in mc %}
        {% include candidate-card.html candidate=candidate municipality=muni %}
      {% endfor %}
    {% endfor %}
  </div>

  <p class="candidate-empty" id="candidate-empty" role="status" hidden>No candidates match your search.</p>

  <div class="callout scorecard-cta">
    <h2>Don’t see a candidate you care about?</h2>
    <p>
      Have a candidate you want represented on the scorecard?
      <a href="mailto:{{ site.email }}">Email us at {{ site.email }}</a> and let us know.
    </p>
  </div>

  <details class="methodology" id="methodology">
    <summary>How we grade — methodology</summary>
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
      <div class="table-scroll">
        <table>
          <thead>
            <tr>
              <th scope="col">Grade</th>
              <th scope="col">Label</th>
              <th scope="col">Description</th>
            </tr>
          </thead>
          <tbody>
            {% for grade in site.data.grades %}
            <tr>
              <td>{% include grade-badge.html grade=grade.letter %}</td>
              <td><strong>{{ grade.label }}</strong></td>
              <td>{{ grade.description }}</td>
            </tr>
            {% endfor %}
          </tbody>
        </table>
      </div>

      <p>
        Some ratings may use modifiers (for example, <strong>C−</strong>) when a
        candidate's positions fall between two levels.
      </p>

      <h2>Questionnaire topics</h2>
      <p>
        Each candidate receives an overall letter grade. Individual questions are tagged
        with the topic that best applies, including a <strong>general</strong> category
        for cross-cutting items.
      </p>

      <div class="table-scroll">
        <table>
          <thead>
            <tr>
              <th scope="col">Topic</th>
              <th scope="col">What we look at</th>
            </tr>
          </thead>
          <tbody>
            {% for subject in site.data.subjects %}
            <tr>
              <td><strong>{{ subject.name }}</strong></td>
              <td>{{ subject.description }}</td>
            </tr>
            {% endfor %}
          </tbody>
        </table>
      </div>

      <h2>How grades are assigned</h2>
      <p>
        Participating organizations are finalizing the questionnaire. When complete, we
        will publish the full question set and weighting here. In general:
      </p>
      <ul>
        <li>Points are awarded for positions that advance coalition goals within each topic.</li>
        <li>Overall grades reflect responses across all topic areas, including general livability questions.</li>
        <li>Points are deducted for positions that would clearly undermine progress on housing, mobility, climate, healthcare access, or other priorities covered in the survey.</li>
      </ul>

      <p>
        Candidates will have an opportunity to review their published responses before
        grades are finalized, consistent with fair voter-information practices.
      </p>
    </div>
  </details>
</div>

<script src="{{ '/assets/js/scorecard.js' | relative_url }}" defer></script>
