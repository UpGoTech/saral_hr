# 002 — Maharashtra Professional Tax (Company Slabs)

| | |
|---|---|
| **Status** | in progress |
| **Branch** | `feat/maharashtra-professional-tax` |
| **Primary DocTypes** | Company, Professional Tax Period, Salary Slip, Salary Structure Assignment, Salary Component |

## Why?

Professional Tax (PT) for Maharashtra is slab-based by salary and gender, with a February override and age exemption. Today the app hardcodes ₹200 (₹300 in February) in salary slip / CTC paths and sometimes reads Salary Component monthly amounts. That cannot express real Maharashtra slabs, cannot differ men vs women, and cannot be versioned when rates change.

## What?

1. **Company → Payroll & Statutory**: configure PT periods and gender slabs (Maharashtra defaults seeded).
2. **Salary Structure Assignment**: keep only **enable / disable** via `is_pt_applicable` (no PT rate config on the component).
3. **Salary Slip / CTC / SSA preview**: calculate PT from Company slabs using final (or preview) gross — **remove** all flat ₹200 / ₹300 hardcodes.

## Decisions (grilling)

| # | Topic | Decision |
|---|--------|----------|
| 1 | Taxable base | Final salary-slip **gross** after proration / attendance / additional salary |
| 2 | Source of truth | Company PT settings only; purge hardcodes everywhere (slip, SSA, CTC) |
| 3 | Default slabs | Maharashtra seed table below (editable per company) |
| 4 | February | One period-level `february_amount`; use it **only when matched slab tax > 0** |
| 5 | Versioning | Periods with `from_date` / `to_date` + SSA lock (same idea as ESIC/PF) |
| 6 | Gender source | Always **Employee** master `gender` |
| 7 | Missing / Other gender | Treat as **Male** slabs |
| 8 | Age exemption | Company period field `age_exempt_years` (default **65**), not a hardcoded constant |
| 9 | Period + slabs UI model | Period child rows; slabs nested in UX (JSON on period — Frappe cannot nest child tables) |
| 10 | February rule detail | Nil stays 0 in Feb; taxable slabs use `february_amount` |
| 11 | Gross timing | Slip uses **final** gross; SSA uses SSA gross as **preview** estimate |
| 12 | SSA PT row | Still insert PT deduction when enabled; amount = slab estimate from SSA gross |
| 13 | Salary Component | Migrate: `is_special_component = 0`, clear monthly amounts; keep deduction shell |
| 14 | v1 scope | Desk Company + salary slip + SSA + CTC calculator/record + unit tests |

## Default seed (per PT period)

| Gender | From (₹) | To (₹) | Tax (₹/month) |
|--------|----------|--------|----------------|
| Male | 0 | 7500 | 0 |
| Male | 7501 | 10000 | 175 |
| Male | 10001 | *(open)* | 200 |
| Female | 0 | 25000 | 0 |
| Female | 25001 | *(open)* | 200 |

Period defaults:

- `february_amount` = **300**
- `age_exempt_years` = **65**
- Open-ended period (`from_date` / `to_date` empty or company-appropriate start) when seeding empty companies

## How?

### Data model

Frappe cannot nest a child table inside a child table. Follow the existing ESIC/PF pattern (`wage_components` JSON + custom Desk UI in `company.js`).

#### New child DocType: `Professional Tax Period` (`istable`)

| Fieldname | Type | Notes |
|-----------|------|--------|
| `from_date` | Date | Period start |
| `to_date` | Date | Period end; stays editable when SSA-locked |
| `february_amount` | Currency | Default 300; used when slab tax > 0 and month is February |
| `age_exempt_years` | Int | Default 65; age ≥ this → PT = 0 |
| `slabs` | Small Text | JSON array of slab objects |

Slab JSON shape:

```json
[
  {"gender": "Male", "from_amount": 0, "to_amount": 7500, "tax_amount": 0},
  {"gender": "Male", "from_amount": 7501, "to_amount": 10000, "tax_amount": 175},
  {"gender": "Male", "from_amount": 10001, "to_amount": null, "tax_amount": 200},
  {"gender": "Female", "from_amount": 0, "to_amount": 25000, "tax_amount": 0},
  {"gender": "Female", "from_amount": 25001, "to_amount": null, "tax_amount": 200}
]
```

`to_amount: null` = open-ended upper bound.

#### Company

- New section under **Payroll & Statutory** (after PF): **Professional Tax Slabs**
- Table field `pt_periods` → `Professional Tax Period`

### Calculation

```
if not is_pt_applicable → 0
match Company pt_periods for slip/SSA date
if no period → 0
if DOB set and age(period_date, DOB) >= age_exempt_years → 0
gender = Employee.gender; if missing or not Male/Female → Male
match slab for gender where from_amount ≤ gross ≤ to_amount (or open-ended)
tax = slab.tax_amount (0 if no match)
if month == February and tax > 0 → february_amount
else → tax
```

Company helpers (mirror `get_esic_config` / `get_pf_config`):

- `get_pt_config(period_date)` → period + parsed slabs
- `calculate_pt(gross, gender, period_date, date_of_birth)` → float amount
- `validate_pt_settings()` — non-overlapping periods; valid non-negative ranges; sensible slab coverage within gender
- `_validate_locked_periods` for PT — when submitted SSA `from_date` falls in period, lock `slabs`, `february_amount`, `age_exempt_years`, `from_date` (`to_date` remains editable)

### Desk UI (`company.js`)

Same pattern as ESIC/PF custom period cards:

- Hide native `pt_periods` grid via CSS
- Render period cards: dates, February amount, age exempt years
- Embedded slab editor (gender / from / to / tax) ↔ JSON `slabs`
- Action: **Load Maharashtra defaults** on new/empty period
- Reuse `_is_period_locked` / SSA lock styling

### Call sites (hardcode purge)

| Location | Change |
|----------|--------|
| `salary_slip.py` | Remove `200.0` / `300.0` PT overrides; compute after final gross via `Company.calculate_pt`; age exempt from period setting |
| `get_statutory_components_internal` | Stop `_sa_local("Professional Tax")`; pass gross + gender + DOB (or compute PT only on slip path after gross is known) |
| `salary_structure_assignment.py` | Replace `_special_component_amount(SC_PT)` with `calculate_pt(SSA gross, gender, from_date, dob)` preview |
| `ctc_calculator.py` / `ctc_calculator_record.py` | Remove `PT_NORMAL` / `PT_FEBRUARY`; use Company slabs (default Male if no employee gender) |
| `install.py` + migrate patch | PT component: `is_special_component=0`, clear monthly amounts; keep `is_pt_component=1` deduction shell |

**Ordering on salary slip:** finalize earnings → gross → then set/replace Professional Tax deduction.

### Seed / migrate

1. Patch: each Company with empty `pt_periods` → one open period + Maharashtra seed
2. Patch: Professional Tax Salary Component → not special; clear `monthly_amounts`
3. Existing SSA `is_pt_applicable` unchanged

### Tests (unit)

- Male boundaries: 0 / 175 / 200
- Female: ≤25000 → 0; above → 200
- February: tax > 0 → `february_amount`; nil stays 0
- Age ≥ `age_exempt_years` → 0
- Missing / Other gender → Male slabs
- `is_pt_applicable = 0` → no PT
- No remaining hardcode paths for PT `200`/`300` by month name

No Playwright for v1.

## Out of scope

- Multi-state PT engines (seed is Maharashtra; other states can be typed into the same editable slabs)
- Playwright e2e
- LWF / other special components
- Changing how `is_pt_applicable` is presented on SSA (keep existing toggle)

## Acceptance criteria

- [ ] Company form shows Professional Tax section with period + male/female slabs
- [ ] New/empty companies can load (or are seeded with) Maharashtra defaults
- [ ] Salary slip PT uses final gross + gender + age + February rules from Company
- [ ] Flat ₹200 / ₹300 hardcodes removed from slip, CTC calculator, CTC record
- [ ] SSA only toggles PT; preview amount comes from slabs + SSA gross
- [ ] PT Salary Component is not a special monthly component after migrate
- [ ] SSA-locked periods block slab/rate edits (to_date still editable)
- [ ] Unit tests above pass on the test site

## Progress log

| Date | Note |
|------|------|
| 2026-08-04 | Spec written after grilling; status `planned` — await review before build |
| 2026-08-04 | Build started on `feat/maharashtra-professional-tax` |
