---
skill_id: utility.timestamp_converter
name: Timestamp Converter
description: Convert between Unix epoch seconds and human-readable ISO timestamps, timezone-aware.
risk: info
permissions: []
requires_confirmation: false
tags: [time, timestamp, convert]
version: 1.0.0
---

# Timestamp Converter

Timestamp Converter translates Unix epoch values to ISO-8601 datetimes and back, always stating the timezone. Naive inputs are treated as UTC and labeled as such.

## When to use

- Reading an epoch timestamp from a log.
- Converting a deadline to epoch for an API.
- Untangling timezone confusion in event data.

## Steps

1. Take the input: epoch seconds (int or float) or an ISO string.
2. Convert with datetime, attaching timezone.utc explicitly - never naive math.
3. Display both forms plus the UTC offset used.
4. For ISO inputs with offsets, normalize to UTC and show the original offset too.

## Honest limits

- Standard library only (datetime).
- Naive datetimes are assumed UTC and the assumption is stated, not hidden.
- Leap seconds and sub-second precision: stated to the precision the input carries.

Original work authored for LEVI - utilities pack.
