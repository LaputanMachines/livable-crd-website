---
layout: page
title: Contact
permalink: /contact/
description: >-
  Get in touch with Livable CRD. Email hello@livablecrd.ca, the best way to
  reach our non-partisan voter-education coalition covering Capital Regional
  District municipal elections.
---

<p>
  <strong>Email is the best way to reach us.</strong> Livable CRD is a coalition
  run by volunteers, so we do not staff a phone line or a mailing address, but
  our inbox is read by real people, and it is the fastest way to get a real
  answer.
</p>

{%- comment -%}
  The address as the page's one button, not boxed in a .callout. A callout is a
  box drawn round something that needs setting apart from the text, and once the
  reply-time line went there was a single link inside a large empty rectangle.

  Labelled with the address rather than "Email us": this is the page somebody
  arrives at to find out what the address is, and a button that hides it behind
  a click answers a question they did not ask. .btn-email keeps it in lower
  case; see _components.scss.
{%- endcomment -%}
<div class="btn-group">
  <a class="btn btn-primary btn-email" href="mailto:{{ site.email }}">{{ site.email }}</a>
</div>

<h2>What to write to us about</h2>
<p>
  Anything, genuinely. But these come up most often, and all of them are
  welcome:
</p>
<ul>
  <li>
    <strong>A candidate we are missing.</strong> Volunteers track every
    announcement across the region, and gaps happen. See
    <a href="{{ '/scorecard/#how-candidates-are-added' | relative_url }}">how candidates get added</a>
    to the scorecard.
  </li>
  <li>
    <strong>A correction.</strong> Wrong office, wrong municipality, misspelled
    name, or anything else that looks off. We would rather hear it than leave it
    wrong.
  </li>
  <li>
    <strong>You are a candidate.</strong> Questions about the questionnaire, your
    responses, or your published grades.
  </li>
  <li>
    <strong>Your organization wants to join the coalition</strong>, or contribute
    questions in your area of focus.
  </li>
  <li>
    <strong>You want to volunteer.</strong> Candidate tracking, outreach, design,
    and development all need hands.
  </li>
  <li>
    <strong>Questions about our methodology</strong>: how grades are assigned and
    who assigns them is documented in our
    <a href="{{ '/scorecard/#methodology' | relative_url }}">published methodology</a>.
  </li>
</ul>

<h2>Press and media</h2>
<p>
  Journalists on deadline: use the same address, and note your deadline in the
  subject line so we can prioritize it. Our
  <a href="{{ '/press/' | relative_url }}">press page</a> covers what to include,
  interview availability, and where to find our
  <a href="{{ '/brand/' | relative_url }}">logos and brand assets</a>.
</p>

<h2>Elsewhere</h2>
<p>
  We post updates on social media, and you can get scorecard releases and
  candidate news by <a href="{{ '/signup/' | relative_url }}">joining our mailing
  list</a>. Social messages are read less reliably than email, so for anything
  you need an answer to, please write to us.
</p>

{% include social-links.html class="social-links--icons" %}
