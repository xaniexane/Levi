---
skill_id: web_html_iframes_sandbox
name: HTML Iframes and Sandboxing
description: Embed third-party content with iframes safely: sandbox attributes, allow lists, and sizing strategies.
risk: info
permissions: []
requires_confirmation: false
tags: [html, frontend, security]
version: 1.0.0
---
# HTML Iframes and Sandboxing
## Purpose
Use iframes for untrusted or third-party content without handing the embedded page the keys to yours.
## Key ideas
- An iframe embeds a full separate document with its own origin, scripts, and storage.
- The sandbox attribute strips capabilities by default; allow-scripts and allow-same-origin re-grant them selectively.
- sandbox without allow-same-origin keeps the framed page at arm's length even if it runs scripts.
- The allow attribute gates powerful features (camera, fullscreen, payment) per iframe.
- Cross-origin iframes cannot reach into your DOM, but they can still navigate the top page unless sandboxed.

## In practice
Default to sandboxed iframes for anything you did not author: embeds, widgets, user-supplied content previews. Grant only the capabilities the embed demonstrably needs, and test what breaks when you remove each one; most embeds need far less than their documentation claims. Communicate with cooperative iframes via postMessage with strict origin checks on both sides, never by reaching across the DOM boundary. Size iframes deliberately with aspect-ratio or fixed heights rather than hoping content fits; a collapsed or overflowing frame looks broken and invites clickjacking confusion.

```html
<iframe
  src="https://widgets.example.com/map"
  title="Store locator map"
  sandbox="allow-scripts"
  allow="geolocation"
  loading="lazy"
  style="width:100%; aspect-ratio: 16/9; border:0">
</iframe>

<script>
// Talk to a cooperative iframe safely
window.addEventListener("message", (e) => {
  if (e.origin !== "https://widgets.example.com") return;
  console.log("widget says:", e.data);
});
</script>
```

## Common mistakes
- Embedding third-party content in unsandboxed iframes with full script and same-origin powers.
- Granting allow-same-origin plus allow-scripts together, which lets the framed page escape the sandbox.
- Accepting postMessage events without checking e.origin, acting on messages from any site.

## Checklist
- Are third-party iframes sandboxed with minimal re-granted capabilities?
- Is allow-same-origin withheld unless the embed genuinely needs it?
- Do postMessage handlers verify the sender's origin?

---
*Original work authored for LEVI. All explanations written fresh; no content copied from external sources.*
