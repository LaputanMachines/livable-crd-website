---
layout: default
title: The questionnaire
permalink: /questionnaire/
description: >-
  Every question the Livable CRD coalition put to Capital Regional District
  municipal election candidates, grouped by policy area, with the organization
  that wrote each one.
---

{%- comment -%}
  The full question set, read-only. Sourced from _data/questions.yml, which
  scripts/sync-questionnaire.py regenerates from the "Question Registry" tab of
  the grading spreadsheet, so this page cannot drift from what candidates were
  actually asked.

  Deliberately a separate page from /scorecard/, not a section of it: the
  scorecard answers "where does this candidate stand", and this answers "what
  were they asked", which is the question a candidate, a journalist or a partner
  organization arrives with. Each candidate's own page renders the same list
  again with that candidate's grades attached.
{%- endcomment -%}
{%- assign questions = site.data.questions -%}
{%- assign items = questions.items -%}

<div class="page-header">
  <div class="container">
    <h1>The questionnaire</h1>
  </div>
</div>

<div class="container page-content questionnaire">
  <p>
    Every confirmed candidate across the Capital Regional District is sent the
    same questionnaire. This is it, in full. Each policy area's questions were
    written by the coalition organization working on that area, and, where a
    question carries a grade, that same organization grades the answers to it.
  </p>

  {%- if items == nil or items.size == 0 %}
  <div class="callout">
    <p>
      <strong>The questionnaire is still being written.</strong>
      {{ questions.note | default: "Participating organizations are developing a shared questionnaire. The full question set is published here before candidates are surveyed." }}
    </p>
  </div>
  {%- else %}

  {%- comment -%}
    Counts stated rather than implied. A reader deciding whether to scroll 55
    questions deserves to know that is what they are in for, and the graded /
    published-unscored split is the honest version of "we asked more than we
    grade".
  {%- endcomment -%}
  {%- assign ungraded = questions.count | minus: questions.graded_count -%}
  {%- comment -%}
    Areas counted off the questions themselves, not off _data/subjects.yml: the
    site lists a "General" topic that the questionnaire has no questions for, so
    the subject list would overstate this page by one.
  {%- endcomment -%}
  {%- assign asked_subjects = items | map: "subject" | uniq -%}
  <div class="callout questionnaire-summary">
    <p>
      <strong>{{ questions.count }} questions across {{ asked_subjects.size }} policy areas.</strong>
      {{ questions.graded_count }} carry a grade.
      {%- if ungraded > 0 %}
      The other {% if ungraded == 1 %}one is published{% else %}{{ ungraded }} are published{% endif %}
      unscored: {% if ungraded == 1 %}it was{% else %}they were{% endif %} asked because the
      {% if ungraded == 1 %}answer informs{% else %}answers inform{% endif %} the coalition's work, but no
      letter is assigned to {% if ungraded == 1 %}it{% else %}them{% endif %}.
      {%- endif %}
      <a href="{{ '/scorecard/#methodology' | relative_url }}">How we grade</a>.
    </p>
  </div>

  {%- comment -%}
    Jump links, not a table of contents with numbers: the page is nine sections
    long and a reader almost always wants exactly one of them. Subjects with no
    questions are skipped rather than linked to an empty section — "General" has
    none, because the general comment boxes on the form are free text nobody
    grades.
  {%- endcomment -%}
  <nav class="questionnaire-jump" aria-label="Jump to a policy area">
    <span class="questionnaire-jump__label">Jump to</span>
    <ul class="questionnaire-jump__list">
      {%- for subject in site.data.subjects %}
      {%- assign subject_questions = items | where: "subject", subject.id %}
      {%- if subject_questions.size > 0 %}
      <li>
        <a href="#questions-{{ subject.id }}" style="--card-accent: {{ subject.accent }}">
          {{ subject.short | default: subject.name }}
          <span class="questionnaire-jump__count">{{ subject_questions.size }}</span>
        </a>
      </li>
      {%- endif %}
      {%- endfor %}
    </ul>
  </nav>

  {%- for subject in site.data.subjects %}
  {%- assign subject_questions = items | where: "subject", subject.id %}
  {%- if subject_questions.size == 0 %}{% continue %}{% endif %}
  {%- comment -%}
    Owner is stated once per section rather than on all six of its questions:
    within a policy area it is nearly always the same organization, and repeating
    it turned every card into the same line of small print. The per-question
    line below only appears where that question's owner differs from the
    section's, which is where a reader actually needs it.

    `credited` is the section-level claim, and it needs every question in the
    section to name the same organization — not just the ones that name anyone.
    Some registry rows have no publishable owner (see sync-questionnaire.py on
    email-shaped owners), and crediting a whole policy area to the one
    organization that happens to be named on its last question would put words
    in their mouth about questions they did not write.
  {%- endcomment -%}
  {%- assign owners = subject_questions | map: "owner" | compact | uniq -%}
  {%- assign owned = subject_questions | where_exp: "q", "q.owner" -%}
  {%- assign credited = false -%}
  {%- if owners.size == 1 and owned.size == subject_questions.size -%}
    {%- assign credited = true -%}
  {%- endif -%}
  {%- comment -%}
    "Written and graded by" is the coalition's standing claim about who owns a
    policy area, and it is false for an area whose questions carry no grade:
    Healthcare access asks one question and scores none of it. Say what is true
    of the section in front of the reader.
  {%- endcomment -%}
  {%- assign graded_here = subject_questions | where: "graded", true -%}
  {%- if graded_here.size > 0 -%}
    {%- assign owner_verb = "Written and graded by" -%}
  {%- else -%}
    {%- assign owner_verb = "Written by" -%}
  {%- endif -%}
  <section class="questionnaire-section" id="questions-{{ subject.id }}" style="--card-accent: {{ subject.accent }}">
    <header class="questionnaire-section__head">
      <img class="questionnaire-section__icon" src="{{ '/assets/images/icons/' | append: subject.icon | relative_url }}" alt="" width="32" height="32" loading="lazy">
      <div class="questionnaire-section__titles">
        <h2>{{ subject.name }}</h2>
        <p class="questionnaire-section__meta">
          {{ subject_questions.size }} question{% if subject_questions.size != 1 %}s{% endif %}
          {%- if credited %} · {{ owner_verb }} {{ owners[0] }}{% endif %}
        </p>
      </div>
    </header>
    <p class="questionnaire-section__desc">{{ subject.description }}</p>

    <ol class="questionnaire-list">
      {%- for q in subject_questions %}
      <li class="questionnaire-item{% unless q.graded %} questionnaire-item--ungraded{% endunless %}" id="question-{{ q.label | downcase }}">
        {%- comment -%}
          Pill first, then the question id, matching a candidate's page. The id
          is a reference for citing a question or looking it up; whether it
          carries a grade at all is the one thing that changes how the question
          itself is read, so it goes above it. What the question is worth and
          who grades it are facts about the answer, and sit below in the foot.
        {%- endcomment -%}
        <div class="questionnaire-item__head">
          {%- unless q.graded %}
          <span class="questionnaire-item__tag">Not graded</span>
          {%- endunless %}
          <span class="questionnaire-item__label">{{ q.label }}</span>
        </div>
        <p class="questionnaire-item__question">{{ q.question }}</p>
        {%- comment -%}
          The answer's shape stays a plain line: it is a description of the form
          a candidate filled in, and reads as a sentence rather than a label. It
          sits above the choices rather than below them because it is the thing
          that tells a reader how to read the list underneath — whether they are
          picking one of these or as many as they like.

          Absent on the ten multi-selects whose own wording already says "select
          all that apply" or "select up to five", which is the same sentence one
          line higher up. See SELECTION_RULE_CUES in sync-questionnaire.py.
        {%- endcomment -%}
        {%- if q.type_label %}
        <p class="questionnaire-item__meta">{{ q.type_label }}</p>
        {%- endif %}
        {%- if q.options %}
        {%- comment -%}
          The answer choices, which are the reason this page exists in the shape
          it does: candidates asked to work the questionnaire through with their
          team before opening the form, and half of these questions are a choice
          between options they could not read anywhere until now.

          Only multi-selects carry them today. The raw tab names every option of
          a multi-select in a column header whether or not anyone picked it,
          while a single-choice question exports as one column holding whatever
          answer came back, so its full option set is recoverable only from the
          form itself. A question with no list here has options; the site does
          not yet know them.
        {%- endcomment -%}
        {%- comment -%}
          Drawn as the control the form draws: a circle where a candidate picks
          one, a square where they pick several. The shape is doing the work the
          question's wording otherwise has to — a reader knows which kind of
          question they are looking at before reading a word of it, and a list
          of full sentences stops reading as a paragraph.
        {%- endcomment -%}
        {%- if q.type contains "multi" %}{% assign option_control = "multi" %}{% else %}{% assign option_control = "single" %}{% endif -%}
        <ul class="questionnaire-item__options questionnaire-item__options--{{ option_control }}">
          {%- for option in q.options %}
          <li>{{ option }}</li>
          {%- endfor %}
        </ul>
        {%- comment -%}
          The cap, where the form sets one the question does not mention. TRN-01
          reads "select all that apply" and stops a candidate at four of its six
          — worth knowing while a team is still deciding which four. Suppressed
          on the questions that state their own ("Select up to five"); see
          SELECTION_CAP_CUES in sync-questionnaire.py.
        {%- endcomment -%}
        {%- if q.option_limit %}
        <p class="questionnaire-item__meta questionnaire-item__meta--limit">Up to {{ q.option_limit }} may be selected.</p>
        {%- endif %}
        {%- endif %}
        {%- if q.areas %}
        {%- comment -%}
          GEN-02's twelve line items. Listed here because the question on its
          own ("how would you allocate it across the following areas?") names
          none of them, and the areas are most of what the question actually
          asks: which twelve things a candidate is made to trade off against
          each other is the whole design of it.

          A different thing from the options above and styled differently: these
          are twelve budgets to fill in, not a list to pick from.
        {%- endcomment -%}
        <ul class="questionnaire-item__areas">
          {%- for area in q.areas %}
          <li>{{ area }}</li>
          {%- endfor %}
        </ul>
        {%- endif %}
        {%- comment -%}
          The foot: what the question is worth, and — where the section head
          could not credit the whole policy area to one organization — who wrote
          and grades this one. Both are pills, because both are the same kind of
          fact as the "Not graded" tag above and a reader picks them out of the
          page rather than reading them in sequence.
        {%- endcomment -%}
        {%- assign show_owner = false -%}
        {%- if q.owner and credited == false %}{% assign show_owner = true %}{% endif -%}
        {%- if q.weight or show_owner %}
        <div class="questionnaire-item__foot">
          {%- if q.weight %}
          <span class="questionnaire-item__tag questionnaire-item__tag--weight">{{ q.weight }} of this topic's grade</span>
          {%- endif %}
          {%- if show_owner %}
          <span class="questionnaire-item__tag questionnaire-item__tag--owner">{% if q.graded %}Written and graded by{% else %}Written by{% endif %} {{ q.owner }}</span>
          {%- endif %}
        </div>
        {%- endif %}
      </li>
      {%- endfor %}
    </ol>
  </section>
  {%- endfor %}

  <div class="callout questionnaire-cta">
    <h2>Where the answers go</h2>
    <p>
      Answers come back to the coalition and are graded by the organization that
      wrote the questions. A policy area is published on a candidate's page only
      once that organization has finished grading it, so a candidate may show
      grades in one area and nothing in another for a while.
    </p>
    <div class="btn-group">
      <a class="btn btn-primary" href="{{ '/scorecard/' | relative_url }}">See the scorecard</a>
      <a class="btn btn-secondary" href="{{ '/scorecard/#methodology' | relative_url }}">How we grade</a>
    </div>
  </div>
  {%- endif %}
</div>
