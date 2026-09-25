---
skill_id: sys_python_pathlib
name: Python pathlib
description: Object-oriented filesystem paths: the modern replacement for os.path string juggling.
risk: info
permissions: []
requires_confirmation: false
tags: [python, stdlib]
version: 1.0.0
---
# Python pathlib

## Purpose

Object-oriented filesystem paths: the modern replacement for os.path string juggling.

## Overview

pathlib treats paths as objects instead of strings. Path('a') / 'b' / 'c.txt' joins with the / operator - readable on every OS, no separator worries. Properties expose parts: .name, .stem, .suffix, .parent, .parts. Methods do the work: .exists(), .is_file(), .is_dir(), .mkdir(parents=True, exist_ok=True), .read_text()/.write_text() for small files, .iterdir() and .glob()/.rglob() for listing and searching. resolve() absolutizes and normalizes; relative_to() strips a base. Compared to os.path, pathlib reads as intent rather than string surgery, and it is cross-platform by construction. Interop is smooth: most stdlib functions accept path-like objects, and str(p) converts when a real string is needed. Two cautions: path objects are immutable (methods return new paths), and / with an absolute right side discards the left (Path('/a') / '/b' is Path('/b')). For scripting, pathlib plus a few shlex-free subprocess calls covers most file chores without touching the shell.

## Quick reference

- Path('a') / 'b': join with /. .name/.stem/.suffix/.parent/.parts: parts.

- .exists()/.is_file()/.is_dir()/.mkdir(parents=True, exist_ok=True).

- .read_text()/.write_text(): small files. .glob()/.rglob(): pattern search.

- .resolve(): absolute + normalized. .relative_to(base): strip prefix.

- Paths are immutable; methods return new Path objects.

- Path('/a') / '/b' == Path('/b'): absolute right side wins.


## Worked example

Everyday pathlib chores:

```
from pathlib import Path

root = Path('project')
root.mkdir(parents=True, exist_ok=True)
(root / 'notes.txt').write_text('hello\n', encoding='utf-8')

for py in root.rglob('*.py'):
    print(py.relative_to(root), py.stat().st_size)

p = Path('/tmp/a/b.txt')
print(p.parent, p.stem, p.suffix)
```

- mkdir(parents=True, exist_ok=True) is the safe recursive create.

- rglob('*.py') recurses; relative_to strips the base for display.

- Always pass encoding to read_text/write_text explicitly.


## Common mistakes

- Forgetting encoding= on read_text/write_text, getting locale-dependent behavior.
  Fix: Always pass encoding='utf-8' explicitly.

- Treating Path like a string: p + '/x' fails.
  Fix: Use the / operator or str(p) when a real string is needed.


## Quick checks

Q: pathlib or os.path - which should new code use?
A: pathlib. It reads as intent, handles separators portably, and bundles inspection with the path object. os.path remains fine in legacy code, but new code has no reason to juggle strings.


Q: Why did my joined path lose its first half?
A: You joined with an absolute path on the right: Path('/a') / '/b' gives /b by design (like os.path.join). Strip the leading slash or check with .is_absolute() first.


## Mental model

os.path is giving directions as raw text ('turn left at the oak, then right'); pathlib is a GPS object that knows the route, the destination name, and can reroute itself. Both get you there, but only one can answer questions about the trip.
