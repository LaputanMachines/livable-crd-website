---
layout: default
title: Find your municipality
permalink: /resources/find-your-municipality/
description: >-
  Enter your address to find out which Capital Regional District municipality
  you vote in, and open that municipality's candidates, grades and official
  election page.
---

{%- comment -%}
  The address lookup, on a page of its own.

  It also sits on the homepage, inside the "Find your municipality" section, and
  both render the same _includes/muni-finder.html so the two cannot drift. What
  a separate page buys is a link: "check which ballot you get" is a thing
  volunteers, partner organizations and our own pages need to be able to point
  at directly, and until now the only way to reach the tool was to send somebody
  to the homepage and hope they scrolled.

  Wide container rather than container--narrow: the municipality index below the
  form is a grid of sixteen cards, and it wants the room.
{%- endcomment -%}
<div class="page-header">
  <div class="container">
    <h1>Find your municipality</h1>
  </div>
</div>

<div class="container page-content">
  <p>
    Which ballot you get depends on which municipality you live in, and in this
    region that is not obvious: 3400 Douglas St has a Victoria mailing address
    and votes in Saanich, and a great deal of what people call "Victoria" is
    really Saanich, Esquimalt or Oak Bay. Enter your address below and the
    municipality you vote in stays lit.
  </p>

  {% include muni-finder.html %}

  <h2 id="what-you-get">What is on each municipality's page</h2>
  <p>
    Every confirmed candidate running there, their grades once the coalition
    publishes them, how many seats are on the ballot, and a link out to that
    municipality's own election page for voting places and advance voting days.
    To compare candidates across the whole region instead, use the
    <a href="{{ '/scorecard/' | relative_url }}">full scorecard</a>.
  </p>

  <h2 id="next">Then what</h2>
  <p>
    Once you know where you vote:
    <a href="{{ '/resources/how-to-vote/' | relative_url }}">how to vote</a>
    covers eligibility, registering and identification, and
    <a href="{{ '/resources/election-day/' | relative_url }}">election day</a>
    covers the hours, the ballot and what to bring.
  </p>

  {%- comment -%}
    No privacy line here: the form carries its own, inside the box, and a second
    copy at the foot of the page said the same thing twice to the same reader.
  {%- endcomment -%}
  <p class="content-follow-up">
    <a href="{{ '/scorecard/' | relative_url }}">Compare every candidate in the
    region <span aria-hidden="true">&rarr;</span></a>
  </p>
</div>

<script src="{{ '/assets/js/muni-finder.js' | asset_url }}" defer></script>
