# 006 — Additional-Only Salary Components (ESIC / PF / PT)

| | |
|---|---|
| **Status** | planned |
| **Branch** | `feat/additional-only-salary-components` (proposed) |
| **Primary DocTypes** | Salary Component, Additional Salary, Additional Salary Component, Additional Deductions, Additional Deduction Component, Company, Salary Slip, Salary Structure Assignment |

## Why?

Additional Salary amounts are added to slip **Total Gross**, but ESIC (and PF when component-wise) is computed from Company-listed wage components only. Today Additional Salary / Additional Deduction use **free-text** `component_type`, so those amounts never reliably enter the ESIC/PF wage map. Component-wise statutory math is therefore wrong whenever Production Incentive, Arrears, etc. are paid via Additional Salary.

## What?

1. Introduce **additional-only** Salary Components (registered master rows — not free text).
2. **Additional Salary** and **Additional Deductions** may only insert **registered** components (Link + filters) — no free-flowing text.
3. These components are **excluded from SSA** (structure / assignment earnings & deductions pickers).
4. Additional-only **earnings** appear in Company **ESIC / PF** wage-component settings and participate in wage-basis `_sum` when selected.
5. Fix slip statutory recompute so Additional Salary lines enter `earnings_map` **by component name** (not a synthetic lump key alone).

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
| 12 | Existing free-text rows | Migrate: if text matches a Salary Component name, convert to Link; else create additional-only component **or** fail migrate with report — prefer match-or-create for known seed names |
| 13 | Seed examples (earnings) | Production Incentive; keep existing Arrears / Arrears - without PF and mark additional-only where appropriate |
| 14 | Seed examples (deductions) | Safety Gadget Penalty (or similar); type Deduction, `is_additional_only = 1` |
| 15 | Abbr on slip | Resolve abbr from Salary Component when appending additional rows to slip |
| 16 | Tests | Unit: Additional Salary earning in Company ESIC wage list → Employee/Employer ESIC includes that amount; free-text rejected; SSA cannot add additional-only component |
| 17 | Delivery | Spec commit first; then tracer: flag + Link fields + earnings_map fix + one ESIC test |

## Statutory matrix

| Statutory | Base | Additional-only earning (e.g. Production Incentive) | Additional-only deduction (e.g. penalty) |
|-----------|------|------------------------------------------------------|------------------------------------------|
| ESIC | Sum of Company-listed **earnings** | Included **if** listed in ESIC wage components | Not in wage list |
| PF | Sum of Company-listed **earnings** (capped if Limited) | Included **if** listed in PF wage components | Not in wage list |
| PT | Final slip **gross** (total earnings) | Included via gross automatically | Not in PT base |

## How?

### 1. Salary Component

Add field:

| Fieldname | Type | Default | Notes |
|-----------|------|---------|--------|
| `is_additional_only` | Check | 0 | If 1: usable only on Additional Salary / Additional Deductions; hidden from SSA |

Validation:

- `is_additional_only` and `is_special_component` are **mutually exclusive** (forbid both on). Special = SSA/statutory monthly fixed; additional-only = ad-hoc docs.

### 2. Additional Salary Component / Additional Deduction Component

| Field | Change |
|-------|--------|
| `component_type` | Fieldtype **Link**, options **Salary Component** |
| Filters (JS `set_query` + server validate) | Salary: Earning + `is_additional_only=1`; Deduction: Deduction + `is_additional_only=1` |

Parent controllers (`additional_salary.py`, `additional_deductions.py`):

- On validate, for each child row assert Link target exists and passes filters.
- Reject blank / unknown / wrong type / non-additional-only.

### 3. SSA / Salary Structure UI

- `set_query` on earnings / deductions / employer_share: `is_additional_only = 0` (and existing type filters).
- Server-side SSA validate: throw if any row references `is_additional_only` component.

### 4. Salary Slip statutory path

In `get_salary_structure_for_employee` (and bulk path equivalent):

1. Build `actual_earnings_map` from SSA earnings (as today).
2. Load Additional Salary for employee/month; for each child:
   `earnings_map[component_type] = earnings_map.get(component_type, 0) + amount`
3. `gross_salary = sum(earnings_map.values())` (keep consistent with current gross definition used by PT/ESIC).
4. Call `get_statutory_components_internal` with that map.
5. When appending additional rows to the slip, set `abbr` from Salary Component.

Remove / stop depending on synthetic `"Additional Salary"` / `"Arrears"` alias inject for wage inclusion once named merge works (may keep a temporary total helper only if still needed for UX totals).

### 5. Company ESIC / PF

No schema change required if UI already loads all Earning components. Optional UX: group or badge “Additional-only” in the checkbox list.

Locked periods: same SSA-lock rules as today — wage list changes still blocked when locked.

### 6. Install / migrate

- Seed Production Incentive (Earning, `is_additional_only=1`).
- Seed Safety Gadget Penalty (Deduction, `is_additional_only=1`) — name can be adjusted at implement time.
- Mark existing **Arrears** / **Arrears - without PF** as `is_additional_only=1` if they should never sit on SSA (confirm against current SSA usage before flipping).
- Patch: convert historical Additional Salary / Deduction child `component_type` strings to Links where possible.

### 7. Frontend / Desk sync

- Additional Salary / Deduction forms: Link + `set_query`.
- SSA: exclude additional-only.
- Company wage UI: no mandatory change; verify additional-only earnings show up.

## Tracer bullet (build order)

1. Spec committed on `feat/additional-only-salary-components`.
2. `is_additional_only` on Salary Component + seed one earning + one deduction.
3. Link + validate on Additional Salary / Additional Deduction (block free text).
4. Exclude from SSA query/validate.
5. Fix slip `earnings_map` merge by component name + ESIC unit test (before/after).
6. Migrate patch for existing free-text rows.
7. Manual check: Company ticks Production Incentive → slip ESIC rises by Incentive × employee %.

## Progress

| Phase | Status |
|-------|--------|
| Spec | planned (this file) |
| Flag + seed | pending |
| Additional DocTypes Link + validate | pending |
| SSA exclude | pending |
| Slip earnings_map / ESIC fix | pending |
| Migrate + tests | pending |

## Non-goals / explicit ignores

- Free-text component names on Additional Salary / Deduction after this ships.
- Additional deductions as ESIC/PF wage components.
- Hard-auto “every additional earning always in ESIC/PF”.
- Renaming virtual Gross / Gross Including Additional Salary UX in this spec (can be a follow-up).
