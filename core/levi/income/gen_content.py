"""Income Batch B — content engines (slots 21-32).

Twelve ORIGINAL, stdlib-only, deterministic content-assembly generators.
Each one assembles a real deliverable document from structured input the
user supplies via params — template/assembly engines, no LLMs, no network,
no paid APIs, zero operating cost.

Every generator:
- runs `run(ctx)` with ctx = {"levi_home", "dry_run", "params"}
- in dry_run: reports what WOULD be produced, writes no deliverable files
- otherwise: writes real artifacts under
  ctx["levi_home"]/".levi"/"income"/"work"/<id>/
- returns WorkReport(generator_id, produced, quoted_amount_usd, notes)

Pricing doctrine: entry $1-5, roughly 30-60% below the giants; the quoted
amount is pricing ADVICE only — income is recorded only by Chauncey via
engine.record_income with basis="confirmed".
"""

from __future__ import annotations

import html as _html
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from levi.income.engine import Generator, WorkReport, register


# --------------------------------------------------------------------------
# shared helpers (original, tiny, stdlib-only)
# --------------------------------------------------------------------------

def _params(ctx: Dict[str, Any]) -> Dict[str, Any]:
    p = ctx.get("params") or {}
    return p if isinstance(p, dict) else {}


def _workdir(ctx: Dict[str, Any], gid: str) -> Path:
    home = Path(ctx.get("levi_home") or Path.home())
    d = home / ".levi" / "income" / "work" / gid
    return d


def _emit(ctx: Dict[str, Any], gid: str, files: Dict[str, str],
          dry: Optional[Dict[str, str]] = None) -> List[str]:
    """Write artifact files unless dry_run. Return the produced names."""
    if ctx.get("dry_run"):
        return list((dry if dry is not None else files).keys())
    d = _workdir(ctx, gid)
    d.mkdir(parents=True, exist_ok=True)
    for name, content in files.items():
        (d / name).write_text(content, encoding="utf-8")
    return list(files.keys())


def _slug(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", str(text).lower()).strip("-")
    return s or "item"


def _esc(text: Any) -> str:
    return _html.escape(str(text), quote=True)


def _bullets(lines: List[str], marker: str = "-") -> str:
    return "\n".join(f"{marker} {str(x).strip()}" for x in lines if str(x).strip())


def _wrap(text: str, width: int = 76) -> str:
    out, cur = [], []
    n = 0
    for word in str(text).split():
        if n + len(word) + (1 if cur else 0) > width:
            out.append(" ".join(cur))
            cur, n = [word], len(word)
        else:
            cur.append(word)
            n += len(word) + (1 if cur[:-1] else 0)
    if cur:
        out.append(" ".join(cur))
    return "\n".join(out)


def _clean_list(value: Any) -> List[str]:
    if isinstance(value, list):
        return [str(x).strip() for x in value if str(x).strip()]
    if isinstance(value, str):
        return [x.strip() for x in value.split("\n") if x.strip()]
    return []


# --------------------------------------------------------------------------
# 21. newsletter-drafter — topic bullets -> full newsletter draft
# --------------------------------------------------------------------------

def _run_newsletter(ctx: Dict[str, Any]) -> WorkReport:
    p = _params(ctx)
    title = str(p.get("title") or "Untitled Newsletter").strip()
    tagline = str(p.get("tagline") or "").strip()
    bullets = _clean_list(p.get("bullets"))
    cta = str(p.get("cta") or "").strip()
    footer = str(p.get("footer") or "You are receiving this because you subscribed.").strip()

    secs = []
    for i, b in enumerate(bullets, 1):
        head, _, rest = b.partition(":")
        head, rest = head.strip(), rest.strip()
        secs.append((head or f"Story {i}", rest or b))

    md = [f"# {title}"]
    if tagline:
        md.append(f"_{tagline}_")
    md.append("")
    if not secs:
        md.append("_No story bullets were provided — add bullets to fill the issue._")
    for i, (head, rest) in enumerate(secs, 1):
        md.append(f"## {i}. {head}")
        md.append(_wrap(rest) if rest else "")
        md.append("")
    if cta:
        md.append(f"**[ {cta} ]**")
        md.append("")
    md.append(f"---\n{footer}")
    markdown = "\n".join(md).rstrip() + "\n"

    plain = [title.upper(), "=" * len(title)]
    if tagline:
        plain.append(tagline)
    plain.append("")
    for i, (head, rest) in enumerate(secs, 1):
        plain.append(f"{i}. {head}")
        plain.append(_wrap(rest))
        plain.append("")
    if cta:
        plain.append(f">>> {cta} <<<")
    plain.append(f"\n{footer}\n")
    text = "\n".join(plain)

    produced = _emit(ctx, "newsletter-drafter",
                     {"newsletter.md": markdown, "newsletter.txt": text})
    return WorkReport(
        generator_id="newsletter-drafter",
        produced=produced,
        quoted_amount_usd=3.0,
        notes=f"Drafted newsletter '{title}' with {len(secs)} section(s)"
              f"{' — dry run, no files written' if ctx.get('dry_run') else ''}.",
    )


# --------------------------------------------------------------------------
# 22. changelog-composer — structured entries -> formatted changelog
# --------------------------------------------------------------------------

_CHANGE_ORDER = ["added", "changed", "deprecated", "removed", "fixed", "security"]


def _run_changelog(ctx: Dict[str, Any]) -> WorkReport:
    p = _params(ctx)
    version = str(p.get("version") or "0.1.0").strip()
    date = str(p.get("date") or "UNRELEASED").strip()
    raw = p.get("entries") or []
    entries: List[Dict[str, str]] = []
    if isinstance(raw, list):
        for e in raw:
            if isinstance(e, dict):
                entries.append({"type": str(e.get("type", "added")).lower().strip(),
                                "text": str(e.get("text", "")).strip()})
            elif isinstance(e, str):
                t, _, rest = e.partition(":")
                entries.append({"type": (t.lower().strip() or "added"),
                                "text": (rest.strip() or e.strip())})
    entries = [e for e in entries if e["text"]]

    grouped: Dict[str, List[str]] = {}
    for e in entries:
        grouped.setdefault(e["type"] if e["type"] else "added", []).append(e["text"])

    order = [t for t in _CHANGE_ORDER if t in grouped]
    order += [t for t in sorted(grouped) if t not in order]

    md = [f"## [{version}] - {date}", ""]
    for t in order:
        md.append(f"### {t.capitalize()}")
        for item in grouped[t]:
            md.append(f"- {item}")
        md.append("")
    if not entries:
        md.append("_No entries supplied — add entries to populate the release._")
        md.append("")
    markdown = "\n".join(md).rstrip() + "\n"

    payload = {"version": version, "date": date,
               "entries": [{"type": t, "items": grouped[t]} for t in order]}
    data = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"

    produced = _emit(ctx, "changelog-composer",
                     {"changelog.md": markdown, "changelog.json": data})
    return WorkReport(
        generator_id="changelog-composer",
        produced=produced,
        quoted_amount_usd=2.0,
        notes=f"Composed changelog for v{version}: {len(entries)} entries across "
              f"{len(order)} section(s)"
              f"{' — dry run, no files written' if ctx.get('dry_run') else ''}.",
    )


# --------------------------------------------------------------------------
# 23. product-description-forge — spec sheets -> benefit-led copy
# --------------------------------------------------------------------------

def _run_product_description(ctx: Dict[str, Any]) -> WorkReport:
    p = _params(ctx)
    name = str(p.get("name") or "Unnamed Product").strip()
    audience = str(p.get("audience") or "").strip()
    specs = []
    raw = p.get("specs") or []
    if isinstance(raw, list):
        for s in raw:
            if isinstance(s, dict):
                specs.append({"feature": str(s.get("feature", "")).strip(),
                              "benefit": str(s.get("benefit", "")).strip()})
            elif isinstance(s, str):
                f, _, b = s.partition("=>")
                specs.append({"feature": f.strip(), "benefit": (b.strip() or f.strip())})

    leads = [s["benefit"] or s["feature"] for s in specs if s["feature"]]
    tagline = leads[0] if leads else f"{name} — built to work."

    md = [f"# {name}", "", f"**{tagline}**", ""]
    if audience:
        md.append(f"Made for: {audience}")
        md.append("")
    if specs:
        md.append("## What it does for you")
        md.append("")
        for s in specs:
            if s["benefit"] and s["benefit"] != s["feature"]:
                md.append(f"- **{s['feature']}** — {s['benefit']}")
            else:
                md.append(f"- **{s['feature']}**")
        md.append("")
        md.append("## The full story")
        md.append("")
        md.append(_wrap(
            f"{name} pairs " + ", ".join(
                s["feature"].lower() for s in specs[:3] if s["feature"]
            ) + " so you get " + ", ".join(leads[:3]) + "."
        ) if leads else _wrap(f"{name}: details coming soon."))
        md.append("")
    else:
        md.append("_No specs supplied — add spec sheets to forge the description._")
        md.append("")
    md.append("---")
    md.append("Ships with clear documentation and human support.")
    markdown = "\n".join(md).rstrip() + "\n"

    bullets = [f"{s['feature']}: {s['benefit'] or s['feature']}" for s in specs]
    listing = "\n".join([name, tagline, "", _bullets(bullets, "•")]).rstrip() + "\n"

    produced = _emit(ctx, "product-description-forge",
                     {"product-description.md": markdown,
                      "listing.txt": listing})
    return WorkReport(
        generator_id="product-description-forge",
        produced=produced,
        quoted_amount_usd=4.0,
        notes=f"Forged product description for '{name}' from {len(specs)} spec(s)"
              f"{' — dry run, no files written' if ctx.get('dry_run') else ''}.",
    )


# --------------------------------------------------------------------------
# 24. faq-builder — Q&A pairs -> categorized FAQ doc with TOC
# --------------------------------------------------------------------------

def _run_faq(ctx: Dict[str, Any]) -> WorkReport:
    p = _params(ctx)
    title = str(p.get("title") or "Frequently Asked Questions").strip()
    categories: List[Dict[str, Any]] = []
    raw_cats = p.get("categories")
    if isinstance(raw_cats, list):
        for c in raw_cats:
            if isinstance(c, dict):
                faqs = []
                for f in (c.get("faqs") or []):
                    if isinstance(f, dict):
                        faqs.append({"q": str(f.get("q", "")).strip(),
                                     "a": str(f.get("a", "")).strip()})
                    elif isinstance(f, str):
                        q, _, a = f.partition("?")
                        faqs.append({"q": (q.strip() + "?" if q.strip() else f.strip()),
                                     "a": a.strip()})
                categories.append({"name": str(c.get("name", "General")).strip(),
                                   "faqs": [f for f in faqs if f["q"]]})
    flat = []
    for f in (p.get("faqs") or []):
        if isinstance(f, dict):
            flat.append({"q": str(f.get("q", "")).strip(),
                         "a": str(f.get("a", "")).strip()})
    if flat:
        categories.append({"name": "General",
                           "faqs": [f for f in flat if f["q"]]})
    categories = [c for c in categories if c["faqs"]]

    md = [f"# {title}", ""]
    total = sum(len(c["faqs"]) for c in categories)
    if categories:
        md.append("## Contents")
        md.append("")
        for c in categories:
            md.append(f"- [{c['name']}](#{_slug(c['name'])})")
        md.append("")
        for c in categories:
            md.append(f"## {c['name']}")
            md.append("")
            for f in c["faqs"]:
                md.append(f"### {f['q']}")
                md.append("")
                md.append(_wrap(f["a"]) if f["a"] else "_Answer pending._")
                md.append("")
    else:
        md.append("_No Q&A pairs supplied — add questions to build the FAQ._")
        md.append("")
    markdown = "\n".join(md).rstrip() + "\n"

    payload = {"title": title,
               "categories": [{"name": c["name"], "faqs": c["faqs"]}
                              for c in categories]}
    data = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"

    produced = _emit(ctx, "faq-builder", {"faq.md": markdown, "faq.json": data})
    return WorkReport(
        generator_id="faq-builder",
        produced=produced,
        quoted_amount_usd=2.5,
        notes=f"Built FAQ doc '{title}': {total} Q&A across "
              f"{len(categories)} categor(ies)"
              f"{' — dry run, no files written' if ctx.get('dry_run') else ''}.",
    )


# --------------------------------------------------------------------------
# 25. meeting-notes-structurer — raw notes -> minutes (decisions/actions)
# --------------------------------------------------------------------------

_DECISION_RE = re.compile(r"^\s*(?:decision|decided|resolved)\s*[:\-–]\s*(.+)$",
                          re.IGNORECASE)
_ACTION_RE = re.compile(
    r"^\s*(?:action|todo|task|follow[\s-]?up)\s*[:\-–]\s*(.+)$", re.IGNORECASE)
_OWNER_RE = re.compile(r"\(([^)]{1,40})\)\s*$")
_HEADING_RE = re.compile(r"^\s*(?:notes?|discussion|agenda|topics?)\s*[:\-–]?\s*$",
                         re.IGNORECASE)


def _run_meeting_notes(ctx: Dict[str, Any]) -> WorkReport:
    p = _params(ctx)
    title = str(p.get("title") or "Meeting Notes").strip()
    date = str(p.get("date") or "").strip()
    attendees = _clean_list(p.get("attendees"))
    raw = str(p.get("notes") or "").strip()

    decisions: List[str] = []
    actions: List[Dict[str, str]] = []
    discussion: List[str] = []

    for line in raw.splitlines():
        s = line.strip()
        if not s or _HEADING_RE.match(s):
            continue
        dm = _DECISION_RE.match(s)
        am = _ACTION_RE.match(s)
        if dm:
            decisions.append(dm.group(1).strip())
        elif am:
            body = am.group(1).strip()
            owner = ""
            om = _OWNER_RE.search(body)
            if om:
                owner = om.group(1).strip()
                body = body[: om.start()].strip()
            actions.append({"action": body, "owner": owner})
        else:
            discussion.append(s)

    md = [f"# {title} — Minutes", ""]
    if date:
        md.append(f"**Date:** {date}")
    if attendees:
        md.append(f"**Attendees:** {', '.join(attendees)}")
    if date or attendees:
        md.append("")
    md.append("## Decisions")
    md.append("")
    if decisions:
        for i, d in enumerate(decisions, 1):
            md.append(f"{i}. {d}")
    else:
        md.append("_None recorded._")
    md.append("")
    md.append("## Action items")
    md.append("")
    if actions:
        for i, a in enumerate(actions, 1):
            own = f" _(owner: {a['owner']})_" if a["owner"] else ""
            md.append(f"{i}. {a['action']}{own}")
    else:
        md.append("_None recorded._")
    md.append("")
    md.append("## Discussion")
    md.append("")
    if discussion:
        md.append(_bullets(discussion))
    else:
        md.append("_No discussion notes supplied._")
    markdown = "\n".join(md).rstrip() + "\n"

    payload = {"title": title, "date": date, "attendees": attendees,
               "decisions": decisions, "actions": actions,
               "discussion": discussion}
    data = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"

    produced = _emit(ctx, "meeting-notes-structurer",
                     {"minutes.md": markdown, "minutes.json": data})
    return WorkReport(
        generator_id="meeting-notes-structurer",
        produced=produced,
        quoted_amount_usd=2.0,
        notes=f"Structured minutes '{title}': {len(decisions)} decision(s), "
              f"{len(actions)} action item(s)"
              f"{' — dry run, no files written' if ctx.get('dry_run') else ''}.",
    )

# --------------------------------------------------------------------------
# 26. invoice-pack — line items -> invoice/quote/receipt (text + HTML)
# --------------------------------------------------------------------------

_DOCTYPES = ("invoice", "quote", "receipt")


def _run_invoice(ctx: Dict[str, Any]) -> WorkReport:
    p = _params(ctx)
    doctype = str(p.get("doctype") or "invoice").strip().lower()
    if doctype not in _DOCTYPES:
        doctype = "invoice"
    biz = str(p.get("business") or "Your Business").strip()
    client = str(p.get("client") or "Client").strip()
    number = str(p.get("number") or f"{doctype.upper()}-1001").strip()
    date = str(p.get("date") or "").strip()
    notes = str(p.get("notes_text") or "").strip()
    try:
        tax_rate = float(p.get("tax_rate") or 0.0)
    except (TypeError, ValueError):
        tax_rate = 0.0

    items: List[Dict[str, Any]] = []
    raw = p.get("items") or []
    if isinstance(raw, list):
        for it in raw:
            if isinstance(it, dict):
                try:
                    qty = float(it.get("qty", 1) or 1)
                except (TypeError, ValueError):
                    qty = 1.0
                try:
                    rate = float(it.get("rate", 0) or 0)
                except (TypeError, ValueError):
                    rate = 0.0
                desc = str(it.get("desc", "")).strip() or "Item"
                items.append({"desc": desc, "qty": qty, "rate": rate,
                              "line": round(qty * rate, 2)})

    subtotal = round(sum(i["line"] for i in items), 2)
    tax = round(subtotal * tax_rate, 2)
    total = round(subtotal + tax, 2)

    title = doctype.upper()
    w = 60
    txt = [biz, client, f"{title} {number}", ("date: " + date) if date else "",
           "=" * w, f"{'Description':38}{'Qty':>6}{'Rate':>8}{'Amount':>8}",
           "-" * w]
    for i in items:
        txt.append(f"{i['desc'][:38]:38}{i['qty']:>6g}{i['rate']:>8.2f}"
                   f"{i['line']:>8.2f}")
    txt += ["-" * w, f"{'Subtotal':>52}{subtotal:>8.2f}"]
    if tax:
        txt.append(f"{'Tax (' + str(tax_rate * 100).rstrip('0').rstrip('.') + '%)':>52}"
                   f"{tax:>8.2f}")
    txt.append(f"{'TOTAL':>52}{total:>8.2f}")
    if notes:
        txt += ["", "Notes:", _wrap(notes)]
    text = "\n".join(x for x in txt if x is not None).rstrip() + "\n"

    rows = "".join(
        f"<tr><td>{_esc(i['desc'])}</td><td>{i['qty']:g}</td>"
        f"<td>${i['rate']:.2f}</td><td>${i['line']:.2f}</td></tr>"
        for i in items)
    html_doc = f"""<!doctype html>
<html><head><meta charset="utf-8"><title>{_esc(title)} {_esc(number)}</title>
<style>body{{font-family:sans-serif;max-width:640px;margin:2em auto;color:#111}}
table{{width:100%;border-collapse:collapse}}td,th{{border:1px solid #999;padding:6px;text-align:left}}
th{{background:#eee}}.tot td{{border:none;text-align:right}}.big{{font-size:1.6em}}</style>
</head><body>
<h1 class="big">{_esc(biz)}</h1>
<p>Bill to: {_esc(client)}</p>
<h2>{_esc(title)} {_esc(number)}</h2>
{"<p>Date: " + _esc(date) + "</p>" if date else ""}
<table><tr><th>Description</th><th>Qty</th><th>Rate</th><th>Amount</th></tr>{rows}</table>
<table class="tot">
<tr><td>Subtotal</td><td>${subtotal:.2f}</td></tr>
{"<tr><td>Tax</td><td>$" + f"{tax:.2f}" + "</td></tr>" if tax else ""}
<tr><td><strong>TOTAL</strong></td><td><strong>${total:.2f}</strong></td></tr>
</table>
{"<p><em>" + _esc(notes) + "</em></p>" if notes else ""}
</body></html>
"""

    produced = _emit(ctx, "invoice-pack",
                     {f"{number}.txt": text, f"{number}.html": html_doc})
    return WorkReport(
        generator_id="invoice-pack",
        produced=produced,
        quoted_amount_usd=3.0,
        notes=f"Built {doctype} {number} for '{client}': {len(items)} line(s), "
              f"total ${total:.2f}"
              f"{' — dry run, no files written' if ctx.get('dry_run') else ''}.",
    )


# --------------------------------------------------------------------------
# 27. contract-lite-kit — parties/terms -> simple service agreement template
# --------------------------------------------------------------------------

def _run_contract_lite(ctx: Dict[str, Any]) -> WorkReport:
    p = _params(ctx)
    provider = str(p.get("provider") or "[Provider]").strip()
    client = str(p.get("client") or "[Client]").strip()
    service = str(p.get("service") or "[description of services]").strip()
    start = str(p.get("start_date") or "[start date]").strip()
    term = str(p.get("term") or "[term, e.g. 6 months]").strip()
    fee = str(p.get("fee") or "[fee]").strip()
    pay_terms = str(p.get("payment_terms") or "[payment terms]").strip()
    extra = _clean_list(p.get("extra_clauses"))

    clauses = [
        ("1. Services",
         f"Provider ({provider}) will perform the following services for "
         f"Client ({client}): {service}."),
        ("2. Term",
         f"This agreement begins on {start} and continues for {term}, "
         "unless ended earlier under section 6."),
        ("3. Fees and payment",
         f"Client will pay Provider {fee}. Payment terms: {pay_terms}."),
        ("4. Changes",
         "Work outside the services described above is a change request and "
         "needs written agreement on scope and fee before it starts."),
        ("5. Confidentiality",
         "Each party keeps the other's non-public information confidential "
         "and uses it only for this agreement."),
        ("6. Ending the agreement",
         "Either party may end this agreement with 14 days' written notice. "
         "Fees for work already done remain due."),
        ("7. Independent relationship",
         "Provider is an independent contractor, not an employee of Client."),
        ("8. Limit of liability",
         "Neither party is liable for indirect or consequential losses. "
         "Total liability under this agreement is capped at the fees paid."),
    ]
    for i, clause in enumerate(extra, len(clauses) + 1):
        clauses.append((f"{i}. Additional term", clause))

    body = "\n\n".join(f"{h}\n{_wrap(t)}" for h, t in clauses)
    txt = (f"SERVICE AGREEMENT (plain-language draft — not legal advice)\n"
           f"{'=' * 60}\n\n"
           f"Between: {provider}\nAnd:     {client}\n"
           f"Effective: {start}\n\n{body}\n\n"
           f"{'_' * 30}    {'_' * 30}\n{provider:<30}    {client}\nDate:            Date:\n")

    md = (f"# Service Agreement — {provider} / {client}\n\n"
          f"> Plain-language draft. Not legal advice — have a licensed "
          f"attorney review before signing.\n\n"
          + "\n\n".join(f"## {h}\n\n{_wrap(t)}" for h, t in clauses)
          + "\n\n---\n\n**Signatures**\n\n"
          f"- {provider}: ______________  date ______\n"
          f"- {client}: ______________  date ______\n")

    produced = _emit(ctx, "contract-lite-kit",
                     {"service-agreement.txt": txt, "service-agreement.md": md})
    return WorkReport(
        generator_id="contract-lite-kit",
        produced=produced,
        quoted_amount_usd=4.0,
        notes=f"Drafted service-agreement template: {provider} x {client}, "
              f"{len(clauses)} clause(s)"
              f"{' — dry run, no files written' if ctx.get('dry_run') else ''}.",
    )


# --------------------------------------------------------------------------
# 28. resume-kit — experience input -> resume + cover letter template set
# --------------------------------------------------------------------------

def _run_resume_kit(ctx: Dict[str, Any]) -> WorkReport:
    p = _params(ctx)
    name = str(p.get("name") or "[Your Name]").strip()
    contact = _clean_list(p.get("contact"))
    summary = str(p.get("summary") or "").strip()
    skills = _clean_list(p.get("skills"))

    jobs: List[Dict[str, Any]] = []
    for j in (p.get("experience") or []):
        if isinstance(j, dict):
            jobs.append({"role": str(j.get("role", "")).strip(),
                         "org": str(j.get("org", "")).strip(),
                         "dates": str(j.get("dates", "")).strip(),
                         "bullets": _clean_list(j.get("bullets"))})

    md = [f"# {name}", ""]
    if contact:
        md.append(" · ".join(contact))
        md.append("")
    if summary:
        md.append("## Summary")
        md.append("")
        md.append(_wrap(summary))
        md.append("")
    if jobs:
        md.append("## Experience")
        md.append("")
        for j in jobs:
            head = f"**{j['role']}**" if j["role"] else ""
            if j["org"]:
                head += f" — {j['org']}"
            if j["dates"]:
                head += f"  ({j['dates']})"
            md.append(head or "_Role_")
            if j["bullets"]:
                md.append(_bullets(j["bullets"]))
            md.append("")
    if skills:
        md.append("## Skills")
        md.append("")
        md.append(", ".join(skills))
        md.append("")
    if not jobs and not summary:
        md.append("_Add experience entries to fill the resume._")
        md.append("")
    resume = "\n".join(md).rstrip() + "\n"

    role = str(p.get("target_role") or "").strip()
    company = str(p.get("target_company") or "").strip()
    why = str(p.get("why_fit") or "").strip()
    letter = [name, ""]
    if contact:
        letter.append(" · ".join(contact))
        letter.append("")
    letter.append("Dear Hiring Manager,")
    letter.append("")
    target = f" for the {role} position" if role else ""
    where = f" at {company}" if company else ""
    letter.append(_wrap(f"I am writing to express my interest in joining your team"
                       f"{target}{where}."))
    letter.append("")
    if summary:
        letter.append(_wrap(summary))
        letter.append("")
    if jobs:
        j = jobs[0]
        letter.append(_wrap(
            f"Most recently as {j['role'] or 'a team member'}"
            f"{' at ' + j['org'] if j['org'] else ''}, "
            f"I {(', '.join(j['bullets'][:2])).lower() if j['bullets'] else 'contributed to team goals'}."
        ))
        letter.append("")
    if why:
        letter.append(_wrap(f"What draws me to this role: {why}"))
        letter.append("")
    letter.append(_wrap("I would welcome the chance to discuss how I can contribute. "
                        "Thank you for your consideration."))
    letter.append("")
    letter.append("Sincerely,")
    letter.append(name)
    cover = "\n".join(letter).rstrip() + "\n"

    produced = _emit(ctx, "resume-kit",
                     {"resume.md": resume, "cover-letter.md": cover})
    return WorkReport(
        generator_id="resume-kit",
        produced=produced,
        quoted_amount_usd=5.0,
        notes=f"Built resume kit for '{name}': {len(jobs)} job(s), "
              f"{len(skills)} skill(s), cover letter included"
              f"{' — dry run, no files written' if ctx.get('dry_run') else ''}.",
    )


# --------------------------------------------------------------------------
# 29. study-guide-builder — outline -> objectives/terms/quiz study guide
# --------------------------------------------------------------------------

def _run_study_guide(ctx: Dict[str, Any]) -> WorkReport:
    p = _params(ctx)
    subject = str(p.get("subject") or "Untitled Subject").strip()
    objectives = _clean_list(p.get("objectives"))
    topics = _clean_list(p.get("topics"))
    terms: List[Dict[str, str]] = []
    for t in (p.get("key_terms") or []):
        if isinstance(t, dict):
            terms.append({"term": str(t.get("term", "")).strip(),
                          "def": str(t.get("definition", "")).strip()})
        elif isinstance(t, str):
            term, _, d = t.partition(":")
            terms.append({"term": term.strip(), "def": d.strip()})
    terms = [t for t in terms if t["term"]]
    quiz: List[Dict[str, str]] = []
    for q in (p.get("quiz") or []):
        if isinstance(q, dict):
            quiz.append({"q": str(q.get("q", "")).strip(),
                         "a": str(q.get("a", "")).strip()})
        elif isinstance(q, str):
            qn, _, an = q.partition("?")
            quiz.append({"q": (qn.strip() + "?" if qn.strip() else q.strip()),
                         "a": an.strip()})
    quiz = [q for q in quiz if q["q"]]

    md = [f"# Study Guide: {subject}", ""]
    if objectives:
        md.append("## Learning objectives")
        md.append("")
        md.append(_bullets(objectives))
        md.append("")
    if topics:
        md.append("## Topics to master")
        md.append("")
        for i, t in enumerate(topics, 1):
            md.append(f"{i}. {t}")
        md.append("")
    if terms:
        md.append("## Key terms")
        md.append("")
        for t in terms:
            md.append(f"### {t['term']}")
            md.append(_wrap(t["def"]) if t["def"] else "_Definition pending._")
            md.append("")
    if quiz:
        md.append("## Self-quiz (no peeking — answers in key below)")
        md.append("")
        for i, q in enumerate(quiz, 1):
            md.append(f"{i}. {q['q']}")
        md.append("")
        md.append("### Answer key")
        md.append("")
        for i, q in enumerate(quiz, 1):
            md.append(f"{i}. {q['a'] or '_Answer pending._'}")
        md.append("")
    if not (objectives or topics or terms or quiz):
        md.append("_No outline input supplied — add objectives, terms, or quiz "
                  "questions to build the guide._")
        md.append("")
    markdown = "\n".join(md).rstrip() + "\n"

    payload = {"subject": subject, "objectives": objectives,
               "topics": topics, "key_terms": terms, "quiz": quiz}
    data = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"

    produced = _emit(ctx, "study-guide-builder",
                     {"study-guide.md": markdown, "study-guide.json": data})
    return WorkReport(
        generator_id="study-guide-builder",
        produced=produced,
        quoted_amount_usd=3.0,
        notes=f"Built study guide '{subject}': {len(objectives)} objective(s), "
              f"{len(terms)} key term(s), {len(quiz)} quiz question(s)"
              f"{' — dry run, no files written' if ctx.get('dry_run') else ''}.",
    )

# --------------------------------------------------------------------------
# 30. caption-forge — topic brief -> caption variants + hashtag sets
# --------------------------------------------------------------------------

_STOP = frozenset("a an the and or of to in on for with at by from as is are "
                 "was were be this that these those it its our your you we they "
                 "his her their my me us them this".split())

_TONES = {
    "professional": ("Here's what you need to know", "Share your take below."),
    "playful": ("Buckle up — this is fun", "Double-tap if you agree!"),
    "bold": ("No fluff. Just facts", "Sound off in the comments."),
    "friendly": ("Quick heads-up for you", "Tell us what you think."),
}


def _make_hashtags(words: List[str], n: int = 8) -> List[str]:
    """Deterministic hashtags derived only from the brief's own words."""
    seen, tags = set(), []
    for w in words:
        w = re.sub(r"[^a-z0-9]", "", w.lower())
        if len(w) > 3 and w not in _STOP and w not in seen:
            seen.add(w)
            tags.append("#" + w)
            if len(tags) >= n:
                break
    return tags


def _run_caption_forge(ctx: Dict[str, Any]) -> WorkReport:
    p = _params(ctx)
    topic = str(p.get("topic") or "something new").strip()
    platform = str(p.get("platform") or "social").strip()
    tone = str(p.get("tone") or "friendly").strip().lower()
    points = _clean_list(p.get("key_points"))
    cta = str(p.get("cta") or "").strip()

    opener, closer = _TONES.get(tone, _TONES["friendly"])
    words = topic.split() + [w for pt in points for w in pt.split()]
    tags = _make_hashtags(words)

    v1 = f"{opener}: {topic}.\n\n" + \
        ("\n".join(f"• {pt}" for pt in points[:3]) + "\n\n" if points else "") + \
        (f"{cta}\n\n" if cta else "") + \
        f"{closer}\n\n{' '.join(tags)}"
    v2 = (f"POV: you finally found {topic}. {' '.join(points[:2])}\n\n"
          f"{cta or closer}\n\n{' '.join(tags[:6])}").rstrip()
    v3 = (f"3 things about {topic}:\n"
          + "\n".join(f"{i}. {pt}" for i, pt in enumerate(points[:3], 1))
          + (f"\n\n{cta}" if cta else "")
          + f"\n\n{' '.join(tags)}") if points else \
        (f"{topic} — {opener.lower()}. {closer}\n\n{' '.join(tags)}")

    md = [f"# Captions — {topic} ({platform}, {tone})", "",
          "## Variant A — classic", "", v1, "",
          "## Variant B — short & punchy", "", v2, "",
          "## Variant C — numbered", "", v3, "",
          "## Hashtag bank", "", " ".join(tags) or "_(no tags derived)_", ""]
    markdown = "\n".join(md).rstrip() + "\n"

    payload = {"topic": topic, "platform": platform, "tone": tone,
               "captions": {"classic": v1, "punchy": v2, "numbered": v3},
               "hashtags": tags}
    data = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"

    produced = _emit(ctx, "caption-forge",
                     {"captions.md": markdown, "captions.json": data})
    return WorkReport(
        generator_id="caption-forge",
        produced=produced,
        quoted_amount_usd=2.0,
        notes=f"Forged 3 caption variants + {len(tags)} hashtag(s) for "
              f"'{topic}' ({platform})"
              f"{' — dry run, no files written' if ctx.get('dry_run') else ''}.",
    )


# --------------------------------------------------------------------------
# 31. press-release-drafter — fact sheet -> formatted press release
# --------------------------------------------------------------------------

def _run_press_release(ctx: Dict[str, Any]) -> WorkReport:
    p = _params(ctx)
    org = str(p.get("organization") or "[Organization]").strip()
    headline = str(p.get("headline") or "[Headline]").strip()
    sub = str(p.get("subheadline") or "").strip()
    location = str(p.get("location") or "[City, State]").strip()
    date = str(p.get("date") or "").strip()
    facts = _clean_list(p.get("facts"))
    quote = str(p.get("quote") or "").strip()
    quote_by = str(p.get("quote_by") or "").strip()
    contact = _clean_list(p.get("contact"))
    boilerplate = str(p.get("boilerplate") or "").strip()

    dateline = f"{location.upper()} —" if location else "—"
    md = ["FOR IMMEDIATE RELEASE", "", f"# {headline}", ""]
    if sub:
        md.append(f"_{sub}_")
        md.append("")
    md.append(f"{dateline} " + (_wrap(" ".join(facts[:2])) if facts else "[Lead paragraph]"))
    md.append("")
    for f in facts[2:]:
        md.append(_wrap(f))
        md.append("")
    if quote:
        by = f", {quote_by}" if quote_by else ""
        md.append(f'"{quote}" said{by}.')
        md.append("")
    md.append("###")
    md.append("")
    if contact:
        md.append("**Media contact:**")
        md.append("")
        md.append(_bullets(contact))
        md.append("")
    if boilerplate:
        md.append(f"**About {org}:**")
        md.append("")
        md.append(_wrap(boilerplate))
        md.append("")
    markdown = "\n".join(md).rstrip() + "\n"

    plain = ["FOR IMMEDIATE RELEASE", "", headline.upper()]
    if sub:
        plain.append(sub)
    plain += ["", f"{dateline} " + " ".join(facts[:2]) if facts else ""]
    plain += ["", *facts[2:]]
    if quote:
        plain += ["", f'"{quote}"' + (f" — {quote_by}" if quote_by else "")]
    plain += ["", "###", ""]
    if contact:
        plain += ["Media contact:"] + contact + [""]
    if boilerplate:
        plain += [f"About {org}:", boilerplate]
    text = "\n".join(plain).rstrip() + "\n"

    produced = _emit(ctx, "press-release-drafter",
                     {"press-release.md": markdown, "press-release.txt": text})
    return WorkReport(
        generator_id="press-release-drafter",
        produced=produced,
        quoted_amount_usd=4.0,
        notes=f"Drafted press release '{headline}' from {len(facts)} fact(s)"
              f"{' — dry run, no files written' if ctx.get('dry_run') else ''}.",
    )


# --------------------------------------------------------------------------
# 32. lesson-plan-builder — curriculum outline -> full lesson plan
# --------------------------------------------------------------------------

def _run_lesson_plan(ctx: Dict[str, Any]) -> WorkReport:
    p = _params(ctx)
    subject = str(p.get("subject") or "Subject").strip()
    title = str(p.get("title") or "Lesson").strip()
    grade = str(p.get("grade") or "").strip()
    objectives = _clean_list(p.get("objectives"))
    materials = _clean_list(p.get("materials"))

    activities: List[Dict[str, Any]] = []
    total_min = 0
    for a in (p.get("activities") or []):
        if isinstance(a, dict):
            try:
                mins = int(a.get("minutes", 0) or 0)
            except (TypeError, ValueError):
                mins = 0
            activities.append({"name": str(a.get("name", "")).strip() or "Activity",
                               "minutes": mins,
                               "desc": str(a.get("desc", "")).strip()})
            total_min += mins
    if not activities:
        for a in _clean_list(p.get("activities")):
            activities.append({"name": a, "minutes": 0, "desc": ""})

    assessment = str(p.get("assessment") or "").strip()
    differentiation = str(p.get("differentiation") or "").strip()

    md = [f"# Lesson Plan: {title}", "",
          f"**Subject:** {subject}" + (f"  |  **Grade:** {grade}" if grade else "")
          + (f"  |  **Time:** ~{total_min} min" if total_min else ""), ""]
    if objectives:
        md.append("## Learning objectives")
        md.append("")
        md.append("By the end of this lesson, students will be able to:")
        md.append("")
        md.append(_bullets(objectives))
        md.append("")
    if materials:
        md.append("## Materials")
        md.append("")
        md.append(_bullets(materials))
        md.append("")
    if activities:
        md.append("## Activities")
        md.append("")
        for i, a in enumerate(activities, 1):
            when = f" ({a['minutes']} min)" if a["minutes"] else ""
            md.append(f"### {i}. {a['name']}{when}")
            if a["desc"]:
                md.append("")
                md.append(_wrap(a["desc"]))
            md.append("")
    if assessment:
        md.append("## Assessment")
        md.append("")
        md.append(_wrap(assessment))
        md.append("")
    if differentiation:
        md.append("## Differentiation")
        md.append("")
        md.append(_wrap(differentiation))
        md.append("")
    md.append("## Closure")
    md.append("")
    md.append("Recap the key points, check for understanding with a quick "
             "exit ticket, and preview what's next.")
    if not (objectives or activities):
        md.append("")
        md.append("_No outline input supplied — add objectives and activities "
                  "to build the plan._")
    markdown = "\n".join(md).rstrip() + "\n"

    payload = {"subject": subject, "title": title, "grade": grade,
               "objectives": objectives, "materials": materials,
               "activities": activities, "total_minutes": total_min,
               "assessment": assessment, "differentiation": differentiation}
    data = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"

    produced = _emit(ctx, "lesson-plan-builder",
                     {"lesson-plan.md": markdown, "lesson-plan.json": data})
    return WorkReport(
        generator_id="lesson-plan-builder",
        produced=produced,
        quoted_amount_usd=3.0,
        notes=f"Built lesson plan '{title}' ({subject}): {len(activities)} "
              f"activit(ies), {total_min} min, {len(objectives)} objective(s)"
              f"{' — dry run, no files written' if ctx.get('dry_run') else ''}.",
    )


# --------------------------------------------------------------------------
# registry — slots 21..32, kind "content-engine"
# --------------------------------------------------------------------------

_DEFS = [
    ("newsletter-drafter", "Newsletter Drafter", 21, 3.0,
     "Drafts a newsletter (sections, headlines, CTAs) from topic bullets.",
     _run_newsletter),
    ("changelog-composer", "Changelog Composer", 22, 2.0,
     "Composes formatted changelogs from structured change entries.",
     _run_changelog),
    ("product-description-forge", "Product Description Forge", 23, 4.0,
     "Forges benefit-led product descriptions from spec sheets.",
     _run_product_description),
    ("faq-builder", "FAQ Builder", 24, 2.5,
     "Builds categorized FAQ docs with TOC from Q&A pairs.", _run_faq),
    ("meeting-notes-structurer", "Meeting Notes Structurer", 25, 2.0,
     "Structures raw notes into minutes: decisions, actions, owners.",
     _run_meeting_notes),
    ("invoice-pack", "Invoice Pack", 26, 3.0,
     "Generates invoice/quote/receipt sets in text and HTML.",
     _run_invoice),
    ("contract-lite-kit", "Contract Lite Kit", 27, 4.0,
     "Drafts plain-language service-agreement templates from parties/terms.",
     _run_contract_lite),
    ("resume-kit", "Resume Kit", 28, 5.0,
     "Builds resume + tailored cover-letter template set from experience input.",
     _run_resume_kit),
    ("study-guide-builder", "Study Guide Builder", 29, 3.0,
     "Builds study guides (objectives, key terms, quizzes) from outlines.",
     _run_study_guide),
    ("caption-forge", "Caption Forge", 30, 2.0,
     "Forges social captions + derived hashtag sets from a topic brief.",
     _run_caption_forge),
    ("press-release-drafter", "Press Release Drafter", 31, 4.0,
     "Drafts press releases (dateline, facts, boilerplate) from fact sheets.",
     _run_press_release),
    ("lesson-plan-builder", "Lesson Plan Builder", 32, 3.0,
     "Builds lesson plans (objectives, activities, assessment) from outlines.",
     _run_lesson_plan),
]

for _gid, _name, _slot, _price, _desc, _fn in _DEFS:
    register(Generator(id=_gid, name=_name, kind="content-engine",
                       description=_desc, version="1.0.0",
                       entry_price_usd=_price, run=_fn), slot=_slot)

del _gid, _name, _slot, _price, _desc, _fn
