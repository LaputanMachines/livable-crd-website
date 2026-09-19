---
title: "Project update: Grades to be published on September 22nd"
date: 2026-09-18 16:30:00 -0700
description: >-
  The questionnaire cut-off brought a large number of last-minute candidate
  responses. Publication moves from September 20 to September 22 so every one of
  them is graded to the same standard as the rest.
---

{%- assign grades_released = site.data.deadlines | where: "id", "grades-released" | first -%}
{%- assign web_cutoff = site.data.deadlines | where: "id", "web-cutoff" | first -%}

Responses and grades were scheduled to be published on September 20. They will
now be published on
<strong>{{ grades_released.date | date: "%A, %B %-d, %Y" }}</strong>, two days
later. Nothing else about the release changes. Everything still goes up at once
rather than as it is finished, still organized by municipality on the
[scorecard]({{ '/scorecard/' | relative_url }}), and still well ahead
of{% if site.election_day %} general voting day,
{{ site.election_day | date: "%A, %B %-d, %Y" }}{% else %} election day{% endif %}.

## Why the date moved

The deadline for candidates to return the questionnaire was
{{ web_cutoff.date | date: "%B %-d" }}. A large share of the responses we
received arrived in the last few days before it, and a substantial number on the
final day itself. That is a good outcome for the scorecard: each of those
submissions is a candidate who chose to tell voters where they stand, and each
one belongs on the scorecard alongside the rest.

The original schedule left two days between the cut-off and publication, which
was enough for the number of last-minute responses the coalition planned for and
not enough for the number that came. Every response is graded question by
question against a published rubric, by the partner organization that wrote those
questions, and reviewed before anything is posted. That is slower than reading,
deliberately: a grade has to be one the coalition can explain and one a candidate
can check against the
[methodology]({{ '/faq/#methodology' | relative_url }}).

Two extra days is the smallest change that finishes that work without shortening
it. The alternatives were worse. Publishing part of the region and filling in the
rest later would leave candidates looking unresponsive when they were not, and
would break the one rule the release runs on, which is that nothing appears
before everything does. Grading faster would put a weaker grade under a
candidate's name during an election, which is the outcome the methodology exists
to prevent.

## What has not moved

The candidate cut-off is unchanged. {{ web_cutoff.date | date: "%B %-d" }} was
the last day to return the questionnaire and be graded, on this site and on
anything printed, and moving the publication date does not reopen it. The two
dates do different jobs: one closes the questionnaire, the other releases the
results, and treating a change to the second as a change to the first would be
unfair to every candidate who met the deadline as published. Candidates who
missed it are still welcome to write to us, and we will note that they responded
late, but a late response is not graded.

Candidates who did respond, including on the final day, are in the grading queue.
The two additional days are for grading, not for a second look at who qualifies.

## What to expect

Voters do not need to do anything before
{{ grades_released.date | date: "%B %-d" }}. Until then a candidate who replied
shows an hourglass rather than a letter on the scorecard, which says nothing
about how that candidate's grading is going. On release day the responses and the
grades appear together, by municipality.

The [project timeline]({{ '/faq/#deadlines' | relative_url }}) has been updated,
and every page that quotes the publication date now shows the new one. Anyone who
wants the announcement can [subscribe to the mailing
list]({{ '/signup/' | relative_url }}). The coalition informs; it does not
endorse.
