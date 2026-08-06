# 004 — Monthly Salary Register (Old Format) Net Payable

| | |
|---|---|
| **Status** | planned |
| **Branch** | `feat/monthly-salary-register` (proposed) |
| **Surface** | New Frappe Script Report (+ PDF & Excel export) |
| **Primary sources** | Salary Slip (submitted), Salary Structure Assignment, Company Link, Employee |
| **Sample** | [specs/refs/monthly-salary-register-sample.png](./refs/monthly-salary-register-sample.png) |

## Why?

Payroll ops still use a wide “Employee Salary Sheet” (one row per employee) with bank details, attendance letter-codes, ACTUAL (SSA) vs EARNING (slip), deductions, and Net Payable — in both PDF and Excel. Saral has individual payslips (`Salary Slip Custom`) and a different `Salary Summary` report; neither matches this **old-format register**. Need a **new** report that reproduces it.

## What?

New report: **Monthly Salary Register (Old Format) Net Payable**

- One row per employee for a selected company + month
- PDF + Excel with the same column model, color bands, totals row, and signature block
- Does **not** replace Salary Slip print or Salary Summary

### Filters

| Filter | Required | Notes |
|--------|----------|--------|
| Company | yes | Single company |
| Year | yes | |
| Month | yes | |
| Population | yes | `All` / `Staff` / `Worker` / `Consultant` (maps to Company Link `category`) |

### Inclusion rules

- Only **submitted** Salary Slips (`docstatus = 1`) for that company + month
- Population filter applied via Company Link category (All = no category filter)
- Sort: employee name ascending (SR. NO. assigned after sort)
- Employees on salary hold with no submitted slip: **excluded** (no row)

### Report header

```
{Company Name} - Employee Salary Sheet
For the Period {dd-MMM-yyyy} to {dd-MMM-yyyy}
Month Days: {calendar days in month}
```

### Column layout

Grouped sections (left → right). Component money columns are **dynamic** (see Component rules).

#### 1. Identity

| Column | Source |
|--------|--------|
| SR. NO. | Row index (1-based) |
| Full Name Of The Employee | Salary Slip `employee_name` / Company Link `full_name` |
| BANK | Employee `bank_name` |
| IFSC | Employee `ifsc_code` |
| BANK ACCOUNT NO | Employee `account_number` |

#### 2. Days

| Column | Source |
|--------|--------|
| TOTAL MONTH DAY | Calendar days in month (same for all rows) |
| P | `present_days` |
| R | `weekly_offs_taken` |
| H | `holidays_taken` |
| C | `total_casual_leaves` |
| T | `total_on_tour` |
| Y | `total_comp_off` |
| OD | **blank** (On Duty not in Attendance/Slip yet) |
| E | `total_earned_leaves` |
| I | **blank** (ESIC Leave not in Attendance/Slip yet) |
| A | `absent_days` only (do **not** add LWP) |
| TOTAL PAID DAYS | `payment_days` |

**Explicitly ignored on this register (not shown, not folded into P):**

- Half Day (`total_half_days`)
- Earned Comp Off (`total_earned_comp_off`)
- LWP (`total_lwp`) — not in A

When OD / ESIC Leave statuses are added to the product later, wire them into OD / I without changing the column letters.

#### 3. ACTUAL (orange header band)

Full-month structure amounts from the **Salary Structure Assignment** active for the slip period (same SSA resolution used elsewhere on the slip):

- One column per **earning** component present on any included employee’s SSA for the month (union of SSA earning components across the cohort)
- Values: SSA amount for that component (0 / blank if employee’s SSA lacks it)
- **Total Gross** (yellow highlight): sum of ACTUAL component amounts on the row

No slip-only extras (e.g. Incentive from Additional Salary) appear under ACTUAL.

#### 4. ERANING / Earning (green header band; label may keep legacy “ERANING” or spell “Earning” — prefer **Earning** in UI, match sample visually)

- Columns for the **union of**:
  - ACTUAL/SSA earning component set, **plus**
  - Any extra earning components that appear on submitted slips that month (e.g. INCENTIVE) but not on SSA
- Values: Salary Slip earnings row amounts (computed / prorated)
- **Total Earning** (yellow): slip `total_earnings` (or sum of shown earning columns — must match slip net math; prefer slip totals fields for Total Earning / Total Deductions / Net)

#### 5. DEDUCTION (red header band)

- Dynamic columns: union of **employee-share** deduction components across slips that month (exclude employer-contribution components)
- Typical examples from sample: PF, ESIC, PT, I-Tax, Loan — but **not hardcoded**; whatever appears
- **Total Deductions** (yellow optional / bold): slip `total_deductions` (employee share)

#### 6. Net

| Column | Source |
|--------|--------|
| Net payable (yellow) | Slip `net_salary` |

### Totals row

Footer row summing all numeric columns (days + money). Identity/bank columns blank or label **Total**.

### Signatures (PDF + Excel)

Same pattern as Salary Summary:

- Prepared By · Checked By · Authorised Signatory

### Visual rules (PDF + Excel)

| Band | Color intent |
|------|----------------|
| ACTUAL header | Orange / amber |
| Earning header | Green |
| Deduction header | Red |
| Total Gross / Total Earning / Net payable cells | Yellow highlight |
| Layout | Landscape **A4** (expect small font / fit-to-width; wide register) |

Excel: apply fill colors on header bands and highlight columns; freeze panes on identity columns if practical.

### Outputs

| Format | How |
|--------|-----|
| Desk grid | Script Report list view |
| PDF | Custom HTML → `get_pdf` (landscape A4), download action on report |
| Excel | `.xlsx` with same columns, colors, totals, signatures |

Reuse patterns from `salary_summary` PDF helpers where practical; keep this report’s HTML/XLSX layout independent so Salary Summary stays untouched.

## How? (implementation sketch)

1. New Script Report under Saral HR: `Monthly Salary Register (Old Format) Net Payable`
2. `execute(filters)` → columns + data for Desk
3. Whitelisted export methods (or report-js buttons) for PDF / Excel
4. Data pipeline per month:
   - Load submitted slips for company + date range
   - Join Company Link (category filter) + Employee (bank fields)
   - Resolve SSA per employee; collect ACTUAL amounts
   - Pivot slip earnings / deductions into dynamic column sets
5. Unit tests: inclusion (submitted only, category filter), day-code mapping, ACTUAL vs Earning column split, totals, blank OD/I

### Tracer bullet

Company + one past month with ≥2 submitted Staff slips → Desk rows → PDF download → Excel download; spot-check Net payable vs slip.

## Out of scope

- Changing Attendance statuses (On Duty / ESIC Leave)
- Changing Salary Slip calculation
- Replacing Salary Slip Custom payslip or Salary Summary
- Multi-company in one run
- Draft slips
- Folding Half Day / ECO / LWP into day codes

## Acceptance

1. Report appears as **Monthly Salary Register (Old Format) Net Payable**
2. Filters: Company, Year, Month, Population (All/Staff/Worker/Consultant)
3. Only submitted slips; one row per slip/employee
4. Day columns match mapping above; OD & I blank; HD/ECO/LWP not shown
5. ACTUAL from SSA only; Earning = SSA comps + slip-only extras; Deductions dynamic employee-share
6. Net payable = slip net; totals row correct
7. PDF (A4 landscape) and Excel both export with color bands + signatures
8. Existing Salary Summary / payslip unchanged

## Decisions log (grilling)

| Topic | Decision |
|-------|----------|
| Shape | New report; 1 row / employee |
| vs existing | Do not replace Slip print / Salary Summary |
| Filters | Company + Year + Month + Population |
| Population | All / Staff / Worker / Consultant |
| Slips | Submitted only |
| Paid days | `payment_days` |
| ACTUAL | SSA full-month |
| Earning | Slip computed |
| Components | Dynamic (union for month) |
| ACTUAL vs Earning align | B — ACTUAL SSA-only; Earning SSA + slip extras |
| Y | Comp Off |
| OD | On Duty → blank until available |
| I | ESIC Leave → blank until available |
| A | `absent_days` only |
| Half Day / ECO | Ignored (not on register) |
| PDF | A4 landscape |
| Excel | Same columns + totals |
| Colors | PDF + Excel |
| Signatures | Yes |
| Name | Monthly Salary Register (Old Format) Net Payable |

## Progress log

| Date | Note |
|------|------|
| 2026-08-06 | Grilled from sample screenshot; spec written (planned) |
