# 009 — Percent of Total Earning Deductions

| | |
|---|---|
| **Status** | in progress |
| **Branch** | `feat/percent-of-total-earning` |
| **Primary DocTypes** | Salary Component, Salary Details, Salary Structure, Salary Structure Assignment, Salary Slip |
| **Grilled** | 2026-08-11 |

## Why?

HR needs deductions like **94J @ 10%** and **91Q @ 2%** of **Total Earnings**, without a formula engine. Each rate belongs on its own Salary Component so users can add as many as they need and attach them via Structure → SSA.

## What?

1. Salary Component: **`% on Total Earning`** + **percent** (1–100).
2. Multiple such deductions allowed on the same slip; each uses its own %.
3. **Slip (authoritative):** after attendance/proration earnings (including Additional Salary) → `amount = max(0, total_earnings) × percent / 100`, rounded with company digits.
4. **SSA (preview):** read-only % + amount from SSA gross × % (preview ≠ final OK).
5. **Structure:** read-only %; Amount stays `0`.
6. Lock % + checkbox once any non-cancelled SSA references the component; unlock when none remain.

### Out of scope (v1)

| Deferred | Notes |
|----------|--------|
| CTC Calculator | No change |
| Income Tax / TDS reports | Afterwards |
| Seed components | Users create 94J / 91Q themselves |
| Tax slabs / regimes / exemptions | Flat % only |
| Period-versioned % (like ESIC/PF periods) | Single % on component + SSA lock |

## Decisions (locked)

| # | Topic | Decision |
|---|--------|----------|
| 1 | Source of truth for rate | **Salary Component** (`%` + checkbox) |
| 2 | Applicability | Component on Structure → SSA → appears on slip |
| 3 | Slip base | `total_earnings` after proration **including Additional Salary** |
| 4 | Timing | After earnings finalized (same phase as PT), before net |
| 5 | Mutual exclusion | Forbidden with: payment days, physical WD, daily wage, special, additional-only, employer contribution |
| 6 | Type | Deduction only |
| 7 | SSA Amount | Read-only preview = SSA earnings sum × % |
| 8 | SSA % display | Read-only, from component |
| 9 | Structure Amount | `0`; show read-only % only |
| 10 | Preview ≠ final | OK |
| 11 | Rate lock | Lock **%** and **checkbox** when any SSA (draft or submitted) references component |
| 12 | Unlock | When all such SSAs are **deleted** or **cancelled** |
| 13 | Editable while locked | Name, abbr, description OK |
| 14 | Zero / negative earnings | Amount = **0** |
| 15 | Rounding | Company `salary_amount_rounding_digits` |
| 16 | Percent validation | Required when checked; `> 0` and `≤ 100` |
| 17 | Slip Amount | **Read-only**; no manual override |
| 18 | Client slip JS | Must mirror server calc |
| 19 | Seeds | None |
| 20 | Reports / CTC | Out of scope |

## Fields

### Salary Component

| Fieldname | Type | Default | Notes |
|-----------|------|---------|--------|
| `percent_on_total_earning` | Check | 0 | Label: **% on Total Earning**; `depends_on: type == Deduction` |
| `percent_of_total_earning` | Percent | | Label: **Percent of Total Earning**; shown when check on; 0–100 |

Validation:
- If check on → type must be Deduction; percent in (0, 100]; clear conflicting flags (or throw).
- If check off → clear percent (or ignore).
- If locked by SSA → reject change to check / percent.

### Salary Details (child)

| Fieldname | Type | Notes |
|-----------|------|--------|
| `percent_of_total_earning` | Percent | `fetch_from` component; read-only; in list view useful on SSA |

`amount` read-only in UI when parent row’s component has `percent_on_total_earning`.

## How?

### 1. Component validate + lock helper

- Mutual exclusion with existing flags (extend `_validate_calculation_flags` / additional-only checks).
- `component_percent_locked(name)` → exists Salary Details row under Salary Structure Assignment where `docstatus != 2` and `salary_component = name`.

### 2. SSA JS

- On earnings amount change / component add: for each %-deduction row, set amount = `gross_salary × percent / 100` (company digits if available).
- Make amount + percent read-only for those rows.

### 3. Structure JS

- On component select: fetch/show percent; force amount `0`; amount read-only for those rows.

### 4. Slip server — `calculate_salary_slip_amounts_exact`

After earnings loop (and thus after Additional Salary rows already on `earnings`):

```text
for deduction row:
  if component.percent_on_total_earning:
    amount = flt(max(total_earnings, 0) * percent / 100, digits)
  elif PT: ...
  else: existing logic
```

Do **not** apply payment-day proration on top.

### 5. Slip client — `apply_attendance`

Same branch as server (load percent from component or child field). Keep Amount read-only for these rows.

### 6. Tests (minimum)

| Case | Expect |
|------|--------|
| Earnings 50k + Additional 5k, 10% component | Deduction 5500 |
| Two components 10% + 2% | Both on same slip |
| Total earnings 0 | Deduction 0 |
| Mutual exclusion flags | Throw on save |
| SSA references component | Cannot change % / uncheck |
| All SSAs cancelled/deleted | Can change % again |
| SSA preview | Amount = SSA gross × % |

## Tracer

1. Spec commit
2. Fields + component validation + lock
3. Slip server calc + unit test (50k+5k → 10%)
4. SSA preview + Structure % display
5. Slip client parity + read-only amount

## Progress log

| Phase | Status | Notes |
|-------|--------|-------|
| Grill / spec | done | |
| Tracer fields + slip calc | done | Component fields, lock, server calc |
| SSA / Structure UI | done | Preview % amount on SSA; Structure amount 0 |
| Client parity + tests | done | Slip JS + 5 unit tests passing |
