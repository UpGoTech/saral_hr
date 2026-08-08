# 007 — Data Cleansing

| | |
|---|---|
| **Status** | in progress |
| **Branch** | `feat/data-cleansing` |
| **Surface** | Desk page `data-cleansing` |
| **Workspace** | Saral HR → card **Data Auditing and Cleansing** → link **Data Cleansing** |
| **Primary sources** | `Company Link`, `Attendance`, `Salary Slip` |

## Why?

While entering historical attendance and payroll, HR users often mark months that were never paid, leave partial months, or leave draft/cancelled slips behind. Ops need one employee-scoped screen to **see which months have attendance and/or salary slips**, flag extras, and **delete wrong rows** (day or whole month) without hunting list views.

## What?

Interactive Desk page **Data Cleansing**:

1. Select an employee (**Company Link**) and a **from month → to month** range.
2. Show a **month grid** of attendance coverage + salary slip presence/status.
3. Flag problem months (all flags below).
4. Drill into a month: list attendance days + slip link.
5. **Delete** wrong attendance (single days or whole month) and/or salary slips — with hard safety rules.
6. Log every cleanse action to **Data Cleansing Log**.

### Filters (v1)

| Filter | Type | Notes |
|--------|------|--------|
| Employee | Link → **Company Link** | Required |
| Scan mode | Toggle | **Period scan** (From–To) or **Whole data search** (default) |
| From (year + month) | Select / Date parts | Required only for Period scan |
| To (year + month) | Select / Date parts | Required only for Period scan; ≥ From |

**Whole data search** — lists every month that has any Attendance or Salary Slip for the employee (no date range). Use this to find mistaken orphans (e.g. only Mar-24 attendance) without guessing From–To.

**Period scan** — same as before: only months inside From–To that have data.

### Month grid rows

- **Period scan:** every calendar month in [From, To] that has any Attendance or any Salary Slip.
- **Whole data search:** every month with data across the employee’s entire history.
- Including months **outside tenure**. Months with neither attendance nor slip are omitted.

| Column | Definition |
|--------|------------|
| Month | `MMM YYYY` |
| Attendance days | Count of Attendance rows in month |
| Expected days | Calendar days overlapping employment in that month (`0` if fully outside tenure) |
| Coverage | Full / Partial / None / Outside tenure |
| Slip | Slip name(s) or — |
| Slip status | Draft / Submitted / Cancelled (multi if any odd case) |
| Flags | See below |
| Actions | View / Delete (role-gated) |

### Flags (all in v1)

| Flag | Meaning |
|------|---------|
| Attendance only | ≥1 attendance day, no slip of any status |
| Slip only | Slip exists (any status), 0 attendance rows |
| Outside tenure | Any attendance/slip date before joining or after left |
| Partial coverage | Inside tenure and `0 < days < expected` |
| Draft slip | At least one Draft slip for the month |

### Delete rules (locked)

**Roles**

| Role | View | Delete |
|------|------|--------|
| Saral HR User | Yes | No |
| Saral HR Manager | Yes | Yes |
| Administrator / System Manager | Yes | Yes |

**Attendance delete**

- Allowed for **selected days** or **whole month**.
- **Hard block** if **any** Salary Slip exists for that employee + month — Draft, Submitted, **or** Cancelled. Slip must be **absent** (deleted) first.
- After slips are gone, Manager may delete attendance freely from this screen.

**Salary Slip delete (from this screen, Manager+)**

- **Draft** / **Cancelled**: delete allowed.
- **Submitted**: cancel then delete (same screen flow; confirm). Cancelling uses standard slip `on_cancel` side effects.
- Purpose: clear the month so attendance can then be removed.

**Confirmations**

- Always confirm with counts (e.g. “Delete 31 attendance rows for Feb 2024 for &lt;employee&gt;?”).
- Slip cancel/delete confirms separately.

### Audit log — Data Cleansing Log (DocType)

Child/log DocType (or single DocType with rows) recording each cleanse:

| Field | Notes |
|-------|--------|
| timestamp | |
| user | |
| employee | Company Link |
| company | |
| month_start | |
| action | `delete_attendance` / `cancel_salary_slip` / `delete_salary_slip` |
| reference_names | JSON / Small Text of deleted/cancelled doc names |
| counts | e.g. attendance rows deleted |
| reason | Optional Text (prompt if easy; can be empty in v1) |

Only System Manager / Saral HR Manager need write via API; Users do not create logs manually.

### Out of scope (v1) — confirmed

v1 is **Attendance + Salary Slip** audit/delete only. Items below are deferred to **v2** (or a follow-on feature), not cancelled.

### Feature scope — v2 (planned)

Extend the same **Data Cleansing** surface (and **Data Cleansing Log**) with:

| # | Feature | Intent |
|---|---------|--------|
| V2.1 | **Additional Salary / Additional Deduction cleanup** | Per employee + month range: list AS/AD docs, flag orphans (e.g. no slip / outside tenure / wrong month), allow Manager+ cancel/delete with same role gate and logging |
| V2.2 | **SSA cleanup** | Surface Salary Structure Assignments that look wrong or unused for the selected employee/range (duplicates, gaps, assignments with no overlapping slips, outside tenure); Manager+ cancel/delete with hard rules TBD in a v2 grill |
| V2.3 | **Company-wide orphan scan** | Company (+ optional From–To) mode: all employees at once — rows flagged Attendance only / Slip only / Outside tenure / Draft slip / (v2) AS·AD·SSA orphans; drill into employee month detail; bulk actions still Manager+ only |
| V2.4 | **Period lock / freeze** | Separate later capability (may ship as its own spec under the Data Auditing and Cleansing card): lock a company month so attendance / slips / related docs cannot change without Admin unlock (+ optional password confirm). Complements cleansing — cleanse first, then freeze |

v2 reopen / grill before build: exact SSA delete rules, AS/AD interaction with submitted slips, and whether period lock is a tab on this page or a distinct page/DocType.

## Decisions

| # | Decision | Choice |
|---|----------|--------|
| 1 | Surface | Desk **Page** (interactive) |
| 2 | Filters | Employee (Company Link) + scan mode toggle + From–To for Period scan |
| 3 | Months shown | Period: months in range with data. **All:** every month with attendance or slip (default UI) |
| 4 | Flags | **All** five |
| 5 | Attendance vs slip | Hard block attendance delete until **no** slip remains (any docstatus) |
| 6 | Audit | DocType **Data Cleansing Log** |
| 7 | Workspace | New card **Data Auditing and Cleansing** → link **Data Cleansing** |
| 8 | v1 scope | Attendance + Salary Slip only; AS/AD, SSA, company-wide orphans, period lock → **v2** |
| 9 | Delete grain | Whole month **and** individual days |
| 10 | Delete roles | Administrator / Saral HR Manager only; HR User view-only |
| 11 | Scan modes | **Period scan** vs **Whole data search** (find orphans without knowing the month) |

## How?

### Backend

Page module `saral_hr/saral_hr/page/data_cleansing/`:

- `get_employee_month_matrix(employee, …, scan_mode=period|all)`
- `get_month_detail(employee, year, month)` — day list + slips
- `delete_attendance(employee, names | month)` — enforces slip-absent rule + role
- `cancel_salary_slip(name)` / `delete_salary_slip(name)` — role + write log
- Permission helper: Manager / Admin / System Manager for mutating APIs; User can call read APIs
- Whole-data discovery: distinct months from Attendance + Salary Slip (no range walk)

Tenure for Expected / Outside tenure uses Company Link `date_of_joining` / `left_date` (same spirit as Attendance Dashboard).

### Frontend

- Filters → load matrix
- Row click / View → drawer or panel with day checkboxes + slip actions
- Delete buttons hidden for Saral HR User

### Workspace

- Card break label: **Data Auditing and Cleansing**
- Link label: **Data Cleansing** → Page `data-cleansing`
- Visible to existing Saral HR workspace roles (User + Manager); delete gated in page/API

### Tests

- Matrix includes outside-tenure months that have data
- Whole data search finds months outside a narrow Period scan
- Flags compute correctly for fixtures
- Attendance delete blocked when Draft / Submitted / Cancelled slip exists
- Attendance delete succeeds after slip removed
- HR User cannot call delete APIs
- Manager delete writes Data Cleansing Log

## Phases

| Phase | Deliverable |
|-------|-------------|
| 0 | Spec + workspace card/link + page stub |
| 1 | Read-only matrix + flags + month detail |
| 2 | Slip cancel/delete from screen + log |
| 3 | Attendance day/month delete (slip-absent gate) + log |
| 4 | Unit tests + polish |
| **v2** | AS/AD cleanup · SSA cleanup · company-wide orphan scan · period lock/freeze (grill + possibly split specs) |

## Progress

| Item | Status |
|------|--------|
| Spec drafted | done |
| v2 scope documented | done |
| Workspace card + link | done (phase 0) |
| Page stub | done (phase 0) |
| Matrix API + UI | done |
| Delete APIs + log DocType | done |
| Tests | done (10) |
| v2 features | planned (not started) |
