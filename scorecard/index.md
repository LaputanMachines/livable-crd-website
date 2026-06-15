---
layout: default
title: Candidate Scorecard
permalink: /scorecard/
description: >-
  Compare where confirmed Capital Regional District municipal election
  candidates stand on transit, housing, climate, arts, walking, and cycling.
  Search by name or filter by municipality.
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
    coalition evaluates. Search by name, filter by municipality, or narrow to
    candidates who meet a minimum grade in a given topic.
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
            <span class="scorecard-matrix__th-label" aria-hidden="true">{{ subject.short | default: subject.name }}</span>
            <span class="sr-only">{{ subject.name }}</span>
          </th>
          {% endfor %}
        </tr>
      </thead>
      {% for muni in site.data.municipalities %}
        {% assign mc = site.data.candidates | where: "municipality", muni.slug %}
        {% if mc.size > 0 %}
        <tbody class="scorecard-matrix__group" data-municipality="{{ muni.slug }}">
          <tr class="scorecard-matrix__group-row">
            <th scope="colgroup" colspan="10" class="scorecard-matrix__group-head">{{ muni.name }}</th>
          </tr>
          {% for c in mc %}
          <tr class="scorecard-row" data-name="{{ c.name | downcase }}" data-municipality="{{ muni.slug }}" data-office="{{ c.office | downcase }}">
            <th scope="row" class="scorecard-matrix__name">
              <span class="scorecard-matrix__cand">{{ c.name }}</span>
              {% if c.office %}<span class="scorecard-matrix__meta">{{ c.office }}</span>{% endif %}
            </th>
            {% for subject in site.data.subjects %}
            {% assign cell = c.scores[subject.id] %}
            <td class="scorecard-matrix__cell" data-topic="{{ subject.id }}">{% include grade-badge.html grade=cell %}</td>
            {% endfor %}
          </tr>
          {% endfor %}
        </tbody>
        {% endif %}
      {% endfor %}
    </table>
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

      <h2>Questionnaire topics</h2>
      <p>
        Each candidate is graded in every policy area below. Individual questions are tagged
        with the topic that best applies, including a <strong>general</strong> category
        for cross-cutting items.
      </p>

      <dl class="topic-defs">
        {% for subject in site.data.subjects %}
        <div class="topic-def">
          <dt class="topic-def__name">{{ subject.name }}</dt>
          <dd class="topic-def__desc">{{ subject.description }}</dd>
        </div>
        {% endfor %}
      </dl>

      <h2>How grades are assigned</h2>
      <p>
        Participating organizations are finalizing the questionnaire. When complete, we
        will publish the full question set and weighting here. In general:
      </p>
      <ul>
        <li>Points are awarded for positions that advance coalition goals within each topic.</li>
        <li>Each topic grade reflects the candidate's responses within that area, including general livability questions.</li>
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
