---
layout: page
title: Join the mailing list
permalink: /signup/
description: >-
  Get updates from Livable CRD on our non-partisan candidate scorecard for
  Capital Regional District municipal elections.
---

<p>
  Sign up for occasional updates from <strong>Livable CRD</strong> — scorecard
  releases, candidate news, and ways to get involved ahead of municipal
  elections in the Capital Regional District. We never share your information.
</p>

{% comment %}
  Action Network embedded signup form. The form slug is set in _config.yml
  (site.signup_form_slug). The <div> id and the widget src must both reference
  the same slug, per Action Network's embed code.
{% endcomment %}
<div class="an-embed">
  <div id="can-form-area-{{ site.signup_form_slug }}" style="width: 100%"></div>
  <script
    type="text/javascript"
    src="https://actionnetwork.org/widgets/v5/form/{{ site.signup_form_slug }}?format=js&source=widget">
  </script>
</div>

{% comment %}
  Post-render cleanup of the Action Network widget. The widget renders async, so
  poll until it exists, then:
    1. Force every "Opt in to email updates" checkbox checked and hide its row
       (this is a mailing-list signup, so consent is implicit).
    2. Strip Action Network branding — the logo image and the "Action by" /
       "Sponsored by" credit lines. These have no stable class names, so we match
       the logo by image src and the credit block by its text content.
{% endcomment %}
<script>
  (function () {
    function cleanup() {
      var form = document.querySelector('.an-embed #can_embed_form');
      if (!form) { return false; }

      // 1. Opt-in checkboxes: check + hide.
      form.querySelectorAll('input[type="checkbox"]').forEach(function (cb) {
        cb.checked = true;
        var row = cb.closest('li') || cb.parentNode;
        if (row) { row.style.display = 'none'; }
      });

      // 2a. Action Network logo — image (any host), wordmark alt, or logo link.
      form.querySelectorAll(
        'img[src*="actionnetwork"], img[src*="action_network"], ' +
        'img[alt*="action network" i], a[href*="actionnetwork.org"]'
      ).forEach(function (el) { el.style.display = 'none'; });

      // 2b. "Action by" / "Sponsored by" credit block.
      form.querySelectorAll('div, p, li').forEach(function (el) {
        var text = (el.textContent || '').trim();
        if (text.length < 200 && /^(Action by|Sponsored by)/i.test(text)) {
          el.style.display = 'none';
        }
      });

      // 2c. Country field: this is a CRD-only list, so country is always Canada
      // (Action Network records it server-side). Hide the whole country UI — the
      // <select> and its container, plus the "Not in <country>?" toggle link.
      var country = form.querySelector('select');
      if (country) {
        // Hide the select's immediate parent (the small country wrapper) — not
        // an ancestor <div>, which wraps every field and would hide the form.
        (country.parentNode || country).style.display = 'none';
      }
      form.querySelectorAll('a').forEach(function (a) {
        if (/^not in\b/i.test((a.textContent || '').trim())) {
          a.style.display = 'none';
        }
      });

      return true;
    }
    var tries = 0;
    var timer = setInterval(function () {
      if (cleanup() || ++tries > 40) { clearInterval(timer); }
    }, 250);
  })();
</script>

<p class="signup-disclaimer">
  We'll only email you project updates and scorecard-related information —
  nothing else. You can unsubscribe at any time.
</p>
