---
skill_id: sys_python_datetime
name: Python datetime Handling
description: Dates, times, timezones, and the rules that prevent time bugs.
risk: info
permissions: []
requires_confirmation: false
tags: [python, stdlib]
version: 1.0.0
---
# Python datetime Handling

## Purpose

Dates, times, timezones, and the rules that prevent time bugs.

## Overview

datetime covers dates, times, and their arithmetic. datetime.now() returns local time; datetime.now(timezone.utc) returns an aware UTC time - prefer aware datetimes everywhere, because naive datetimes (no tzinfo) compare and convert ambiguously. The iron rule: store and compute in UTC, convert to local only for display. timedelta does date arithmetic (now + timedelta(days=7)); subtracting two aware datetimes gives a timedelta. Parsing: datetime.fromisoformat handles ISO 8601 strings; strptime parses custom formats with %Y %m %d directives. Formatting: strftime for display, isoformat() for interchange. time.monotonic() is for measuring durations (immune to clock adjustments); time.time() is wall-clock for timestamps. zoneinfo (3.9+) provides IANA timezones without third-party packages. Classic traps: daylight-saving transitions making local times ambiguous or nonexistent (another reason for UTC internally), comparing naive with aware (TypeError), and assuming timedelta.days holds the whole story (use total_seconds()). For calendrical math beyond timedeltas - month arithmetic - dateutil is the usual external answer.

## Quick reference

- Aware > naive: datetime.now(timezone.utc); never mix the two.

- Store and compute in UTC; convert to local only for display.

- timedelta for arithmetic; total_seconds() for the full magnitude.

- fromisoformat / strptime for parsing; isoformat() for interchange.

- time.monotonic() for durations; time.time() for wall-clock timestamps.

- zoneinfo: IANA timezones from the stdlib (3.9+).


## Worked example

UTC internally, local only for display:

```
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

now_utc = datetime.now(timezone.utc)
deadline = now_utc + timedelta(days=7)

local = deadline.astimezone(ZoneInfo('America/Chicago'))
print('store:', now_utc.isoformat())
print('show :', local.strftime('%Y-%m-%d %H:%M %Z'))

start = __import__('time').monotonic()
sum(range(10**6))
print('took', __import__('time').monotonic() - start)
```

- now(timezone.utc) is aware; arithmetic and comparison are safe.

- astimezone converts for display without touching stored UTC.

- monotonic() measures elapsed time immune to NTP clock jumps.


## Common mistakes

- datetime.now() (naive local) stored and later compared across zones.
  Fix: Use datetime.now(timezone.utc) and keep everything aware.

- Using time.time() to measure durations across a clock adjustment.
  Fix: Durations need time.monotonic(); wall clock is for timestamps.


## Quick checks

Q: Why did comparing two datetimes raise TypeError?
A: One was naive, the other aware. Python refuses the comparison rather than guess. Make both aware (usually UTC) before comparing.


Q: Should I store local time or UTC in my database?
A: UTC, always. Local times hit DST ambiguities and make ordering across zones painful. Convert to the viewer's zone at render time.


## Mental model

Naive datetimes are wall clocks with no city label - '3 PM' means nothing without knowing where. Aware UTC datetimes are timestamps on a single world clock; converting for display is just reading that clock in the local language.
