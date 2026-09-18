---
layout: default
title: Election day
permalink: /resources/election-day/
description: >-
  General voting day in the Capital Regional District is Saturday, October 17,
  2026: voting hours, what is on the ballot, what to bring, where to vote, and
  when results are published.
---

{%- comment -%}
  The day itself: when it is, what is on the ballot, what to bring, where to go.

  Split from /resources/how-to-vote/ on purpose. That page is the rules a reader
  needs before the day - who is eligible, how registration and identification
  work, every way to cast a ballot. This one is the half-hour they actually
  spend voting, which is a different question asked by a reader in a different
  frame of mind. Neither repeats the other at length; both link across.

  Every date and seat count is read from _config.yml (`election_day`,
  `election_year`) and _data/municipalities.yml rather than typed here, the same
  contract the FAQ's #election-day panel and the municipality indexes keep: a
  wrong voting day is the worst fact this site could publish, so there is one
  copy of it. The 8:00 a.m. to 8:00 p.m. hours and the October 7 advance voting
  day come from the Province's 2026 Voter's Guide and are written out, because
  they are published facts rather than anything this site can derive.
{%- endcomment -%}
<div class="page-header">
  <div class="container container--narrow">
    <h1>Election day</h1>
  </div>
</div>

<div class="container container--narrow page-content">
  {%- if site.election_day %}
  <p>
    General voting day across British Columbia is
    <strong>{{ site.election_day | date: "%A, %B %-d, %Y" }}</strong>. Voting
    places are open <strong>8:00 a.m. to 8:00 p.m. local time</strong>. Local
    elections are held province-wide on the third Saturday of October every four
    years, so every municipality in the Capital Regional District votes on the
    same day.
  </p>
  {%- else %}
  <p>
    Voting places are open <strong>8:00 a.m. to 8:00 p.m. local time</strong> on
    general voting day. Local elections are held province-wide on the third
    Saturday of October every four years, so every municipality in the Capital
    Regional District votes on the same day.
  </p>
  {%- endif %}
  <p>
    If that Saturday does not work for you, you do not have to wait for it:
    every jurisdiction holds advance voting on
    <strong>Wednesday, October 7, 2026</strong> at a minimum, most hold more
    days than that, and some offer mail ballots. Employers are not required to
    give time off to vote in a local election, which is part of why advance
    voting exists.
  </p>

  <h2 id="what-to-bring">What to bring</h2>
  <p>
    If your municipality keeps a list of registered electors and you are on it,
    nothing: you give your name and get a ballot. If you are registering at the
    voting place - which every municipality allows, and some require - bring
    <strong>two pieces of identification</strong> showing who you are and where
    you live, at least one of them signed. A driver's licence, a BCID card, a
    Certificate of Indian Status, an Indigenous governing body's citizenship or
    membership card, a utility bill with your address, or a credit or debit card
    all count. If none of your documents shows your address, you can make a
    solemn declaration about where you live instead.
  </p>
  <p>
    The full rules, including what non-resident property electors have to bring,
    are on <a href="{{ '/resources/how-to-vote/' | relative_url }}">how to
    vote</a>.
  </p>

  <h2 id="on-the-ballot">What is on the ballot</h2>
  <p>
    More than most people expect. You vote for a mayor, for several councillors
    at once, and for school trustees, and the number of councillors depends on
    where you live:
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
    In the Capital Regional District's three electoral areas - Juan de Fuca,
    Salt Spring Island and the Southern Gulf Islands - there is no mayor and
    council. Voters there elect a regional director, and on the islands also
    Islands Trust trustees. School trustee races, regional directors and Islands
    Trust seats are outside the scope of this scorecard, which grades candidates
    for mayor and council.
  </p>
  <p>
    Because you are electing a whole council rather than one representative, a
    ballot asks you to mark several names - up to the number of seats. Marking
    fewer than the maximum is allowed and your ballot still counts.
  </p>

  <h2 id="where-to-vote">Where to vote</h2>
  <p>
    Voting places are chosen and published by each municipality's Chief Election
    Officer, and where you vote depends on which municipality you live in rather
    than what your mailing address says. If you are not certain,
    <a href="{{ '/resources/find-your-municipality/' | relative_url }}">check
    your address</a> - the boundaries surprise people, and a ballot cast in the
    wrong municipality is not a ballot.
  </p>
  {% include municipal-election-links.html %}

  <h2 id="help">If you need help at the voting place</h2>
  <p>
    Voting places must be as accessible as reasonably possible. You can ask an
    election official to bring a ballot out to you at the curb, ask an official,
    a friend or a relative to help you mark it, or bring a translator. Whoever
    helps you swears to keep your ballot secret and to mark it exactly as you
    direct.
  </p>

  <h2 id="results">Afterwards</h2>
  <p>
    Preliminary results are released by each municipality on election night,
    usually within a few hours of the polls closing, and are declared official a
    few days later once the count is finalized. Each municipality publishes its
    own; this site does not carry results.
  </p>

  {%- comment -%}
    The one thing on this page that is ours rather than the Province's: the
    reason a reader on this site is reading about election day at all. The
    grades are published by municipality ahead of the vote, and the candidate
    pages print, which is what makes them useful to carry to a voting place.
  {%- endcomment -%}
  <h2 id="before-you-go">Before you go</h2>
  <p>
    A council ballot asks for several names at once, and that is a lot to decide
    in the booth. Our
    <a href="{{ '/scorecard/' | relative_url }}">scorecard</a> grades every
    confirmed candidate in the region on transit, housing, climate, arts and the
    rest of what a council decides, and each candidate's page prints on a single
    sheet, so you can mark your choices at the kitchen table and carry them in
    with you.
  </p>

  <p class="content-follow-up">
    Voting rules and registration:
    <a href="{{ '/resources/how-to-vote/' | relative_url }}">how to vote
    <span aria-hidden="true">&rarr;</span></a>
  </p>
</div>
