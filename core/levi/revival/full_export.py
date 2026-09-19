"""One-command full export: your whole code-home as one open documented bundle.

Studied from: github-pattern-hunt-20260916-0018/report.md [Ranked additions 1]

The mechanism: a code-home's records (code snapshots, issues, pull
requests, stars, follows, CI history, contribution history) are collected
into a single versioned bundle whose layout is documented *inside* the
bundle itself — a MANIFEST.json describing every section, plus a human
README. Each section file carries a SHA-256 checksum recorded in the
manifest, so ``verify`` can confirm the bundle survived intact without
trusting any particular host.

Design notes, kept honest:

- The bundle is only as complete as the records handed to it. LEVI cannot
  reach out to fetch anything (local-first, no network), so ``collect``
  assembles whatever the caller supplies — ``export_everything`` is the
  one command that turns "everything I have" into "everything, portable".
- Checksums prove *integrity*, not *authorship*. For authorship, pair
  with ``signed_reputation``.
- Output is plain JSON/JSONL + a README: no proprietary format, nothing
  that needs this module to read back (though ``read_bundle`` is provided).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Sequence

ORIGIN = "levi-revival/full-export"

BUNDLE_FORMAT = "levi-forge-export/1"


@dataclass
class ExportSection:
    """One logical section of the bundle: name, records, and a note on shape."""

    name: str
    records: List[Dict] = field(default_factory=list)
    schema_note: str = ""

    def add(self, record: Dict) -> "ExportSection":
        self.records.append(record)
        return self

    def add_many(self, records: Iterable[Dict]) -> "ExportSection":
        self.records.extend(records)
        return self

    def checksum(self) -> str:
        canon = json.dumps(self.records, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canon.encode("utf-8")).hexdigest()


class FullExport:
    """Assemble the everything-bundle, then write it out in one command."""

    # The sections the wave's ranked addition calls for.
    KNOWN_SECTIONS = (
        "code",
        "issues",
        "pull_requests",
        "stars",
        "follows",
        "ci_history",
        "contributions",
        "wikis",
    )

    def __init__(self, home_name: str):
        self.home_name = home_name
        self._sections: Dict[str, ExportSection] = {}

    # -- collection ------------------------------------------------------
    def collect(
        self, section: str, records: Iterable[Dict], schema_note: str = ""
    ) -> FullExport:
        sec = self._sections.setdefault(section, ExportSection(name=section))
        sec.add_many(records)
        if schema_note and not sec.schema_note:
            sec.schema_note = schema_note
        return self

    def collect_repo(
        self,
        name: str,
        commits: Sequence[Dict],
        readme: str = "",
    ) -> FullExport:
        """Hand the exporter one repository's snapshot."""
        return self.collect(
            "code",
            [{"repo": name, "commits": list(commits), "readme": readme}],
            schema_note="one record per repo: {repo, commits, readme}",
        )

    def section_names(self) -> List[str]:
        return sorted(self._sections)

    def record_count(self) -> int:
        return sum(len(s.records) for s in self._sections.values())

    # -- writing ---------------------------------------------------------
    def export_everything(self, destination: str | Path) -> Path:
        """The one command: write the whole bundle, manifest + README."""
        dest = Path(destination)
        dest.mkdir(parents=True, exist_ok=True)

        section_files: Dict[str, Dict] = {}
        for name in sorted(self._sections):
            sec = self._sections[name]
            fname = f"{name}.json"
            (dest / fname).write_text(
                json.dumps(
                    {"section": name, "records": sec.records},
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )
            section_files[name] = {
                "file": fname,
                "records": len(sec.records),
                "sha256": sec.checksum(),
                "schema_note": sec.schema_note,
            }

        manifest = {
            "format": BUNDLE_FORMAT,
            "home": self.home_name,
            "sections": section_files,
            "total_records": self.record_count(),
        }
        (dest / "MANIFEST.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8"
        )
        (dest / "README.md").write_text(self._readme(manifest), encoding="utf-8")
        return dest

    def _readme(self, manifest: Dict) -> str:
        lines = [
            f"# Full export of {self.home_name}",
            "",
            f"Format: `{BUNDLE_FORMAT}`. This bundle is self-describing:",
            "`MANIFEST.json` lists every section, its record count, and the",
            "SHA-256 of its canonical JSON. Recompute the checksum of any",
            "section file to verify it arrived intact.",
            "",
            "| section | records | sha256 |",
            "| --- | --- | --- |",
        ]
        for name, info in manifest["sections"].items():
            lines.append(f"| {name} | {info['records']} | `{info['sha256'][:16]}…` |")
        lines += [
            "",
            f"Total records: {manifest['total_records']}.",
            "",
            "Nothing here is host-specific. Take it anywhere.",
        ]
        return "\n".join(lines) + "\n"

    # -- verification ----------------------------------------------------
    @staticmethod
    def verify(bundle_dir: str | Path) -> Dict[str, object]:
        """Recompute every section checksum; report what matches and what broke."""
        dest = Path(bundle_dir)
        manifest = json.loads((dest / "MANIFEST.json").read_text(encoding="utf-8"))
        ok: List[str] = []
        broken: List[str] = []
        for name, info in manifest["sections"].items():
            data = json.loads((dest / info["file"]).read_text(encoding="utf-8"))
            sec = ExportSection(name=name, records=data["records"])
            (ok if sec.checksum() == info["sha256"] else broken).append(name)
        return {
            "format_ok": manifest.get("format") == BUNDLE_FORMAT,
            "ok": ok,
            "broken": broken,
            "intact": not broken and manifest.get("format") == BUNDLE_FORMAT,
        }

    @staticmethod
    def read_bundle(bundle_dir: str | Path) -> Dict[str, List[Dict]]:
        """Load a bundle back into memory: section name -> records."""
        dest = Path(bundle_dir)
        manifest = json.loads((dest / "MANIFEST.json").read_text(encoding="utf-8"))
        out: Dict[str, List[Dict]] = {}
        for name, info in manifest["sections"].items():
            data = json.loads((dest / info["file"]).read_text(encoding="utf-8"))
            out[name] = data["records"]
        return out
