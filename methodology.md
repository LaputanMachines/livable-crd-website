---
layout: page
title: Methodology
permalink: /methodology/
---

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
