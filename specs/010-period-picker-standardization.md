# 010 — Company-first period pickers & 2024 year floor

| | |
|---|---|
| **Status** | in progress |
| **Branch** | `feat/period-picker-standardization` |
| **Surface** | App-wide period filters & payroll-period DocType fields |

## Why?

Period pickers are inconsistent: some screens use **Year → Month → Company**, year ranges vary (`current±2`, hardcoded lists, Int `1950–2099`). HR needs **Company → Year → Month** and a fixed year floor of **2024**.

## What?

1. **Order:** **Company → Year → Month** on every payroll-period picker (extra filters after Month).
2. **Year range:** **2024 … current calendar year + 1** (inclusive).
3. **Hard lock:** Year **< 2024** cannot be selected or saved in scope.
4. **Existing DB rows** with year < 2024 **stay** in lists. Opening such a doc **clears Year**; user must pick 2024+ before save.
5. **No** Company `data_start_year` field.

## Decisions (grilling)

| # | Topic | Decision |
|---|--------|----------|
| 1 | Field order | Company → Year → Month |
| 2 | Scope | All period pickers (reports, pages, dialogs, payroll DocTypes) |
| 3 | Year start | Fixed **2024** |
| 4 | Year end | Current year **+ 1** |
| 5 | Pre-2024 on save | Hard lock |
| 6 | Pre-2024 in DB | Leave data; no purge |
| 7 | Open old doc | Clear Year; force 2024+ before save |

## How?

- Shared `saral_hr/public/js/period_picker.js` + `saral_hr/utils/period.py`
- `app_include_js` in `hooks.py`
- Reports: reorder filters; year options from helper
- Desk pages & Salary Slip dialogs: same
- DocTypes: Additional Salary/Deductions, Employee Salary Hold, Variable Pay Assignment — client + server validation

## Progress log

| Date | Note |
|------|------|
| 2026-08-18 | Spec written after grilling |
