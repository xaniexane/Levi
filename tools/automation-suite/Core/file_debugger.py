#!/usr/bin/env python3
"""Analyze any file and print a diagnostic report.

Reports: size, sha256, text-vs-binary detection, encoding guess,
line-ending style, line/word/byte counts, and (for .py files)
a py_compile syntax check. Read-only; never modifies the file.
"""

import argparse
import hashlib
import os
import sys

SAMPLE = 65536


def human_size(n):
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.1f} {unit}" if unit != "B" else f"{n} B"
        n /= 1024


def looks_like_text(data):
    if b"\x00" in data:
        return False
    sample = data[:8192]
    if not sample:
        return True
    bad = sum(1 for b in sample if b < 9 or (13 < b < 32 and b != 27))
    return (bad / len(sample)) < 0.30


def guess_encoding(data):
    try:
        data[:8192].decode("utf-8")
        return "utf-8"
    except UnicodeDecodeError:
        pass
    try:
        data[:8192].decode("ascii")
        return "ascii"
    except UnicodeDecodeError:
        pass
    return "unknown (not valid UTF-8; treat as binary)"


def line_ending_style(data):
    crlf = data.count(b"\r\n")
    lone_cr = data.count(b"\r") - crlf
    lf = data.count(b"\n") - crlf
    kinds = [k for k, v in (("CRLF", crlf), ("LF", lf), ("CR", lone_cr)) if v]
    if not kinds:
        return "none (no line breaks)"
    if len(kinds) == 1:
        return kinds[0]
    return "mixed (" + ", ".join(f"{k}={v}" for k, v in
                                 (("CRLF", crlf), ("LF", lf), ("CR", lone_cr)) if v) + ")"


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Print a diagnostic report for any file (read-only).")
    ap.add_argument("file", help="file to analyze")
    args = ap.parse_args(argv)

    path = args.file
    if not os.path.isfile(path):
        print(f"error: not a file: {path}", file=sys.stderr)
        return 2

    with open(path, "rb") as fh:
        data = fh.read(SAMPLE + 1)
    truncated = len(data) > SAMPLE
    data = data[:SAMPLE]

    size = os.path.getsize(path)
    sha = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            sha.update(chunk)

    is_text = looks_like_text(data)
    print(f"file:        {os.path.abspath(path)}")
    print(f"size:        {human_size(size)} ({size} bytes)")
    print(f"sha256:      {sha.hexdigest()}")
    print(f"type:        {'text' if is_text else 'binary'}"
          + (" (first 64KB sampled)" if truncated else ""))

    if is_text:
        print(f"encoding:    {guess_encoding(data)}")
        print(f"line endings:{line_ending_style(data)}")
        text = data.decode("utf-8", errors="replace")
        lines = text.splitlines()
        words = text.split()
        print(f"lines:       {len(lines)}")
        print(f"words:       {len(words)}")
        print(f"bytes:       {size}")
    else:
        print("line/word counts skipped (binary file)")

    if path.endswith(".py"):
        try:
            with open(path, "r", encoding="utf-8") as fh:
                compile(fh.read(), path, "exec")
            print("py_compile:  OK (syntax valid)")
        except SyntaxError as err:
            print(f"py_compile:  FAIL at line {err.lineno}: {err.msg}")
        except (OSError, UnicodeDecodeError) as exc:
            print(f"py_compile:  could not read: {exc}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
