---
skill_id: sys_python_modules_packages
name: Python Modules and Packages
description: How imports work, package layout, and the import system underneath.
risk: info
permissions: []
requires_confirmation: false
tags: [python, language]
version: 1.0.0
---
# Python Modules and Packages

## Purpose

How imports work, package layout, and the import system underneath.

## Overview

A module is a .py file; a package is a directory of modules (with or without __init__.py since namespace packages in 3.3). import loads a module once, executes its top-level code, and caches it in sys.modules - later imports reuse the cached object, which is why import-time side effects happen exactly once. from x import y binds y directly; import x.y binds the top package name. Absolute imports (from pkg import mod) beat relative ones (from . import mod) for readability everywhere except inside large packages. The import search order: sys.modules cache, then finders over sys.path (script directory, PYTHONPATH, stdlib, site-packages). Circular imports - a imports b imports a - fail because the partially-initialized module lacks the names the other wants; fix by restructuring, deferring the import into a function, or importing the module instead of names from it. __name__ == '__main__' guards script behavior so a file works both imported and executed. Keep modules cohesive and small; a package's __init__.py should re-export the public API, not implement it. Avoid import * - it pollutes the namespace and breaks linters' ability to track names. For slow or optional dependencies, import inside the function that needs them so startup stays fast.

## Quick reference

- Module = .py file. Package = directory of modules.

- import executes the module once and caches it in sys.modules.

- Search order: sys.modules, then sys.path (script dir, PYTHONPATH, stdlib, site-packages).

- Circular imports: restructure, defer into functions, or import modules not names.

- if __name__ == '__main__': makes a file both importable and runnable.

- Avoid `from x import *`; re-export public API from __init__.py instead.


## Worked example

Package layout and the main guard:

```
# mypkg/__init__.py
from mypkg.core import run  # re-export the public API

# mypkg/core.py
def run(argv):
    print('running with', argv)
    return 0

def main():
    import sys
    raise SystemExit(run(sys.argv[1:]))

if __name__ == '__main__':
    main()
```

- __init__.py re-exports so users write from mypkg import run.

- Heavy imports deferred into main() keep import time fast.

- The __main__ guard lets python -m mypkg.core run it as a script.


## Common mistakes

- Naming your script the same as a stdlib module (email.py, random.py).
  Fix: It shadows the stdlib on sys.path and breaks unrelated imports. Rename it.

- Import-time heavy work (network calls, big loads) at module top level.
  Fix: Defer into functions; imports should be cheap and side-effect free.


## Quick checks

Q: Why does my import work in one directory but not another?
A: The script's directory (or cwd for -c/interactive) leads sys.path. Running from a different directory changes what is importable. Fix with a proper package install (pip install -e .) or PYTHONPATH, not sys.path hacks.


Q: How do I break a circular import?
A: Restructure so the shared code moves to a third module both can import. Quick relief: move one import inside the function that needs it, or import the module object and access attributes lazily.


## Mental model

Modules are books, packages are bookshelves. import is pulling a book off the shelf and reading it once, then keeping it open on your desk (sys.modules) - grabbing it again just reuses the open copy. A circular import is two books that each say 'see the other book first'.
