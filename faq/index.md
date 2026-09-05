---
layout: default
title: Frequently asked questions
permalink: /faq/
description: >-
  How Livable CRD grades Capital Regional District municipal election
  candidates: the methodology, who writes and grades each topic, what every
  category covers, how candidates get added, and the questionnaire deadlines.
---

{%- comment -%}
  Every one of these panels used to sit at the foot of /scorecard/, below the
  matrix. They are answers about how the project works rather than about any
  candidate, and half the pages on the site were deep-linking past a screen of
  grades to reach them, so they are their own page now and /scorecard/ links
  down to it.

  Anchors are unchanged on purpose (#methodology, #who-grades, #categories,
  #category-<id>, #how-candidates-are-added, #deadlines): they are what the
  homepage topic cards, the candidate pages and the code of conduct link to,
  and only the path in front of them moved.
{%- endcomment -%}
<div class="page-header">
  <div class="container">
    <h1>Frequently asked questions</h1>
  </div>
</div>

<div class="container page-content">
  {%- comment -%}
    A plain intro paragraph directly under the header, the same shape the
    scorecard and donate pages open with: what the page is, and what a reader
    can expect to find on it, before any of the page's own furniture.
  {%- endcomment -%}
  <p>
    How the coalition's candidate scorecard is built, in the coalition's own
    words. Each panel below opens onto one answer: when the election is and what
    is on the ballot, what the letter grades mean and how they are assigned,
    which organization writes and grades each topic, what every policy category
    covers, how a candidate gets added to the
    <a href="{{ '/scorecard/' | relative_url }}">scorecard</a>, and the dates the
    <a href="{{ '/questionnaire/' | relative_url }}">questionnaire</a> runs to.
  </p>

  {%- comment -%}
    First panel, and the only one on this page not about how the scorecard
    works. It is here because it was the plainest question about this election
    that the site could not answer anywhere: the schedule this project runs to
    was published in full, and the date the whole schedule exists to get ahead
    of was not written down once.

    Both facts come from _config.yml (`election_day`, `election_year`) and
    _data/municipalities.yml, so this panel and the municipality indexes
    cannot disagree about the date or about how many seats a council has.
  {%- endcomment -%}
  <details class="methodology" id="election-day">
    <summary>When is the {% if site.election_year %}{{ site.election_year }} {% endif %}municipal election?</summary>
    <div class="methodology__body">
      {%- if site.election_day %}
      <p>
        General voting day across British Columbia is
        <strong>{{ site.election_day | date: "%A, %B %-d, %Y" }}</strong>. Local
        elections are held province-wide on the third Saturday of October every
        four years, so every municipality in the Capital Regional District votes
        on the same day.
      </p>
      {%- endif %}
      <p>
        Advance voting days, voting places, and mail-in ballots are set by each
        municipality rather than by the province, and each one publishes its own.
        Every <a href="{{ '/scorecard/' | relative_url }}">municipality's page on
        this site</a> links to its election page for exactly that.
      </p>

      <h2>What is on the ballot</h2>
      <p>
        Each municipality elects a mayor and a council, and the size of the
        council varies:
      </p>
      <ul>
        {%- for muni in site.data.municipalities %}
        {%- if muni.council_seats %}
        <li>
          <strong>{{ muni.name }}</strong>:
          {{ muni.mayor_seats }} mayor and {{ muni.council_seats }} councillors
        </li>
        {%- endif %}
        {%- endfor %}
      </ul>
      <p>
        Voters also elect school trustees, and in the electoral areas and on the
        islands a regional director and Islands Trust trustees. Those races are
        outside the scope of this scorecard, which covers candidates for mayor
        and council.
      </p>
    </div>
  </details>

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

      {%- comment -%}
        The two empty states, spelled out. The legend at the top of the scorecard has
        room for two words each; this is where a reader who wants to know what a
        dash costs a candidate can find out that sometimes it costs them nothing.
      {%- endcomment -%}
      <h2>When there is no letter</h2>
      <dl class="grade-defs">
        <div class="grade-def">
          <dt class="grade-def__term">
            {% include grade-badge.html grade="" state="review" %}
            <span class="grade-def__label">Not published yet</span>
          </dt>
          <dd class="grade-def__desc">
            This candidate returned the questionnaire and this topic has not been
            published yet. Grading is done by the coalition organization that wrote
            the topic's questions, and each topic is published as that organization
            finishes it, so a candidate can show letters in one topic and this in
            another. It also shows on the two topics we do not grade,
            <strong>General</strong> and <strong>Healthcare access</strong>,
            until their answers are released. It says nothing about how the
            topic is going.
          </dd>
        </div>
        <div class="grade-def">
          <dt class="grade-def__term">
            {% include grade-badge.html grade="" state="answers" %}
            <span class="grade-def__label">Answered, not graded</span>
          </dt>
          <dd class="grade-def__desc">
            The candidate answered, this is a topic we do not assign a letter in,
            and their answers are published. Two topics work this way:
            <strong>General</strong>, which asks what a candidate would change and
            how they would split a budget, and <strong>Healthcare access</strong>,
            which asks one question about primary care clinics. The coalition puts
            them to every candidate because the answers are worth reading, not
            because we score them. Open the candidate's page to read what they
            wrote.
          </dd>
        </div>
        <div class="grade-def">
          <dt class="grade-def__term">
            {% include grade-badge.html grade="" %}
            <span class="grade-def__label">Not graded</span>
          </dt>
          <dd class="grade-def__desc">
            No completed questionnaire has come back from this candidate yet, so
            there is nothing to publish in any topic. A candidate who has replied
            carries an hourglass or a speech bubble instead. A dash is never a bad
            grade: the grades are <strong>A</strong> through <strong>F</strong>,
            and a candidate who scores poorly gets a letter saying so.
          </dd>
        </div>
      </dl>

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

      <p>
        Responses are published as written. The one exception is set out in our
        <a href="{{ '/code-of-conduct/' | relative_url }}">questionnaire code of conduct</a>:
        hateful, harassing, or threatening content is neither graded nor published.
        Disagreeing with the coalition is not covered by that: a low grade and a
        conduct decision are separate things, decided separately.
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
        of focus, so no single organization assigns a candidate's full slate of grades
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
          <dd class="topic-def__desc">{{ subject.description }}</dd>
        </div>
        {% endfor %}
      </dl>
    </div>
  </details>

  <details class="methodology" id="how-candidates-are-added">
    <summary>How candidates get added to the scorecard</summary>
    <div class="methodology__body">
      <p>
        Our volunteers maintain a working spreadsheet of everyone running for municipal
        office across the Capital Regional District. A candidate's entry starts out
        internal to that sheet, and is marked <strong>confirmed</strong> only once they
        have <strong>publicly announced their candidacy</strong>. The scorecard is generated
        from the confirmed entries, so a name appears there after that public
        announcement, not before.
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
        announcements do not arrive in a tidy list, so gaps happen.
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

  {%- comment -%}
    Every date below comes from _data/deadlines.yml, including the one quoted
    mid-sentence: writing "September 18" into the prose would be a second copy
    to keep in sync with the list right above it.
  {%- endcomment -%}
  {%- assign web_cutoff = site.data.deadlines | where: "id", "web-cutoff" | first -%}
  <details class="methodology" id="deadlines">
    <summary>Key dates, and what a missed deadline means</summary>
    <div class="methodology__body">
      <p>
        The grades on the scorecard come from the coalition questionnaire, which goes
        to every confirmed candidate. Only one date below is one a candidate can
        miss, and it carries its own heading underneath; the others are the
        coalition milestones leading up to it and the publication date that
        follows it, listed so the whole schedule is public. The same schedule runs as a
        timeline on the <a href="{{ '/' | relative_url }}">homepage</a>.
      </p>

      {% include deadline-list.html class="deadline-list--stacked" %}

      <h2>What the deadline covers</h2>
      <p>
        <strong>{{ web_cutoff.date | date: "%B %-d" }}</strong> is the last day a
        candidate can return the questionnaire and still be graded. One date
        covers everything we produce: the grades on this website, and the printed
        scorecards, stickers, and posters.
      </p>
      <p>
        Until then the questionnaire is open and grading runs alongside it, so
        results reach the scorecard in batches as each partner organization finishes
        the topics it owns, rather than all at once on the closing day. A
        candidate who returns it early is graded early.
      </p>

      <h2>What happens to a candidate who does not respond</h2>
      <p>
        A missed deadline never removes anyone from the scorecard. Every confirmed
        candidate stays listed with their row intact; their topic grades simply
        stay pending. We do not treat silence as a failing grade, and we do not
        drop the candidate from the list. See
        <a href="#how-candidates-are-added">how candidates get added</a> for why the
        list itself is not selective.
      </p>
      <p>
        If you are a candidate and the questionnaire has not reached you, or you
        want to confirm your response was received,
        <a href="mailto:{{ site.email }}?subject=Questionnaire%20deadline">email us at {{ site.email }}</a>.
      </p>
    </div>
  </details>
</div>

{%- comment -%}
  Opens whichever panel a #hash points into. The scorecard used to carry this
  inside scorecard.js because the panels were on that page; it is its own file
  now so the FAQ can load it without the matrix filtering code.
{%- endcomment -%}
<script src="{{ '/assets/js/details-hash.js' | asset_url }}" defer></script>
