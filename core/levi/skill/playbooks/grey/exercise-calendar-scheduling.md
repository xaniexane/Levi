---
skill_id: grey_exercise_calendar_scheduling
name: Exercise Calendar and Scheduling
description: Schedule the exercise: phases, windows, blackouts, and stakeholder notifications.
risk: low
permissions: []
requires_confirmation: false
tags: [grey-team, setup, scheduling]
version: 1.0.0
team: grey
---
# Exercise Calendar and Scheduling

## Purpose

Exercises need calendars: phase windows, blackout periods, maintenance conflicts, and
stakeholder notifications. This scheduling deconflicts the exercise with reality before
it collides.

## When to use

- During exercise planning.
- When phases have hard time constraints.

## Prerequisites

- Exercise phase plan with durations.
- Organizational calendar (change freezes, holidays, maintenance).
- Stakeholder notification list.

## Procedure

1. Map phases to calendar windows with buffers between them.
2. Deconflict: change freezes, business peaks, maintenance windows, other exercises.
3. Define blackout periods (no exercise traffic) and quiet hours.
4. Notify stakeholders: system owners, SOC, helpdesk, leadership — with the exercise
   codename and contacts.
5. Publish the master schedule; establish the change process for slips.
6. Confirm the schedule at the final planning sync.

## Expected outputs

- Master exercise schedule.
- Deconfliction record.
- Stakeholder-notification log.

## Pitfalls

- Undeconflicted exercises colliding with change freezes — check the calendar.
- Stakeholders learning about the exercise from an alert — notify first.
- No buffers between phases — schedules slip, buffers absorb.

## References

- Exercise-management literature.

## Exercise role

The calendar is where the exercise meets reality — deconflicted before it starts, or
reality deconflicts it for you.

> **Exercise guard.** This is range-operations material for the grey team (exercise infrastructure). It builds, scores, observes, resets, or snapshots exercise environments. Destructive operations require confirmation. Invoking this skill only reads this playbook.
