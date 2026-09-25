#!/usr/bin/env python3
"""Read-only Chrome/Chromium history extraction (local only, no network).

Copies the live History SQLite database to a temp file first -- the live DB
is never opened directly (it may be locked by a running browser) and is
never modified. Dumps urls+visits to urls.csv and a JSON report.

Exit codes: 0 = ok, 1 = unexpected error, 2 = no Chrome/Chromium profile found.
"""

import argparse
import csv
import json
import os
import shutil
import sqlite3
import sys
import tempfile
from datetime import datetime, timedelta

CHROME_EPOCH = datetime(1601, 1, 1)

CANDIDATE_PROFILES = [
    os.path.expanduser("~/.config/google-chrome/Default"),
    os.path.expanduser("~/.config/chromium/Default"),
]


def chrome_time(micros):
    try:
        return (CHROME_EPOCH + timedelta(microseconds=int(micros))).isoformat()
    except (TypeError, ValueError, OverflowError):
        return ""


def find_history(profile):
    candidates = []
    if profile:
        candidates.append(profile)
    candidates.extend(CANDIDATE_PROFILES)
    for cand in candidates:
        hist = os.path.join(cand, "History")
        if os.path.isfile(hist):
            return cand, hist
    return None, None


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Extract Chrome/Chromium browsing history (read-only) "
        "to CSV + JSON. Local only."
    )
    ap.add_argument(
        "--profile",
        default=None,
        help="profile dir containing the History file "
        "(default: auto-detect Chrome/Chromium Default)",
    )
    ap.add_argument(
        "--output",
        default=None,
        help="output directory (default: ./browser_carve_<timestamp>)",
    )
    args = ap.parse_args(argv)

    profile_dir, history = find_history(args.profile)
    if not history:
        print("no Chrome/Chromium History database found.", file=sys.stderr)
        print("looked in:", file=sys.stderr)
        tried = ([args.profile] if args.profile else []) + CANDIDATE_PROFILES
        for t in tried:
            print(f"  {t}/History", file=sys.stderr)
        print("hint: pass --profile /path/to/<ProfileDir>", file=sys.stderr)
        return 2

    outdir = args.output or os.path.join(
        os.getcwd(), "browser_carve_" + datetime.now().strftime("%Y%m%d-%H%M%S")
    )
    os.makedirs(outdir, exist_ok=True)

    # Work on a temp copy; the live DB is never touched.
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    try:
        shutil.copy2(history, tmp.name)
        con = sqlite3.connect(f"file:{tmp.name}?mode=ro", uri=True)
        try:
            cur = con.cursor()
            cur.execute(
                "SELECT id, url, title, visit_count, last_visit_time FROM urls "
                "ORDER BY last_visit_time DESC"
            )
            urls = cur.fetchall()
            try:
                cur.execute("SELECT COUNT(*) FROM visits")
                visit_count = cur.fetchone()[0]
            except sqlite3.Error:
                visit_count = 0
        finally:
            con.close()
    except sqlite3.Error as exc:
        print(f"error reading History copy: {exc}", file=sys.stderr)
        return 1
    finally:
        os.unlink(tmp.name)

    rows = [
        {"url": u, "title": t or "", "visit_count": vc, "last_visit": chrome_time(lvt)}
        for _, u, t, vc, lvt in urls
    ]

    csv_path = os.path.join(outdir, "urls.csv")
    with open(csv_path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["url", "title", "visit_count", "last_visit"])
        w.writeheader()
        w.writerows(rows)

    report = {
        "tool": "advanced_browser_carver",
        "profile": profile_dir,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "url_count": len(rows),
        "visit_count": visit_count,
        "urls": rows,
    }
    json_path = os.path.join(outdir, "report.json")
    with open(json_path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)

    print(f"profile:  {profile_dir}")
    print(f"urls:     {len(rows)}")
    print(f"visits:   {visit_count}")
    print(f"csv:      {csv_path}")
    print(f"json:     {json_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
