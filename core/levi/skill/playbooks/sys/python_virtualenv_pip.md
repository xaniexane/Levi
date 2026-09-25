---
skill_id: sys_python_virtualenv_pip
name: Python Virtual Environments and pip
description: Isolated environments, dependency pinning, and reproducible installs.
risk: info
permissions: []
requires_confirmation: false
tags: [python, tooling]
version: 1.0.0
---
# Python Virtual Environments and pip

## Purpose

Isolated environments, dependency pinning, and reproducible installs.

## Overview

A virtual environment is an isolated Python installation: its own interpreter link, its own site-packages, and no visibility into other projects' packages. Create with python -m venv .venv, activate with source .venv/bin/activate (or .venv\Scripts\activate on Windows), and the python and pip on PATH become the environment's. Always use one per project: it ends 'works on my machine' version conflicts and keeps the system Python pristine. pip installs from PyPI; pip install -r requirements.txt reproduces a known set. Pin versions for reproducibility (pkg==1.2.3) and regenerate the pin file with pip freeze after verifying things work - unpinned installs drift over time as new releases land. pip install -e . installs your own project editable so imports pick up live source during development. Never pip install with sudo into the system Python: it fights the OS package manager and breaks on upgrades. Modern projects declare metadata in pyproject.toml (PEP 517/518); setup.py is legacy. For locked, repeatable environments, tools like pip-tools or uv compile loose requirements into exact pins. Keep the venv directory out of version control and out of zip artifacts - it is disposable by design and rebuilt from the requirements file.

## Quick reference

- python -m venv .venv: create. source .venv/bin/activate: activate.

- One venv per project; never install into system Python with sudo.

- pip install -r requirements.txt: reproduce. pip freeze: snapshot pins.

- Pin with == for reproducibility; loose pins drift as releases land.

- pip install -e .: editable install of your own project for development.

- pyproject.toml is the modern metadata file; setup.py is legacy.

- Never commit the .venv directory; rebuild it from requirements.


## Worked example

Standard venv workflow:

```
$ python -m venv .venv
$ source .venv/bin/activate
(.venv) $ python -m pip install --upgrade pip
(.venv) $ pip install requests==2.31.0
(.venv) $ pip freeze > requirements.txt
(.venv) $ cat requirements.txt
requests==2.31.0
(.venv) $ deactivate
```

- python -m pip guarantees pip matches the active interpreter.

- requirements.txt is the rebuild recipe; the venv itself is disposable.

- deactivate restores the previous PATH and prompt.


## Common mistakes

- Committing .venv to git: thousands of files, platform-specific binaries.
  Fix: Add .venv to .gitignore; document the rebuild steps instead.

- sudo pip install: fights the OS package manager, breaks on upgrades.
  Fix: Use a venv, or pip install --user as a weaker fallback.


## Quick checks

Q: Why not just pip install everything globally?
A: Global installs create one shared namespace where projects fight over versions - project A needs requests 2.x, project B needs 3.x. Venvs give each project its own sandbox; the system Python stays clean for the OS.


Q: requirements.txt vs pyproject.toml - which do I need?
A: Both, different jobs: pyproject.toml declares your project's abstract dependencies (>= style); requirements.txt (or a lock file) pins the exact versions for a reproducible deploy.


## Mental model

A venv is a separate lunchbox per project. Without it, every project's sandwiches pile into one communal fridge and someone's tuna (version 3.x) ruins your peanut butter (version 2.x). Each lunchbox keeps flavors - and dependencies - from mixing.
