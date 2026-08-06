# 003 — Attendance Dashboard yearly headcount & marking coverage

| | |
|---|---|
| **Status** | in progress |
| **Branch** | `feat/attendance-dashboard-yearly` |
| **Surface** | Desk page `attendance-dashboard` (Yearly tab only) |
| **Primary sources** | `Company Link`, `Attendance` |

## Why?

Yearly view today rolls up status person-days (`Present`, `On Leave`, `Half Day`, `Absent`, `Holidays`, `Attendance %`). That is the wrong report. Ops need month-wise **headcount movement** plus **whether every calendar day has an Attendance row** (including pre-join / post-left Absents).

## What?

Replace the Yearly table and summary cards. Daily / Monthly tabs unchanged.

### Yearly table columns (final)

| # | Column | Definition |
|---|---|---|
| 1 | **Month** | Past completed months of selected year only |
| 2 | **Opening** | Closing headcount of **previous calendar month** (Jan → Dec of prior year) |
| 3 | **Joined** | `Company Link` with `date_of_joining` in the month |
| 4 | **Left** | `Company Link` with `left_date` in the month |
| 5 | **Closing** | `Opening + Joined − Left` |
| 6 | **Total strength** | `Opening + Joined` (everyone on rolls at any point in the month) |
| 7 | **Attendance marked** | Count of strength employees with Attendance for **every calendar day** of the month |
| 8 | **Attendance not marked** | Count of strength employees missing **≥ 1** calendar day |

Invariants:

- `Marked + Not marked = Total strength`
- `Opening + Joined − Left = Closing`
- Status of a day does **not** matter for marked; **row existence** does (Absent before join / after left still = marked)

### Rows shown

- Render **only fully completed past months** of the selected year
- If selected year is current year: Jan … previous month only
- If selected year is future: empty table
- If selected year is past: all 12 months

### Summary cards (yearly)

Replace status rollups with year aggregates over **shown** months:

| Card | Value |
|---|---|
| Joined | sum(Joined) |
| Left | sum(Left) |
| Avg Closing | mean(Closing) |
| Marked coverage % | `sum(Marked) / sum(Total strength) × 100` (0 if strength 0) |

### Filters

- Existing **Company**, **Year**, **Department** apply to all columns
- Employee user-permissions (same as today) apply

### Drill-downs (all counts clickable)

| Click | List content |
|---|---|
| Opening / Joined / Left / Closing | Employee name, department, designation |
| **Attendance marked** | Name, department, designation only |
| **Attendance not marked** | Name, department, designation + **missing day count** + **missing dates** + action/link to **Mark Attendance** |

### Dropped from yearly

- Present / On Leave / Half Day / Absent-LWP / Holidays / Attendance %
- Average attendance / Attendance strength
- Holidays column

## How?

### Backend

New whitelisted APIs on `attendance_dashboard.py`:

- `get_yearly_summary(company, year, department=None)` — single call for all past months
- `get_yearly_employee_list(company, year, month, list_type, department=None)` — drill-down

Per included month:

1. **Opening** = Closing of prior month (always previous Closing; Jan uses Dec of `year-1`)
2. **Joined / Left** = count `Company Link` by `date_of_joining` / `left_date` in range (+ dept + permissions)
3. **Closing** = Opening + Joined − Left
4. **Strength pool** = Opening set ∪ Joined set
5. Marked = distinct attendance dates for month == calendar days in month

Closing / Opening sets use tenure dates (not only `is_active`):

- On rolls at month end: `date_of_joining <= month_end` AND (`left_date` is null OR `left_date > month_end`)

### Frontend

- Rewrite `loadYearly` / `renderYearly` to call `get_yearly_summary` once
- New columns + cards; click → drawer lists
- Not marked: missing dates + Mark Attendance CTA (`/app/mark-attendance`)

### Tests

Unit/integration tests for:

- Opening(Jan Y) = Closing(Dec Y−1)
- Marked + Not marked = Strength; Opening + Joined − Left = Closing
- One missing day → Not marked
- Absent on all days still Marked
- Current month excluded from rows
- Department filter scopes pool and counts

## Out of scope

- Daily / Monthly tab redesign
- Changing Mark Attendance outside-tenure Absent logic
- Changing Overview headcount formulas
- Export / PDF

## Acceptance

1. Yearly columns match the table above; old status columns gone
2. Jan opening comes from prior December closing
3. Past months only; current/future months absent
4. Marked/Not marked based on full calendar-day row coverage
5. All six counts open employee lists; Not marked has missing dates + Mark Attendance link
6. Department filter works; cards show Joined / Left / Avg Closing / Marked coverage %

## Progress log

| Date | Note |
|------|------|
| 2026-08-06 | Spec grilled and written |
| 2026-08-06 | Implemented yearly API + UI; unit tests passing |
