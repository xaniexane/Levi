---
skill_id: sys_python_logging
name: Python Logging
description: The logging module: levels, handlers, and production-grade log hygiene.
risk: info
permissions: []
requires_confirmation: false
tags: [python, stdlib]
version: 1.0.0
---
# Python Logging

## Purpose

The logging module: levels, handlers, and production-grade log hygiene.

## Overview

logging replaces print for anything that matters. Loggers form a hierarchy (logging.getLogger(__name__)); levels rank severity - DEBUG, INFO, WARNING, ERROR, CRITICAL - and a logger emits records at or above its level. Handlers decide where records go (stderr, files, syslog); formatters decide their shape; filters add routing logic. Configure once at program start with logging.basicConfig or dictConfig - libraries should never configure, only log. Use lazy %-style formatting (log.info('user %s', name)): the string builds only if the level passes, unlike f-strings which always pay. Log exceptions with log.exception inside except blocks for automatic tracebacks. Structured logging (key=value or JSON records) makes logs machine-queryable; include request IDs to trace work across components. Hygiene rules: INFO for normal operations, WARNING for degraded-but-working, ERROR for failed operations; never log secrets, tokens, or full PII; keep DEBUG out of production by default but make it one flag away. Rotate files with RotatingFileHandler so disks do not fill. Good logs are a flight recorder - boring until the one day they save you.

## Quick reference

- Levels: DEBUG < INFO < WARNING < ERROR < CRITICAL.

- Logger hierarchy via getLogger(__name__); configure once at startup.

- Handlers: destinations. Formatters: shape. Filters: routing.

- Lazy formatting: log.info('x=%s', x) - builds only if emitted.

- log.exception in except blocks: message + traceback.

- Never log secrets/tokens/PII. Rotate files with RotatingFileHandler.


## Worked example

One-time config and proper call sites:

```
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(name)s %(levelname)s %(message)s',
)
log = logging.getLogger(__name__)

def process(user_id, items):
    log.info('processing %d items for user %s', len(items), user_id)
    try:
        return [transform(i) for i in items]
    except Exception:
        log.exception('transform failed for user %s', user_id)
        raise
```

- basicConfig once at startup; libraries only get loggers.

- %-style args defer string building until the level check passes.

- log.exception captures the traceback; bare log.error would not.


## Common mistakes

- f-string in every log call: pays formatting cost even when disabled.
  Fix: Use lazy %-args; the message builds only if the level emits.

- Logging passwords/tokens 'for debugging' and shipping it.
  Fix: Redact secrets at the call site; treat logs as semi-public.


## Quick checks

Q: print vs logging - when does it actually matter?
A: When output must be leveled, routed, or kept: production services, libraries, anything debugged after the fact. print is fine for throwaway scripts and user-facing CLI output.


Q: Why do my library's logs never appear?
A: Libraries must not configure logging - only the application calls basicConfig/dictConfig. If nobody configures, records go to the last-resort handler (stderr, WARNING+).


## Mental model

logging is a ship's logbook with ranked entries: the captain (configuration) decides what severity gets ink and which books it goes in. print is shouting over the rail - fine in calm seas, useless when you need to reconstruct the storm a week later.
