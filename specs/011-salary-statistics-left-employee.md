# 011 — Salary statistics for left employees

| | |
|---|---|
| **Status** | ready for review |
| **Branch** | `fix/salary-statistics-left-employee` |
| **Surface** | Salary Statistics desk page |

## Problem

Leaving a company sets Company Link `is_active` to 0. Salary Statistics loads employees with `is_active = 1` only. A leaver opened from Employee Profile still gets a detail page, but the month list is built from that active-only query, so every month says "Not processed" even when submitted Salary Slips exist.

Example: HR-EMP-00017 (Jitesh N Bokade), Fabrixcel Private Limited, left 2025-07-27. Submitted slips run October 2024 through July 2025. The page opens on the current year, which has no slips, and switching to 2025 still shows a blank month list.

## What?

1. The company **Active Employees** list stays active-only.
2. The detail view (profile deep link and year switcher) includes the employee being viewed even when inactive, with their submitted slip nets.
3. On first open, if that inactive employee has no slips in the selected year, the page moves once to the year of their latest submitted slip. Changing the year afterwards does not jump back.
4. Month detail already reads Salary Slip without an active check. That stays.

## How?

- `get_employees_for_company(..., employee=None)`: when `employee` is set, also return that Company Link if it belongs to the company (and to the user's employee permission, when restricted).
- If that person is inactive and the requested year has no submitted slips, set `latest_slip_year` on their row.
- Detail page passes `employee` into the company query. Initial load follows `latest_slip_year` once. The search list does not pass `employee`.

## Progress log

| Date | Note |
|------|------|
| 2026-09-27 | Spec written. Detail query includes one inactive employee; page opens on their latest slip year. |
