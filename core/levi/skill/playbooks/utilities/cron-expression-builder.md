---
skill_id: utility.cron_expression_builder
name: Cron Expression Builder
description: Build a correct 5-field cron expression from a plain-language schedule.
risk: info
permissions: []
requires_confirmation: false
tags: [cron, schedule, time]
version: 1.0.0
---

# Cron Expression Builder

Cron Expression Builder turns a schedule you describe in words - 'every weekday at 8:30am' - into a valid 5-field cron expression, explaining what each field means. It displays the expression; installing it is separate.

## When to use

- Scheduling a backup every night at 2am.
- Running a report on the first of each month.
- Sanity-checking a cron line someone else wrote.

## Steps

1. State the schedule in plain words: how often, at what time, on which days.
2. Map it to minute, hour, day-of-month, month, day-of-week fields.
3. Display the expression with each field labeled and a plain-language re-read.
4. Verify with a quick mental dry-run of the next two fire times.

## Honest limits

- Display only - nothing is installed into any crontab by this skill.
- Cron runs in the system's timezone; say which one you assumed.
- Day-of-month and day-of-week together mean OR in most crons - a classic trap, flagged every time.

Original work authored for LEVI - utilities pack.
