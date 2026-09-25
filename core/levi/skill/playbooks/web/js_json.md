---
skill_id: web_js_json
name: JavaScript JSON Handling
description: Parse and produce JSON safely: validation, revivers, error handling, and what JSON cannot carry.
risk: info
permissions: []
requires_confirmation: false
tags: [javascript, frontend, http]
version: 1.0.0
---
# JavaScript JSON Handling
## Purpose
Move data between JSON text and JavaScript values without crashes or silent corruption.
## Key ideas
- JSON.parse throws on malformed input; always parse inside try/catch at trust boundaries.
- JSON.stringify drops functions, undefined, and symbols, and converts dates to ISO strings silently.
- Circular structures make stringify throw; decide how to handle cycles before they appear.
- Validate parsed shape (required fields, types) before use; parsing successfully does not mean the data is right.
- A reviver function can transform values during parse, e.g. reviving date strings into Date objects.

## In practice
Treat every JSON.parse of external data as a trust boundary: catch syntax errors and then validate the shape with explicit checks or a schema, because a 200 response with an unexpected body is a routine production event. When stringifying, remember the silent conversions: dates become strings, undefined object values vanish, and Map/Set become empty objects unless you convert them first. Keep a canonical serialization for anything you sign or compare (sorted keys, no whitespace surprises), since two equivalent objects can stringify differently. Log the raw text on parse failure; without it you are debugging blind.

```javascript
function parseOrder(text) {
  let data;
  try {
    data = JSON.parse(text);
  } catch (err) {
    throw new Error(`invalid order JSON: ${err.message}`);
  }
  if (typeof data.id !== "number" || !Array.isArray(data.items)) {
    throw new Error("order JSON has wrong shape");
  }
  return data;
}

const payload = JSON.stringify({ id: 42, items: ["book"] });
```

## Common mistakes
- Parsing without try/catch and crashing the whole handler on one bad payload.
- Trusting parsed shape without validation, then reading properties of undefined.
- Stringifying Maps, Sets, or class instances and losing their contents silently.

## Checklist
- Is external JSON parsed inside try/catch with shape validation after?
- Are silent stringify conversions (dates, undefined, Map) accounted for?
- Is raw text preserved in logs when parsing fails?

---
*Original work authored for LEVI. All explanations written fresh; no content copied from external sources.*
