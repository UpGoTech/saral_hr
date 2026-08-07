# 005 — Monthly Salary Register Compressed format

| | |
|---|---|
| **Status** | ready for review |
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
| `Compressed` | Fixed 9 data-column layout below (+ Desk serial / export SR. NO.) |

Filters otherwise unchanged: Company, Year, Month, Population (All/Staff/Worker/Consultant). Inclusion rules same as 004 (submitted slips only, sort by **Employee ID**, exclude holds with no slip).

### Sort (Full + Compressed)

Default order: **Employee ID** ascending (`Company Link.employee`, fallback Salary Slip `employee`). SR. NO. assigned after that order.

### Compressed columns (exact)

| # | Column | Source / notes |
|---|--------|----------------|
| — | Serial | Desk: DataTable built-in `_rowIndex` (no duplicate SR. NO. column). PDF/Excel prepend **SR. NO.** |
| 1 | Full Name | Slip `employee_name` / Company Link `full_name` |
| 2 | IFSC Code | Employee `ifsc_code` (left-aligned; wide enough for 11-char IFSC) |
| 3 | Account Number | Employee `account_number` (left-aligned) |
| 4 | Days in Month | Calendar days in month |
| 5 | Paid For Days | Slip `payment_days` — whole numbers without `.0`; one decimal when fractional; **no sum on Total row** |
| 6 | Actual Gross | Sum of SSA earning amounts (same as Full **Total Gross**) |
| 7 | Earning Gross | Slip `total_earnings` (same as Full **Total Earning**) |
| 8 | Deductions | Slip `total_deductions` (employee-share total) |
| 9 | Net Payable | Slip `net_salary` |

**Dropped vs Full in Compressed:**

- BANK name
- All day letter-codes (P / R / H / C / T / Y / OD / E / I / A)
- All per-component ACTUAL / Earning / Deduction columns

### Desk UX

- Multi-word Compressed headers wrap to **two lines** (`<br>`); header row tall enough to show both lines
- Column widths sized for content with **one-sided** horizontal padding (avoid page overflow)
- Serial column widened so digits are not clipped
- **No yellow** highlight on Actual / Earning / Deductions / Net
- Total row stays **pinned at bottom** when sorting any column
- Row **hover** highlight on Desk grid
- Currency figures use default Currency formatter (no invalid `span` wrap around Currency `<div>`)

### Header / footer / exports

- Header same idea as Full (`Employee Salary Sheet` + period + Month Days)
- Totals row: sum money columns (Actual Gross, Earning Gross, Deductions, Net); identity blank or “Total”; Paid For Days blank on Total
- Signatures: **Prepared By / Checked By / Authorised Signatory** in **one row**, equally spaced (PDF table layout — wkhtmltopdf does not honour flexbox; Excel merged thirds)
- PDF: A4 landscape
- Excel: same column model + proportional widths aligned to Desk
- No ACTUAL/Earning/Deduction color **component bands** in Compressed

### PDF layout details

| Topic | Decision |
|-------|----------|
| Column widths | `<colgroup>` with **proportional** widths from column defs (not equal-width) |
| Vertical borders | Solid (unchanged) |
| Horizontal borders (data rows) | Thin **dashed** |
| Header / Total borders | Solid |
| Zebra rows | Odd/even data-row backgrounds for readability |
| Left margin | **18mm** for filing / hole-punch; other margins stay tight |
| Signatures | Single equidistant row under the table |

### Desk / PDF / Excel

All three use the Compressed column model when Format = Compressed. Full exports unchanged when Format = Full (except shared sort-by-Employee-ID and shared PDF signature / margin / border polish where applicable).

### Default Format

**Full** (preserve existing behaviour for current users).

## How? (implementation sketch)

1. Add `format` filter: `Full` \| `Compressed` (default `Full`)
2. Reuse `build_register` data pipeline; when Compressed, project each row to the fields above (skip building dynamic component columns)
3. PDF/Excel builders branch on format; PDF uses colgroup + zebra + dashed horizontals; Excel uses `_excel_col_width`
4. Desk JS: two-line header CSS, serial widen, pin Total on sort, hover, Paid For Days display formatter
5. Tests: Compressed column count/labels; paid-days formatting; no paid-days total; Employee ID sort; PDF colgroup proportions; Full mode regression smoke

### Naming note

Keep Desk report name **Monthly Salary Register Old Format Net Payable** (no new scrub path / no parentheses). Format is a filter only.

## Out of scope

- New standalone report DocType/name
- Changing Full day-code mapping from 004
- Per-component breakdown in Compressed
- BANK name column in Compressed

## Acceptance

1. Format filter Full / Compressed works
2. Compressed shows the 9 data columns listed (Desk serial is separate; PDF/Excel prepend SR. NO.)
3. Values match Full’s Total Gross / Total Earning / Total Deductions / Net / Paid Days for the same slips
4. PDF + Excel export Compressed correctly (proportional columns, signatures in one row, dashed data horizontals, 18mm left margin, zebra rows)
5. Full mode behavior unchanged aside from shared Employee ID sort and shared PDF chrome polish
6. Paid For Days: whole numbers without `.0`; one decimal when fractional; blank on Total
7. Desk: two-line headers readable; Total pinned on sort; row hover; IFSC/Account not clipped; Account left-aligned

## Decisions log (grilling)

| Topic | Decision |
|-------|----------|
| Surface | Same report + Format filter (`Full` / `Compressed`) |
| Compressed columns | 9 data cols; Desk uses DT serial; PDF/Excel prepend SR. NO. |
| BANK name | Dropped in Compressed |
| Day codes | Dropped in Compressed |
| Component columns | Dropped in Compressed |
| Default format | Full |
| Default sort | Employee ID (not name) |
| Yellow highlight | Removed for money columns |
| Paid For Days Total | Not summed |
| PDF column widths | Proportional colgroup (not equal) |
| PDF horizontal rules | Thin dashed in data area |
| PDF left margin | 18mm for punching/filing |
| PDF signatures | One equidistant row (table, not flex) |
| Desk hover | Enabled on data rows |

## Progress log

| Date | Note |
|------|------|
| 2026-08-07 | Spec drafted and saved (planned) |
| 2026-08-07 | Format filter + compressed layout implemented; tests added |
| 2026-08-07 | UX polish: no yellow; two-line headers; pin Total; drop Desk SR. NO.; paid days formatting; Employee ID sort; IFSC width; PDF/Excel parity; signatures row; zebra; dashed horizontals; 18mm left margin; Desk hover |
| 2026-08-07 | Spec reconciled to final Desk/PDF/Excel behaviour; ready for PR |
