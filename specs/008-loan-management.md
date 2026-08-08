# 008 — Loan Management Improvement

| | |
|---|---|
| **Status** | in progress |
| **Branch** | `feat/loan-management` |
| **Surfaces** | DocTypes `Employee Loan`, `Employee Advance`; Desk page / Report **Monthly Loan Prep**; Reports **Employee Loan Ledger** (employee + document); cash recovery on form; PDF prints |
| **Workspace** | Saral HR → separate **Loans** and **Advances** links (no shared “Loan Advance” list as primary UX) |
| **Primary sources** | Evolve `Employee Loan Advance` + schedule + salary slip hooks + existing loan reports |
| **Grilled** | 2026-08-08 |

## Why?

Payroll already creates loans/advances, builds EMI schedules, deducts via Salary Slip, and shows summary ledgers — but ops still open **each loan** to tweak next month’s EMI, Loan and Advance share one DocType (confusing), there is **no cash recovery** outside salary, and the ledger is a schedule summary rather than a **Tally-style Dr/Cr party ledger** with running balance. PDF output needs polish for audit/sign-off.

## What?

v1 improves loan/advance management end-to-end:

1. **Split DocTypes** — `Employee Loan` and `Employee Advance` (migrate away from `Employee Loan Advance`).
2. **Naming** — keep `{employee}-Loan-{####}` / `{employee}-Advance-{####}` (e.g. `HR-EMP-00002-Loan-0001`).
3. **Monthly Loan Prep** — company + month bulk grid: see due instalments, edit amounts / defer, **save once**; salary slip picks up the saved schedule (same spirit as today).
4. **Record Cash Recovery** — button on Loan and Advance (amount, date, remark) → Cr on loan/advance and employee ledger; **never** via salary.
5. **Tally-style ledgers** — (C) employee ledger (all loans + advances) **and** drill-down per loan/advance document; Dr/Cr + running balance.
6. **PDF polish** — employee ledger, per-document ledger, monthly prep / register prints in v1.

### Out of scope (v1)

| Deferred | Notes |
|----------|--------|
| Interest / interest-bearing loans | Not in v1 |
| Deferral semantics redesign | Keep existing `is_deferred` / `deferred_to` flags; no new deferral engine |
| Greenfield salary-slip rewrite | Retarget `get_loan_advance_deductions` / sync hooks only |
| Manual cash **on** salary slip | Explicitly excluded — cash is ledger Cr only |

## Decisions (locked from grill)

| # | Topic | Decision |
|---|--------|----------|
| 1 | Pain focus | Bulk monthly prep + Tally ledger + DocType split clarity |
| 2 | Ledger shape | **Both**: employee party ledger + per-document drill-down |
| 3 | Cash recovery | Button on document (**Record Cash Recovery**); Cr on loan **and** employee ledger; not on salary |
| 4 | DocType split | **Two DocTypes** — `Employee Loan` + `Employee Advance`; migrate existing rows |
| 5 | Advances in ledger | Yes — cash recovery + Tally employee ledger include advances |
| 6 | Mid-tenure cash vs schedule | **Leave schedule alone**; HR fixes future EMIs in Monthly Prep |
| 7 | Partial cash | Yes — any amount ≤ outstanding |
| 8 | Outstanding → 0 | Leave schedule rows as-is, but salary **must not** pull remaining undeducted rows once outstanding is 0 |
| 9 | Advance repayment | **One-shot** — no EMI schedule; clear via salary and/or cash |
| 10 | PDF | **In v1** — polish employee ledger, document ledger, monthly prep / registers |
| 11 | Naming | Preserve `{employee}-Loan-{####}` / `{employee}-Advance-{####}` |
| 12 | Evolve vs rewrite | Evolve existing controllers, salary hooks, and reports — do not discard |

## DocTypes

### Employee Loan (submittable)

| Field | Type | Notes |
|-------|------|--------|
| employee | Link → Company Link | Required |
| full_name | Data | Fetch from employee |
| company | Data / Link | Fetch from employee |
| date | Date | Disbursement / taken-on date; Required |
| amount | Currency | Loan principal; Required |
| reason | Small Text | |
| start_month / start_year | Select | First EMI month |
| tenure_months | Int | Synced from schedule row count (as today) |
| installment_gap | Select | Monthly / 2 Month Gap / 3 Month Gap |
| monthly_deduction | Currency | Read-only base EMI |
| total_deducted | Currency | Read-only — salary deductions + cash recoveries |
| outstanding_amount | Currency | Read-only — `amount − total_deducted` |
| schedule | Table → Employee Loan Schedule | EMI rows; editable after submit (non-deducted) |
| cash_recoveries | Table → Employee Loan Cash Recovery | Or equivalent child; allow_on_submit create via dialog |
| amended_from | Link | Standard |

**Autoname:** `{employee}-Loan-{####}` (same algorithm as current Loan branch of `Employee Loan Advance.autoname`).

### Employee Loan Schedule (child)

| Field | Type | Notes |
|-------|------|--------|
| month | Data | e.g. `January 2026`; read-only once set |
| deduction_amount | Currency | allow_on_submit |
| is_deducted | Check | Set by Salary Slip submit/cancel; read-only |
| is_deferred | Check | allow_on_submit |
| deferred_to | Data | When deferred |

Carry forward existing schedule generate / lock / “Add Next Month” UX from current form JS.

### Employee Advance (submittable)

| Field | Type | Notes |
|-------|------|--------|
| employee | Link → Company Link | Required |
| full_name / company | | Fetch |
| date | Date | Required |
| amount | Currency | Required |
| reason | Small Text | |
| is_deducted | Check | Salary one-shot flag (as today) |
| total_recovered | Currency | Salary + cash |
| outstanding_amount | Currency | Read-only |
| cash_recoveries | Table → Employee Advance Cash Recovery | |
| amended_from | Link | |

**No schedule.** Naming: `{employee}-Advance-{####}`.

### Cash recovery (child on Loan and Advance)

| Field | Type | Notes |
|-------|------|--------|
| recovery_date | Date | Required |
| amount | Currency | Required; ≤ outstanding at save |
| remark | Small Text | Optional |
| created_by / creation | | Standard |

**Record Cash Recovery** dialog on submitted docs → appends child row → recalculates outstanding. Cancel/amend rules: block delete of cash rows that would break audit if needed; v1 minimum = cannot delete cash row after save without cancel/amend of parent (document in implementation).

**Outstanding formula**

- Loan: `outstanding = amount − Σ(schedule.deduction_amount where is_deducted) − Σ(cash_recoveries.amount)`
- Advance: `outstanding = amount − (amount if is_deducted else 0) − Σ(cash_recoveries.amount)` — if partial salary ever appears, treat deducted portion explicitly; v1 advance salary remains full remaining-to-salary or full amount as today unless cash already reduced outstanding (salary should deduct **min(remaining outstanding, advance amount logic)** — see Salary interaction).

## Monthly Loan Prep

### Surface

Desk **Page** or editable Script Report upgraded to a saveable grid (prefer Desk page if report cannot save reliably). Workspace link: **Monthly Loan Prep**.

### Filters

| Filter | Required | Notes |
|--------|----------|--------|
| Company | Yes | |
| Month + Year | Yes | Target payroll month |
| Employee | No | Optional narrow |
| Status | No | Pending / Deferred / All |

### Grid columns

| Column | Editable | Notes |
|--------|----------|--------|
| Employee / Name | No | |
| Loan ID | No | Link → Employee Loan |
| Outstanding | No | |
| Scheduled EMI | Yes | Writes `deduction_amount` for that month row |
| Deferred | Yes | Toggle `is_deferred` |
| Deferred To | Yes | When deferred |
| Status | No | Pending / Deferred / Deducted (read-only if already deducted) |
| Slip exists | No | Warn if submitted slip already for month |

### Save rules

- Only **Loan** schedule rows for the selected month (Advances **not** in this grid — one-shot elsewhere).
- Block edit when `is_deducted` or submitted Salary Slip exists for that employee+month (same spirit as current form).
- Save updates schedule rows in bulk; revalidate schedule totals vs loan amount (same throw rules as today: instalments must sum to loan amount).
- After cash closed a loan (`outstanding = 0`), rows may still appear — UI shows outstanding 0; salary must skip (see below). Prep may still let HR zero/defer leftover rows.

### Relation to existing report

Replace/upgrade **Loan Deduction For Month** as the read-only cousin, or point that report at the same query and make **Monthly Loan Prep** the editing surface. Do not leave two conflicting editors.

## Salary interaction

Retarget [`salary_slip.py`](saral_hr/saral_hr/doctype/salary_slip/salary_slip.py):

- `get_loan_advance_deductions` → read `Employee Loan` schedule + `Employee Advance` outstanding
- `_sync_loan_advance_deducted` → mark loan schedule / advance `is_deducted` on submit; reverse on cancel

**Hard rules**

1. Loan: include schedule row for slip month only if `not is_deducted` and parent **outstanding > 0** before this deduction.
2. Advance: include only if not fully recovered (`outstanding > 0`) and not already salary-flagged as deducted for the remaining path; amount = outstanding (or remaining after cash).
3. Never create salary lines for cash recoveries.

## Ledgers (Tally-style)

### Employee ledger (party)

Filters: Company (required), Employee (required for full party view; optional company-wide summary later), From–To dates (optional).

| Column | Definition |
|--------|------------|
| Date | Disbursement date / slip period date / cash recovery_date |
| Particulars | Narration, e.g. `Loan given — {loan_id}`, `Salary recovery — {slip}`, `Cash recovery — {remark}` |
| Voucher | Link to Loan / Advance / Salary Slip / recovery row |
| Debit | Loan/Advance disbursement (principal) |
| Credit | Salary recovery + cash recovery |
| Balance | Running balance (Dr − Cr cumulative); employee owing company = positive Dr balance convention — document as **Dr balance = amount receivable from employee** |

**Opening:** If From date set, opening balance = prior Dr − Cr before From.

**Rows sourced from:** all submitted Employee Loans + Advances for employee; salary-marked schedule/advance deductions; cash recovery children.

### Document ledger (per Loan or Advance)

Same columns; single document’s vouchers only. Opening = 0 at disbursement (first Dr = amount).

### Summary list

Keep a summary register (loan/advance ID, amount, paid, outstanding, status) as entry point — evolve **Employee Loan Advance Ledger** summary; detail becomes true Dr/Cr ledger, not schedule-only.

### Registers

Keep **Loan Register** / **Advance Register** for month recovery snapshots; retarget DocTypes; include cash recoveries in balance where relevant.

## PDF (v1 polish)

| Print | Requirements |
|-------|----------------|
| Employee ledger | Company header, employee meta, Dr/Cr/Balance table, opening/closing, signatory block (Prepared / Checked / Authorised), A4 landscape or portrait consistent with other Saral reports |
| Document ledger | Same for one Loan/Advance; title includes document name |
| Monthly Loan Prep / Loan Register | Match existing register PDF quality: page breaks, totals, signatures; update titles after DocType split |

Reuse patterns from current [`employee_loan_advance_ledger.py`](saral_hr/saral_hr/report/employee_loan_advance_ledger/employee_loan_advance_ledger.py) / [`loan_register.py`](saral_hr/saral_hr/report/loan_register/loan_register.py) print helpers; tighten typography, totals, and voucher references (include cash lines).

## Migration

From `Employee Loan Advance` → split:

| Source `type` | Target |
|---------------|--------|
| `Loan` / legacy `Loan-I` / `Loan-II` | `Employee Loan` (+ schedule child rename/copy) |
| `Advance` | `Employee Advance` |

Rules:

1. Prefer **keeping document `name`** when it already matches `{employee}-Loan-{####}` / `{employee}-Advance-{####}` so salary component labels and historical links stay stable.
2. Patch copies fields + schedule; maps child table to `Employee Loan Schedule`.
3. Update salary slip sync, reports, workspace, employee_profile, salary_insight, transaction_checklist, fixtures (`report.json`, `workspace.json`, `custom_docperm.json`).
4. Deprecate `Employee Loan Advance` after patch (hide from workspace; optional later removal).
5. No cash recovery rows to migrate (feature is new).

## Permissions

| Role | Loan/Advance CRUD | Monthly Prep edit | Cash recovery | Ledgers / PDF |
|------|-------------------|-------------------|---------------|---------------|
| Saral HR Manager | Yes | Yes | Yes | Yes |
| Saral HR User | Yes (match today’s loan perms) | Yes | Yes | Yes |
| Employee (self) | No | No | No | Read own employee ledger only if already supported |

Mirror current `Employee Loan Advance` permission rows unless grill revisits.

## How?

### Backend

- New DocTypes under `saral_hr/saral_hr/doctype/` via JSON + migrate (no manual mkdir of empty trees beyond writing JSON/controller as app convention).
- Patch: migrate data from `Employee Loan Advance`.
- Whitelist: `record_cash_recovery(doctype, name, amount, date, remark)`, `save_monthly_loan_prep(company, month, year, rows)`.
- Salary slip: retarget loan/advance helpers; outstanding gate.
- Reports: rewrite ledger execute + detail APIs for Dr/Cr; retarget registers; Monthly Prep APIs.

### Frontend

- Loan / Advance forms: schedule UX (loan only), cash recovery button/dialog.
- Monthly Loan Prep page: filter → grid → save.
- Ledger: summary → drill to document ledger; print buttons.

### Workspace

- Links: **Employee Loan**, **Employee Advance**, **Monthly Loan Prep**, **Employee Loan Ledger** (rename from Advance Ledger as needed).
- Remove primary reliance on combined Loan Advance list.

### Tests

| Case | Expect |
|------|--------|
| Autoname | Second loan for employee is `…-Loan-0002` |
| Schedule sum | Mismatch throws (existing rule) |
| Monthly prep save | Updates multiple loans’ EMI for month in one call |
| Prep blocked | Cannot change deducted / slipped month |
| Cash partial | Outstanding decreases; schedule unchanged |
| Cash to zero | Salary deductions API returns no further loan rows for that loan |
| Advance cash + salary | Recoveries cannot exceed amount; ledger Cr lines both appear |
| Employee ledger | Running balance matches Dr/Cr order |
| Migration | Old Loan/Advance rows readable under new DocTypes with same names |
| PDF | Print endpoints return file URL (smoke) |

## Phases (tracer bullets)

| Phase | Deliverable |
|-------|-------------|
| 0 | Spec + branch `feat/loan-management` |
| 1 | DocTypes Employee Loan / Advance / Schedule / Cash Recovery children + migrate patch + salary retarget (tracer: create loan → salary deduct still works) |
| 2 | Record Cash Recovery + outstanding math + salary outstanding gate |
| 3 | Monthly Loan Prep bulk grid + save |
| 4 | Tally employee + document ledgers (Desk) |
| 5 | PDF polish for ledgers + registers/prep |
| 6 | Workspace/fixtures cleanup; deprecate old DocType from UI; unit tests |

## Progress

| Item | Status |
|------|--------|
| Grill decisions locked | done |
| Spec drafted | done |
| Branch / implementation | in progress (`feat/loan-management`) |
| DocType split + migration | done (phase 1) |
| Cash recovery | not started |
| Monthly Loan Prep | not started |
| Tally ledgers | not started |
| PDF polish | not started |
| Tests | not started |
| Salary retarget | done (phase 1) |
