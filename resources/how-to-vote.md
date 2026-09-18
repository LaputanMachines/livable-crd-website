---
layout: default
title: How to vote
permalink: /resources/how-to-vote/
description: >-
  Who can vote in the 2026 Capital Regional District municipal elections, how to
  register, what identification to bring, and every way to cast a ballot:
  advance voting, general voting day, mail ballots and special voting.
---

{%- comment -%}
  The voting mechanics, in one place, for the region this site covers.

  Everything on this page is a rule set by the Province of B.C. or run by a
  municipality, not by this coalition. The site had grades and candidates and
  no answer at all to "am I allowed to vote, and how", which is the question in
  front of the one this project exists to help with.

  Sourced from the Province's "Voter's Guide to Local Elections in B.C. 2026"
  (www2.gov.bc.ca, under local-governments/governance-powers), its voter
  eligibility and voter registration pages, and Elections BC's 2026 general
  local elections page. Those are not linked on the page itself, so this comment
  is the only record of where each rule came from: do not edit a number here
  without re-reading them, because a wrong rule on this page costs somebody a
  ballot.

  Deliberately split from /resources/election-day/: this page is the rules you
  need before you go (eligibility, registration, identification, the ways to
  vote), and that one is the day itself. Each links to the other rather than
  repeating it.

  Dates come from _config.yml (`election_day`) wherever the site already knows
  them. The advance voting date and the rules are written out, because they are
  facts about this election published by the Province rather than anything this
  site derives, and a derived date on this page would be a guess dressed up as
  an answer.
{%- endcomment -%}
<div class="page-header">
  <div class="container container--narrow">
    <h1>How to vote</h1>
  </div>
</div>

<div class="container container--narrow page-content">
  <p>
    Municipal elections in British Columbia are run by each municipality, not by
    the Province and not by Elections BC. The rules below are the same
    everywhere in the Capital Regional District; the voting places, the advance
    voting days and whether mail ballots are offered are set by your own
    municipality, and the last section links to all of them.
  </p>

  <h2 id="can-i-vote">Can I vote?</h2>
  <p>
    There are two ways to be eligible, and you only need one of them.
  </p>
  <p>
    <strong>As a resident elector</strong>, you can vote where you live if you:
  </p>
  <ul>
    <li>
      are 18 or older on general voting day{% if site.election_day %}
      ({{ site.election_day | date: "%B %-d, %Y" }}){% endif %}, or when you
      register;
    </li>
    <li>are a Canadian citizen;</li>
    <li>have lived in B.C. for at least six months before you register;</li>
    <li>live in the municipality or electoral area you are voting in; and</li>
    <li>are not disqualified from voting by law.</li>
  </ul>
  <p>
    You do not need to own property, and you do not need a fixed address.
    Renters vote on exactly the same terms as owners, and someone living in a
    tiny home, an RV or without a residential address can register as a resident
    elector where they usually stay.
  </p>
  <p>
    <strong>As a non-resident property elector</strong>, you can vote in a
    municipality you do not live in if you are a Canadian citizen, 18 or older,
    have lived in B.C. for six months, and have been the registered owner of
    property there for at least 30 days. Some conditions come with it: only one
    owner per property may vote, and where a property has several owners the
    majority must designate that person in writing. Owning two properties in the
    same municipality does not get you two votes, property held through a
    company gets no vote at all, and you cannot vote as both a resident and a
    non-resident property elector in the same place.
  </p>
  <p>
    If you live in one municipality and study or work in another, you vote in
    one of them, not both. Students may choose either their usual home or where
    they attend school. People living on Reserve are eligible to vote; where
    they vote depends on whether the Reserve falls inside a municipality's or a
    regional district's boundaries, so the municipality or the CRD is the place
    to ask.
  </p>

  <h2 id="registering">Registering to vote</h2>
  <p>
    Registering for a local election is not the same thing as being on the
    provincial or federal list, and it works one of two ways depending on the
    municipality: some use the Provincial Voters List or keep their own register
    of electors, and others register everybody at the voting place on the day.
  </p>
  <p>
    In practice, you do not need to do anything in advance. Every municipality
    lets you register when you vote. It takes a minute at the table, and the
    only thing it asks of you is identification.
  </p>

  <h2 id="identification">What identification to bring</h2>
  <p>
    If you are already on your municipality's list of registered electors, you
    do not need identification at all. If you are not - or if your municipality
    registers everyone on the day - you need
    <strong>two separate pieces of identification</strong> that satisfy the
    election official of who you are and where you live. At least one of them
    must carry your signature.
  </p>
  <p>Documents that count include:</p>
  <ul>
    <li>a driver's licence;</li>
    <li>
      a B.C. Identification (BCID) card (a BC Services Card combined with a
      driver's licence counts as one piece, not two);
    </li>
    <li>a Certificate of Indian Status;</li>
    <li>
      a citizenship or membership card issued by an Indigenous governing body;
    </li>
    <li>a utility bill showing your residential address; or</li>
    <li>a credit or debit card.</li>
  </ul>
  <p>
    If none of your documents shows your address, you can make a solemn
    declaration about where you live instead. The full list of accepted
    documents is in the Local Government Elections Regulation, and your
    municipality's election office will tell you what it accepts if you are not
    sure. Voting as a non-resident property elector also means bringing proof of
    ownership - the address or legal description and the title certificate - and
    the written consent of the other owners if there are any.
  </p>

  <h2 id="ways-to-vote">The ways to vote</h2>
  <p>
    <strong>Advance voting.</strong> Every jurisdiction in B.C. must hold at
    least one advance voting opportunity on the tenth day before general voting
    day, which for this election is <strong>Wednesday, October 7, 2026</strong>.
    Most municipalities hold more than one; the CRD's electoral areas, for
    instance, are voting on October 7 and October 14. Advance voting is open to
    every eligible voter, with no reason required.
  </p>
  <p>
    <strong>General voting day.</strong>
    {%- if site.election_day %}
    {{ site.election_day | date: "%A, %B %-d, %Y" }}, with voting places open
    8:00 a.m. to 8:00 p.m. local time.
    {%- else %}
    Voting places are open 8:00 a.m. to 8:00 p.m. local time.
    {%- endif %}
    See <a href="{{ '/resources/election-day/' | relative_url }}">election day</a>
    for what to expect.
  </p>
  <p>
    <strong>Mail ballots.</strong> Available where a municipality has authorized
    them in its election bylaw, so this one genuinely varies - ask yours. The
    CRD offers mail ballots to residents and non-resident property electors in
    all three electoral areas, and applications there close on
    <strong>September 30, 2026</strong>.
  </p>
  <p>
    <strong>Special voting opportunities.</strong> Municipalities may run voting
    at hospitals, long-term care facilities and other places where getting to a
    voting place is hard. Only the electors they are designated for may vote at
    them.
  </p>
  <p>
    You cannot vote online or by phone in a B.C. local election. Nobody will
    ever email or text you a ballot.
  </p>

  <h2 id="where-to-vote">Where to vote</h2>
  <p>
    Voting places are set by each municipality's Chief Election Officer and
    published by that municipality, along with its advance voting days and its
    mail ballot rules. Not sure which municipality you vote in? The boundaries
    are not where most people think they are, so
    <a href="{{ '/resources/find-your-municipality/' | relative_url }}">check your
    address</a> first.
  </p>
  {% include municipal-election-links.html %}

  <p class="content-follow-up">
    Know how to vote, and not who to vote for yet? See
    <a href="{{ '/scorecard/' | relative_url }}">the scorecard</a>: every
    confirmed candidate in the region, graded on transit, housing, climate,
    arts and the rest of what a council decides.
  </p>
</div>
