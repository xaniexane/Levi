"""Demo: triage → file → search, fully local (working title: sovmail)."""

from __future__ import annotations

import tempfile
from pathlib import Path

from .archive import Archive
from .bayes import score, train
from .bridge import baseline_bundle
from .filters import Filter, disposition
from .scamlinks import analyze_links, is_suspicious
from .search import search_index
from .stationery import compose, default_stationery

MESSAGE = {
    "id": "<demo-1>",
    "from": "boss@example.com",
    "to": ["me@example.com"],
    "subject": "Q3 planning",
    "body": "Let's meet Thursday to plan Q3. Thanks!",
    "list_unsub": False,
}


def main() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="sovmail-demo-"))
    filters = [
        Filter(
            id="boss-file",
            predicates=({"field": "from", "domain_is": "example.com"},),
            action="file:work",
            priority=10,
        )
    ]
    disp = disposition(MESSAGE, filters)
    print("disposition:", disp, "| baseline bundle:", baseline_bundle(MESSAGE, tmp))

    model = train(
        [("free money click now", "spam"), ("meeting thursday planning", "ham")]
    )
    print("bayes P(spam):", round(score(model, MESSAGE["body"]), 3))
    print(
        "scam links:",
        analyze_links(MESSAGE),
        "suspicious:",
        is_suspicious(analyze_links(MESSAGE)),
    )

    draft = compose(default_stationery()[0], MESSAGE)
    print("draft:", draft["template_id"], "|", draft["kind"])

    archive = Archive(tmp / "archive")
    archive.append(disp["folder"], MESSAGE)
    index = archive.build_index(disp["folder"])
    print("search 'planning':", search_index(index, "planning"))


if __name__ == "__main__":
    main()
