# 008 — Loan Management (Fresh Rebuild)

| | |
|---|---|
| **Status** | cancelled (legacy scrap) → planned rebuild |
| **Branch** | `feat/loan-management` |
| **Note** | Legacy loan/advance DocTypes + reports removed 2026-08-09. Rebuild from scratch next. |

## Why scrap?

The previous loan system was not fit for purpose:

- No durable FK between Salary Slip and loan instalment (only soft match via `Loan-0001` component text + employee/month)
- Confusing combined Loan/Advance DocType and weak monthly prep UX
- Reports/ledgers not Tally-grade

## What was removed (this phase)

Deleted from codebase + site patch `scrap_legacy_loan_module`:

| Kind | Names |
|------|--------|
| DocTypes | `Employee Loan Advance`, `Employee Loan Advance Schedule`, `Employee Loan`, `Employee Advance`, `Employee Loan Schedule`, cash-recovery children |
| Reports | `Loan Deduction For Month`, `Employee Loan Advance Ledger`, `Loan Register`, `Advance Register` |
| Salary hooks | `get_loan_advance_deductions`, submit/cancel schedule sync |
| Workspace | Loan/Advance links + shortcuts |

**Preserved:** historical Salary Slip deduction lines (`Loan-*` / `Advance-*` amounts). Payroll totals on old slips stay intact.

## Rebuild (next — grill again before coding)

Greenfield design TBD. Locked intent from earlier grill (re-confirm before build):

1. Explicit slip ↔ instalment link (store loan + schedule/month on Salary Details)
2. Separate Loan vs Advance masters
3. Bulk monthly prep
4. Cash recovery + Tally employee/document ledgers + PDF

## Progress

| Item | Status |
|------|--------|
| Legacy scrap (code + DB patch) | done |
| Fresh grill / redesign | not started |
| New DocTypes / reports | not started |
