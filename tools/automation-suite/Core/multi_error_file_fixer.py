#!/usr/bin/env python3
"""Iteratively apply SAFE whitespace fixes to Python files until they compile.

Each pass runs the equivalent of py_compile and applies ONLY safe fixes:
  - trailing whitespace removal
  - leading tabs converted to 4 spaces (fixes TabError / mixed indentation)
  - missing final newline added

The original file is backed up to <file>.bak BEFORE any change (created once;
an existing .bak is never overwritten).

This tool NEVER guesses at logic errors. If a pass makes no changes and the
file still does not compile, it reports "<file>:<line>: <compiler message>"
and stops.

Exit codes: 0 = all files compile, 1 = unfixable error / unreadable file,
2 = usage error.
"""

import argparse
import os
import shutil
import sys

MAX_PASSES = 10


def check_source(source, path):
    """Return a SyntaxError, or None if the source compiles."""
    try:
        compile(source, str(path), "exec")
        return None
    except SyntaxError as err:
        return err
    except ValueError as err:  # e.g. null bytes
        class _E:  # minimal shim with the attributes we report
            lineno = 0
            msg = str(err)
            text = ""
        return _E()


def safe_fix(lines):
    """Apply safe whitespace fixes. Returns (new_lines, changed)."""
    out = []
    changed = False
    for line in lines:
        if line.endswith("\r\n"):
            body, nl = line[:-2], "\r\n"
        elif line.endswith("\n") or line.endswith("\r"):
            body, nl = line[:-1], line[-1:]
        else:
            body, nl = line, ""
        stripped = body.lstrip(" \t")
        lead = body[:len(body) - len(stripped)]
        new_lead = lead.replace("\t", "    ")
        new_body = stripped.rstrip(" \t")
        new_line = new_lead + new_body + nl
        if new_line != line:
            changed = True
        out.append(new_line)
    if out and not out[-1].endswith(("\n", "\r")):
        out[-1] += "\n"
        changed = True
    return out, changed


def report_error(path, err):
    lineno = getattr(err, "lineno", "?") or "?"
    msg = getattr(err, "msg", None) or str(err)
    text = (getattr(err, "text", "") or "").rstrip("\n")
    print(f"{path}:{lineno}: {msg}", file=sys.stderr)
    if text:
        print(f"    {text}", file=sys.stderr)


def fix_file(path):
    if not os.path.isfile(path):
        print(f"error: not a file: {path}", file=sys.stderr)
        return 1
    try:
        with open(path, "r", encoding="utf-8", newline="") as fh:
            original = fh.read()
    except (OSError, UnicodeDecodeError) as exc:
        print(f"error: cannot read {path}: {exc}", file=sys.stderr)
        return 1

    err = check_source(original, path)
    if err is None:
        print(f"OK (already compiles): {path}")
        return 0

    bak = path + ".bak"
    if not os.path.exists(bak):
        shutil.copy2(path, bak)
        print(f"backup: {bak}")
    else:
        print(f"backup: keeping existing {bak}")

    lines = original.splitlines(keepends=True)
    for pass_no in range(1, MAX_PASSES + 1):
        lines, changed = safe_fix(lines)
        if not changed:
            report_error(path, check_source("".join(lines), path))
            print(f"unfixable after {pass_no - 1} pass(es): "
                  f"only safe whitespace fixes are applied; original kept in {bak}",
                  file=sys.stderr)
            return 1
        with open(path, "w", encoding="utf-8", newline="") as fh:
            fh.writelines(lines)
        err = check_source("".join(lines), path)
        if err is None:
            print(f"FIXED in {pass_no} pass(es): {path}")
            return 0

    report_error(path, check_source("".join(lines), path))
    print(f"unfixable after {MAX_PASSES} passes; original kept in {bak}",
          file=sys.stderr)
    return 1


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Apply only safe whitespace fixes to Python files until "
                    "they compile. Backs up to .bak first; never touches logic.")
    ap.add_argument("files", nargs="+", help="Python file(s) to repair")
    args = ap.parse_args(argv)
    rc = 0
    for path in args.files:
        if fix_file(path) != 0:
            rc = 1
    return rc


if __name__ == "__main__":
    sys.exit(main())
