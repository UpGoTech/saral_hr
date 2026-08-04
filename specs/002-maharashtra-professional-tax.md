# 002 — Maharashtra Professional Tax (Company Slabs)

| | |
|---|---|
| **Status** | in progress |
| **Branch** | `feat/maharashtra-professional-tax` |
| **Primary DocTypes** | Company, Professional Tax Period, Salary Slip, Salary Structure Assignment, Salary Component |

## Why?

Professional Tax (PT) for Maharashtra is slab-based by salary and gender, with a **per-slab** February override (males only for the annual ₹2500 / ₹2200 bands) and age exemption. Females in the taxable band pay ₹200 × 12 = **₹2400/year** — no February surcharge. Flat ₹200/₹300 hardcodes cannot express this.

## What?

1. **Company → Payroll & Statutory**: configure PT periods and gender slabs (Maharashtra defaults seeded).
2. **Salary Structure Assignment**: keep only **enable / disable** via `is_pt_applicable` (no PT rate config on the component).
3. **Salary Slip / CTC / SSA preview**: calculate PT from Company slabs using final (or preview) gross — **no** flat ₹200 / ₹300 hardcodes.
4. **February**: live on each slab as optional `february_amount` (not on the period). Female taxable slabs have no February amount.

## Decisions (grilling)

| # | Topic | Decision |
|---|--------|----------|
| 1 | Taxable base | Final salary-slip **gross** after proration / attendance / additional salary |
| 2 | Source of truth | Company PT settings only; purge hardcodes everywhere (slip, SSA, CTC) |
| 3 | Default slabs | Maharashtra seed table below (editable per company) |
| 4 | ~~February (period)~~ | **Superseded by #15** — was period-level `february_amount` |
| 5 | Versioning | Periods with `from_date` / `to_date` + SSA lock (same idea as ESIC/PF) |
| 6 | Gender source | Always **Employee** master `gender` |
| 7 | Missing / Other gender | Treat as **Male** slabs |
| 8 | Age exemption | Company period field `age_exempt_years` (default **65**), not a hardcoded constant |
| 9 | Period + slabs UI model | Period child rows; slabs nested in UX (JSON on period — Frappe cannot nest child tables) |
| 10 | ~~February rule (period)~~ | **Superseded by #15–#17** |
| 11 | Gross timing | Slip uses **final** gross; SSA uses SSA gross as **preview** estimate |
| 12 | SSA PT row | Still insert PT deduction when enabled; amount = slab estimate from SSA gross |
| 13 | Salary Component | Migrate: `is_special_component = 0`, clear monthly amounts; keep deduction shell |
| 14 | v1 scope | Desk Company + salary slip + SSA + CTC calculator/record + unit tests |
| 15 | February location | **Per-slab** optional `february_amount` (`null` = no Feb override). **Remove** period-level `february_amount` |
| 16 | Nil + validation | Tax 0 always stays 0 in February; **validation error** if `february_amount` set on a zero-tax slab |
| 17 | MH Male Feb amounts | Mid band 175 → Feb **275** (₹2200/year); top band 200 → Feb **300** (₹2500/year) |
| 18 | MH Female Feb | Taxable female slab tax **200**, `february_amount` **null** (₹2400/year, no surcharge) |
| 19 | Multi-state | **Deferred** — no state picker / engines in this spec; other states = manual slab entry until a later spec |
| 20 | Migrate existing periods | By tax amount: Male `tax==175` → Feb 275; Male `tax==200` → Feb 300; then drop period `february_amount`. Custom non-175/200 Male slabs get no Feb unless edited later |
| 21 | Delivery | Amend this spec; continue on `feat/maharashtra-professional-tax` before PR |

## Default seed (per PT period)

| Gender | From (₹) | To (₹) | Tax (₹/month) | February (₹) |
|--------|----------|--------|----------------|--------------|
| Male | 0 | 7500 | 0 | — |
| Male | 7501 | 10000 | 175 | **275** |
| Male | 10001 | *(open)* | 200 | **300** |
| Female | 0 | 25000 | 0 | — |
| Female | 25001 | *(open)* | 200 | — |

Period defaults:

- `age_exempt_years` = **65**
- **No** period-level `february_amount`
- Open-ended period when seeding empty companies

Annual check (Maharashtra):

- Male mid: 175×11 + 275 = **₹2,200**
- Male top: 200×11 + 300 = **₹2,500**
- Female taxable: 200×12 = **₹2,400**

## How?

### Data model

Frappe cannot nest a child table inside a child table. Follow the existing ESIC/PF pattern (`wage_components` JSON + custom Desk UI in `company.js`).

#### Child DocType: `Professional Tax Period` (`istable`)

| Fieldname | Type | Notes |
|-----------|------|--------|
| `from_date` | Date | Period start |
| `to_date` | Date | Period end; stays editable when SSA-locked |
| `age_exempt_years` | Int | Default 65; age ≥ this → PT = 0 |
| `slabs` | Small Text | JSON array of slab objects |

**Removed:** period field `february_amount` (was in first build — drop via DocType JSON + migrate patch).

Slab JSON shape:

```json
[
  {"gender": "Male", "from_amount": 0, "to_amount": 7500, "tax_amount": 0, "february_amount": null},
  {"gender": "Male", "from_amount": 7501, "to_amount": 10000, "tax_amount": 175, "february_amount": 275},
  {"gender": "Male", "from_amount": 10001, "to_amount": null, "tax_amount": 200, "february_amount": 300},
  {"gender": "Female", "from_amount": 0, "to_amount": 25000, "tax_amount": 0, "february_amount": null},
  {"gender": "Female", "from_amount": 25001, "to_amount": null, "tax_amount": 200, "february_amount": null}
]
```

`to_amount: null` = open-ended upper bound.  
`february_amount: null` (or omitted) = use `tax_amount` in all months including February.

#### Company

- Section under **Payroll & Statutory** (after PF): **Professional Tax Slabs**
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
if tax == 0 → 0
if month == February and slab.february_amount is not null → slab.february_amount
else → tax
```

Company helpers:

- `get_pt_config(period_date)` → period + parsed slabs (no period february)
- `calculate_pt(gross, gender, period_date, date_of_birth)` → float amount
- `validate_pt_settings()` — non-overlapping periods; valid non-negative ranges; slab coverage; **reject `february_amount` when `tax_amount == 0`**
- `_validate_locked_periods` for PT — lock `slabs`, `age_exempt_years`, `from_date` (`to_date` remains editable)

### Desk UI (`company.js`)

- Hide native `pt_periods` grid via CSS
- Period cards: dates, age exempt years (**no** period February field)
- Slab editor columns: gender / from / to / tax / **February** ↔ JSON `slabs`
- Action: **Load Maharashtra defaults** (seed table above)
- Reuse `_is_period_locked` / SSA lock styling

### Call sites

Already wired to `Company.calculate_pt` in first build — only calc + seed + UI + validation change for February-per-slab. No new hardcodes.

### Seed / migrate

1. **Already done:** empty companies → open period + MH seed; PT component not special
2. **New patch:** for each PT period row:
   - Parse `slabs`; for each Male slab: if `tax_amount == 175` set `february_amount = 275`; if `tax_amount == 200` set `february_amount = 300`
   - Clear / ignore period `february_amount`
3. Update `MAHARASHTRA_PT_SLABS` constant + “Load Maharashtra defaults” to the table above
4. Remove `february_amount` from Professional Tax Period DocType JSON

### Tests (unit)

- Male boundaries: 0 / 175 / 200 (non-Feb)
- Female: ≤25000 → 0; above → 200 **in February too** (no bump)
- February Male mid: 175 → **275**; Male top: 200 → **300**
- Nil stays 0 in February
- Validation: `february_amount` on zero-tax slab → error
- Age ≥ `age_exempt_years` → 0
- Missing / Other gender → Male slabs
- `is_pt_applicable = 0` → no PT

No Playwright for v1.

## Out of scope

- Multi-state PT engines / state picker / state seed catalog (manual editable slabs only until a later spec)
- Playwright e2e
- LWF / other special components
- Changing how `is_pt_applicable` is presented on SSA (keep existing toggle)

## Acceptance criteria

### Done (first build)

- [x] Company form shows Professional Tax section with period + male/female slabs
- [x] New/empty companies seeded with Maharashtra defaults
- [x] Flat ₹200 / ₹300 hardcodes removed from slip, CTC calculator, CTC record
- [x] SSA only toggles PT; preview amount comes from slabs + SSA gross
- [x] PT Salary Component is not a special monthly component after migrate
- [x] SSA-locked periods block slab/rate edits (to_date still editable)

### Remaining (this amendment)

- [x] Period-level `february_amount` removed; February only on slabs
- [x] MH seed: Male 175→Feb 275, Male 200→Feb 300; Female taxable Feb null
- [x] Female taxable stays ₹200 in February (₹2400 annual)
- [x] Validation rejects `february_amount` on zero-tax slabs
- [x] Migrate patch maps existing Male 175/200 slabs to Feb amounts
- [x] Unit tests for Female Feb + Male mid/top Feb amounts pass

## Progress log

| Date | Note |
|------|------|
| 2026-08-04 | Spec written after grilling; status `planned` — await review before build |
| 2026-08-04 | Build started on `feat/maharashtra-professional-tax` |
| 2026-08-04 | Implemented: PT Period child + Company slabs UI/helpers; purged 200/300 hardcodes; patches + unit tests green |
| 2026-08-04 | Re-grilled: Female ₹2400/year (no Feb); per-slab `february_amount`; multi-state deferred; amend spec on same branch |
| 2026-08-04 | Implemented per-slab February; migrate + tests |
