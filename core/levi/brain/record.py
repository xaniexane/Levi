"""Recording — export corpus + brain table to markdown (Word via external docx later)."""

from __future__ import annotations

from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

from levi.brain.corpus import Corpus
from levi.brain.table import BrainTable


def export_markdown(out_path: Optional[Path] = None) -> Path:
    """Export corpus + brain table to markdown. Raises ValueError on a
    non-path ``out_path``."""
    if out_path is not None and not isinstance(out_path, (str, Path)):
        raise ValueError(
            "export_markdown: out_path must be a path or None, got %s"
            % type(out_path).__name__
        )
    out = (
        Path(out_path)
        if out_path
        else Path.home()
        / ".levi"
        / "recordings"
        / (f"levi_record_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.md")
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    corpus = Corpus()
    table = BrainTable()
    lines = [
        "# LEVI Recording",
        f"Exported: {datetime.now(timezone.utc).isoformat()}",
        "",
        "## Indexed brain",
        "",
    ]
    for r in table.search()[:100]:
        lines.append(f"- **[{r.domain}] {r.key}**: {r.value}")
    lines.extend(["", "## Corpus", ""])
    for u in reversed(corpus.list(limit=100)):
        lines.append(f"- **{u.kind}** ({u.id}): {u.text}")
    out.write_text("\n".join(lines), encoding="utf-8")
    return out
