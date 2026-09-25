---
skill_id: sys_python_error_handling
name: Python Error Handling
description: Exceptions done right: raising, catching, and designing error behavior.
risk: info
permissions: []
requires_confirmation: false
tags: [python, language]
version: 1.0.0
---
# Python Error Handling

## Purpose

Exceptions done right: raising, catching, and designing error behavior.

## Overview

Exceptions are Python's error-signaling mechanism: raise creates one, try/except catches it, and uncaught exceptions terminate with a traceback. Catch specific exception types, never bare except - bare except also swallows KeyboardInterrupt and SystemExit, making programs unkillable and hiding bugs. The try block should be small: wrap only the operation that can fail, so you know which line raised. else runs when no exception occurred (good for the 'success path'), finally runs always (good for cleanup, though with blocks are usually better). Raise with context: raise ValueError('port out of range') beats a bare raise, and raise ... from err chains exceptions so the original cause stays visible. Design your own exception hierarchy on stdlib bases - subclass Exception, group related errors under a common parent so callers can catch the group. Let unexpected exceptions propagate: catching everything and logging is how corrupted state becomes silent data loss. The EAFP style (easier to ask forgiveness than permission) - try the operation, handle the failure - fits Python's duck typing better than pre-checking every condition (LBYL). Assertions (assert) are for programmer errors and internal invariants, never for validating user input, since -O strips them.

## Quick reference

- try/except/else/finally: else = no exception, finally = always runs.

- Catch specific types; bare except swallows KeyboardInterrupt - avoid it.

- Keep try blocks small so the failing operation is obvious.

- raise X from err chains exceptions, preserving the original cause.

- Subclass Exception for custom errors; group related ones under a common parent.

- EAFP (try it) over LBYL (pre-check) for duck-typed code.

- assert is for internal invariants, not user input validation.


## Worked example

Specific catches, chaining, and a custom hierarchy:

```
class AppError(Exception):
    """Base for all application errors."""

class ConfigError(AppError):
    pass

def load_port(raw):
    try:
        port = int(raw)
    except ValueError as err:
        raise ConfigError(f'bad port value: {raw!r}') from err
    if not 1 <= port <= 65535:
        raise ConfigError(f'port out of range: {port}')
    return port
```

- int(raw) is the only fallible line inside try - precise catching.

- raise ... from err keeps the original ValueError visible in the traceback.

- Callers can catch AppError to handle every app-level failure at once.


## Common mistakes

- except Exception: pass - silently discarding every error.
  Fix: Log at minimum; better to catch narrowly and let the rest propagate.

- Raising strings or old-style exceptions instead of Exception subclasses.
  Fix: Always raise instances of Exception subclasses with helpful messages.


## Quick checks

Q: Why is bare `except:` considered harmful?
A: It catches everything including KeyboardInterrupt, SystemExit, and MemoryError. Programs become unkillable with Ctrl-C, and real bugs get silently swallowed. Catch the specific exception you can handle.


Q: EAFP vs LBYL - what is the practical difference?
A: LBYL checks first (if key in d), EAFP tries first (try: d[key] except KeyError). EAFP avoids race conditions between check and use and reads cleaner with duck typing; LBYL is fine when the check is cheap and clear.


## Mental model

Exceptions are a fire alarm system: raise pulls the alarm at the fire's location, except blocks are the fire doors that contain specific kinds of fire, and letting it propagate is letting the alarm reach the fire station. A bare except is stuffing a pillow over every alarm - quiet, and the building burns down unnoticed.
