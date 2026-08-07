# 006 — Additional-Only Salary Components (ESIC / PF / PT)

| | |
|---|---|
| **Status** | done |
| **Branch** | `feat/additional-only-salary-components` |
| **Primary DocTypes** | Salary Component, Additional Salary, Additional Salary Component, Additional Deductions, Additional Deduction Component, Company, Salary Slip, Salary Structure Assignment |

## Why?

Additional Salary amounts are added to slip **Total Gross**, but ESIC (and PF when component-wise) is computed from Company-listed wage components only. Previously Additional Salary / Additional Deduction used **free-text** `component_type`, so those amounts never reliably entered the ESIC/PF wage map. Component-wise statutory math was wrong whenever Production Incentive, Arrears, etc. were paid via Additional Salary.

## What?

1. Introduce **additional-only** Salary Components (registered master rows — not free text).
2. **Additional Salary** and **Additional Deductions** may only insert **registered** components (Link + filters) — no free-flowing text.
3. These components are **excluded from SSA** (structure / assignment earnings & deductions pickers).
4. Additional-only **earnings** appear in Company **ESIC / PF** wage-component settings and participate in wage-basis `_sum` when selected.
5. Fix slip statutory recompute so Additional Salary lines enter `earnings_map` **by component name** (not a synthetic lump key alone).
6. Slip print lists Additional Salary earnings as line items (not only in the total).
7. Company ESIC / PF / PT period lock is based on **submitted Salary Slips** so periods can be unlocked for data correction.

Out of scope for this spec:

- Changing PT slab rules (PT already uses final gross; once Additional Salary is on the slip as earnings, PT follows).
- Putting **deduction** penalties into ESIC/PF wage basis (they reduce net only).
- Auto-including every additional earning in ESIC/PF with no Company opt-out.

## Decisions

| # | Topic | Decision |
|---|--------|----------|
| 1 | Master | Real **Salary Component** rows; no second component DocType |
| 2 | Flag | New Check `is_additional_only` on Salary Component. Do **not** reuse `is_special_component` (month-wise fixed amounts / LWF) |
| 3 | Additional Salary child | `component_type`: **Data → Link** to Salary Component; filter `type = Earning` and `is_additional_only = 1` |
| 4 | Additional Deduction child | Same: Link; filter `type = Deduction` and `is_additional_only = 1` |
| 5 | Free text | **Removed.** Validate on save: component must exist and match type + flag |
| 6 | SSA | Exclude `is_additional_only = 1` from SSA / Salary Structure earnings & deductions queries; reject if somehow inserted |
| 7 | Company ESIC / PF UI | Continue listing Earning Salary Components — additional-only earnings appear automatically and are selectable |
| 8 | Wage inclusion | **Selectable** in Company period wage list (not hard-auto for all). Allows `Arrears - without PF` style opt-out |
| 9 | Deduction penalties | Additional-only **deductions** never enter ESIC/PF wage components |
| 10 | Slip earnings_map | When recomputing statutory, merge Additional Salary rows into `earnings_map[component_name] += amount` (same names as wage list) |
| 11 | Legacy lump key | Drop reliance on synthetic `"Additional Salary"` / `"Arrears"` alias inject for wage math once named merge works |
| 12 | Existing free-text rows | Migrate: if text matches a Salary Component name, convert to Link; else create additional-only component — prefer match-or-create |
| 13 | Seed examples (earnings) | Production Incentive; mark Arrears / Arrears - without PF as additional-only (confirmed unused on SSA) |
| 14 | Seed examples (deductions) | Safety Gadget Penalty; type Deduction, `is_additional_only = 1` |
| 15 | Abbr on slip | Resolve abbr from Salary Component when appending additional rows to slip |
| 16 | Tests | Unit: Additional Salary earning in Company ESIC wage list → Employee/Employer ESIC includes that amount; free-text rejected; SSA cannot add additional-only component; period lock unlocks when slips cleared |
| 17 | Delivery | Spec commit first; then tracer: flag + Link fields + earnings_map fix + ESIC test |
| 18 | Slip print | Salary Slip Custom must append Additional Salary earnings into print rows (fixture + module JSON kept in sync). Totals alone are not enough |
| 19 | Period lock purpose | Protect wage components / rates **after payroll has used them** |
| 20 | Period lock rule | Lock when a **submitted** Salary Slip `start_date` falls in the period. **SSA alone does not lock** |
| 21 | Period unlock / correction | Cancel (or cancel then delete) all submitted slips in that period → period unlocks for data correction; SSAs may remain |
| 22 | Period close workflow | `to_date` stays editable on locked rows; close period + add new period for future rate changes without canceling history |
| 23 | Draft slips | Draft (`docstatus = 0`) and cancelled (`docstatus = 2`) slips do **not** lock |

## Statutory matrix

| Statutory | Base | Additional-only earning (e.g. Production Incentive) | Additional-only deduction (e.g. penalty) |
|-----------|------|------------------------------------------------------|------------------------------------------|
| ESIC | Sum of Company-listed **earnings** | Included **if** listed in ESIC wage components | Not in wage list |
| PF | Sum of Company-listed **earnings** (capped if Limited) | Included **if** listed in PF wage components | Not in wage list |
| PT | Final slip **gross** (total earnings) | Included via gross automatically | Not in PT base |

## How?

### 1. Salary Component

| Fieldname | Type | Default | Notes |
|-----------|------|---------|--------|
| `is_additional_only` | Check | 0 | If 1: usable only on Additional Salary / Additional Deductions; hidden from SSA |

Validation: `is_additional_only` and `is_special_component` are **mutually exclusive**.

### 2. Additional Salary / Deduction children

- `component_type` → Link to Salary Component
- Filters + server validate: type + `is_additional_only = 1`

### 3. SSA / Salary Structure

- `set_query` excludes `is_additional_only = 1`
- Server reject if inserted

### 4. Salary Slip statutory path

1. Build `actual_earnings_map` from SSA earnings
2. Merge Additional Salary by component name into `earnings_map`
3. Recompute statutory when attendance data exists **or** additional names intersect wage lists / Gross virtuals
4. Set `abbr` from Salary Component on additional rows

### 5. Company ESIC / PF / PT period lock

```
locked ⇔ exists submitted Salary Slip
         where company matches
           and start_date ∈ [period.from_date, period.to_date]
```

- UI + server (`_period_is_locked` / `_validate_locked_periods`) share this rule
- Protected fields: wage components and rates (`to_date` excluded)
- Hint on Company form explains cancel/delete slips to unlock, or close + new period

**Rejected alternatives (documented during review):**

| Rule | Why rejected |
|------|----------------|
| SSA `from_date` in period only | Misses coverage months (Jul unlocked while Apr SSA still applies) |
| SSA date-range overlap | Locks every future period while open-ended SSAs exist; blocks close+new |
| SSA start **or** submitted slip | Keeps Apr–Jun locked after all slips cleared; blocks data correction |

### 6. Install / migrate

- Seed Production Incentive, Safety Gadget Penalty
- Mark Arrears / Arrears - without PF as additional-only
- Patch `seed_additional_only_salary_components`: match-or-create free-text child values (e.g. Production Incentives, I-Tax)

### 7. Slip print

- Ensure `Salary Slip Custom` HTML includes Additional Salary earnings in the Earnings / Computed Earnings row list
- Keep `fixtures/print_format.json` and module print format JSON in sync (stale fixture previously hid Production Incentive on print while totals included it)

## Tracer bullet (build order) — completed

1. Spec committed on `feat/additional-only-salary-components`
2. `is_additional_only` + seeds
3. Link + validate on Additional Salary / Deduction
4. Exclude from SSA / Salary Structure
5. Slip `earnings_map` merge + ESIC unit tests
6. Migrate patch for free-text rows
7. Print format fixture sync
8. Statutory period lock → submitted slips only (+ unlock tests)

## Progress

| Phase | Status |
|-------|--------|
| Spec | done |
| Flag + seed | done |
| Additional DocTypes Link + validate | done |
| SSA exclude | done |
| Slip earnings_map / ESIC fix | done |
| Migrate + tests | done |
| Slip print Additional Salary rows | done |
| Statutory period lock (slip-based) | done |

## Manual verification notes (Fabrixcel / Sandeep Mankar Jul 2024)

- Additional Salary **Production Incentives** ₹1,270 was on the slip child table and in total ₹16,270 but missing from print until fixture sync
- ESIC wage list must explicitly include Production Incentives / Production Incentive for ESIC to rise with the incentive
- Close old ESIC period + new period from 01-07-2024 is the path to change wage components without editing history
- Clearing **submitted** slips in a period unlocks that period for correction; SSA can stay

## Non-goals / explicit ignores

- Free-text component names on Additional Salary / Deduction after this ships
- Additional deductions as ESIC/PF wage components
- Hard-auto “every additional earning always in ESIC/PF”
- Renaming virtual Gross / Gross Including Additional Salary UX (follow-up)
- Locking periods based on SSA existence alone
