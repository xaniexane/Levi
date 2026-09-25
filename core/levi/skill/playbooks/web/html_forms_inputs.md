---
skill_id: web_html_forms_inputs
name: HTML Forms and Inputs
description: Build forms that validate, label, and submit correctly: input types, labels, fieldset, and native validation.
risk: info
permissions: []
requires_confirmation: false
tags: [html, frontend]
version: 1.0.0
---
# HTML Forms and Inputs
## Purpose
Collect user input with the browser's built-in help: correct keyboards, validation, and accessible labels.
## Key ideas
- Every input needs an associated <label>; placeholders are hints, not labels, and vanish when typing starts.
- Input types (email, tel, number, date) summon the right mobile keyboard and free validation.
- required, minlength, pattern, and type-based checks run natively before any JavaScript.
- Group related controls with <fieldset> and <legend> so screen readers announce the group purpose.
- The form's method and action define submission; name attributes define the keys the server receives.

## In practice
Design the form's data contract first: what keys, what types, what is required; then let the markup enforce it. Use the most specific input type available and add inputmode where the type is text but the content is numeric. Keep native validation enabled and layer custom messages on top rather than replacing the whole mechanism; browsers have already solved focus management for invalid fields. On submit, disable the button or guard against double-submission, because users double-click and networks retry. Always re-validate server-side: client validation is user experience, server validation is security.

```html
<form method="post" action="/signup">
  <label for="email">Email address</label>
  <input type="email" id="email" name="email" required autocomplete="email">

  <fieldset>
    <legend>Plan</legend>
    <label><input type="radio" name="plan" value="free" checked> Free</label>
    <label><input type="radio" name="plan" value="pro"> Pro</label>
  </fieldset>

  <button type="submit">Create account</button>
</form>
```

## Common mistakes
- Using placeholders as the only label, stranding screen-reader users and anyone who starts typing.
- Disabling native validation and reimplementing it worse in JavaScript.
- Trusting client-side validation alone and accepting unvalidated data on the server.

## Checklist
- Does every input have a real label, not just a placeholder?
- Are input types specific enough to trigger validation and mobile keyboards?
- Is the same validation enforced again on the server?

---
*Original work authored for LEVI. All explanations written fresh; no content copied from external sources.*
