#!/usr/bin/env python3
"""Sort files in a target directory into category subfolders.

Default is a DRY RUN: prints the planned moves and changes nothing.
Pass --apply to actually move the files.

Safety:
  - Only files directly inside the target dir are considered (no recursion).
  - Hidden files (dotfiles) are skipped.
  - Category subfolders created by previous runs are skipped (they are dirs).
  - Name collisions are resolved by suffixing: photo.jpg -> photo_1.jpg.
  - Every applied move is appended to a receipt log.
"""

import argparse
import os
import shutil
import sys
from datetime import datetime

CATEGORIES = {
    "images": {"jpg", "jpeg", "png", "gif", "bmp", "webp", "svg", "tiff", "tif", "ico", "heic"},
    "documents": {"pdf", "doc", "docx", "odt", "txt", "md", "markdown", "rtf",
                  "xls", "xlsx", "csv", "ppt", "pptx", "epub", "tex"},
    "audio": {"mp3", "wav", "flac", "ogg", "oga", "m4a", "aac", "opus"},
    "video": {"mp4", "mkv", "avi", "mov", "webm", "m4v", "mpg", "mpeg"},
    "archives": {"zip", "tar", "gz", "bz2", "xz", "7z", "rar", "tgz"},
    "code": {"py", "js", "ts", "tsx", "jsx", "sh", "bash", "html", "htm", "css",
             "json", "yml", "yaml", "xml", "java", "c", "h", "cpp", "go", "rs",
             "php", "rb", "sql", "toml", "ini", "cfg"},
}

RECEIPT_NAME = "moves_receipt.log"


def category_for(name):
    if "." in name:
        ext = name.rsplit(".", 1)[1].lower()
        for cat, exts in CATEGORIES.items():
            if ext in exts:
                return cat
    return "other"


def unique_dest(directory, name):
    dest = os.path.join(directory, name)
    if not os.path.exists(dest):
        return dest
    stem, dot, ext = name.rpartition(".")
    if not dot:  # no extension
        stem, ext = name, ""
    else:
        ext = "." + ext
    i = 1
    while True:
        candidate = os.path.join(directory, f"{stem}_{i}{ext}")
        if not os.path.exists(candidate):
            return candidate
        i += 1


def plan_moves(target):
    plans = []
    for entry in sorted(os.listdir(target)):
        if entry.startswith("."):
            continue  # hidden files skipped
        if entry == RECEIPT_NAME:
            continue  # never move our own receipt
        src = os.path.join(target, entry)
        if not os.path.isfile(src) or os.path.islink(src):
            continue  # dirs (incl. our category dirs) and symlinks skipped
        cat = category_for(entry)
        dest_dir = os.path.join(target, cat)
        dest = unique_dest(dest_dir, entry)
        plans.append((src, dest, cat))
    return plans


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Sort files in a directory into category subfolders. "
                    "Dry-run by default; use --apply to move.")
    ap.add_argument("target", nargs="?", default=".",
                    help="directory to organize (default: current dir)")
    ap.add_argument("--apply", action="store_true",
                    help="perform the moves (default: dry-run, print plan only)")
    ap.add_argument("--receipt", default=None,
                    help="receipt log path (default: <target>/moves_receipt.log)")
    args = ap.parse_args(argv)

    target = os.path.abspath(args.target)
    if not os.path.isdir(target):
        print(f"error: not a directory: {target}", file=sys.stderr)
        return 2

    plans = plan_moves(target)
    if not plans:
        print("nothing to organize.")
        return 0

    if not args.apply:
        print(f"dry-run: {len(plans)} file(s) would be moved (use --apply to move):")
        for src, dest, cat in plans:
            print(f"  {os.path.basename(src)} -> {cat}/{os.path.basename(dest)}")
        return 0

    receipt = args.receipt or os.path.join(target, RECEIPT_NAME)
    moved = 0
    with open(receipt, "a", encoding="utf-8") as log:
        for src, dest, cat in plans:
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            shutil.move(src, dest)
            stamp = datetime.now().isoformat(timespec="seconds")
            log.write(f"{stamp} MOVED {src} -> {dest}\n")
            print(f"  moved {os.path.basename(src)} -> {cat}/{os.path.basename(dest)}")
            moved += 1
    print(f"done: {moved} file(s) moved. receipt: {receipt}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
