"""Income Batch A — 12 micro-tool generators (slots 1-12).

All original, from-scratch, stdlib-only logic. Zero operating cost, no
network calls. Each generator's ``run(ctx)`` does real work on the
caller's params:

- dry_run=True: computes the result and reports what WOULD be produced.
  No deliverable files are written.
- dry_run=False: writes real artifacts under
  ``<levi_home>/.levi/income/work/<generator-id>/`` and returns a
  WorkReport describing them.

Pricing doctrine: no free core, entry $1-5 (~30-60% below giant-tool
equivalents). WorkReports carry a quoted_amount_usd as pricing advice;
income is recorded only by Chauncey via engine.record_income with
basis="confirmed". These generators never record or invent income.
"""

from __future__ import annotations

import csv
import io
import json
import re
import secrets
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Tuple

from levi.income.engine import Generator, WorkReport, register

_GID_PREFIX = ""  # ids are plain slugs; see _DEFINITIONS below


def _work_dir(ctx: Dict[str, Any], gid: str) -> Path:
    return Path(ctx["levi_home"]) / ".levi" / "income" / "work" / gid


def _write(work: Path, name: str, text: str) -> Path:
    work.mkdir(parents=True, exist_ok=True)
    p = work / name
    p.write_text(text, encoding="utf-8")
    return p


def _params(ctx: Dict[str, Any]) -> Dict[str, Any]:
    params = ctx.get("params") or {}
    if not isinstance(params, dict):
        raise ValueError("ctx['params'] must be a dict")
    return params


# ---------------------------------------------------------------------------
# 1. text-deduper
# ---------------------------------------------------------------------------


def _dedupe_run(ctx: Dict[str, Any]) -> WorkReport:
    gid = "text-deduper"
    p = _params(ctx)
    text = str(p.get("text", ""))
    mode = str(p.get("mode", "line")).lower()  # "line" | "paragraph"
    ignore_case = bool(p.get("ignore_case", False))
    strip_ws = bool(p.get("strip_ws", True))

    if mode not in ("line", "paragraph"):
        raise ValueError(f"mode must be 'line' or 'paragraph', got {mode!r}")

    if mode == "paragraph":
        units: List[str] = [
            u for u in re.split(r"\n\s*\n", text) if u.strip() != ""
        ]
        joiner = "\n\n"
    else:
        units = text.splitlines()
        joiner = "\n"

    seen: set = set()
    kept: List[str] = []
    removed = 0
    for unit in units:
        key = unit.strip() if strip_ws else unit
        if ignore_case:
            key = key.lower()
        if key in seen:
            removed += 1
            continue
        seen.add(key)
        kept.append(unit)

    total = len(units)
    result = joiner.join(kept)
    if mode == "line" and text.endswith("\n"):
        result += "\n"
    notes = (
        f"Scanned {total} {mode}s, removed {removed} duplicate(s), "
        f"kept {len(kept)} unique."
    )
    if ctx.get("dry_run"):
        return WorkReport(
            generator_id=gid,
            produced=[],
            quoted_amount_usd=3.0,
            notes="DRY RUN — " + notes + " Would write deduped.txt + report.txt.",
        )
    work = _work_dir(ctx, gid)
    _write(work, "deduped.txt", result)
    _write(
        work,
        "report.txt",
        f"text-deduper report\nmode={mode} ignore_case={ignore_case} "
        f"strip_ws={strip_ws}\n{notes}\n",
    )
    return WorkReport(
        generator_id=gid,
        produced=["deduped.txt", "report.txt"],
        quoted_amount_usd=3.0,
        notes=notes,
    )


# ---------------------------------------------------------------------------
# 2. csv-columnizer
# ---------------------------------------------------------------------------


def _slug_header(name: str, seen: Dict[str, int]) -> str:
    slug = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^0-9a-zA-Z]+", "_", slug.strip().lower()).strip("_")
    if not slug:
        slug = "col"
    base, n = slug, seen.get(slug, 0)
    while slug in seen:
        n += 1
        slug = f"{base}_{n}"
    seen[slug] = n
    return slug


def _columnizer_run(ctx: Dict[str, Any]) -> WorkReport:
    gid = "csv-columnizer"
    p = _params(ctx)
    text = str(p.get("csv_text", ""))
    if not text.strip():
        raise ValueError("csv_text must be a non-empty CSV document")

    sample = text[:8192]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=[",", ";", "\t", "|"])
    except csv.Error:
        dialect = csv.excel
    delim_name = {",": "comma", ";": "semicolon", "\t": "tab", "|": "pipe"}.get(
        dialect.delimiter, repr(dialect.delimiter)
    )

    reader = csv.reader(io.StringIO(text), dialect)
    rows = [r for r in reader if r]
    if not rows:
        raise ValueError("no rows found in csv_text")
    header, data = rows[0], rows[1:]
    seen: Dict[str, int] = {}
    mapping = [(h, _slug_header(h, seen)) for h in header]
    width = len(header)
    normalized = [
        (row + [""] * width)[:width] if len(row) != width else row for row in data
    ]

    out = io.StringIO()
    writer = csv.writer(out, quoting=csv.QUOTE_MINIMAL, lineterminator="\n")
    writer.writerow([new for _, new in mapping])
    writer.writerows(normalized)
    cleaned = out.getvalue()

    renamed = [f"{old!r} -> {new!r}" for old, new in mapping if old != new]
    notes = (
        f"Detected {delim_name} delimiter; {len(data)} data rows x {width} cols. "
        f"Headers normalized to {delim_name} CSV; "
        f"{len(renamed)} header(s) renamed."
    )
    if ctx.get("dry_run"):
        return WorkReport(
            generator_id=gid,
            produced=[],
            quoted_amount_usd=2.5,
            notes="DRY RUN — " + notes
            + " Would write cleaned.csv + report.txt.",
        )
    work = _work_dir(ctx, gid)
    _write(work, "cleaned.csv", cleaned)
    _write(
        work,
        "report.txt",
        "csv-columnizer report\n"
        f"delimiter={delim_name} rows={len(data)} cols={width}\n"
        "renamed headers:\n" + "\n".join(renamed or ["(none)"]) + "\n",
    )
    return WorkReport(
        generator_id=gid,
        produced=["cleaned.csv", "report.txt"],
        quoted_amount_usd=2.5,
        notes=notes,
    )


# ---------------------------------------------------------------------------
# 3. filename-normalizer
# ---------------------------------------------------------------------------


def _slug_filename(name: str) -> str:
    stem, dot, ext = name.rpartition(".")
    if not dot:
        stem, ext = name, ""
    slug = unicodedata.normalize("NFKD", stem).encode("ascii", "ignore").decode()
    slug = slug.lower().replace("_", "-").replace(" ", "-")
    slug = re.sub(r"[^a-z0-9.-]+", "-", slug)
    slug = re.sub(r"-{2,}", "-", slug).strip("-.")
    if not slug:
        slug = "file"
    ext = re.sub(r"[^a-z0-9]+", "", ext.lower())
    return f"{slug}.{ext}" if ext else slug


def _normalizer_run(ctx: Dict[str, Any]) -> WorkReport:
    gid = "filename-normalizer"
    p = _params(ctx)
    names = p.get("filenames")
    if not names or not isinstance(names, list):
        raise ValueError("filenames must be a non-empty list of file names")

    mapping: Dict[str, str] = {}
    used: set = set()
    changed = 0
    for original in names:
        original = str(original)
        new = _slug_filename(original)
        base, dot, ext = new.rpartition(".")
        candidate, n = new, 1
        while candidate in used:
            n += 1
            candidate = f"{base}-{n}.{ext}" if dot else f"{base}-{n}"
        used.add(candidate)
        mapping[original] = candidate
        if candidate != original:
            changed += 1

    manifest = {
        "generator": gid,
        "convention": "lowercase slug, hyphens, ascii-only; collisions get -N suffix",
        "mapping": mapping,
    }
    plan_lines = [
        f"{o}  ->  {n}" + ("" if o == n else "  [rename]")
        for o, n in mapping.items()
    ]
    notes = f"{len(names)} name(s) scanned, {changed} need renaming."
    if ctx.get("dry_run"):
        return WorkReport(
            generator_id=gid,
            produced=[],
            quoted_amount_usd=2.0,
            notes="DRY RUN — " + notes
            + " Would write undo_manifest.json + rename_plan.txt.",
        )
    work = _work_dir(ctx, gid)
    _write(work, "undo_manifest.json", json.dumps(manifest, indent=2) + "\n")
    _write(work, "rename_plan.txt", "\n".join(plan_lines) + "\n")
    return WorkReport(
        generator_id=gid,
        produced=["undo_manifest.json", "rename_plan.txt"],
        quoted_amount_usd=2.0,
        notes=notes + " Undo manifest written for safe rollback.",
    )


# ---------------------------------------------------------------------------
# 4. json-prettifier-validator
# ---------------------------------------------------------------------------


def _json_run(ctx: Dict[str, Any]) -> WorkReport:
    gid = "json-prettifier-validator"
    p = _params(ctx)
    text = str(p.get("json_text", ""))
    sort_keys = bool(p.get("sort_keys", False))
    if not text.strip():
        raise ValueError("json_text must be non-empty")

    try:
        obj = json.loads(text)
    except json.JSONDecodeError as exc:
        lines = text.splitlines()
        ctx_line = ""
        if 1 <= exc.lineno <= len(lines):
            ctx_line = lines[exc.lineno - 1]
        pointer = " " * max(exc.colno - 1, 0) + "^"
        detail = (
            f"INVALID JSON: {exc.msg} at line {exc.lineno}, column {exc.colno}\n"
            f"  {ctx_line}\n  {pointer}\n"
        )
        if ctx.get("dry_run"):
            return WorkReport(
                generator_id=gid,
                produced=[],
                quoted_amount_usd=2.0,
                notes="DRY RUN — " + detail.strip()
                + " Would write error_report.txt only.",
            )
        work = _work_dir(ctx, gid)
        _write(work, "error_report.txt", detail)
        return WorkReport(
            generator_id=gid,
            produced=["error_report.txt"],
            quoted_amount_usd=2.0,
            notes=detail.strip(),
        )

    pretty = json.dumps(obj, indent=2, ensure_ascii=False, sort_keys=sort_keys) + "\n"
    kind = type(obj).__name__
    size = len(obj) if isinstance(obj, (list, dict)) else 1
    notes = f"Valid JSON ({kind}, {size} top-level entr{'ies' if kind != 'dict' else 'y'})."
    if ctx.get("dry_run"):
        return WorkReport(
            generator_id=gid,
            produced=[],
            quoted_amount_usd=2.0,
            notes="DRY RUN — " + notes + " Would write pretty.json.",
        )
    work = _work_dir(ctx, gid)
    _write(work, "pretty.json", pretty)
    return WorkReport(
        generator_id=gid,
        produced=["pretty.json"],
        quoted_amount_usd=2.0,
        notes=notes,
    )


# ---------------------------------------------------------------------------
# 5. markdown-toc-builder
# ---------------------------------------------------------------------------

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")


def _md_slug(text: str) -> str:
    slug = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9 _-]", "", slug.lower())
    return re.sub(r"\s+", "-", slug.strip()).strip("-")


def _toc_run(ctx: Dict[str, Any]) -> WorkReport:
    gid = "markdown-toc-builder"
    p = _params(ctx)
    text = str(p.get("markdown", ""))
    if not text.strip():
        raise ValueError("markdown must be a non-empty document")

    headings: List[Tuple[int, str]] = []
    for line in text.splitlines():
        m = _HEADING_RE.match(line)
        if m:
            level = len(m.group(1))
            title = m.group(2).strip()
            if title:
                headings.append((level, title))
    if not headings:
        raise ValueError("no markdown headings found")

    used: Dict[str, int] = {}
    toc_lines = []
    for level, title in headings:
        slug = _md_slug(title) or "section"
        if slug in used:
            used[slug] += 1
            slug = f"{slug}-{used[slug]}"
        else:
            used[slug] = 0
        indent = "  " * (level - 1)
        toc_lines.append(f"{indent}- [{title}](#{slug})")
    toc = "\n".join(toc_lines)

    marker = "<!-- TOC -->"
    if marker in text:
        updated = text.replace(marker, f"{marker}\n\n{toc}", 1)
    else:
        updated = f"<!-- TOC -->\n\n{toc}\n\n{text.lstrip(chr(10))}"

    notes = f"Built TOC with {len(headings)} heading(s) across {max(l for l, _ in headings)} level(s)."
    if ctx.get("dry_run"):
        return WorkReport(
            generator_id=gid,
            produced=[],
            quoted_amount_usd=2.0,
            notes="DRY RUN — " + notes + " Would write with_toc.md.",
        )
    work = _work_dir(ctx, gid)
    _write(work, "with_toc.md", updated)
    return WorkReport(
        generator_id=gid,
        produced=["with_toc.md"],
        quoted_amount_usd=2.0,
        notes=notes,
    )


# ---------------------------------------------------------------------------
# 6. whitespace-surgeon
# ---------------------------------------------------------------------------


def _hygiene(text: str, tab_width: int) -> Tuple[str, Dict[str, int]]:
    stats = {"trailing_ws": 0, "tabs_expanded": 0, "blank_collapsed": 0}
    lines = text.split("\n")
    fixed: List[str] = []
    for line in lines:
        if line != line.expandtabs(tab_width):
            stats["tabs_expanded"] += line.count("\t")
            line = line.expandtabs(tab_width)
        stripped = line.rstrip(" \t")
        if stripped != line:
            stats["trailing_ws"] += 1
        fixed.append(stripped)
    collapsed: List[str] = []
    blank_run = 0
    for line in fixed:
        if line == "":
            blank_run += 1
            if blank_run > 2:
                stats["blank_collapsed"] += 1
                continue
        else:
            blank_run = 0
        collapsed.append(line)
    result = "\n".join(collapsed).rstrip("\n") + "\n"
    return result, stats


def _surgeon_run(ctx: Dict[str, Any]) -> WorkReport:
    gid = "whitespace-surgeon"
    p = _params(ctx)
    files = p.get("files")
    if not files or not isinstance(files, dict):
        raise ValueError("files must be a dict of {name: content}")
    tab_width = int(p.get("tab_width", 4))

    per_file: List[str] = []
    total_fixes = 0
    cleaned: Dict[str, str] = {}
    for name, content in files.items():
        new_text, stats = _hygiene(str(content), tab_width)
        cleaned[str(name)] = new_text
        n = sum(stats.values())
        total_fixes += n
        per_file.append(
            f"{name}: {n} fix(es) "
            f"(trailing_ws={stats['trailing_ws']}, "
            f"tabs={stats['tabs_expanded']}, blank_runs={stats['blank_collapsed']})"
        )
    report = (
        "whitespace-surgeon report\n"
        f"files={len(files)} total_fixes={total_fixes} tab_width={tab_width}\n"
        + "\n".join(per_file)
        + "\n"
    )
    notes = f"Scanned {len(files)} file(s); {total_fixes} hygiene fix(es) applied."
    if ctx.get("dry_run"):
        return WorkReport(
            generator_id=gid,
            produced=[],
            quoted_amount_usd=3.5,
            notes="DRY RUN — " + notes + " Would write cleaned files + report.txt.",
        )
    work = _work_dir(ctx, gid)
    produced = []
    for name, content in cleaned.items():
        _write(work, str(name), content)
        produced.append(str(name))
    _write(work, "report.txt", report)
    produced.append("report.txt")
    return WorkReport(
        generator_id=gid,
        produced=produced,
        quoted_amount_usd=3.5,
        notes=notes,
    )


# ---------------------------------------------------------------------------
# 7. regex-batch-replacer
# ---------------------------------------------------------------------------


def _replacer_run(ctx: Dict[str, Any]) -> WorkReport:
    gid = "regex-batch-replacer"
    p = _params(ctx)
    text = str(p.get("text", ""))
    patterns = p.get("patterns")
    if not patterns or not isinstance(patterns, list):
        raise ValueError("patterns must be a non-empty list of {pattern, replacement}")

    compiled = []
    for i, spec in enumerate(patterns):
        if not isinstance(spec, dict) or "pattern" not in spec:
            raise ValueError(f"patterns[{i}] must be a dict with a 'pattern' key")
        try:
            rx = re.compile(spec["pattern"])
        except re.error as exc:
            raise ValueError(f"patterns[{i}] invalid regex: {exc}") from exc
        compiled.append((rx, str(spec.get("replacement", ""))))

    preview_lines: List[str] = []
    current = text
    total_matches = 0
    for rx, repl in compiled:
        matches = list(rx.finditer(current))
        total_matches += len(matches)
        samples = [repr(m.group(0))[:60] for m in matches[:3]]
        preview_lines.append(
            f"/{rx.pattern}/ -> {repl!r}: {len(matches)} match(es)"
            + (f" e.g. {', '.join(samples)}" if samples else "")
        )
    current = text
    for rx, repl in compiled:
        current = rx.sub(repl, current)
    replaced = current != text

    preview = "regex-batch-replacer PREVIEW (nothing applied yet):\n" + "\n".join(
        preview_lines
    ) + "\n"
    notes = f"{len(patterns)} pattern(s), {total_matches} total match(es); {'text would change' if replaced else 'no change'}."
    if ctx.get("dry_run"):
        return WorkReport(
            generator_id=gid,
            produced=[],
            quoted_amount_usd=4.0,
            notes="DRY RUN — " + preview + notes,
        )
    work = _work_dir(ctx, gid)
    _write(work, "preview.txt", preview)
    _write(work, "replaced.txt", current)
    return WorkReport(
        generator_id=gid,
        produced=["preview.txt", "replaced.txt"],
        quoted_amount_usd=4.0,
        notes=notes,
    )


# ---------------------------------------------------------------------------
# 8. excerpt-extractor
# ---------------------------------------------------------------------------

_STOPWORDS = frozenset(
    "a an and are as at be been but by for from had has have he her his i in "
    "into is it its of on or s she that the their them they this to was we "
    "were will with you your".split()
)


def _sentences(text: str) -> List[str]:
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [s.strip() for s in parts if len(s.strip()) >= 20]


def _excerpt_run(ctx: Dict[str, Any]) -> WorkReport:
    gid = "excerpt-extractor"
    p = _params(ctx)
    text = str(p.get("text", ""))
    count = int(p.get("count", 3))
    if count < 1:
        raise ValueError("count must be >= 1")
    sents = _sentences(text)
    if not sents:
        raise ValueError("no sentences found in text")

    freq: Dict[str, int] = {}
    for s in sents:
        for w in re.findall(r"[a-z]+", s.lower()):
            if w not in _STOPWORDS:
                freq[w] = freq.get(w, 0) + 1

    scored: List[Tuple[float, int, str]] = []
    for i, s in enumerate(sents):
        words = [w for w in re.findall(r"[a-z]+", s.lower()) if w not in _STOPWORDS]
        density = sum(freq[w] for w in words) / max(len(words), 1)
        position_bonus = 1.0 / (1.0 + i * 0.15)
        scored.append((density * position_bonus, i, s))
    scored.sort(key=lambda t: t[0], reverse=True)
    top = sorted(scored[:count], key=lambda t: t[1])

    excerpt = "\n\n".join(s for _, _, s in top)
    lines = [
        f"[{i+1}] score={score:.3f}: {s[:80]}" for score, i, s in scored[:count]
    ]
    notes = f"Pulled {len(top)} key excerpt(s) from {len(sents)} sentence(s)."
    if ctx.get("dry_run"):
        return WorkReport(
            generator_id=gid,
            produced=[],
            quoted_amount_usd=3.0,
            notes="DRY RUN — " + notes + " Would write excerpts.txt + scores.txt.",
        )
    work = _work_dir(ctx, gid)
    _write(work, "excerpts.txt", excerpt + "\n")
    _write(work, "scores.txt", "\n".join(lines) + "\n")
    return WorkReport(
        generator_id=gid,
        produced=["excerpts.txt", "scores.txt"],
        quoted_amount_usd=3.0,
        notes=notes,
    )


# ---------------------------------------------------------------------------
# 9. unit-converter-pro
# ---------------------------------------------------------------------------

_UNITS: Dict[str, Dict[str, float]] = {
    "length": {"m": 1, "km": 1000, "cm": 0.01, "mm": 0.001, "mi": 1609.344,
               "yd": 0.9144, "ft": 0.3048, "in": 0.0254, "nmi": 1852},
    "mass": {"kg": 1, "g": 0.001, "mg": 1e-6, "lb": 0.45359237,
             "oz": 0.028349523125, "t": 1000},
    "time": {"s": 1, "ms": 0.001, "min": 60, "h": 3600, "day": 86400, "week": 604800},
    "area": {"m2": 1, "km2": 1e6, "cm2": 1e-4, "ft2": 0.09290304,
             "acre": 4046.8564224, "ha": 10000},
    "volume": {"m3": 1, "L": 0.001, "mL": 1e-6, "gal": 0.003785411784,
               "qt": 0.000946352946, "ft3": 0.028316846592},
    "speed": {"m/s": 1, "km/h": 1 / 3.6, "mph": 0.44704, "knot": 0.5144444444,
              "ft/s": 0.3048},
    "pressure": {"Pa": 1, "kPa": 1000, "MPa": 1e6, "bar": 100000,
                 "psi": 6894.757293168, "atm": 101325, "mmHg": 133.322387415},
    "energy": {"J": 1, "kJ": 1000, "cal": 4.184, "kcal": 4184,
               "kWh": 3.6e6, "BTU": 1055.05585262, "eV": 1.602176634e-19},
    "power": {"W": 1, "kW": 1000, "hp": 745.6998715822702},
    "data": {"B": 1, "KB": 1024, "MB": 1024 ** 2, "GB": 1024 ** 3,
             "TB": 1024 ** 4, "bit": 1 / 8},
}

_ALIASES = {
    "meter": "m", "metre": "m", "meters": "m", "kilometer": "km", "kilometre": "km",
    "centimeter": "cm", "centimetre": "cm", "millimeter": "mm", "millimetre": "mm",
    "mile": "mi", "miles": "mi", "yard": "yd", "yards": "yd", "foot": "ft",
    "feet": "ft", "inch": "in", "inches": "in", "gram": "g", "grams": "g",
    "kilogram": "kg", "pound": "lb", "pounds": "lb", "ounce": "oz",
    "second": "s", "seconds": "s", "minute": "min", "minutes": "min",
    "hour": "h", "hours": "h", "liter": "L", "litre": "L", "liters": "L",
    "gallon": "gal", "gallons": "gal", "celsius": "C", "fahrenheit": "F",
    "kelvin": "K", "degC": "C", "degF": "F", "watt": "W", "watts": "W",
    "byte": "B", "bytes": "B", "kilobyte": "KB", "megabyte": "MB",
}


def _to_celsius(v: float, unit: str) -> float:
    if unit == "C":
        return v
    if unit == "F":
        return (v - 32) * 5 / 9
    if unit == "K":
        return v - 273.15
    raise ValueError(f"unknown temperature unit {unit!r}")


def _convert(value: float, src: str, dst: str) -> Tuple[float, str]:
    src = _ALIASES.get(src, src)
    dst = _ALIASES.get(dst, dst)
    if src in ("C", "F", "K") or dst in ("C", "F", "K"):
        if src not in ("C", "F", "K") or dst not in ("C", "F", "K"):
            raise ValueError(f"incompatible dimensions: {src!r} vs {dst!r}")
        c = _to_celsius(value, src)
        out = {"C": c, "F": c * 9 / 5 + 32, "K": c + 273.15}[dst]
        return out, "temperature"
    dim_src = dim_dst = None
    for dim, table in _UNITS.items():
        if src in table:
            dim_src = dim
        if dst in table:
            dim_dst = dim
    if dim_src is None:
        raise ValueError(f"unknown unit {src!r}")
    if dim_dst is None:
        raise ValueError(f"unknown unit {dst!r}")
    if dim_src != dim_dst:
        raise ValueError(f"incompatible dimensions: {src!r} vs {dst!r}")
    base = value * _UNITS[dim_src][src]
    return base / _UNITS[dim_dst][dst], dim_src


def _converter_run(ctx: Dict[str, Any]) -> WorkReport:
    gid = "unit-converter-pro"
    p = _params(ctx)
    jobs = p.get("conversions")
    if jobs is None:
        single = {k: p.get(k) for k in ("value", "from", "to")}
        if any(v is None for v in single.values()):
            raise ValueError(
                "supply conversions=[{value, from, to}, ...] or value/from/to"
            )
        jobs = [single]
    if not isinstance(jobs, list) or not jobs:
        raise ValueError("conversions must be a non-empty list")

    rows: List[str] = []
    records: List[Dict[str, Any]] = []
    for i, job in enumerate(jobs):
        try:
            value = float(job["value"])
            result, dim = _convert(value, str(job["from"]), str(job["to"]))
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"conversions[{i}]: {exc}") from exc
        records.append(
            {"value": value, "from": job["from"], "to": job["to"],
             "result": round(result, 6), "dimension": dim}
        )
        rows.append(f"{value:g} {job['from']} = {result:.6g} {job['to']}  [{dim}]")
    body = "\n".join(rows) + "\n"
    notes = f"Converted {len(records)} value(s) across {len({r['dimension'] for r in records})} dimension(s)."
    if ctx.get("dry_run"):
        return WorkReport(
            generator_id=gid,
            produced=[],
            quoted_amount_usd=2.5,
            notes="DRY RUN — " + notes + " Would write conversions.txt + conversions.json.",
        )
    work = _work_dir(ctx, gid)
    _write(work, "conversions.txt", body)
    _write(work, "conversions.json", json.dumps(records, indent=2) + "\n")
    return WorkReport(
        generator_id=gid,
        produced=["conversions.txt", "conversions.json"],
        quoted_amount_usd=2.5,
        notes=notes,
    )


# ---------------------------------------------------------------------------
# 10. passphrase-forge
# ---------------------------------------------------------------------------

_FORGE_WORDS = (
    "amber anchor apple arc atlas badge baker beam birch blaze bloom bolt "
    "brave bridge brook cabin cargo cedar chalk chest cider cliff cloud cobra "
    "comet copper coral crane crisp cinder dawn delta dogwood drift dune "
    "eagle ember fern field finch flame flint forest frost grove hawk heron "
    "honey ivory jade june kayak knoll larch lark lemon lilac linen lotus "
    "lumen maple meadow mesa mist moon moss north nova oak opal otter owl "
    "oasis paint panel pebble pine pitch plain plaza pond prairie quilt "
    "quarry quartz raven ridge river roost sage sand seal shell shore sieve "
    "slate smoke sparrow spice spruce stag stone storm sumac swift talon "
    "tango teal thorn timber topaz trail trout tulip umber union vapor "
    "vega velvet vixen wagon walnut wedge willow wren yacht yarrow yawl "
    "yodel zest zinc".split()
)  # 128 words, original list


def _forge_run(ctx: Dict[str, Any]) -> WorkReport:
    gid = "passphrase-forge"
    p = _params(ctx)
    n_words = int(p.get("words", 6))
    n_pass = int(p.get("passphrases", 5))
    sep = str(p.get("separator", "-"))
    add_digit = bool(p.get("add_digit", True))
    if not 3 <= n_words <= 12:
        raise ValueError("words must be 3..12")
    if not 1 <= n_pass <= 50:
        raise ValueError("passphrases must be 1..50")

    bits_per_word = len(_FORGE_WORDS).bit_length() - 1  # 7 for 128
    entropy = n_words * bits_per_word + (3 if add_digit else 0)
    made: List[str] = []
    for _ in range(n_pass):
        words = [secrets.choice(_FORGE_WORDS) for _ in range(n_words)]
        if add_digit:
            words.append(str(secrets.randbelow(10)))
        made.append(sep.join(words))

    notes = (
        f"Forged {n_pass} passphrase(s), {n_words} words each, ~{entropy} bits "
        f"entropy via the secrets module (CSPRNG)."
    )
    if ctx.get("dry_run"):
        return WorkReport(
            generator_id=gid,
            produced=[],
            quoted_amount_usd=2.0,
            notes="DRY RUN — " + notes + " Would write passphrases.txt (0600).",
        )
    work = _work_dir(ctx, gid)
    path = _write(work, "passphrases.txt", "\n".join(made) + "\n")
    try:
        import os as _os

        _os.chmod(path, 0o600)
    except OSError:
        pass
    return WorkReport(
        generator_id=gid,
        produced=["passphrases.txt"],
        quoted_amount_usd=2.0,
        notes=notes + " File written with 0600 permissions.",
    )


# ---------------------------------------------------------------------------
# 11. diff-summarizer
# ---------------------------------------------------------------------------

_HUNK_RE = re.compile(r"^@@ -\d+(?:,\d+)? \+\d+(?:,\d+)? @@(.*)$")
_FUNC_RE = re.compile(r"\b(?:def|class|function|fn|func)\s+([A-Za-z_][\w]*)")


def _diff_run(ctx: Dict[str, Any]) -> WorkReport:
    gid = "diff-summarizer"
    p = _params(ctx)
    text = str(p.get("diff", ""))
    if not text.strip():
        raise ValueError("diff must be a non-empty unified diff")

    files: Dict[str, Dict[str, Any]] = {}
    current: Dict[str, Any] = {}
    for line in text.splitlines():
        if line.startswith("diff --git"):
            parts = line.split()
            name = parts[-1][2:] if parts[-1].startswith("b/") else parts[-1]
            current = files.setdefault(
                name, {"added": 0, "removed": 0, "symbols": [], "hunks": 0}
            )
        elif line.startswith("+++"):
            name = line[4:].strip()
            if name.startswith("b/"):
                name = name[2:]
            current = files.setdefault(
                name, {"added": 0, "removed": 0, "symbols": [], "hunks": 0}
            )
        elif not current:
            continue
        elif (m := _HUNK_RE.match(line)):
            current["hunks"] += 1
            for sym in _FUNC_RE.findall(m.group(1)):
                if sym not in current["symbols"]:
                    current["symbols"].append(sym)
        elif line.startswith("+") and not line.startswith("+++"):
            current["added"] += 1
        elif line.startswith("-") and not line.startswith("---"):
            current["removed"] += 1

    if not files:
        raise ValueError("no file sections found in diff")

    summaries: List[str] = []
    tot_add = tot_rem = 0
    for name, st in files.items():
        tot_add += st["added"]
        tot_rem += st["removed"]
        verb = "added" if st["added"] >= st["removed"] else "trimmed"
        sym = ""
        if st["symbols"]:
            sym = f" Touching {', '.join(st['symbols'][:5])}."
        summaries.append(
            f"In {name}, {st['added']} line(s) added and {st['removed']} removed "
            f"across {st['hunks']} hunk(s) — net {verb}.{sym}"
        )
    body = "\n\n".join(summaries) + "\n"
    notes = (
        f"Summarized {len(files)} file(s): +{tot_add}/-{tot_rem} lines total, "
        "in plain language."
    )
    if ctx.get("dry_run"):
        return WorkReport(
            generator_id=gid,
            produced=[],
            quoted_amount_usd=3.0,
            notes="DRY RUN — " + notes + " Would write summary.txt.",
        )
    work = _work_dir(ctx, gid)
    _write(work, "summary.txt", body)
    return WorkReport(
        generator_id=gid,
        produced=["summary.txt"],
        quoted_amount_usd=3.0,
        notes=notes,
    )


# ---------------------------------------------------------------------------
# 12. license-header-stamper
# ---------------------------------------------------------------------------

_TEMPLATES = {
    "hash": "# {marker}\n# {license} — (c) {year} {owner}\n# All rights reserved.\n",
    "slash": "// {marker}\n// {license} — (c) {year} {owner}\n// All rights reserved.\n",
    "block": "/* {marker}\n * {license} — (c) {year} {owner}\n * All rights reserved.\n */\n",
    "html": "<!-- {marker}\n     {license} — (c) {year} {owner}\n     All rights reserved.\n-->\n",
    "python-doc": '""" {marker}\n{license} — (c) {year} {owner}.\nAll rights reserved.\n"""\n',
}

_EXT_STYLE = {
    ".py": "hash", ".sh": "hash", ".rb": "hash", ".pl": "hash", ".yml": "hash",
    ".yaml": "hash", ".toml": "hash",
    ".js": "slash", ".ts": "slash", ".java": "slash", ".c": "slash",
    ".cpp": "slash", ".go": "slash", ".rs": "slash",
    ".css": "block", ".php": "block",
    ".html": "html", ".xml": "html",
}


def _stamp_run(ctx: Dict[str, Any]) -> WorkReport:
    gid = "license-header-stamper"
    p = _params(ctx)
    files = p.get("files")
    if not files or not isinstance(files, dict):
        raise ValueError("files must be a dict of {name: content}")
    owner = str(p.get("owner", "Unknown"))
    year = str(p.get("year", "2026"))
    license_name = str(p.get("license", "Proprietary"))
    marker = str(p.get("marker", "LEVI-LICENSE-HEADER"))
    style_override = p.get("style")

    stamped: Dict[str, str] = {}
    report_lines: List[str] = []
    stamped_n = skipped_n = 0
    for name, content in files.items():
        name = str(name)
        body = str(content)
        head = "\n".join(body.splitlines()[:12])
        if marker in head:
            skipped_n += 1
            report_lines.append(f"{name}: already stamped — skipped")
            stamped[name] = body
            continue
        style = style_override or _EXT_STYLE.get(Path(name).suffix.lower(), "hash")
        template = _TEMPLATES.get(style, _TEMPLATES["hash"])
        header = template.format(
            marker=marker, license=license_name, year=year, owner=owner
        )
        lines = body.splitlines(keepends=True)
        prefix = ""
        if lines and lines[0].startswith("#!"):
            prefix = lines[0]
            body = "".join(lines[1:])
        stamped[name] = prefix + header + "\n" + body.lstrip("\n")
        stamped_n += 1
        report_lines.append(f"{name}: stamped ({style})")

    report = (
        f"license-header-stamper report: {stamped_n} stamped, {skipped_n} skipped\n"
        + "\n".join(report_lines)
        + "\n"
    )
    notes = f"Processed {len(files)} file(s): {stamped_n} stamped, {skipped_n} already had the header."
    if ctx.get("dry_run"):
        return WorkReport(
            generator_id=gid,
            produced=[],
            quoted_amount_usd=2.5,
            notes="DRY RUN — " + notes + " Would write stamped files + report.txt.",
        )
    work = _work_dir(ctx, gid)
    produced = []
    for name, content in stamped.items():
        _write(work, name, content)
        produced.append(name)
    _write(work, "report.txt", report)
    produced.append("report.txt")
    return WorkReport(
        generator_id=gid,
        produced=produced,
        quoted_amount_usd=2.5,
        notes=notes,
    )


# ---------------------------------------------------------------------------
# Registration — Batch A claims slots 1..12
# ---------------------------------------------------------------------------

_DEFINITIONS = [
    ("text-deduper", "Text Deduper",
     "Removes duplicate lines/paragraphs from text and reports counts.",
     3.0, _dedupe_run, 1),
    ("csv-columnizer", "CSV Columnizer",
     "Normalizes messy CSVs: delimiter sniffing, header cleanup, safe quoting.",
     2.5, _columnizer_run, 2),
    ("filename-normalizer", "Filename Normalizer",
     "Batch-renames files to a clean slug convention; writes an undo manifest.",
     2.0, _normalizer_run, 3),
    ("json-prettifier-validator", "JSON Prettifier & Validator",
     "Validates JSON, pinpoints errors with line/column, pretty-prints valid input.",
     2.0, _json_run, 4),
    ("markdown-toc-builder", "Markdown TOC Builder",
     "Builds or updates a table of contents in markdown documents.",
     2.0, _toc_run, 5),
    ("whitespace-surgeon", "Whitespace Surgeon",
     "Whole-directory whitespace hygiene with a per-file fix report.",
     3.5, _surgeon_run, 6),
    ("regex-batch-replacer", "Regex Batch Replacer",
     "Multi-pattern find/replace across text with a preview before applying.",
     4.0, _replacer_run, 7),
    ("excerpt-extractor", "Excerpt Extractor",
     "Extractive key-excerpt puller for long text via sentence scoring.",
     3.0, _excerpt_run, 8),
    ("unit-converter-pro", "Unit Converter Pro",
     "Engineering unit conversions (10 dimensions + temperature) with batch mode.",
     2.5, _converter_run, 9),
    ("passphrase-forge", "Passphrase Forge",
     "Memorable diceware-style passphrases from a 128-word list via secrets.",
     2.0, _forge_run, 10),
    ("diff-summarizer", "Diff Summarizer",
     "Turns unified diffs into plain-language change summaries per file.",
     3.0, _diff_run, 11),
    ("license-header-stamper", "License Header Stamper",
     "Stamps or updates license headers across a project; idempotent, shebang-safe.",
     2.5, _stamp_run, 12),
]

for _gid, _name, _desc, _price, _run, _slot in _DEFINITIONS:
    register(
        Generator(
            id=_gid,
            name=_name,
            kind="micro-tool",
            description=_desc,
            version="1.0.0",
            entry_price_usd=_price,
            run=_run,
        ),
        slot=_slot,
    )

__all__ = ["_DEFINITIONS"]
