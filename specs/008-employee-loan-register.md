# 008 — Employee Loan Register

| | |
|---|---|
| **Status** | planned |
| **Branch** | `feat/loan-management` |
| **Surfaces** | DocType **Employee Loan**; DocType **Employee Loan Due**; Desk page **Generate Monthly Loan Dues**; Reports **Employee Loan Ledger** + **Loan Ledger** (per loan); Salary Slip deductions |
| **Workspace** | Saral HR → card **Employee Loans** → links: Employee Loan, Generate Monthly Loan Dues, Employee Loan Ledger |
| **Roles** | Saral HR User, Saral HR Manager (create/edit/dues page/prepay/ledgers); same for both in v1 |
| **Grilled** | 2026-08-09 |

## Why?

HR needs a simple loan **register**: record each loan given to an employee, use **Generate Monthly Loan Dues** to set expected EMIs before payroll, let salary slips deduct those amounts (one line per loan), capture **prepayments**, and show **Tally-style ledgers** (employee + per loan) with running balance.

## What?

1. **Employee Loan** — one submitted document per loan grant (new loan number each time).
2. **Employee Loan Due** — separate DocType for each employee + loan + month EMI (created on the dues page, editable there).
3. **Generate Monthly Loan Dues** — Desk page: company + month → Generate → edit amounts / add rows → Save.
4. **Salary Slip** — loads saved dues for that month; **one deduction line per loan**; writes **Salary Slip** name onto each due row; locks further edits.
5. **Prepayment** — child table on Employee Loan; increases recovered; can close loan.
6. **Ledgers** — employee party ledger + per-loan ledger (Dr/Cr + running balance) + PDF.
7. **Proposed vs actual** — proposed tenure on loan vs months until outstanding hits 0 (reporting).

### Out of scope (v1)

| Deferred | Notes |
|----------|--------|
| Interest | Not in v1 |
| Defer-to-another-month UI | HR may set due amount to **0** for a month instead |
| Auto-create dues without using the page | Explicit **Generate** on **Generate Monthly Loan Dues** only |

## Decisions (locked)

| # | Topic | Decision |
|---|--------|----------|
| 1 | EMI plan | **Rolling month** — no full schedule on loan create |
| 2 | Expected months | **Read-only projection** on loan (for proposed period understanding) |
| 3 | EMI edit | **Only** on Generate Monthly Loan Dues; locked after salary slip on that due |
| 4 | Slip link | Store **Salary Slip** name on **Employee Loan Due** when deducted |
| 5 | Multi-loan slip | **Separate deduction lines** (one per loan) |
| 6 | Create fields | Employee, date, amount, **reason**, **expected EMI**, **start month**, **proposed tenure** (months) — all required |
| 7 | Prepayment | **Child table** on loan; partial OK; can close loan; next EMI stays same until HR edits on dues page |
| 8 | Generate dues | HR opens **Generate Monthly Loan Dues**, clicks **Generate**; can **add** rows manually too |
| 9 | Last EMI | Proposed amount = `min(expected_EMI, outstanding)` |
| 10 | Due storage | Separate DocType **Employee Loan Due** (not child of loan) |
| 11 | Naming | `{last4}-LN-{nn}` (last 4 digits of employee id; sequence ≥ 2 digits) |
| 12 | Ledger | Date, Particulars, Voucher, Debit, Credit, Running balance; opening OK |
| 13 | Workspace | Card **Employee Loans** + links |
| 14 | Roles | Saral HR User + Saral HR Manager |

## DocTypes

### Employee Loan (submittable)

| Field | Type | Notes |
|-------|------|--------|
| employee | Link → Company Link | Required |
| full_name | Data | Fetch |
| company | Data | Fetch |
| loan_date | Date | Amount given date; Required |
| amount | Currency | Principal; Required |
| reason | Small Text | Required |
| expected_emi | Currency | Default monthly proposal; Required |
| start_month | Select / Data | First EMI month (`MMMM YYYY` or month+year); Required |
| proposed_tenure_months | Int | Proposed period for reporting; Required |
| total_recovered | Currency | Read-only — salary dues deducted + prepayments |
| outstanding_amount | Currency | Read-only — `amount − total_recovered` |
| status | Select | Active / Closed (outstanding ≤ 0) |
| prepayments | Table → Employee Loan Prepayment | |
| amended_from | Link | |

**Autoname:** `{last4}-LN-{nn}` where `last4` is the last 4 digits of the employee (Company Link) id and `{nn}` is a sequence with at least 2 digits (e.g. `HR-EMP-00002` → `0002-LN-01`).

**Read-only projection (not stored rows):**  
`expected_months_remaining ≈ ceil(outstanding / expected_emi)` (handle EMI=0); display proposed end ≈ start + proposed_tenure vs actual months with dues/prepayments until Closed.

### Employee Loan Prepayment (child)

| Field | Type | Notes |
|-------|------|--------|
| prepayment_date | Date | Required |
| amount | Currency | Required; ≤ outstanding at save |
| remark | Small Text | Optional |

On save: recalc `total_recovered` / `outstanding` / `status`. If outstanding → 0, **Closed**; Generate must skip closed loans.

### Employee Loan Due (prefer **not** submittable; status fields)

Standalone DocType so Generate Monthly Loan Dues can list/edit without opening each loan.

| Field | Type | Notes |
|-------|------|--------|
| employee | Link → Company Link | Required |
| loan | Link → Employee Loan | Required |
| company | Data | Fetch / denormalize for filters |
| month | Data | `MMMM YYYY`; Required |
| year | Int | Optional helper for filters |
| amount | Currency | EMI for this month; Required |
| status | Select | Pending / Deducted / Skipped (amount 0 saved intentionally) |
| salary_slip | Link → Salary Slip | Set on slip submit; clear on slip cancel |
| remarks | Small Text | Optional |

**Unique:** `(loan, month)` — one due per loan per month.

**Lock:** if `salary_slip` set (and slip submitted), amount/employee/loan/month not editable.

## Generate Monthly Loan Dues (Desk page)

### Filters

| Filter | Required |
|--------|----------|
| Company | Yes |
| Month + Year | Yes |
| Employee | Optional |

### Actions

1. **Load** (single button) — for the selected company + month:
   - If any **submitted** Salary Slip exists for that company in the month → **period locked**: show existing dues read-only (no create / edit / add / save).
   - Otherwise → create any missing dues for Active loans (`amount = min(expected_emi, outstanding)`), then show existing + newly created rows for edit.
2. Grid: employee, loan ID, outstanding, amount (editable when unlocked), remarks.
3. When unlocked, HR may **edit amounts**, **Add Row**, **Save**.
4. Amount `0` allowed (skip month without deferral UI).
5. Individual rows with a linked salary slip stay locked even if the period is otherwise open.

### Save rules

- Reject edit if due already has `salary_slip` linked to a submitted slip.
- Revalidate amount ≥ 0; hard block if amount > outstanding.

## Salary Slip integration

### Create / refresh deductions

`get_loan_dues_for_slip(employee, start_date)`:

- Resolve month label from slip `start_date`.
- Find Employee Loan Due: employee + month, status Pending (or no salary_slip), amount > 0, loan Active.
- Return one row per due: `salary_component` = Loan, **`abbr` = Loan ID** (e.g. `0002-LN-01`), `amount`, **`loan`**, **`loan_due`** (due name). Loan ID is also visible on the Salary Details grid.

### Persist link on Salary Details (hard requirement)

Add fields on **Salary Details** (complements due.salary_slip):

- On slip **submit**: for each deduction tied to a due (match by stored `loan_due`), set `Employee Loan Due.salary_slip = slip.name`, status Deducted; recalc loan recovered/outstanding.
- On slip **cancel**: clear `salary_slip`, status Pending; reverse recovered.

**v1:** hidden/read-only Link fields on Salary Details: `loan` → Employee Loan, `loan_due` → Employee Loan Due.

### Slip UI

One deduction line per due/loan — never merge.

## Ledgers

### Employee Loan Ledger (party)

Filters: Company, Employee (required for detail), optional From–To.

| Column | Definition |
|--------|------------|
| Date | loan_date / slip period date / prepayment_date |
| Particulars | Loan given — {loan}; Salary recovery — {loan} — {slip}; Prepayment — {remark} |
| Loan ID | Employee Loan name (reference on every line, especially salary recovery) |
| Voucher | Link to loan / slip / (loan for prepay) |
| Debit | Loan principal |
| Credit | Salary due amount + prepayment |
| Balance | Running (Dr − Cr); positive = receivable from employee |

Opening balance if From date set.

### Loan Ledger (per document)

Same columns; single loan; first line Dr = amount.

### PDF

Both ledgers: company header, meta, Dr/Cr/Balance, totals, signatory block (Prepared / Checked / Authorised).

## Outstanding math

```
total_recovered = Σ(due.amount where salary_slip set) + Σ(prepayment.amount)
outstanding     = amount − total_recovered
status          = Closed if outstanding <= 0 else Active
```

## Permissions

| Role | Loan CRUD | Prepay | Generate Monthly Loan Dues | Ledgers/PDF |
|------|-----------|--------|----------------------------|-------------|
| Saral HR Manager | Yes | Yes | Yes | Yes |
| Saral HR User | Yes | Yes | Yes | Yes |

## How?

### Backend

- DocTypes under `saral_hr/saral_hr/doctype/` (JSON + migrate; no empty mkdir-only trees).
- Page `generate_monthly_loan_dues`: generate / list / save APIs.
- Salary slip: fetch dues; submit/cancel sync due + outstanding.
- Reports: employee ledger + loan ledger (+ print).

### Frontend

- Employee Loan form: fields + prepayments + projection display.
- Generate Monthly Loan Dues page grid.
- Salary slip loads loan dues as deduction lines when the slip is prepared.

### Workspace

Card **Employee Loans**:

- Employee Loan (DocType)
- Generate Monthly Loan Dues (Page)
- Employee Loan Ledger (Report)

### Tests

| Case | Expect |
|------|--------|
| Autoname | Second loan for same last-4 → `0002-LN-02` |
| Generate | Creates dues with min(EMI, outstanding); skips closed / existing month |
| Edit dues | Saves amount; blocked after slip linked |
| Two loans | Slip gets two deduction lines |
| Submit slip | due.salary_slip set; outstanding drops |
| Cancel slip | due unlocked; outstanding restored |
| Prepayment | Partial + close; Generate skips closed |
| Ledger | Running balance matches Dr/Cr order |

## Phases

| Phase | Deliverable |
|-------|-------------|
| 0 | Spec commit |
| 1 | Employee Loan + Prepayment child + outstanding math |
| 2 | Employee Loan Due + Generate Monthly Loan Dues page (Generate / edit / save) |
| 3 | Salary Details loan links + slip fetch/submit/cancel sync |
| 4 | Employee + per-loan Tally ledgers + PDF |
| 5 | Workspace card; proposed vs actual display; unit tests |

## Progress

| Item | Status |
|------|--------|
| Grill locked | done |
| Spec drafted | done |
| Phase 1–3 (Loan, Due, Generate page, slip sync) | done |
| Phase 4 ledgers + PDF | done — ready to test |
| Phase 5 workspace + polish tests | workspace done; unit tests stub |
