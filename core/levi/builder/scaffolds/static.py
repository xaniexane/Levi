"""Static scaffold: single-page frontend, no build step.

Renders a complete ``index.html`` (inline CSS/JS) plus a README.
Runs with ``python3 -m http.server`` and nothing else.
"""

from __future__ import annotations

from typing import Dict

from .spec import BuildSpec


def render_static(spec: BuildSpec) -> Dict[str, str]:
    features_html = (
        "\n".join(
            f'      <li class="feature">{_esc(f)}</li>' for f in spec.features[:8]
        )
        or '      <li class="feature">A clean, fast single page.</li>'
    )
    pages_js = ", ".join(f'"{p}"' for p in spec.pages[:6]) or '"home"'

    index_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_esc(spec.title)}</title>
<style>
  :root {{ color-scheme: dark; }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; font-family: system-ui, -apple-system, sans-serif;
    background: #0b0e14; color: #e6e9f0; line-height: 1.6;
  }}
  header {{
    padding: 3rem 1.5rem; text-align: center;
    background: radial-gradient(ellipse at 50% 0%, #1b2340 0%, #0b0e14 70%);
  }}
  h1 {{ margin: 0 0 .5rem; font-size: 2.2rem; letter-spacing: .02em; }}
  p.tag {{ color: #9aa4c0; max-width: 40rem; margin: 0 auto; }}
  main {{ max-width: 46rem; margin: 0 auto; padding: 2rem 1.5rem 4rem; }}
  .features {{ list-style: none; padding: 0; display: grid; gap: .75rem; }}
  .feature {{
    background: #121828; border: 1px solid #232c4a; border-radius: .6rem;
    padding: .9rem 1.1rem;
  }}
  .demo {{ margin-top: 2.5rem; background: #121828; border: 1px solid #232c4a;
           border-radius: .6rem; padding: 1.2rem; }}
  button {{
    background: #3b5bff; color: white; border: 0; border-radius: .5rem;
    padding: .6rem 1.2rem; font-size: 1rem; cursor: pointer;
  }}
  button:hover {{ background: #2f4ae0; }}
  #out {{ margin-top: 1rem; color: #9aa4c0; font-family: monospace; }}
  footer {{ text-align: center; color: #5b6480; padding: 2rem; font-size: .85rem; }}
</style>
</head>
<body>
<header>
  <h1>{_esc(spec.title)}</h1>
  <p class="tag">{_esc(spec.description)}</p>
</header>
<main>
  <h2>Features</h2>
  <ul class="features">
{features_html}
  </ul>
  <section class="demo">
    <h2>Try it</h2>
    <button id="go">Run demo</button>
    <div id="out">Press the button.</div>
  </section>
</main>
<footer>Built locally with LEVI Builder · stdlib only · yours, completely.</footer>
<script>
  const PAGES = [{pages_js}];
  document.getElementById('go').addEventListener('click', () => {{
    const now = new Date().toLocaleTimeString();
    document.getElementById('out').textContent =
      '{_esc(spec.title)} is live · ' + now + ' · pages: ' + PAGES.join(', ');
  }});
</script>
</body>
</html>
"""

    readme = f"""# {_esc(spec.title)}

{_esc(spec.description)}

Built locally with **LEVI Builder** — stdlib only, no build step, no
accounts, no cloud. You own it completely.

## Run it

```sh
python3 -m http.server 8000
```

Then open http://127.0.0.1:8000/ — the app is `index.html`.

## Files

- `index.html` — the whole app (markup, styles, and script inline)
- `levi-build.json` — build manifest and provenance
"""

    return {"index.html": index_html, "README.md": readme}


def _esc(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
