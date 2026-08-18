# Specs progress

Single board for all specs in this folder. New specs get the next number (`002-…`, `003-…`). Update status here when work moves.

| # | Spec | Status | Notes |
|---|------|--------|-------|
| 001 | [Company list employee counts](./001-company-list-employee-counts.md) | done | List + form headcount from Company Link; tests passing |
| 002 | [Maharashtra Professional Tax](./002-maharashtra-professional-tax.md) | in progress | Per-slab Feb amounts; Female no Feb surcharge; multi-state deferred |
| 003 | [Attendance Dashboard yearly](./003-attendance-dashboard-yearly.md) | done | Merged PR #33 — yearly headcount + marking coverage |
| 004 | [Monthly Salary Register (Old Format)](./004-monthly-salary-register.md) | done | Script Report + PDF/Excel; tests passing |
| 005 | [Monthly Salary Register Compressed](./005-monthly-salary-register-compressed.md) | ready for review | Format filter + Desk/PDF/Excel UX polish |
| 006 | [Additional-Only Salary Components](./006-additional-only-salary-components.md) | done | Link-only AS/AD; earnings_map by name; slip print; period lock = submitted slips |
| 007 | [Data Cleansing](./007-data-cleansing.md) | in progress | v1 matrix+delete+log; v2 AS/AD, SSA, orphans, period lock |
| 008 | [Employee Loan Register](./008-employee-loan-register.md) | in progress | Phases 1–4 coded (loan/dues/slip/ledgers); polish tests pending |
| 009 | [Percent of Total Earning](./009-percent-of-total-earning.md) | in progress | Implemented on `feat/percent-of-total-earning`; tests passing |
| 010 | [Period picker standardization](./010-period-picker-standardization.md) | in progress | Company → Year → Month; year floor 2024 |

## Status legend

| Status | Meaning |
|--------|---------|
| `planned` | Spec written; not started |
| `in progress` | Implementation underway on a `feat/` / `fix/` branch |
| `done` | Merged / complete; keep the row for history |
| `cancelled` | Won't do; leave a short note |

## Conventions

- One markdown file per spec: `specs/NNN-short-slug.md`
- Numbers are zero-padded (`001`, `002`, …) so files sort naturally
- Commit the spec before development commits (see `AGENTS.md`)
- Reconcile this board after each meaningful phase
