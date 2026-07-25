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
    coalition evaluates. Search by name, filter by municipality, or narrow to
    candidates who meet a minimum grade in a given topic.
  </p>

  <div class="status-banner">
    <p><strong>This list grows as candidates come forward.</strong> Candidates are added once they publicly announce their candidacy. Our volunteers track every announcement across the region as best we can, but mistakes happen — if a candidate is missing or listed incorrectly, <a href="mailto:{{ site.email }}?subject=Scorecard%20correction">email us at {{ site.email }}</a>. More on <a href="#how-candidates-are-added">how candidates get added</a>.</p>
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
            {% if subject.abbr %}
            <span class="scorecard-matrix__th-label scorecard-matrix__th-label--abbr" aria-hidden="true">{{ subject.abbr }}</span>
            <span class="scorecard-matrix__th-label scorecard-matrix__th-label--full" aria-hidden="true">{{ subject.short | default: subject.name }}</span>
            {% else %}
            <span class="scorecard-matrix__th-label" aria-hidden="true">{{ subject.short | default: subject.name }}</span>
            {% endif %}
            <span class="sr-only">{{ subject.name }}</span>
          </th>
          {% endfor %}
        </tr>
      </thead>
      {% comment %}
        Every municipality and electoral area gets a heading, including those with
        no confirmed candidates yet — an absent heading reads as an oversight
        rather than as "nobody has announced here". Empty groups are marked
        data-empty so the filter script can hide them once a search or filter
        narrows the view.
      {% endcomment %}
      {% for muni in site.data.municipalities %}
        {% assign mc = site.data.candidates | where: "municipality", muni.slug %}
        <tbody class="scorecard-matrix__group" data-municipality="{{ muni.slug }}"{% if mc.size == 0 %} data-empty="true"{% endif %}>
          <tr class="scorecard-matrix__group-row">
            <th scope="colgroup" colspan="10" class="scorecard-matrix__group-head">{{ muni.name }}</th>
          </tr>
          {% if mc.size == 0 %}
          <tr class="scorecard-matrix__empty-row">
            <td colspan="10" class="scorecard-matrix__empty-cell">
              No candidates have publicly announced here yet. Check back, or
              <a href="mailto:{{ site.email }}?subject=Candidate%20in%20{{ muni.name | url_encode }}">tell us about one</a>.
            </td>
          </tr>
          {% endif %}
          {% for c in mc %}
          <tr class="scorecard-row" data-name="{{ c.name | downcase }}" data-municipality="{{ muni.slug }}" data-office="{{ c.office | downcase }}">
            <th scope="row" class="scorecard-matrix__name">
              <span class="scorecard-matrix__cand">{{ c.display_name | default: c.name }}</span>
              {%- assign status = "" -%}
              {%- if c.incumbent == true -%}{%- assign status = "Incumbent" -%}{%- elsif c.incumbent == false -%}{%- assign status = "Newcomer" -%}{%- endif -%}
              {%- if c.office and status != "" -%}<span class="scorecard-matrix__meta">{{ c.office }} · {{ status }}</span>
              {%- elsif c.office -%}<span class="scorecard-matrix__meta">{{ c.office }}</span>
              {%- elsif status != "" -%}<span class="scorecard-matrix__meta">{{ status }}</span>{%- endif -%}
            </th>
            {% for subject in site.data.subjects %}
            {% assign cell = c.scores[subject.id] %}
            <td class="scorecard-matrix__cell" data-topic="{{ subject.id }}">{% include grade-badge.html grade=cell %}</td>
            {% endfor %}
          </tr>
          {% endfor %}
        </tbody>
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
        of expertise, so no single organization assigns a candidate's full slate of grades
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
          <dd class="topic-def__desc">
            {{ subject.description }}
            {% if subject.example %}
            <span class="topic-def__example">
              <span class="topic-def__example-label">Example question</span>
              “{{ subject.example }}”
            </span>
            {% endif %}
          </dd>
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
        from the confirmed entries, so a name appears here after that public announcement
        — not before.
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
        announcements do not arrive in a tidy list — so gaps happen.
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
</div>

<script src="{{ '/assets/js/scorecard.js' | relative_url }}" defer></script>
