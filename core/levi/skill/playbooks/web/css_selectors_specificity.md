---
skill_id: web_css_selectors_specificity
name: CSS Selectors and Specificity
description: How selectors match and which rule wins: specificity scoring, the cascade order, and keeping selectors lean.
risk: info
permissions: []
requires_confirmation: false
tags: [css, frontend]
version: 1.0.0
---
# CSS Selectors and Specificity
## Purpose
Write selectors you can reason about, so the rule that wins is the rule you intended.
## Key ideas
- Specificity is scored per selector: ids outweigh classes, classes outweigh element names.
- Inline styles beat all selectors; !important beats everything and should be reserved for utilities and overrides.
- When specificity ties, the later rule in source order wins; this is the cascade's final tiebreaker.
- Origin matters too: author styles beat user styles beat browser defaults, with !important flipping each layer.
- Long selector chains are brittle; prefer short, class-based selectors that say what the thing is.

## In practice
Keep specificity flat and low on purpose: style with single classes, reserve ids for JavaScript hooks, and avoid nesting selectors three levels deep just because the markup is nested. When a rule is not applying, compute the competing specificities instead of escalating with !important; the devtools panel shows the winning and losing rules side by side. If you find yourself writing !important to beat your own stylesheet, that is a signal to simplify the selectors, not to armor them. Utility classes work precisely because they are single-class, late in the cascade, and honest about it.

```css
/* Low, flat, predictable */
.btn { padding: 8px 16px; }
.btn-primary { background: #2563eb; color: #fff; }

/* High specificity: hard to override later, avoid */
#sidebar .nav ul li a.active { color: red; }

/* The cascade tiebreaker: later wins at equal specificity */
.alert { color: blue; }
.alert { color: red; } /* this one applies */
```

## Common mistakes
- Reaching for !important to win fights with your own selectors instead of lowering specificity.
- Using ids for styling, locking those elements out of reusable class-based overrides.
- Writing long descendant chains that break the moment markup is refactored.

## Checklist
- Are most selectors single classes with flat specificity?
- Is !important absent except in deliberate utility layers?
- When a rule loses, do you compare specificity instead of escalating?

---
*Original work authored for LEVI. All explanations written fresh; no content copied from external sources.*
