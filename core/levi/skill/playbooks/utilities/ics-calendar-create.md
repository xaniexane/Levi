---
skill_id: utility.ics_calendar_create
name: ICS Calendar Create
description: Build an .ics calendar file for an event using only the standard library.
risk: moderate
permissions: []
requires_confirmation: true
tags: [calendar, ics, events]
version: 1.0.0
---

# ICS Calendar Create

ICS Calendar Create assembles a VCALENDAR file by hand - the format is plain text, so no third-party package is needed - with your event's title, start, end, and description, written to a new .ics file.

## When to use

- Creating a calendar invite file to share.
- Generating events from a schedule programmatically.
- Exporting a date for import into any calendar app.

## Steps

1. Gather the event: title, start and end (with timezone), location, description.
2. Format timestamps as UTC (YYYYMMDDTHHMMSSZ), escaping commas and semicolons in text fields.
3. Assemble the VCALENDAR/VEVENT text with a fresh UID per event.
4. Write the .ics file.
5. Validate by importing it into a calendar app and confirming the time is right.

## Honest limits

- Standard library only - ICS is text, and honesty prefers text over a dependency.
- Times are written in UTC; double-check the conversion from your local time.
- Recurring rules are kept simple (or omitted) - complex RRULEs deserve a dedicated library.

Original work authored for LEVI - utilities pack.
