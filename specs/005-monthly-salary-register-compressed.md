# 005 — Monthly Salary Register Compressed format

| | |
|---|---|
| **Status** | in progress |
| **Branch** | `feat/monthly-salary-register-compressed` |
| **Depends on** | [004 — Monthly Salary Register Old Format](./004-monthly-salary-register.md) |
| **Surface** | Extend existing Script Report **Monthly Salary Register Old Format Net Payable** |
| **Primary sources** | Same as 004 (submitted Salary Slip, SSA, Employee bank) |

## Why?

The full old-format register is too wide for everyday review/print. Need a **compressed** view of the same month’s payables with fewer columns, without losing the full layout when ops need component-level detail.

## What?

Add a **Format** filter to the existing report:

| Value | Behavior |
|-------|----------|
| `Full` | Current 004 layout (identity + day codes + dynamic ACTUAL/Earning/Deduction comps + net) |
| `Compressed` | Fixed 10-column layout below |

Filters otherwise unchanged: Company, Year, Month, Population (All/Staff/Worker/Consultant). Inclusion rules same as 004 (submitted slips only, sort by name, exclude holds with no slip).

### Compressed columns (exact)

| # | Column | Source |
|---|--------|--------|
| 1 | SR. NO. | Row index (1-based) |
| 2 | Full Name | Slip `employee_name` / Company Link `full_name` |
| 3 | IFSC Code | Employee `ifsc_code` |
| 4 | Account Number | Employee `account_number` |
| 5 | Days in Month | Calendar days in month |
| 6 | Paid For Days | Slip `payment_days` |
| 7 | Actual Gross | Sum of SSA earning amounts (same as Full **Total Gross**) |
| 8 | Earning Gross | Slip `total_earnings` (same as Full **Total Earning**) |
| 9 | Deductions | Slip `total_deductions` (employee-share total) |
| 10 | Net Payable | Slip `net_salary` |

**Dropped vs Full in Compressed:**

- BANK name
- All day letter-codes (P / R / H / C / T / Y / OD / E / I / A)
- All per-component ACTUAL / Earning / Deduction columns

### Header / footer / exports

- Header same idea as Full (`Employee Salary Sheet` + period + Month Days)
- Totals row: sum numeric money/day columns; identity blank or “Total”
- Signatures: Prepared / Checked / Authorised (same as Full)
- PDF: A4 landscape; Excel: same columns as Desk for the selected format
- Highlight Net Payable (and optionally Actual Gross / Earning Gross) in yellow — match Full highlight spirit
- No ACTUAL/Earning/Deduction color **component bands** in Compressed (no component blocks)

### Desk / PDF / Excel

All three use the Compressed column model when Format = Compressed. Full exports unchanged when Format = Full.

### Default Format

**Full** (preserve existing behaviour for current users).

## How? (implementation sketch)

1. Add `format` filter: `Full` \| `Compressed` (default `Full`)
2. Reuse `build_register` data pipeline; when Compressed, project each row to the 10 fields above (skip building dynamic component columns)
3. PDF/Excel builders branch on format (or share a slim table renderer for Compressed)
4. Tests: Compressed column count/labels; Actual Gross = SSA sum; Earning/Deductions/Net match slip; Full mode regression smoke

### Naming note

Keep Desk report name **Monthly Salary Register Old Format Net Payable** (no new scrub path / no parentheses). Format is a filter only.

## Out of scope

- New standalone report DocType/name
- Changing Full layout or day-code mapping from 004
- Per-component breakdown in Compressed
- BANK name column in Compressed

## Acceptance

1. Format filter Full / Compressed works
2. Compressed shows exactly the 10 columns listed
3. Values match Full’s Total Gross / Total Earning / Total Deductions / Net / Paid Days for the same slips
4. PDF + Excel export Compressed correctly
5. Full mode behavior unchanged

## Decisions log (grilling)

| Topic | Decision |
|-------|----------|
| Surface | Same report + Format filter (`Full` / `Compressed`) |
| Compressed columns | SR, Full Name, IFSC, Account Number, Days in Month, Paid For Days, Actual Gross, Earning Gross, Deductions, Net Payable |
| BANK name | Dropped in Compressed |
| Day codes | Dropped in Compressed |
| Component columns | Dropped in Compressed |
| Default format | Full |

## Progress log

| Date | Note |
|------|------|
| 2026-08-07 | Spec drafted and saved (planned) |
| 2026-08-07 | Format filter + compressed layout implemented; tests added |
